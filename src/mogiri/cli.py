import click


@click.group()
def main():
    """mogiri - simple local job manager"""
    pass


@main.command()
@click.option("--config", "config_path", default=None, type=click.Path(),
              help="Path to config.yaml (default: ~/.mogiri/config.yaml)")
@click.option("--host", default=None, help="Host to bind to")
@click.option("--port", default=None, type=int, help="Port to bind to")
@click.option("--debug", is_flag=True, default=False, help="Enable debug mode")
def serve(config_path, host, port, debug):
    """Start the mogiri web server and scheduler."""
    from mogiri import create_app

    app = create_app(config_path=config_path)

    # CLI flags override YAML config
    run_host = host or app.config.get("SERVER_HOST", "127.0.0.1")
    run_port = port or app.config.get("SERVER_PORT", 8899)

    # Block non-localhost binding without a password
    if run_host not in ("127.0.0.1", "localhost", "::1"):
        if not app.config.get("AUTH_PASSWORD"):
            raise click.ClickException(
                f"Binding to '{run_host}' requires a password. "
                "Set auth.password in config.yaml or "
                "MOGIRI_PASSWORD environment variable."
            )

    app.run(host=run_host, port=run_port, debug=debug, use_reloader=False)


@main.command()
@click.option("--config", "config_path", default=None, type=click.Path(),
              help="Path to write config.yaml (default: ~/.mogiri/config.yaml)")
def init(config_path):
    """Generate a sample config.yaml."""
    from pathlib import Path

    from mogiri.config import DATA_DIR

    if config_path is None:
        dest = DATA_DIR / "config.yaml"
    else:
        dest = Path(config_path)

    if dest.exists():
        if not click.confirm(f"{dest} already exists. Overwrite?"):
            return

    dest.parent.mkdir(parents=True, exist_ok=True)

    sample = """\
# mogiri configuration
# All settings are optional — defaults are shown below.

server:
  host: "127.0.0.1"
  port: 8899

log:
  # Delete executions older than this many days (0 = keep forever)
  retention_days: 30
  # Keep at most this many executions per job (0 = unlimited)
  max_per_job: 100

auth:
  # Set to false to disable API token authentication
  # (not recommended when using --host 0.0.0.0)
  enabled: true
  # Set a password to protect the Web UI (required for --host 0.0.0.0)
  # Can also be set via MOGIRI_PASSWORD environment variable
  password: ""
"""
    dest.write_text(sample)
    click.echo(f"Config written to {dest}")


if __name__ == "__main__":
    main()
