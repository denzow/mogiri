import json
import os
import subprocess
import threading

from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    stream_with_context,
    url_for,
)

from flask import url_for as _url_for

from mogiri.models import Execution, Job, Setting, db
from mogiri.scheduler import execute_job, register_job, unregister_job

_samples_cache = None


def _get_samples_reference():
    """Load samples README and script contents for AI context."""
    global _samples_cache
    if _samples_cache is not None:
        return _samples_cache

    samples_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "samples")
    samples_dir = os.path.abspath(samples_dir)
    if not os.path.isdir(samples_dir):
        _samples_cache = ""
        return _samples_cache

    parts = ["The following sample scripts are available as references:\n"]

    for filename in sorted(os.listdir(samples_dir)):
        filepath = os.path.join(samples_dir, filename)
        if not os.path.isfile(filepath):
            continue
        if filename.startswith("."):
            continue
        try:
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
            parts.append(f"--- {filename} ---\n{content}\n")
        except Exception:
            continue

    _samples_cache = "\n".join(parts)
    return _samples_cache


def _schedule_ctx(job):
    """Build template context variables for the cron_editor partial."""
    st = job.schedule_type if job else "cron"
    sv = job.schedule_value if job else ""
    cron_parts = sv.split() if st == "cron" and sv and len(sv.split()) == 5 else ["*"] * 5
    return {
        "prefix": "job",
        "schedule_type": st or "cron",
        "schedule_value": sv or "",
        "cron_parts": cron_parts,
        "show_none": True,
        "preview_url": _url_for("jobs.cron_preview"),
    }


def _build_schedule(form, prefix="job"):
    """Extract schedule_type and schedule_value from form fields."""
    schedule_type = form.get(f"{prefix}_schedule_type", "cron")
    schedule_value = form.get(f"{prefix}_schedule_value", "")
    # Fallback: if JS sync missed, build cron from individual fields
    if schedule_type == "cron" and not schedule_value.strip():
        parts = [
            form.get(f"{prefix}_cron_minute", "*").strip() or "*",
            form.get(f"{prefix}_cron_hour", "*").strip() or "*",
            form.get(f"{prefix}_cron_day", "*").strip() or "*",
            form.get(f"{prefix}_cron_month", "*").strip() or "*",
            form.get(f"{prefix}_cron_weekday", "*").strip() or "*",
        ]
        schedule_value = " ".join(parts)
    return schedule_type, schedule_value

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
    scheduled_jobs = (
        Job.query.filter(Job.schedule_type.in_(["cron", "once"]))
        .order_by(Job.created_at.desc())
        .all()
    )
    manual_jobs = (
        Job.query.filter(Job.schedule_type == "none")
        .order_by(Job.created_at.desc())
        .all()
    )
    tab = request.args.get("tab", "scheduled")
    return render_template(
        "jobs/list.html",
        scheduled_jobs=scheduled_jobs,
        manual_jobs=manual_jobs,
        tab=tab,
    )


@bp.route("/new")
def job_new():
    return render_template("jobs/form.html", job=None, **_schedule_ctx(None))


@bp.route("/", methods=["POST"])
def job_create():
    job = Job(
        name=request.form["name"],
        description=request.form.get("description", ""),
        command_type=request.form.get("command_type", "shell"),
        command=request.form["command"],
        schedule_type=_build_schedule(request.form)[0],
        schedule_value=_build_schedule(request.form)[1],
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
    return render_template(
        "jobs/detail.html", job=job, executions=executions,
    )


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
    return render_template("jobs/form.html", job=job, **_schedule_ctx(job))


@bp.route("/<job_id>", methods=["POST"])
def job_update(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    job.name = request.form["name"]
    job.description = request.form.get("description", "")
    job.command_type = request.form.get("command_type", "shell")
    job.command = request.form["command"]
    sched_type, sched_value = _build_schedule(request.form)
    job.schedule_type = sched_type
    job.schedule_value = sched_value
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


@bp.route("/ai-chat", methods=["POST"])
def ai_chat():
    """Stream AI CLI response for the chat assistant."""
    data = request.get_json()
    message = data.get("message", "")
    command_type = data.get("command_type", "shell")
    current_command = data.get("current_command", "")
    job_name = data.get("job_name", "")
    job_description = data.get("job_description", "")
    history = data.get("history", [])

    ai_provider = Setting.get("ai_provider", "claude")

    system_prompt = (
        "You are an AI assistant embedded in mogiri, a local job manager. "
        "Help users write shell commands or Python scripts for their scheduled jobs. "
        "When providing code, always use a fenced code block with the appropriate "
        "language tag (```bash for shell, ```python for Python). "
        "Keep responses concise and focused on the task.\n\n"
        + _get_samples_reference()
    )

    # Build prompt with conversation context
    prompt_parts = []
    if job_name.strip():
        job_ctx = f"Job name: {job_name}"
        if job_description.strip():
            job_ctx += f"\nJob description: {job_description}"
        prompt_parts.append(job_ctx)
    if history:
        for msg in history:
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")
            prompt_parts.append(f"{role}: {content}")
        prompt_parts.append("")
    if current_command.strip():
        prompt_parts.append(
            f"The user's current {command_type} command in the editor:\n```\n{current_command}\n```\n"
        )
    prompt_parts.append(message)
    prompt = "\n".join(prompt_parts)

    # Build CLI command based on provider
    if ai_provider == "gemini":
        full_prompt = f"[System]\n{system_prompt}\n\n[User]\n{prompt}"
        cmd = ["gemini", "-p", full_prompt]
        cmd_label = "gemini"
    else:
        cmd = ["claude", "-p", "--system-prompt", system_prompt, prompt]
        cmd_label = "claude"

    def generate():
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            while True:
                chunk = proc.stdout.read1(4096)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                yield f"data: {json.dumps({'t': text})}\n\n"
            proc.wait()
            if proc.returncode != 0:
                err = proc.stderr.read().decode("utf-8", errors="replace")
                if err.strip():
                    yield f"data: {json.dumps({'error': err.strip()})}\n\n"
        except FileNotFoundError:
            yield f"data: {json.dumps({'error': f'{cmd_label} command not found. Make sure {cmd_label} CLI is installed.'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.route("/<job_id>/run", methods=["POST"])
def job_run(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    thread = threading.Thread(target=execute_job, args=(job.id,))
    thread.start()

    flash(f"Job '{job.name}' triggered.", "info")
    return "", 200, {"HX-Refresh": "true"}
