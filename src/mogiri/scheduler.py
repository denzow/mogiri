import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from mogiri.models import (
    Execution, Job, Setting, Workflow, WorkflowEdge, WorkflowNodePosition, db,
)

scheduler = BackgroundScheduler()
_app = None

# Registry of running processes: execution_id -> subprocess.Popen
_running_processes = {}
_running_lock = threading.Lock()


def init_scheduler(app):
    global _app
    _app = app
    sync_all(app)

    scheduler.add_job(
        rotate_logs,
        CronTrigger(hour=3, minute=0),
        id="_mogiri_log_rotation",
        replace_existing=True,
    )

    scheduler.start()
    print(f"[mogiri] Scheduler started with {len(scheduler.get_jobs())} job(s)")


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)


def sync_all(app):
    """Load all enabled jobs and workflows and register with APScheduler."""
    with app.app_context():
        scheduler.remove_all_jobs()

        # Register jobs with their own schedules
        for job in Job.query.filter_by(is_enabled=True).all():
            _add_scheduler_job(job)

        # Register workflows with their own schedules
        for wf in Workflow.query.filter_by(is_enabled=True).all():
            _add_scheduler_workflow(wf)


def _make_trigger(schedule_type, schedule_value):
    if schedule_type == "cron" and schedule_value:
        return CronTrigger.from_crontab(schedule_value)
    elif schedule_type == "once" and schedule_value:
        return DateTrigger(run_date=datetime.fromisoformat(schedule_value))
    else:
        return None


def _add_scheduler_job(job):
    try:
        trigger = _make_trigger(job.schedule_type, job.schedule_value)
        if trigger is None:
            return
        scheduler.add_job(
            execute_job,
            trigger=trigger,
            id=f"job:{job.id}",
            args=[job.id],
            replace_existing=True,
            max_instances=1,
        )
        print(f"[mogiri] Registered job: {job.name} ({job.schedule_type}: {job.schedule_value})")
    except Exception as e:
        print(f"[mogiri] Failed to schedule job {job.id} ({job.name}): {e}")


def _add_scheduler_workflow(wf):
    try:
        trigger = _make_trigger(wf.schedule_type, wf.schedule_value)
        if trigger is None:
            return
        scheduler.add_job(
            execute_workflow,
            trigger=trigger,
            id=f"wf:{wf.id}",
            args=[wf.id],
            replace_existing=True,
            max_instances=1,
        )
    except Exception as e:
        print(f"Failed to schedule workflow {wf.id} ({wf.name}): {e}")


def register_job(job):
    if job.is_enabled:
        _add_scheduler_job(job)
    else:
        unregister_job(job.id)


def unregister_job(job_id):
    try:
        scheduler.remove_job(f"job:{job_id}")
    except Exception:
        pass


def register_workflow(wf):
    if wf.is_enabled:
        _add_scheduler_workflow(wf)
    else:
        unregister_workflow(wf.id)


def unregister_workflow(wf_id):
    try:
        scheduler.remove_job(f"wf:{wf_id}")
    except Exception:
        pass


# ---------- Cancellation ----------

_is_cancelled = set()


