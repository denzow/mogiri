from flask import Blueprint, abort, render_template

from mogiri.models import Execution, db

bp = Blueprint("executions", __name__, url_prefix="/executions")


@bp.route("/<execution_id>")
def execution_detail(execution_id):
    execution = db.session.get(Execution, execution_id)
    if not execution:
        abort(404)
    return render_template("executions/detail.html", execution=execution)
