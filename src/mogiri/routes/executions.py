from flask import Blueprint, abort, redirect, render_template, url_for

from mogiri.models import Execution, db
from mogiri.scheduler import cancel_execution

bp = Blueprint("executions", __name__, url_prefix="/executions")


@bp.route("/<execution_id>")
def execution_detail(execution_id):
    execution = db.session.get(Execution, execution_id)
    if not execution:
        abort(404)
    return render_template("executions/detail.html", execution=execution)


@bp.route("/<execution_id>/cancel", methods=["POST"])
def execution_cancel(execution_id):
    execution = db.session.get(Execution, execution_id)
    if not execution:
        abort(404)
    if execution.status == "running":
        cancel_execution(execution_id)
    return redirect(url_for("executions.execution_detail", execution_id=execution_id))
