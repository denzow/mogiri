import json
import os
import subprocess
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from mogiri.models import Execution, Job, db

scheduler = BackgroundScheduler()
_app = None


def init_scheduler(app):
    global _app
    _app = app
    sync_jobs(app)

    # Log rotation: run daily at 03:00
    scheduler.add_job(
        rotate_logs,
        CronTrigger(hour=3, minute=0),
        id="_mogiri_log_rotation",
        replace_existing=True,
    )

    scheduler.start()


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)


def sync_jobs(app):
    """Load all enabled jobs from DB and register with APScheduler."""
    with app.app_context():
        # Remove all existing APScheduler jobs to avoid duplicates
        scheduler.remove_all_jobs()

        jobs = Job.query.filter_by(is_enabled=True).all()
        for job in jobs:
            _add_scheduler_job(job)


def _make_trigger(job):
    if job.schedule_type == "cron":
        return CronTrigger.from_crontab(job.schedule_value)
    elif job.schedule_type == "once":
        run_date = datetime.fromisoformat(job.schedule_value)
        return DateTrigger(run_date=run_date)
    else:
        raise ValueError(f"Unknown schedule_type: {job.schedule_type}")


def _add_scheduler_job(job):
    try:
        trigger = _make_trigger(job)
        scheduler.add_job(
            execute_job,
            trigger=trigger,
            id=job.id,
            args=[job.id],
            replace_existing=True,
            max_instances=1,
        )
    except Exception as e:
        print(f"Failed to schedule job {job.id} ({job.name}): {e}")


def register_job(job):
    """Register or update a job in the scheduler."""
    if job.is_enabled:
        _add_scheduler_job(job)
    else:
        unregister_job(job.id)


def unregister_job(job_id):
    """Remove a job from the scheduler."""
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass


def execute_job(job_id: str) -> None:
    """Execute a job's command and record the result."""
    app = _app
    if app is None:
        return

    with app.app_context():
        job = db.session.get(Job, job_id)
        if not job:
            return

        execution = Execution(job_id=job.id, status="running")
        db.session.add(execution)
        db.session.commit()

        env = os.environ.copy()
        if job.env_vars:
            try:
                env.update(json.loads(job.env_vars))
            except (json.JSONDecodeError, TypeError):
                pass

        try:
            result = subprocess.run(
                job.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=3600,
                env=env,
            )
            execution.exit_code = result.returncode
            execution.stdout = result.stdout
            execution.stderr = result.stderr
            execution.status = "success" if result.returncode == 0 else "failed"
        except subprocess.TimeoutExpired as e:
            execution.stdout = e.stdout or ""
            execution.stderr = e.stderr or ""
            execution.status = "timeout"
            execution.exit_code = -1
        except Exception as e:
            execution.stderr = str(e)
            execution.status = "failed"
            execution.exit_code = -1
        finally:
            execution.finished_at = datetime.now()
            db.session.commit()


def rotate_logs() -> None:
    """Delete old execution logs based on retention settings."""
    app = _app
    if app is None:
        return

    with app.app_context():
        retention_days = app.config.get("LOG_RETENTION_DAYS", 30)
        max_per_job = app.config.get("LOG_MAX_PER_JOB", 100)
        deleted = 0

        # Delete executions older than retention_days
        if retention_days > 0:
            cutoff = datetime.now() - timedelta(days=retention_days)
            old = Execution.query.filter(Execution.started_at < cutoff).all()
            for ex in old:
                db.session.delete(ex)
                deleted += 1

        # Keep only the latest max_per_job executions per job
        if max_per_job > 0:
            jobs = Job.query.all()
            for job in jobs:
                excess = (
                    job.executions
                    .order_by(Execution.started_at.desc())
                    .offset(max_per_job)
                    .all()
                )
                for ex in excess:
                    db.session.delete(ex)
                    deleted += 1

        if deleted > 0:
            db.session.commit()
            print(f"[mogiri] Log rotation: deleted {deleted} old execution(s)")
