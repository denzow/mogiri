from flask import Blueprint, render_template

from mogiri.models import Execution, Job

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    total_jobs = Job.query.count()
    enabled_jobs = Job.query.filter_by(is_enabled=True).count()
    recent_executions = (
        Execution.query.order_by(Execution.started_at.desc()).limit(10).all()
    )
    return render_template(
        "dashboard.html",
        total_jobs=total_jobs,
        enabled_jobs=enabled_jobs,
        recent_executions=recent_executions,
    )
