from datetime import datetime, timedelta

from mogiri.models import Execution, Job, db as _db
from mogiri.scheduler import execute_job, rotate_logs


def test_execute_job_success(app):
    with app.app_context():
        job = Job(
            name="echo test",
            command="echo hello",
            schedule_type="cron",
            schedule_value="* * * * *",
        )
        _db.session.add(job)
        _db.session.commit()
        job_id = job.id

    execute_job(job_id)

    with app.app_context():
        execution = Execution.query.filter_by(job_id=job_id).first()
        assert execution is not None
        assert execution.status == "success"
        assert execution.exit_code == 0
        assert "hello" in execution.stdout


def test_execute_job_failure(app):
    with app.app_context():
        job = Job(
            name="fail test",
            command="exit 1",
            schedule_type="cron",
            schedule_value="* * * * *",
        )
        _db.session.add(job)
        _db.session.commit()
        job_id = job.id

    execute_job(job_id)

    with app.app_context():
        execution = Execution.query.filter_by(job_id=job_id).first()
        assert execution is not None
        assert execution.status == "failed"
        assert execution.exit_code == 1


def test_execute_job_with_env_vars(app):
    import json

    with app.app_context():
        job = Job(
            name="env test",
            command="echo $MY_VAR",
            schedule_type="cron",
            schedule_value="* * * * *",
            env_vars=json.dumps({"MY_VAR": "test_value"}),
        )
        _db.session.add(job)
        _db.session.commit()
        job_id = job.id

    execute_job(job_id)

    with app.app_context():
        execution = Execution.query.filter_by(job_id=job_id).first()
        assert execution is not None
        assert execution.status == "success"
        assert "test_value" in execution.stdout


def test_execute_python_job(app):
    with app.app_context():
        job = Job(
            name="python test",
            command_type="python",
            command="import sys\nprint(f'python {sys.version_info.major}')",
            schedule_type="cron",
            schedule_value="* * * * *",
        )
        _db.session.add(job)
        _db.session.commit()
        job_id = job.id

    execute_job(job_id)

    with app.app_context():
        execution = Execution.query.filter_by(job_id=job_id).first()
        assert execution is not None
        assert execution.status == "success"
        assert execution.exit_code == 0
        assert "python 3" in execution.stdout


def test_execute_python_job_with_error(app):
    with app.app_context():
        job = Job(
            name="python error test",
            command_type="python",
            command="raise ValueError('test error')",
            schedule_type="cron",
            schedule_value="* * * * *",
        )
        _db.session.add(job)
        _db.session.commit()
        job_id = job.id

    execute_job(job_id)

    with app.app_context():
        execution = Execution.query.filter_by(job_id=job_id).first()
        assert execution is not None
        assert execution.status == "failed"
        assert execution.exit_code == 1
        assert "ValueError" in execution.stderr


def test_execute_job_nonexistent(app):
    """Executing a nonexistent job should not raise."""
    execute_job("nonexistent-id")


def test_rotate_logs_by_retention_days(app):
    with app.app_context():
        app.config["LOG_RETENTION_DAYS"] = 7
        app.config["LOG_MAX_PER_JOB"] = 0  # disable per-job limit

        job = Job(name="rot test", command="echo hi", schedule_type="cron", schedule_value="* * * * *")
        _db.session.add(job)
        _db.session.commit()

        # Old execution (10 days ago)
        old_exec = Execution(job_id=job.id, status="success", exit_code=0,
                             started_at=datetime.now() - timedelta(days=10))
        # Recent execution (1 day ago)
        new_exec = Execution(job_id=job.id, status="success", exit_code=0,
                             started_at=datetime.now() - timedelta(days=1))
        _db.session.add_all([old_exec, new_exec])
        _db.session.commit()
        new_exec_id = new_exec.id

        assert Execution.query.count() == 2

    rotate_logs()

    with app.app_context():
        assert Execution.query.count() == 1
        remaining = Execution.query.first()
        assert remaining.id == new_exec_id


def test_rotate_logs_by_max_per_job(app):
    with app.app_context():
        app.config["LOG_RETENTION_DAYS"] = 0  # disable time-based
        app.config["LOG_MAX_PER_JOB"] = 3

        job = Job(name="max test", command="echo hi", schedule_type="cron", schedule_value="* * * * *")
        _db.session.add(job)
        _db.session.commit()

        for i in range(5):
            _db.session.add(Execution(
                job_id=job.id, status="success", exit_code=0,
                started_at=datetime.now() - timedelta(hours=5 - i),
            ))
        _db.session.commit()

        assert Execution.query.count() == 5

    rotate_logs()

    with app.app_context():
        assert Execution.query.count() == 3
