import uuid
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def generate_uuid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now()


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, default="")
    command_type = db.Column(db.String, default="shell")  # "shell" or "python"
    command = db.Column(db.String, nullable=False)
    schedule_type = db.Column(db.String, nullable=False)  # "cron", "once", or "none"
    schedule_value = db.Column(db.String, default="")
    env_vars = db.Column(db.Text, default="{}")  # JSON string
    working_dir = db.Column(db.String, default="")  # Working directory for execution
    is_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    executions = db.relationship(
        "Execution", backref="job", lazy="dynamic", cascade="all, delete-orphan",
        foreign_keys="Execution.job_id",
    )


class Execution(db.Model):
    __tablename__ = "executions"

    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    job_id = db.Column(db.String, db.ForeignKey("jobs.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=now)
    finished_at = db.Column(db.DateTime, nullable=True)
    exit_code = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String, default="running")  # running, success, failed, timeout
    stdout = db.Column(db.Text, default="")
    stderr = db.Column(db.Text, default="")
    node_key = db.Column(db.String, nullable=True)
    workflow_id = db.Column(
        db.String, db.ForeignKey("workflows.id"), nullable=True,
    )
    triggered_by_execution_id = db.Column(
        db.String, db.ForeignKey("executions.id"), nullable=True,
    )
    triggered_by_chain_id = db.Column(
        db.String, db.ForeignKey("workflow_edges.id"), nullable=True,
    )

    parent_execution = db.relationship(
        "Execution", remote_side=[id], foreign_keys=[triggered_by_execution_id],
    )
    workflow = db.relationship("Workflow", foreign_keys=[workflow_id])


class Workflow(db.Model):
    __tablename__ = "workflows"

    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, default="")
    is_enabled = db.Column(db.Boolean, default=True)
    schedule_type = db.Column(db.String, default="none")  # "cron", "once", "none"
    schedule_value = db.Column(db.String, default="")
    entry_job_ids = db.Column(db.Text, default="[]")  # JSON list of job IDs
    entry_node_keys = db.Column(db.Text, default="[]")  # JSON list of {"node_key", "job_id"}
    start_node_x = db.Column(db.Float, default=50)
    start_node_y = db.Column(db.Float, default=250)
    created_at = db.Column(db.DateTime, default=now)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    edges = db.relationship(
        "WorkflowEdge", backref="workflow", cascade="all, delete-orphan",
    )
    node_positions = db.relationship(
        "WorkflowNodePosition", backref="workflow", cascade="all, delete-orphan",
    )


class WorkflowEdge(db.Model):
    __tablename__ = "workflow_edges"

    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workflow_id = db.Column(db.String, db.ForeignKey("workflows.id"), nullable=False)
    source_job_id = db.Column(db.String, db.ForeignKey("jobs.id"), nullable=False)
    target_job_id = db.Column(db.String, db.ForeignKey("jobs.id"), nullable=False)
    source_node_key = db.Column(db.String, nullable=True)
    target_node_key = db.Column(db.String, nullable=True)
    trigger_condition = db.Column(db.String, nullable=False, default="success")
    # "success", "failure", "any"

    source_job = db.relationship("Job", foreign_keys=[source_job_id])
    target_job = db.relationship("Job", foreign_keys=[target_job_id])


class Setting(db.Model):
    __tablename__ = "settings"

    key = db.Column(db.String, primary_key=True)
    value = db.Column(db.Text, default="")

    @staticmethod
    def get(key, default=""):
        row = db.session.get(Setting, key)
        return row.value if row else default

    @staticmethod
    def set(key, value):
        row = db.session.get(Setting, key)
        if row:
            row.value = value
        else:
            row = Setting(key=key, value=value)
            db.session.add(row)
        db.session.commit()


class WorkflowNodePosition(db.Model):
    __tablename__ = "workflow_node_positions"

    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workflow_id = db.Column(db.String, db.ForeignKey("workflows.id"), nullable=False)
    job_id = db.Column(db.String, db.ForeignKey("jobs.id"), nullable=False)
    node_key = db.Column(db.String, nullable=False)  # e.g. "job-uuid:0"
    x = db.Column(db.Float, nullable=False, default=0)
    y = db.Column(db.Float, nullable=False, default=0)
