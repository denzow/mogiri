from flask import Blueprint, render_template

from mogiri.models import Execution, Job, Workflow

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    total_jobs = Job.query.count()
    scheduled_jobs = Job.query.filter(
        Job.schedule_type != "none",
        Job.is_enabled.is_(True),
    ).count()
    total_workflows = Workflow.query.count()
    scheduled_workflows = Workflow.query.filter(
        Workflow.schedule_type != "none",
        Workflow.is_enabled.is_(True),
    ).count()
    recent_executions = (
        Execution.query.order_by(Execution.started_at.desc()).limit(10).all()
    )
    return render_template(
        "dashboard.html",
        total_jobs=total_jobs,
        scheduled_jobs=scheduled_jobs,
        total_workflows=total_workflows,
        scheduled_workflows=scheduled_workflows,
        recent_executions=recent_executions,
    )
