from mogiri.models import Execution, Job, Workflow
from mogiri.models import db as _db


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


# ---------- Workflow API ----------

def test_api_create_workflow(client, app):
    response = client.post("/api/workflows", json={"name": "Test WF"})
    assert response.status_code == 201
    data = response.get_json()
    assert data["name"] == "Test WF"
    assert data["id"]


def test_api_list_workflows(client, app):
    with app.app_context():
        _db.session.add(Workflow(name="WF1"))
        _db.session.add(Workflow(name="WF2"))
        _db.session.commit()
    response = client.get("/api/workflows")
    assert response.status_code == 200
    assert len(response.get_json()) == 2


def test_api_get_workflow(client, app):
    with app.app_context():
        wf = Workflow(name="WF")
        _db.session.add(wf)
        _db.session.commit()
        wf_id = wf.id
    response = client.get(f"/api/workflows/{wf_id}")
    assert response.status_code == 200
    assert response.get_json()["name"] == "WF"


def test_api_update_workflow(client, app):
    with app.app_context():
        wf = Workflow(name="old")
        _db.session.add(wf)
        _db.session.commit()
        wf_id = wf.id
    response = client.patch(f"/api/workflows/{wf_id}", json={"name": "new"})
    assert response.status_code == 200
    assert response.get_json()["name"] == "new"


def test_api_delete_workflow(client, app):
    with app.app_context():
        wf = Workflow(name="del")
        _db.session.add(wf)
        _db.session.commit()
        wf_id = wf.id
    response = client.delete(f"/api/workflows/{wf_id}")
    assert response.status_code == 200
    with app.app_context():
        assert _db.session.get(Workflow, wf_id) is None


def test_api_run_workflow(client, app):
    with app.app_context():
        wf = Workflow(name="run")
        _db.session.add(wf)
        _db.session.commit()
        wf_id = wf.id
    response = client.post(f"/api/workflows/{wf_id}/run")
    assert response.status_code == 202


# ---------- Execution API ----------

def test_api_list_executions(client, app):
    with app.app_context():
        job = Job(name="J", command="echo", schedule_type="none")
        _db.session.add(job)
        _db.session.commit()
        _db.session.add(Execution(job_id=job.id, status="success"))
        _db.session.add(Execution(job_id=job.id, status="failed"))
        _db.session.commit()
    response = client.get("/api/executions")
    assert response.status_code == 200
    assert len(response.get_json()) == 2


def test_api_list_executions_filter(client, app):
    with app.app_context():
        j1 = Job(name="J1", command="echo 1", schedule_type="none")
        j2 = Job(name="J2", command="echo 2", schedule_type="none")
        _db.session.add_all([j1, j2])
        _db.session.commit()
        _db.session.add(Execution(job_id=j1.id, status="success"))
        _db.session.add(Execution(job_id=j2.id, status="success"))
        _db.session.commit()
        j1_id = j1.id
    response = client.get(f"/api/executions?job_id={j1_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["job_id"] == j1_id


def test_api_get_execution(client, app):
    with app.app_context():
        job = Job(name="J", command="echo", schedule_type="none")
        _db.session.add(job)
        _db.session.commit()
        ex = Execution(job_id=job.id, status="success", stdout="hello", stderr="")
        _db.session.add(ex)
        _db.session.commit()
        ex_id = ex.id
    response = client.get(f"/api/executions/{ex_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["stdout"] == "hello"
    assert data["status"] == "success"


# ---------- Settings API ----------

def test_api_settings_get_set(client, app):
    response = client.get("/api/settings/ai_provider")
    assert response.status_code == 200
    assert response.get_json()["key"] == "ai_provider"

    response = client.put("/api/settings/ai_provider", json={"value": "gemini"})
    assert response.status_code == 200
    assert response.get_json()["value"] == "gemini"

    response = client.get("/api/settings/ai_provider")
    assert response.get_json()["value"] == "gemini"
