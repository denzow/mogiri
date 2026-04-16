import json
import time

from mogiri.models import Execution, Job, Workflow, WorkflowEdge, db as _db
from mogiri.routes.chains import _has_cycle
from mogiri.scheduler import execute_job, execute_workflow


def test_has_cycle_no_cycle():
    connections = [
        {"source_job_id": "a", "target_job_id": "b",
         "source_node_key": "a:0", "target_node_key": "b:0"},
        {"source_job_id": "b", "target_job_id": "c",
         "source_node_key": "b:0", "target_node_key": "c:0"},
    ]
    assert _has_cycle(connections) is False


def test_has_cycle_with_cycle():
    connections = [
        {"source_job_id": "a", "target_job_id": "b",
         "source_node_key": "a:0", "target_node_key": "b:0"},
        {"source_job_id": "b", "target_job_id": "a",
         "source_node_key": "b:0", "target_node_key": "a:0"},
    ]
    assert _has_cycle(connections) is True


def test_has_cycle_self_loop():
    connections = [
        {"source_job_id": "a", "target_job_id": "a",
         "source_node_key": "a:0", "target_node_key": "a:0"},
    ]
    assert _has_cycle(connections) is True


def test_has_cycle_same_job_different_nodes():
    """Same job used twice with different node_keys is NOT a cycle."""
    connections = [
        {"source_job_id": "a", "target_job_id": "b",
         "source_node_key": "a:0", "target_node_key": "b:0"},
        {"source_job_id": "b", "target_job_id": "a",
         "source_node_key": "b:0", "target_node_key": "a:1"},
    ]
    assert _has_cycle(connections) is False


def test_has_cycle_legacy_no_node_keys():
    """Fallback to job_id when node_keys are absent (legacy data)."""
    connections = [
        {"source_job_id": "a", "target_job_id": "b"},
        {"source_job_id": "b", "target_job_id": "c"},
    ]
    assert _has_cycle(connections) is False


def _create_workflow_with_edge(db_session, job_a, job_b, condition="success"):
    nk_a = f"{job_a.id}:0"
    nk_b = f"{job_b.id}:0"
    wf = Workflow(
        name="Test WF",
        entry_job_ids=json.dumps([job_a.id]),
        entry_node_keys=json.dumps([{"node_key": nk_a, "job_id": job_a.id}]),
    )
    db_session.add(wf)
    db_session.commit()
    edge = WorkflowEdge(
        workflow_id=wf.id,
        source_job_id=job_a.id,
        target_job_id=job_b.id,
        source_node_key=nk_a,
        target_node_key=nk_b,
        trigger_condition=condition,
    )
    db_session.add(edge)
    db_session.commit()
    return wf


def test_chain_triggered_via_workflow(app):
    """Chain fires when job runs as part of a workflow."""
    with app.app_context():
        job_a = Job(name="Job A", command="echo A", schedule_type="none")
        job_b = Job(name="Job B", command="echo B", schedule_type="none")
        _db.session.add_all([job_a, job_b])
        _db.session.commit()
        wf = _create_workflow_with_edge(_db.session, job_a, job_b, "success")
        wf_id = wf.id
        job_b_id = job_b.id

    execute_workflow(wf_id)
    time.sleep(1.5)

    with app.app_context():
        exec_b = Execution.query.filter_by(job_id=job_b_id).first()
        assert exec_b is not None
        assert exec_b.status == "success"
        assert exec_b.workflow_id == wf_id


def test_chain_not_triggered_without_workflow(app):
    """Chain does NOT fire when job runs independently (not via workflow)."""
    with app.app_context():
        job_a = Job(name="Job A", command="echo A", schedule_type="none")
        job_b = Job(name="Job B", command="echo B", schedule_type="none")
        _db.session.add_all([job_a, job_b])
        _db.session.commit()
        _create_workflow_with_edge(_db.session, job_a, job_b, "success")
        job_a_id = job_a.id
        job_b_id = job_b.id

    # Run job_a directly (no workflow context)
    execute_job(job_a_id)
    time.sleep(0.5)

    with app.app_context():
        exec_b = Execution.query.filter_by(job_id=job_b_id).first()
        assert exec_b is None  # Should NOT be triggered


