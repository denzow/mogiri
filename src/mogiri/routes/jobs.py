import json
import threading

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for

from mogiri.models import Execution, Job, db
from mogiri.scheduler import execute_job, register_job, unregister_job


def _build_schedule_value(form):
    """Build schedule_value from form fields depending on schedule_type."""
    schedule_type = form["schedule_type"]
    if schedule_type == "cron":
        parts = [
            form.get("cron_minute", "*").strip() or "*",
            form.get("cron_hour", "*").strip() or "*",
            form.get("cron_day", "*").strip() or "*",
            form.get("cron_month", "*").strip() or "*",
            form.get("cron_weekday", "*").strip() or "*",
        ]
        return " ".join(parts)
    else:
        return form.get("once_value", "") or form.get("schedule_value", "")

bp = Blueprint("jobs", __name__, url_prefix="/jobs")


def _parse_env_vars(form):
    """Parse env_key[] and env_value[] from form data into a JSON string."""
    keys = form.getlist("env_key")
    values = form.getlist("env_value")
    env_dict = {}
    for k, v in zip(keys, values):
        k = k.strip()
        if k:
            env_dict[k] = v
    return json.dumps(env_dict)


@bp.route("/")
def job_list():
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    return render_template("jobs/list.html", jobs=jobs)


@bp.route("/new")
def job_new():
    return render_template("jobs/form.html", job=None)


@bp.route("/", methods=["POST"])
def job_create():
    job = Job(
        name=request.form["name"],
        description=request.form.get("description", ""),
        command=request.form["command"],
        schedule_type=request.form["schedule_type"],
        schedule_value=_build_schedule_value(request.form),
        env_vars=_parse_env_vars(request.form),
        is_enabled="is_enabled" in request.form,
    )
    db.session.add(job)
    db.session.commit()

    register_job(job)
    flash(f"Job '{job.name}' created.", "success")
    return redirect(url_for("jobs.job_detail", job_id=job.id))


@bp.route("/<job_id>")
def job_detail(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)
    executions = (
        job.executions.order_by(Execution.started_at.desc()).limit(50).all()
    )
    return render_template("jobs/detail.html", job=job, executions=executions)


@bp.route("/<job_id>/executions")
def job_executions(job_id):
    """Partial endpoint for htmx polling of execution list."""
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)
    executions = (
        job.executions.order_by(Execution.started_at.desc()).limit(50).all()
    )
    return render_template("partials/execution_list.html", executions=executions)


@bp.route("/<job_id>/edit")
def job_edit(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)
    return render_template("jobs/form.html", job=job)


@bp.route("/<job_id>", methods=["POST"])
def job_update(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    job.name = request.form["name"]
    job.description = request.form.get("description", "")
    job.command = request.form["command"]
    job.schedule_type = request.form["schedule_type"]
    job.schedule_value = _build_schedule_value(request.form)
    job.env_vars = _parse_env_vars(request.form)
    job.is_enabled = "is_enabled" in request.form

    db.session.commit()

    register_job(job)
    flash(f"Job '{job.name}' updated.", "success")
    return redirect(url_for("jobs.job_detail", job_id=job.id))


@bp.route("/<job_id>", methods=["DELETE"])
def job_delete(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    unregister_job(job.id)
    db.session.delete(job)
    db.session.commit()

    flash(f"Job '{job.name}' deleted.", "success")
    return "", 200, {"HX-Redirect": url_for("jobs.job_list")}


@bp.route("/<job_id>/toggle", methods=["PATCH"])
def job_toggle(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    job.is_enabled = not job.is_enabled
    db.session.commit()

    register_job(job)

    if job.is_enabled:
        badge = '<span class="badge badge-enabled">Enabled</span>'
    else:
        badge = '<span class="badge badge-disabled">Disabled</span>'

    return f"""<span hx-patch="{url_for('jobs.job_toggle', job_id=job.id)}"
                     hx-swap="outerHTML"
                     class="toggle-btn">{badge}</span>"""


@bp.route("/cron-preview")
def cron_preview():
    """Return next 5 run times for a cron expression."""
    from datetime import datetime

    from apscheduler.triggers.cron import CronTrigger

    expr = request.args.get("expr", "").strip()
    if not expr:
        return jsonify({"error": "Empty expression"})
    try:
        trigger = CronTrigger.from_crontab(expr)
        now = datetime.now()
        runs = []
        previous = None
        for _ in range(5):
            next_time = trigger.get_next_fire_time(previous, now)
            if next_time is None:
                break
            runs.append(next_time.strftime("%Y-%m-%d %H:%M"))
            previous = next_time
            now = next_time
        return jsonify({"next_runs": runs})
    except Exception as e:
        return jsonify({"error": str(e)})


@bp.route("/<job_id>/run", methods=["POST"])
def job_run(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    thread = threading.Thread(target=execute_job, args=(job.id,))
    thread.start()

    flash(f"Job '{job.name}' triggered.", "info")
    return "", 200, {"HX-Refresh": "true"}
