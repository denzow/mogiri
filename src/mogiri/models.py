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
    command = db.Column(db.String, nullable=False)
    schedule_type = db.Column(db.String, nullable=False)  # "cron" or "once"
    schedule_value = db.Column(db.String, nullable=False)
    env_vars = db.Column(db.Text, default="{}")  # JSON string
    is_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    executions = db.relationship(
        "Execution", backref="job", lazy="dynamic", cascade="all, delete-orphan"
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
