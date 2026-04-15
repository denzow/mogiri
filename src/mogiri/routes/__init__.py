from mogiri.routes.chains import bp as chains_bp
from mogiri.routes.dashboard import bp as dashboard_bp
from mogiri.routes.executions import bp as executions_bp
from mogiri.routes.jobs import bp as jobs_bp
from mogiri.routes.settings import bp as settings_bp


def register_routes(app):
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(executions_bp)
    app.register_blueprint(chains_bp)
    app.register_blueprint(settings_bp)
