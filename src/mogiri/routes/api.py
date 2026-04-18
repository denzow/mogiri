import json
import threading

from flask import Blueprint, jsonify, request

from mogiri.models import Execution, Job, Setting, Workflow, db
from mogiri.scheduler import (
    cancel_execution,
    execute_job,
    execute_workflow,
    register_job,
    register_workflow,
    unregister_job,
    unregister_workflow,
)

bp = Blueprint("api", __name__, url_prefix="/api")


def _job_to_dict(job):
    env = {}
    try:
        env = json.loads(job.env_vars or "{}")
    except (json.JSONDecodeError, TypeError):
        pass
    return {
        "id": job.id,
        "name": job.name,
        "description": job.description,
        "command_type": job.command_type,
        "command": job.command,
        "schedule_type": job.schedule_type,
        "schedule_value": job.schedule_value or "",
        "env_vars": env,
        "working_dir": job.working_dir or "",
        "is_enabled": job.is_enabled,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


VALID_SCHEDULE_TYPES = ("cron", "once", "none")
VALID_COMMAND_TYPES = ("shell", "python")


@bp.route("/jobs", methods=["GET"])
def list_jobs():
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    return jsonify([_job_to_dict(j) for j in jobs])


@bp.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(_job_to_dict(job))


@bp.route("/jobs", methods=["POST"])
def create_job():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    name = data.get("name", "").strip()
    command = data.get("command", "").strip()
    if not name or not command:
        return jsonify({"error": "name and command are required"}), 400

    command_type = data.get("command_type", "shell")
    if command_type not in VALID_COMMAND_TYPES:
        return jsonify({"error": f"command_type must be one of {VALID_COMMAND_TYPES}"}), 400

    schedule_type = data.get("schedule_type", "none")
    if schedule_type not in VALID_SCHEDULE_TYPES:
        return jsonify({"error": f"schedule_type must be one of {VALID_SCHEDULE_TYPES}"}), 400

    env_vars = data.get("env_vars", {})
    if isinstance(env_vars, dict):
        env_vars = json.dumps(env_vars)

    job = Job(
        name=name,
        description=data.get("description", ""),
        command_type=command_type,
        command=command,
        schedule_type=schedule_type,
        schedule_value=data.get("schedule_value", ""),
        env_vars=env_vars,
        working_dir=data.get("working_dir", ""),
        is_enabled=data.get("is_enabled", True),
    )
    db.session.add(job)
    db.session.commit()
    register_job(job)
    return jsonify(_job_to_dict(job)), 201


@bp.route("/jobs/<job_id>", methods=["PATCH"])
def update_job(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    if "name" in data:
        job.name = data["name"]
    if "description" in data:
        job.description = data["description"]
    if "command_type" in data:
        if data["command_type"] not in VALID_COMMAND_TYPES:
            return jsonify({"error": f"command_type must be one of {VALID_COMMAND_TYPES}"}), 400
        job.command_type = data["command_type"]
    if "command" in data:
        job.command = data["command"]
    if "schedule_type" in data:
        if data["schedule_type"] not in VALID_SCHEDULE_TYPES:
            return jsonify({"error": f"schedule_type must be one of {VALID_SCHEDULE_TYPES}"}), 400
        job.schedule_type = data["schedule_type"]
    if "schedule_value" in data:
        job.schedule_value = data["schedule_value"]
    if "env_vars" in data:
        env_vars = data["env_vars"]
        if isinstance(env_vars, dict):
            env_vars = json.dumps(env_vars)
        job.env_vars = env_vars
    if "working_dir" in data:
        job.working_dir = data["working_dir"]
    if "is_enabled" in data:
        job.is_enabled = data["is_enabled"]

    db.session.commit()
    register_job(job)
    return jsonify(_job_to_dict(job))


@bp.route("/jobs/<job_id>", methods=["DELETE"])
def delete_job(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    unregister_job(job.id)
    db.session.delete(job)
    db.session.commit()
    return jsonify({"message": f"Job '{job.name}' deleted"})


@bp.route("/jobs/<job_id>/copy", methods=["POST"])
def copy_job(job_id):
    source = db.session.get(Job, job_id)
    if not source:
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json() or {}
    new_name = data.get("name", f"{source.name} (Copy)").strip()

    job = Job(
        name=new_name,
        description=source.description,
        command_type=source.command_type,
        command=source.command,
        schedule_type=source.schedule_type,
        schedule_value=source.schedule_value,
        env_vars=source.env_vars,
        working_dir=source.working_dir,
        is_enabled=source.is_enabled,
    )
    db.session.add(job)
    db.session.commit()
    register_job(job)
    return jsonify(_job_to_dict(job)), 201


@bp.route("/jobs/<job_id>/run", methods=["POST"])
def run_job(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    thread = threading.Thread(target=execute_job, args=(job.id,))
    thread.start()
    return jsonify({"message": f"Job '{job.name}' triggered"}), 202


# ---------- Workflow API ----------

def _workflow_to_dict(wf):
    entry_node_keys = []
    try:
        entry_node_keys = json.loads(wf.entry_node_keys or "[]")
    except (json.JSONDecodeError, TypeError):
        pass
    return {
        "id": wf.id,
        "name": wf.name,
        "description": wf.description,
        "is_enabled": wf.is_enabled,
        "schedule_type": wf.schedule_type,
        "schedule_value": wf.schedule_value or "",
        "entry_node_keys": entry_node_keys,
        "edges": [
            {
                "source_job_id": e.source_job_id,
                "target_job_id": e.target_job_id,
                "source_node_key": e.source_node_key,
                "target_node_key": e.target_node_key,
                "trigger_condition": e.trigger_condition,
            }
            for e in wf.edges
        ],
        "created_at": wf.created_at.isoformat() if wf.created_at else None,
        "updated_at": wf.updated_at.isoformat() if wf.updated_at else None,
    }


@bp.route("/workflows", methods=["GET"])
def list_workflows():
    workflows = Workflow.query.order_by(Workflow.created_at.desc()).all()
    return jsonify([_workflow_to_dict(wf) for wf in workflows])


@bp.route("/workflows/<workflow_id>", methods=["GET"])
def get_workflow(workflow_id):
    wf = db.session.get(Workflow, workflow_id)
    if not wf:
        return jsonify({"error": "Workflow not found"}), 404
    return jsonify(_workflow_to_dict(wf))


@bp.route("/workflows", methods=["POST"])
def create_workflow():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    schedule_type = data.get("schedule_type", "none")
    if schedule_type not in VALID_SCHEDULE_TYPES:
        return jsonify({"error": f"schedule_type must be one of {VALID_SCHEDULE_TYPES}"}), 400

    wf = Workflow(
        name=name,
        description=data.get("description", ""),
        schedule_type=schedule_type,
        schedule_value=data.get("schedule_value", ""),
        is_enabled=data.get("is_enabled", True),
    )
    db.session.add(wf)
    db.session.commit()
    register_workflow(wf)
    return jsonify(_workflow_to_dict(wf)), 201


@bp.route("/workflows/<workflow_id>", methods=["PATCH"])
def update_workflow(workflow_id):
    wf = db.session.get(Workflow, workflow_id)
    if not wf:
        return jsonify({"error": "Workflow not found"}), 404
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    if "name" in data:
        wf.name = data["name"]
    if "description" in data:
        wf.description = data["description"]
    if "schedule_type" in data:
        if data["schedule_type"] not in VALID_SCHEDULE_TYPES:
            return jsonify({"error": f"schedule_type must be one of {VALID_SCHEDULE_TYPES}"}), 400
        wf.schedule_type = data["schedule_type"]
    if "schedule_value" in data:
        wf.schedule_value = data["schedule_value"]
    if "is_enabled" in data:
        wf.is_enabled = data["is_enabled"]

    db.session.commit()
    register_workflow(wf)
    return jsonify(_workflow_to_dict(wf))


@bp.route("/workflows/<workflow_id>", methods=["DELETE"])
def delete_workflow(workflow_id):
    wf = db.session.get(Workflow, workflow_id)
    if not wf:
        return jsonify({"error": "Workflow not found"}), 404
    unregister_workflow(wf.id)
    db.session.delete(wf)
    db.session.commit()
    return jsonify({"message": f"Workflow '{wf.name}' deleted"})


@bp.route("/workflows/<workflow_id>/run", methods=["POST"])
def run_workflow(workflow_id):
    wf = db.session.get(Workflow, workflow_id)
    if not wf:
        return jsonify({"error": "Workflow not found"}), 404
    thread = threading.Thread(
        target=execute_workflow, args=(wf.id,), kwargs={"force": True}
    )
    thread.start()
    return jsonify({"message": f"Workflow '{wf.name}' triggered"}), 202


# ---------- Execution API ----------

def _execution_to_dict(ex, include_output=False):
    d = {
        "id": ex.id,
        "job_id": ex.job_id,
        "job_name": ex.job.name if ex.job else None,
        "workflow_id": ex.workflow_id,
        "pid": ex.pid,
        "status": ex.status,
        "exit_code": ex.exit_code,
        "started_at": ex.started_at.isoformat() if ex.started_at else None,
        "finished_at": ex.finished_at.isoformat() if ex.finished_at else None,
    }
    if include_output:
        d["stdout"] = ex.stdout or ""
        d["stderr"] = ex.stderr or ""
    return d


@bp.route("/executions", methods=["GET"])
def list_executions():
    limit = request.args.get("limit", 50, type=int)
    q = Execution.query
    job_id = request.args.get("job_id")
    if job_id:
        q = q.filter_by(job_id=job_id)
    workflow_id = request.args.get("workflow_id")
    if workflow_id:
        q = q.filter_by(workflow_id=workflow_id)
    execs = q.order_by(Execution.started_at.desc()).limit(limit).all()
    return jsonify([_execution_to_dict(ex) for ex in execs])


@bp.route("/executions/<execution_id>", methods=["GET"])
def get_execution(execution_id):
    ex = db.session.get(Execution, execution_id)
    if not ex:
        return jsonify({"error": "Execution not found"}), 404
    return jsonify(_execution_to_dict(ex, include_output=True))


@bp.route("/executions/<execution_id>/cancel", methods=["POST"])
def cancel_execution_api(execution_id):
    ex = db.session.get(Execution, execution_id)
    if not ex:
        return jsonify({"error": "Execution not found"}), 404
    if ex.status != "running":
        return jsonify({"error": "Execution is not running"}), 409
    if cancel_execution(execution_id):
        return jsonify({"message": "Cancellation requested"})
    return jsonify({"error": "Process not found (may have already finished)"}), 409


# ---------- Settings API ----------

@bp.route("/settings/<key>", methods=["GET"])
def get_setting(key):
    return jsonify({"key": key, "value": Setting.get(key, "")})


@bp.route("/settings/<key>", methods=["PUT"])
def set_setting(key):
    data = request.get_json()
    if not data or "value" not in data:
        return jsonify({"error": "value is required"}), 400
    Setting.set(key, data["value"])
    return jsonify({"key": key, "value": data["value"]})
