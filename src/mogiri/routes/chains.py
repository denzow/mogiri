from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from mogiri.models import (
    Execution,
    Job,
    Workflow,
    WorkflowEdge,
    WorkflowNodePosition,
    db,
)

bp = Blueprint("workflows", __name__, url_prefix="/workflows")


def _wf_schedule_ctx(wf):
    """Build template context for the cron_editor partial (workflow)."""
    from flask import url_for as _url_for

    st = wf.schedule_type if wf else "none"
    sv = wf.schedule_value if wf else ""
    cron_parts = sv.split() if st == "cron" and sv and len(sv.split()) == 5 else ["*"] * 5
    return {
        "prefix": "wf",
        "schedule_type": st or "none",
        "schedule_value": sv or "",
        "cron_parts": cron_parts,
        "show_none": True,
        "preview_url": _url_for("jobs.cron_preview"),
    }


# ---------- Workflow list ----------

@bp.route("/")
def workflow_list():
    workflows = Workflow.query.order_by(Workflow.created_at.desc()).all()
    return render_template("chains/list.html", workflows=workflows)


@bp.route("/new", methods=["GET", "POST"])
def workflow_new():
    if request.method == "POST":
        from mogiri.scheduler import register_workflow

        wf = Workflow(
            name=request.form["name"],
            description=request.form.get("description", ""),
            schedule_type=request.form.get("wf_schedule_type", "none"),
            schedule_value=request.form.get("wf_schedule_value", ""),
        )
        db.session.add(wf)
        db.session.commit()
        register_workflow(wf)
        return redirect(url_for("workflows.workflow_editor", workflow_id=wf.id))
    return render_template("chains/new.html", **_wf_schedule_ctx(None))


@bp.route("/<workflow_id>/delete", methods=["DELETE"])
def workflow_delete(workflow_id):
    wf = db.session.get(Workflow, workflow_id)
    if not wf:
        abort(404)
    db.session.delete(wf)
    db.session.commit()
    flash(f"Workflow '{wf.name}' deleted.", "success")
    return "", 200, {"HX-Redirect": url_for("workflows.workflow_list")}


@bp.route("/<workflow_id>/toggle", methods=["PATCH"])
def workflow_toggle(workflow_id):
    from mogiri.scheduler import register_workflow

    wf = db.session.get(Workflow, workflow_id)
    if not wf:
        abort(404)
    wf.is_enabled = not wf.is_enabled
    db.session.commit()
    register_workflow(wf)

    if wf.is_enabled:
        badge = '<span class="badge badge-enabled">Enabled</span>'
    else:
        badge = '<span class="badge badge-disabled">Disabled</span>'
    return f"""<span hx-patch="{url_for('workflows.workflow_toggle', workflow_id=wf.id)}"
                     hx-swap="outerHTML"
                     class="toggle-btn">{badge}</span>"""


# ---------- Run workflow ----------

@bp.route("/<workflow_id>/run", methods=["POST"])
def workflow_run(workflow_id):
    import threading

    from mogiri.scheduler import execute_workflow

    wf = db.session.get(Workflow, workflow_id)
    if not wf:
        abort(404)

    thread = threading.Thread(target=execute_workflow, args=(wf.id,), kwargs={"force": True})
    thread.start()

    history_url = url_for("workflows.chain_history", workflow_id=wf.id)
    flash(
        f"Workflow '{wf.name}' triggered. "
        f'<a href="{history_url}">View execution history</a>',
        "info",
    )
    return "", 200, {"HX-Refresh": "true"}


@bp.route("/<workflow_id>/cancel", methods=["POST"])
def workflow_cancel(workflow_id):
    from mogiri.scheduler import cancel_workflow

    wf = db.session.get(Workflow, workflow_id)
    if not wf:
        abort(404)

    count = cancel_workflow(wf.id)
    if count > 0:
        flash(f"Cancelled {count} running execution(s) in '{wf.name}'.", "info")
    else:
        flash(f"No running executions in '{wf.name}'.", "info")
    return "", 200, {"HX-Refresh": "true"}


# ---------- Workflow editor ----------

