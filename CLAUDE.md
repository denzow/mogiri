# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**mogiri** is a local job manager with Web UI. Users can create scheduled jobs (cron, one-time, or manual), execute shell/Python commands with custom environment variables, build multi-job workflows with conditional chaining, and view execution logs.

## Tech Stack

- **Python 3.12** (pyenv virtualenv `mogiri`)
- **Flask** — Web framework with Jinja2 templates
- **Flask-Migrate (Alembic)** — Database schema migrations
- **APScheduler 3.x** — Background job scheduling (cron/one-time triggers)
- **SQLite + Flask-SQLAlchemy** — Database (stored at `~/.mogiri/mogiri.db`)
- **htmx + Pico CSS** — Frontend interactivity without JS build step
- **PyYAML** — YAML configuration file support

## Commands

```bash
# Install dependencies (editable mode)
pip install -e ".[dev]"

# Start server (default: http://127.0.0.1:8899)
mogiri serve
mogiri serve --port 9000 --debug
mogiri serve --config /path/to/config.yaml

# Generate sample config
mogiri init

# Run tests
pytest tests/ -v

# Run a single test
pytest tests/test_scheduler.py::test_execute_job_success -v

# Lint
ruff check src/ tests/

# Database migrations (via flask CLI)
FLASK_APP=mogiri.app flask db migrate -m "description"
FLASK_APP=mogiri.app flask db upgrade
```

## Architecture

Single-process: Flask web server + APScheduler BackgroundScheduler in the same process. Migrations are auto-applied on startup (`upgrade()` in `create_app`).

```
src/mogiri/
  __init__.py        # App factory (create_app) — wires DB, migrations, routes, scheduler
  app.py             # Minimal Flask app for `flask` CLI (migrations, no scheduler)
  config.py          # Config: YAML loading, DB path (~/.mogiri/), defaults
  models.py          # SQLAlchemy models: Job, Execution, Workflow, WorkflowEdge,
                     #   WorkflowNodePosition, Setting
  scheduler.py       # APScheduler init, sync_all, execute_job, execute_workflow,
                     #   chain triggering, log rotation
  cli.py             # Click CLI entry point (mogiri serve, mogiri init)
  mogiricli.py       # CLI client (mogiricli) — wraps REST API for terminal/Claude Code use
  routes/
    __init__.py      # register_routes — wires all blueprints
    api.py           # REST API: /api/jobs, /api/workflows, /api/executions, /api/settings
    dashboard.py     # GET / — overview with recent executions
    jobs.py          # Job CRUD, toggle, run-now, cron preview, AI chat
    executions.py    # GET /executions/<id> — log viewer
    chains.py        # Workflow CRUD, visual editor, run, history
    settings.py      # Global settings (environment variables, AI provider)
  templates/         # Jinja2 templates (base.html, jobs/, executions/, chains/, settings/, partials/)
  static/style.css   # Status colors, log output styling
migrations/          # Alembic migrations directory
```

## Configuration

YAML config at `~/.mogiri/config.yaml` (generate with `mogiri init`):

```yaml
server:
  host: "127.0.0.1"
  port: 8899
log:
  retention_days: 30    # 0 = keep forever
  max_per_job: 100      # 0 = unlimited
```

Priority: env vars > YAML > defaults. CLI flags (`--host`, `--port`) override YAML.

## Key Design Decisions

- **Scheduler is disabled in tests** (`TESTING=True` skips `init_scheduler`). Test fixtures set `scheduler._app` manually for `execute_job` tests.
- **`use_reloader=False`** in `mogiri serve` — Flask's reloader would spawn a second APScheduler.
- **Two command types**: `shell` (runs via `shell=True` in subprocess.run) and `python` (writes to temp file, runs with `sys.executable`).
- **Environment variables**: Global env vars in `Setting` table, per-job env vars in `jobs.env_vars` (JSON). At execution: `os.environ` + global + job-specific (later overrides earlier).
- **Data directory** defaults to `~/.mogiri/`, overridable via `MOGIRI_DATA_DIR` env var.
- **Workflows** define DAGs of jobs with edges (success/failure/any conditions). Entry jobs are stored in `Workflow.entry_job_ids`. Cycle detection prevents invalid graphs.
- **Chain execution** runs in threads; `_chain_visited` set prevents runtime cycles.
- **Log rotation** runs daily at 03:00 via APScheduler (configurable retention).
- **Migrations auto-applied** on startup; tests use `db.create_all()` instead.

## Data Model

- **Job**: name, description, command_type (shell/python), command, schedule_type (cron/once/none), schedule_value, env_vars (JSON), is_enabled
- **Execution**: job_id (FK), status (running/success/failed/timeout), exit_code, stdout, stderr, started_at, finished_at, workflow_id (FK), triggered_by_execution_id (FK), triggered_by_chain_id (FK)
- **Workflow**: name, description, is_enabled, schedule_type, schedule_value, entry_job_ids (JSON), start_node_x/y
- **WorkflowEdge**: workflow_id (FK), source_job_id (FK), target_job_id (FK), trigger_condition (success/failure/any)
- **WorkflowNodePosition**: workflow_id (FK), job_id (FK), node_key, x, y
- **Setting**: key-value store (used for global_env_vars, ai_provider)

## REST API

Base URL: `http://127.0.0.1:8899/api`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/jobs` | List all jobs |
| GET | `/api/jobs/<id>` | Get job details |
| POST | `/api/jobs` | Create job (requires `name`, `command`) |
| PATCH | `/api/jobs/<id>` | Partial update job |
| DELETE | `/api/jobs/<id>` | Delete job |
| POST | `/api/jobs/<id>/run` | Trigger job execution (202) |
| GET | `/api/workflows` | List all workflows |
| GET | `/api/workflows/<id>` | Get workflow details (includes edges) |
| POST | `/api/workflows` | Create workflow (requires `name`) |
| PATCH | `/api/workflows/<id>` | Update workflow |
| DELETE | `/api/workflows/<id>` | Delete workflow |
| POST | `/api/workflows/<id>/run` | Trigger workflow execution (202) |
| GET | `/api/executions` | List executions (`?job_id=`, `?workflow_id=`, `?limit=`) |
| GET | `/api/executions/<id>` | Get execution with stdout/stderr |
| GET | `/api/settings/<key>` | Get setting value |
| PUT | `/api/settings/<key>` | Set setting value (`{"value": "..."}`) |

## mogiricli

CLI client for mogiri. Requires the server to be running.

```bash
# Configure server URL (default: http://127.0.0.1:8899)
export MOGIRI_URL=http://127.0.0.1:8899

# Jobs
mogiricli jobs list
mogiricli jobs get <id>
mogiricli jobs create --name "Job" --command "echo hi"
mogiricli jobs update <id> --name "New Name"
mogiricli jobs delete <id> --yes
mogiricli jobs run <id>

# Workflows
mogiricli workflows list
mogiricli workflows create --name "WF"
mogiricli workflows run <id>

# Executions
mogiricli executions list --job-id <id> --limit 10
mogiricli executions get <id>

# Settings
mogiricli settings get ai_provider
mogiricli settings set ai_provider gemini

# JSON output (for scripting / Claude Code)
mogiricli --json jobs list
```
