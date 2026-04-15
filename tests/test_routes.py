from mogiri.models import Job, db as _db


def test_dashboard(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Dashboard" in response.data


def test_job_list_empty(client):
    response = client.get("/jobs/")
    assert response.status_code == 200
    assert b"No jobs yet" in response.data


def test_job_create_and_view(client, app):
    # Create job
    response = client.post(
        "/jobs/",
        data={
            "name": "Test Job",
            "command": "echo test",
            "schedule_type": "cron",
            "schedule_value": "* * * * *",
            "is_enabled": "on",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Test Job" in response.data

    # Verify in DB
    with app.app_context():
        job = Job.query.first()
        assert job is not None
        assert job.name == "Test Job"


def test_job_edit(client, app):
    # Create job first
    with app.app_context():
        job = Job(
            name="Original",
            command="echo original",
            schedule_type="cron",
            schedule_value="* * * * *",
        )
        _db.session.add(job)
        _db.session.commit()
        job_id = job.id

    # Edit
    response = client.post(
        f"/jobs/{job_id}",
        data={
            "name": "Updated",
            "command": "echo updated",
            "schedule_type": "cron",
            "schedule_value": "*/5 * * * *",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        job = _db.session.get(Job, job_id)
        assert job.name == "Updated"
        assert job.command == "echo updated"


def test_job_delete(client, app):
    with app.app_context():
        job = Job(
            name="To Delete",
            command="echo delete",
            schedule_type="cron",
            schedule_value="* * * * *",
        )
        _db.session.add(job)
        _db.session.commit()
        job_id = job.id

    response = client.delete(f"/jobs/{job_id}")
    assert response.status_code == 200

    with app.app_context():
        assert _db.session.get(Job, job_id) is None


def test_job_toggle(client, app):
    with app.app_context():
        job = Job(
            name="Toggle Me",
            command="echo toggle",
            schedule_type="cron",
            schedule_value="* * * * *",
            is_enabled=True,
        )
        _db.session.add(job)
        _db.session.commit()
        job_id = job.id

    response = client.patch(f"/jobs/{job_id}/toggle")
    assert response.status_code == 200
    assert b"Disabled" in response.data

    with app.app_context():
        job = _db.session.get(Job, job_id)
        assert job.is_enabled is False


def test_job_new_form(client):
    response = client.get("/jobs/new")
    assert response.status_code == 200
    assert b"New Job" in response.data