@bp.route("/<workflow_id>/edit")
def workflow_editor(workflow_id):
    wf = db.session.get(Workflow, workflow_id)
    if not wf:
        abort(404)

    jobs = Job.query.order_by(Job.name).all()
    edges = WorkflowEdge.query.filter_by(workflow_id=wf.id).all()
    node_positions = [
        {"node_key": p.node_key, "job_id": p.job_id, "x": p.x, "y": p.y}
        for p in WorkflowNodePosition.query.filter_by(workflow_id=wf.id).all()
    ]

    jobs_data = [
        {"id": j.id, "name": j.name, "command_type": j.command_type or "shell"}
        for j in jobs
    ]
    edges_data = [
        {
            "source_job_id": e.source_job_id,
            "target_job_id": e.target_job_id,
            "source_node_key": e.source_node_key,
            "target_node_key": e.target_node_key,
            "trigger_condition": e.trigger_condition,
        }
        for e in edges
    ]

    import json as _json
    entry_job_ids = []
    try:
        entry_job_ids = _json.loads(wf.entry_job_ids or "[]")
    except (ValueError, TypeError):
        pass
    entry_node_keys = []
    try:
        entry_node_keys = _json.loads(wf.entry_node_keys or "[]")
    except (ValueError, TypeError):
        pass

    has_saved_state = bool(edges_data or entry_job_ids or entry_node_keys)

    return render_template(
        "chains/editor.html",
        workflow=wf,
        jobs_data=jobs_data,
        edges_data=edges_data,
        node_positions=node_positions,
        entry_job_ids=entry_job_ids,
        entry_node_keys=entry_node_keys,
        has_saved_state=has_saved_state,
        start_node_x=wf.start_node_x or 50,
        start_node_y=wf.start_node_y or 250,
        **_wf_schedule_ctx(wf),
    )


@bp.route("/<workflow_id>/save", methods=["POST"])
def workflow_save(workflow_id):
    wf = db.session.get(Workflow, workflow_id)
    if not wf:
        return jsonify({"error": "Workflow not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    import json as _json

    from mogiri.scheduler import register_workflow

    connections = data.get("connections", [])
    node_positions = data.get("node_positions", [])
    entry_job_ids = data.get("entry_job_ids", [])
    entry_node_keys_data = data.get("entry_node_keys", [])
    start_pos = data.get("start_node", {})
    name = data.get("name")
    description = data.get("description")
    schedule_type = data.get("schedule_type")
    schedule_value = data.get("schedule_value")
    max_iterations = data.get("max_iterations")

    if name is not None:
        wf.name = name
    if description is not None:
        wf.description = description
    if schedule_type is not None:
        wf.schedule_type = schedule_type
    if schedule_value is not None:
        wf.schedule_value = schedule_value
    if max_iterations is not None:
        wf.max_iterations = max(1, int(max_iterations))

    wf.entry_job_ids = _json.dumps(entry_job_ids)
    wf.entry_node_keys = _json.dumps(entry_node_keys_data)
    if start_pos:
        wf.start_node_x = start_pos.get("x", 50)
        wf.start_node_y = start_pos.get("y", 250)

    # Replace edges — deduplicate by (source_node_key, target_node_key, condition)
    WorkflowEdge.query.filter_by(workflow_id=wf.id).delete()
    seen_edges = set()
    for conn in connections:
        src_nk = conn.get("source_node_key") or conn["source_job_id"]
        tgt_nk = conn.get("target_node_key") or conn["target_job_id"]
        edge_key = (src_nk, tgt_nk, conn.get("trigger_condition", "success"))
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        db.session.add(WorkflowEdge(
            workflow_id=wf.id,
            source_job_id=conn["source_job_id"],
            target_job_id=conn["target_job_id"],
            source_node_key=conn.get("source_node_key"),
            target_node_key=conn.get("target_node_key"),
            trigger_condition=conn.get("trigger_condition", "success"),
        ))

    # Replace node positions (supports multiple instances of same job)
    WorkflowNodePosition.query.filter_by(workflow_id=wf.id).delete()
    for np in node_positions:
        db.session.add(WorkflowNodePosition(
            workflow_id=wf.id,
            job_id=np["job_id"],
            node_key=np["node_key"],
            x=np["x"],
            y=np["y"],
        ))

    db.session.commit()
    register_workflow(wf)
    return jsonify({"ok": True})


# ---------- History ----------

@bp.route("/history")
def chain_history_all():
    """All workflow executions across all workflows."""
    executions = (
        Execution.query.filter(Execution.workflow_id.isnot(None))
        .order_by(Execution.started_at.desc())
        .limit(50)
        .all()
    )
    return render_template("chains/history.html", executions=executions, workflow=None)


@bp.route("/<workflow_id>/history")
def chain_history(workflow_id):
    """Execution history for a specific workflow."""
    wf = db.session.get(Workflow, workflow_id)
    if not wf:
        abort(404)
    executions = (
        Execution.query.filter(Execution.workflow_id == wf.id)
        .order_by(Execution.started_at.desc())
        .limit(50)
        .all()
    )
    return render_template("chains/history.html", executions=executions, workflow=wf)
