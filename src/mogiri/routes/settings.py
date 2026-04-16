import json

from flask import Blueprint, flash, redirect, render_template, request, url_for

from mogiri.models import Setting, db

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.route("/")
def index():
    raw = Setting.get("global_env_vars", "{}")
    try:
        env_vars = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        env_vars = {}
    ai_provider = Setting.get("ai_provider", "claude")
    return render_template("settings/index.html", env_vars=env_vars, ai_provider=ai_provider)


@bp.route("/", methods=["POST"])
def update():
    keys = request.form.getlist("env_key")
    values = request.form.getlist("env_value")
    env_vars = {}
    for k, v in zip(keys, values):
        k = k.strip()
        if k:
            env_vars[k] = v
    Setting.set("global_env_vars", json.dumps(env_vars))

    ai_provider = request.form.get("ai_provider", "claude")
    if ai_provider in ("claude", "gemini"):
        Setting.set("ai_provider", ai_provider)

    flash("Settings saved.", "success")
    return redirect(url_for("settings.index"))