def _kill_process(proc):
    """Kill a process and its children."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (OSError, ProcessLookupError):
        pass
    try:
        proc.kill()
    except (OSError, ProcessLookupError):
        pass


def cancel_execution(execution_id: str) -> bool:
    """Cancel a running execution. Returns True if cancellation was initiated."""
    with _running_lock:
        proc = _running_processes.get(execution_id)
    if proc is None:
        return False
    _is_cancelled.add(execution_id)
    _kill_process(proc)
    return True


# ---------- Workflow execution ----------

def execute_workflow(workflow_id: str, force: bool = False) -> None:
    """Execute a workflow by running its entry jobs."""
    app = _app
    if app is None:
        return

    with app.app_context():
        wf = db.session.get(Workflow, workflow_id)
        if not wf:
            return
        if not force and not wf.is_enabled:
            return

        # Prefer entry_node_keys (node_key aware) over entry_job_ids
        entry_nodes = []
        try:
            entry_nodes = json.loads(wf.entry_node_keys or "[]")
        except (json.JSONDecodeError, TypeError):
            pass

        if entry_nodes:
            launched = False
            for entry in entry_nodes:
                if isinstance(entry, dict):
                    node_key = entry.get("node_key")
                    job_id = entry.get("job_id")
                elif isinstance(entry, str):
                    # Legacy string format — look up job_id from node positions
                    node_key = entry
                    pos = WorkflowNodePosition.query.filter_by(
                        workflow_id=wf.id, node_key=entry
                    ).first()
                    job_id = pos.job_id if pos else None
                else:
                    continue
                if not job_id:
                    continue
                launched = True
                thread = threading.Thread(
                    target=execute_job,
                    args=(job_id,),
                    kwargs={"_workflow_id": wf.id, "_node_key": node_key},
                )
                thread.start()
            if launched:
                return

        # Fallback: use entry_job_ids (legacy)
        entry_ids = set()
        try:
            entry_ids = set(json.loads(wf.entry_job_ids or "[]"))
        except (json.JSONDecodeError, TypeError):
            pass

        if not entry_ids:
            # Fallback: auto-detect
            edges = WorkflowEdge.query.filter_by(workflow_id=wf.id).all()
            target_ids = {e.target_job_id for e in edges}
            source_ids = {e.source_job_id for e in edges}
            entry_ids = source_ids - target_ids

        for job_id in entry_ids:
            thread = threading.Thread(
                target=execute_job,
                args=(job_id,),
                kwargs={"_workflow_id": wf.id},
            )
            thread.start()


# ---------- Job execution ----------

def execute_job(
    job_id: str,
    _workflow_id: str = None,
    _node_key: str = None,
    triggered_by_execution_id: str = None,
    triggered_by_chain_id: str = None,
    _chain_visited: set = None,
) -> None:
    """Execute a job's command and record the result."""
    app = _app
    if app is None:
        return

    # Track visited by node_key when available, else by job_id
    visit_key = _node_key or job_id
    chain_visited = _chain_visited or {visit_key}

    with app.app_context():
        job = db.session.get(Job, job_id)
        if not job:
            return

        execution = Execution(
            job_id=job.id,
            node_key=_node_key,
            status="running",
            workflow_id=_workflow_id,
            triggered_by_execution_id=triggered_by_execution_id,
            triggered_by_chain_id=triggered_by_chain_id,
        )
        db.session.add(execution)
        db.session.commit()

        env = os.environ.copy()
        # Apply global env vars first
        try:
            global_env = json.loads(Setting.get("global_env_vars", "{}"))
            env.update(global_env)
        except (json.JSONDecodeError, TypeError):
            pass
        # Job-specific vars override global ones
        if job.env_vars:
            try:
                env.update(json.loads(job.env_vars))
            except (json.JSONDecodeError, TypeError):
                pass

        # Inject parent execution info for chain jobs
        if triggered_by_execution_id:
            parent_exec = db.session.get(Execution, triggered_by_execution_id)
            if parent_exec:
                parent_job = db.session.get(Job, parent_exec.job_id)
                env["MOGIRI_PARENT_EXECUTION_ID"] = parent_exec.id
                env["MOGIRI_PARENT_STATUS"] = parent_exec.status or ""
                env["MOGIRI_PARENT_EXIT_CODE"] = str(
                    parent_exec.exit_code if parent_exec.exit_code is not None else ""
                )
                env["MOGIRI_PARENT_STDOUT"] = (parent_exec.stdout or "")[-4000:]
                env["MOGIRI_PARENT_STDERR"] = (parent_exec.stderr or "")[-4000:]
                env["MOGIRI_PARENT_JOB_NAME"] = parent_job.name if parent_job else ""

        tmp_script = None
        proc = None
        try:
            if job.command_type == "python":
                tmp_script = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".py", delete=False
                )
                tmp_script.write(job.command)
                tmp_script.close()
                cmd = [sys.executable, tmp_script.name]
                shell = False
            else:
                cmd = job.command
                shell = True

            cwd = job.working_dir if job.working_dir else None

            proc = subprocess.Popen(
                cmd,
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=cwd,
                start_new_session=True,
            )
            with _running_lock:
                _running_processes[execution.id] = proc

            try:
                stdout, stderr = proc.communicate(timeout=3600)
            except subprocess.TimeoutExpired:
                _kill_process(proc)
                stdout, stderr = proc.communicate()
                execution.stdout = stdout or ""
                execution.stderr = stderr or ""
                execution.status = "timeout"
                execution.exit_code = -1
            else:
                # Check if cancelled during execution
                if execution.id in _is_cancelled:
                    execution.stdout = stdout or ""
                    execution.stderr = stderr or ""
                    execution.status = "cancelled"
                    execution.exit_code = -1
                else:
                    execution.exit_code = proc.returncode
                    execution.stdout = stdout or ""
                    execution.stderr = stderr or ""
                    execution.status = "success" if proc.returncode == 0 else "failed"
        except Exception as e:
            execution.stderr = str(e)
            execution.status = "failed"
            execution.exit_code = -1
        finally:
            with _running_lock:
                _running_processes.pop(execution.id, None)
            _is_cancelled.discard(execution.id)
            if tmp_script is not None:
                try:
                    os.unlink(tmp_script.name)
                except OSError:
                    pass
            execution.finished_at = datetime.now()
            db.session.commit()

            # Only trigger chains when running as part of a workflow
            # Don't trigger chains if cancelled
            if _workflow_id and execution.status != "cancelled":
                _trigger_chains(execution, _workflow_id, _node_key, chain_visited)


