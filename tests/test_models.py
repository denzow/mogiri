from mogiri.models import Execution, Job


def test_create_job(db):
    job = Job(
        name="test job",
        command="echo hello",
        schedule_type="cron",
        schedule_value="* * * * *",
    )
    db.session.add(job)
    db.session.commit()

    assert job.id is not None
    assert job.name == "test job"
    assert job.is_enabled is True

    fetched = db.session.get(Job, job.id)
    assert fetched.command == "echo hello"


def test_create_execution(db):
    job = Job(
        name="test job",
        command="echo hello",
        schedule_type="cron",
        schedule_value="* * * * *",
    )
    db.session.add(job)
    db.session.commit()

    execution = Execution(
        job_id=job.id, status="success",
        exit_code=0, stdout="hello\n",
    )
    db.session.add(execution)
    db.session.commit()

    assert execution.id is not None
    assert execution.job.name == "test job"


def test_job_execution_relationship(db):
    job = Job(
        name="test job",
        command="echo hello",
        schedule_type="cron",
        schedule_value="* * * * *",
    )
    db.session.add(job)
    db.session.commit()

    for i in range(3):
        db.session.add(Execution(job_id=job.id, status="success", exit_code=0))
    db.session.commit()

    assert job.executions.count() == 3


def test_cascade_delete(db):
    job = Job(
        name="test job",
        command="echo hello",
        schedule_type="cron",
        schedule_value="* * * * *",
    )
    db.session.add(job)
    db.session.commit()

    db.session.add(Execution(job_id=job.id, status="success", exit_code=0))
    db.session.commit()

    db.session.delete(job)
    db.session.commit()

    assert Execution.query.count() == 0