def test_chain_not_triggered_on_wrong_condition(app):
    with app.app_context():
        job_a = Job(name="Job A", command="exit 1", schedule_type="none")
        job_b = Job(name="Job B", command="echo B", schedule_type="none")
        _db.session.add_all([job_a, job_b])
        _db.session.commit()
        wf = _create_workflow_with_edge(_db.session, job_a, job_b, "success")
        wf_id = wf.id
        job_b_id = job_b.id

    execute_workflow(wf_id)
    time.sleep(0.5)

    with app.app_context():
        assert Execution.query.filter_by(job_id=job_b_id).first() is None


def test_chain_triggered_on_failure(app):
    with app.app_context():
        job_a = Job(name="Job A", command="exit 1", schedule_type="none")
        job_b = Job(name="Job B", command="echo B", schedule_type="none")
        _db.session.add_all([job_a, job_b])
        _db.session.commit()
        wf = _create_workflow_with_edge(_db.session, job_a, job_b, "failure")
        wf_id = wf.id
        job_b_id = job_b.id

    execute_workflow(wf_id)
    time.sleep(1.5)

    with app.app_context():
        exec_b = Execution.query.filter_by(job_id=job_b_id).first()
        assert exec_b is not None and exec_b.status == "success"


def test_disabled_workflow_not_triggered(app):
    with app.app_context():
        job_a = Job(name="Job A", command="echo A", schedule_type="none")
        job_b = Job(name="Job B", command="echo B", schedule_type="none")
        _db.session.add_all([job_a, job_b])
        _db.session.commit()
        wf = _create_workflow_with_edge(_db.session, job_a, job_b, "success")
        wf.is_enabled = False
        _db.session.commit()
        wf_id = wf.id
        job_a_id = job_a.id

    execute_workflow(wf_id)
    time.sleep(0.5)

    with app.app_context():
        # Disabled workflow should not execute anything
        assert Execution.query.count() == 0


def test_multiple_workflows_same_jobs(app):
    with app.app_context():
        job_a = Job(name="Job A", command="echo A", schedule_type="none")
        job_b = Job(name="Job B", command="echo B", schedule_type="none")
        job_c = Job(name="Job C", command="echo C", schedule_type="none")
        _db.session.add_all([job_a, job_b, job_c])
        _db.session.commit()

        # Workflow 1: A -> B on success
        wf1 = _create_workflow_with_edge(_db.session, job_a, job_b, "success")
        # Workflow 2: A -> C on success (separate workflow)
        nk_a2 = f"{job_a.id}:0"
        nk_c = f"{job_c.id}:0"
        wf2 = Workflow(
            name="WF2",
            entry_job_ids=json.dumps([job_a.id]),
            entry_node_keys=json.dumps([{"node_key": nk_a2, "job_id": job_a.id}]),
        )
        _db.session.add(wf2)
        _db.session.commit()
        _db.session.add(WorkflowEdge(
            workflow_id=wf2.id, source_job_id=job_a.id,
            target_job_id=job_c.id,
            source_node_key=nk_a2, target_node_key=nk_c,
            trigger_condition="success",
        ))
        _db.session.commit()

        wf1_id, wf2_id = wf1.id, wf2.id
        job_b_id, job_c_id = job_b.id, job_c.id

    # Only run workflow 1
    execute_workflow(wf1_id)
    time.sleep(1.5)

    with app.app_context():
        exec_b = Execution.query.filter_by(job_id=job_b_id).first()
        exec_c = Execution.query.filter_by(job_id=job_c_id).first()
        assert exec_b is not None  # Triggered by WF1
        assert exec_c is None  # NOT triggered (WF2 not run)


