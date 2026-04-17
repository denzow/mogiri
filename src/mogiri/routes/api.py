import json
import threading

from flask import Blueprint, jsonify, request

from mogiri.models import Job, db
from mogiri.scheduler import execute_job, register_job, unregister_job

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


@bp.route("/jobs/<job_id>/run", methods=["POST"])
def run_job(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    thread = threading.Thread(target=execute_job, args=(job.id,))
    thread.start()
    return jsonify({"message": f"Job '{job.name}' triggered"}), 202
