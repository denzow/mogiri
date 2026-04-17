from mogiri.models import Job, db as _db


def test_api_create_job(client, app):
    response = client.post("/api/jobs", json={
        "name": "test job",
        "command": "echo hello",
        "command_type": "shell",
        "schedule_type": "none",
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data["name"] == "test job"
    assert data["command"] == "echo hello"
    assert data["id"]

    with app.app_context():
        job = _db.session.get(Job, data["id"])
        assert job is not None
        assert job.name == "test job"


def test_api_create_job_with_env_vars(client, app):
    response = client.post("/api/jobs", json={
        "name": "env job",
        "command": "echo $FOO",
        "env_vars": {"FOO": "bar"},
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data["env_vars"] == {"FOO": "bar"}


def test_api_create_job_validation(client):
    response = client.post("/api/jobs", json={"name": "no command"})
    assert response.status_code == 400
    assert "required" in response.get_json()["error"]

    response = client.post("/api/jobs", json={
        "name": "bad type",
        "command": "echo",
        "command_type": "ruby",
    })
    assert response.status_code == 400


def test_api_list_jobs(client, app):
    with app.app_context():
        _db.session.add(Job(name="A", command="echo a", schedule_type="none"))
        _db.session.add(Job(name="B", command="echo b", schedule_type="none"))
        _db.session.commit()

    response = client.get("/api/jobs")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2


def test_api_get_job(client, app):
    with app.app_context():
        job = Job(name="X", command="echo x", schedule_type="none")
        _db.session.add(job)
        _db.session.commit()
        job_id = job.id

    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    assert response.get_json()["name"] == "X"


def test_api_get_job_not_found(client):
    response = client.get("/api/jobs/nonexistent")
    assert response.status_code == 404


def test_api_update_job(client, app):
    with app.app_context():
        job = Job(name="old", command="echo old", schedule_type="none")
        _db.session.add(job)
        _db.session.commit()
        job_id = job.id

    response = client.patch(f"/api/jobs/{job_id}", json={
        "name": "new",
        "command": "echo new",
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["name"] == "new"
    assert data["command"] == "echo new"


def test_api_delete_job(client, app):
    with app.app_context():
        job = Job(name="del", command="echo del", schedule_type="none")
        _db.session.add(job)
        _db.session.commit()
        job_id = job.id

    response = client.delete(f"/api/jobs/{job_id}")
    assert response.status_code == 200

    with app.app_context():
        assert _db.session.get(Job, job_id) is None


def test_api_run_job(client, app):
    with app.app_context():
        job = Job(name="run", command="echo hi", schedule_type="none")
        _db.session.add(job)
        _db.session.commit()
        job_id = job.id

    response = client.post(f"/api/jobs/{job_id}/run")
    assert response.status_code == 202