def test_workflow_save_api(client, app):
    with app.app_context():
        wf = Workflow(name="Test WF")
        _db.session.add(wf)
        job_a = Job(name="A", command="echo a", schedule_type="cron", schedule_value="* * * * *")
        job_b = Job(name="B", command="echo b", schedule_type="cron", schedule_value="* * * * *")
        _db.session.add_all([job_a, job_b])
        _db.session.commit()
        wf_id, a_id, b_id = wf.id, job_a.id, job_b.id

    response = client.post(f"/chains/{wf_id}/save", json={
        "connections": [
            {"source_job_id": a_id, "target_job_id": b_id,
             "source_node_key": f"{a_id}:0", "target_node_key": f"{b_id}:0",
             "trigger_condition": "success"}
        ],
        "node_positions": [
            {"job_id": a_id, "node_key": f"{a_id}:0", "x": 100, "y": 100},
            {"job_id": b_id, "node_key": f"{b_id}:0", "x": 400, "y": 100},
        ],
        "entry_job_ids": [a_id],
        "entry_node_keys": [{"node_key": f"{a_id}:0", "job_id": a_id}],
        "schedule_type": "cron",
        "schedule_value": "0 * * * *",
    })
    assert response.status_code == 200
    assert response.get_json()["ok"] is True

    with app.app_context():
        edges = WorkflowEdge.query.filter_by(workflow_id=wf_id).all()
        assert len(edges) == 1
        assert edges[0].source_node_key == f"{a_id}:0"
        assert edges[0].target_node_key == f"{b_id}:0"
        wf = _db.session.get(Workflow, wf_id)
        assert wf.schedule_type == "cron"
        assert wf.schedule_value == "0 * * * *"


def test_workflow_save_rejects_cycle(client, app):
    with app.app_context():
        wf = Workflow(name="Test WF")
        _db.session.add(wf)
        job_a = Job(name="A", command="echo a", schedule_type="cron", schedule_value="* * * * *")
        job_b = Job(name="B", command="echo b", schedule_type="cron", schedule_value="* * * * *")
        _db.session.add_all([job_a, job_b])
        _db.session.commit()
        wf_id, a_id, b_id = wf.id, job_a.id, job_b.id

    response = client.post(f"/chains/{wf_id}/save", json={
        "connections": [
            {"source_job_id": a_id, "target_job_id": b_id,
             "source_node_key": f"{a_id}:0", "target_node_key": f"{b_id}:0"},
            {"source_job_id": b_id, "target_job_id": a_id,
             "source_node_key": f"{b_id}:0", "target_node_key": f"{a_id}:0"},
        ],
        "node_positions": [],
        "entry_job_ids": [],
    })
    assert response.status_code == 400
    assert "Cycle" in response.get_json()["error"]


def test_workflow_save_allows_same_job_different_nodes(client, app):
    """Same job used as two separate nodes (A:0 -> B:0 -> A:1) is not a cycle."""
    with app.app_context():
        wf = Workflow(name="Test WF")
        _db.session.add(wf)
        job_a = Job(name="A", command="echo a", schedule_type="cron", schedule_value="* * * * *")
        job_b = Job(name="B", command="echo b", schedule_type="cron", schedule_value="* * * * *")
        _db.session.add_all([job_a, job_b])
        _db.session.commit()
        wf_id, a_id, b_id = wf.id, job_a.id, job_b.id

    response = client.post(f"/chains/{wf_id}/save", json={
        "connections": [
            {"source_job_id": a_id, "target_job_id": b_id,
             "source_node_key": f"{a_id}:0", "target_node_key": f"{b_id}:0"},
            {"source_job_id": b_id, "target_job_id": a_id,
             "source_node_key": f"{b_id}:0", "target_node_key": f"{a_id}:1"},
        ],
        "node_positions": [
            {"job_id": a_id, "node_key": f"{a_id}:0", "x": 100, "y": 100},
            {"job_id": b_id, "node_key": f"{b_id}:0", "x": 300, "y": 100},
            {"job_id": a_id, "node_key": f"{a_id}:1", "x": 500, "y": 100},
        ],
        "entry_job_ids": [a_id],
        "entry_node_keys": [{"node_key": f"{a_id}:0", "job_id": a_id}],
    })
    assert response.status_code == 200
    assert response.get_json()["ok"] is True

    with app.app_context():
        edges = WorkflowEdge.query.filter_by(workflow_id=wf_id).all()
        assert len(edges) == 2
