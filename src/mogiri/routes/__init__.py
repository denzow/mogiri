from flask import redirect, request, session, url_for

from mogiri.routes.api import bp as api_bp
from mogiri.routes.auth import bp as auth_bp
from mogiri.routes.chains import bp as chains_bp
from mogiri.routes.dashboard import bp as dashboard_bp
from mogiri.routes.executions import bp as executions_bp
from mogiri.routes.jobs import bp as jobs_bp
from mogiri.routes.settings import bp as settings_bp


def register_routes(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(executions_bp)
    app.register_blueprint(chains_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(api_bp)

    @app.before_request
    def require_password():
        """Redirect to login page if password is configured."""
        password = app.config.get("AUTH_PASSWORD")
        if not password:
            return

        # Skip for API (protected by Bearer token), login, static
        if request.endpoint and (
            request.endpoint.startswith("api.")
            or request.endpoint in ("auth.login", "auth.logout", "static")
        ):
            return

        if not session.get("authenticated"):
            return redirect(
                url_for("auth.login", next=request.url)
            )