def _trigger_chains(execution, workflow_id, source_node_key, chain_visited):
    """After a job finishes within a workflow, trigger chained jobs."""
    # Prefer matching by source_node_key; fall back to source_job_id
    if source_node_key:
        edges = WorkflowEdge.query.filter_by(
            workflow_id=workflow_id,
            source_node_key=source_node_key,
        ).all()
    else:
        edges = WorkflowEdge.query.filter_by(
            workflow_id=workflow_id,
            source_job_id=execution.job_id,
        ).all()

    for edge in edges:
        if edge.trigger_condition == "success" and execution.status != "success":
            continue
        if edge.trigger_condition == "failure" and execution.status not in (
            "failed", "timeout",
        ):
            continue

        # Track visited by node_key when available, else by job_id
        visit_key = edge.target_node_key or edge.target_job_id
        if visit_key in chain_visited:
            print(f"[mogiri] Chain cycle detected: skipping {visit_key}")
            continue

        target_job = db.session.get(Job, edge.target_job_id)
        if not target_job:
            continue

        new_visited = chain_visited | {visit_key}
        thread = threading.Thread(
            target=execute_job,
            args=(edge.target_job_id,),
            kwargs={
                "_workflow_id": workflow_id,
                "_node_key": edge.target_node_key,
                "triggered_by_execution_id": execution.id,
                "triggered_by_chain_id": edge.id,
                "_chain_visited": new_visited,
            },
        )
        thread.start()


def rotate_logs() -> None:
    app = _app
    if app is None:
        return

    with app.app_context():
        retention_days = app.config.get("LOG_RETENTION_DAYS", 30)
        max_per_job = app.config.get("LOG_MAX_PER_JOB", 100)
        deleted = 0

        if retention_days > 0:
            cutoff = datetime.now() - timedelta(days=retention_days)
            old = Execution.query.filter(Execution.started_at < cutoff).all()
            for ex in old:
                db.session.delete(ex)
                deleted += 1

        if max_per_job > 0:
            jobs = Job.query.all()
            for job in jobs:
                excess = (
                    job.executions.order_by(Execution.started_at.desc())
                    .offset(max_per_job)
                    .all()
                )
                for ex in excess:
                    db.session.delete(ex)
                    deleted += 1

        if deleted > 0:
            db.session.commit()
            print(f"[mogiri] Log rotation: deleted {deleted} old execution(s)")
