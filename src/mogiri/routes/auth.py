from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        expected = current_app.config.get("AUTH_PASSWORD", "")
        if password == expected:
            session["authenticated"] = True
            next_url = request.args.get("next", url_for("dashboard.index"))
            return redirect(next_url)
        return render_template("login.html", error="Password is incorrect.")
    return render_template("login.html", error=None)


@bp.route("/logout", methods=["POST"])
def logout():
    session.pop("authenticated", None)
    return redirect(url_for("auth.login"))
