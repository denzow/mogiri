# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**mogiri** is a local job manager with Web UI. Users can create scheduled jobs (cron or one-time), execute shell commands with custom environment variables, and view execution logs.

## Tech Stack

- **Python 3.12** (pyenv virtualenv `mogiri`)
- **Flask** — Web framework with Jinja2 templates
- **APScheduler 3.x** — Background job scheduling (cron/one-time triggers)
- **SQLite + Flask-SQLAlchemy** — Database (stored at `~/.mogiri/mogiri.db`)
- **htmx + Pico CSS** — Frontend interactivity without JS build step

## Commands

```bash
# Install dependencies (editable mode)
pip install -e ".[dev]"

# Start server (default: http://127.0.0.1:8899)
mogiri serve
mogiri serve --port 9000 --debug

# Run tests
pytest tests/ -v

# Run a single test
pytest tests/test_scheduler.py::test_execute_job_success -v

# Lint
ruff check src/ tests/
```

## Architecture

Single-process: Flask web server + APScheduler BackgroundScheduler in the same process.

```
src/mogiri/
  __init__.py        # App factory (create_app) — wires DB, routes, scheduler
  config.py          # Config: DB path (~/.mogiri/), secret key
  models.py          # SQLAlchemy models: Job, Execution
  scheduler.py       # APScheduler init, sync_jobs, execute_job (subprocess.run)
  cli.py             # Click CLI entry point (mogiri serve)
  routes/
    dashboard.py     # GET / — overview with recent executions
    jobs.py          # Job CRUD, toggle, run-now, execution list partial
    executions.py    # GET /executions/<id> — log viewer
  templates/         # Jinja2 templates (base.html, jobs/, executions/, partials/)
  static/style.css   # Status colors, log output styling
```

## Key Design Decisions

- **Scheduler is disabled in tests** (`TESTING=True` skips `init_scheduler`). Test fixtures set `scheduler._app` manually for `execute_job` tests.
- **`use_reloader=False`** in `mogiri serve` — Flask's reloader would spawn a second APScheduler.
- **`shell=True`** in subprocess.run — users define shell commands (pipes, redirects).
- **Environment variables** stored as JSON string in `jobs.env_vars`, merged onto `os.environ.copy()` at execution time.
- **Data directory** defaults to `~/.mogiri/`, overridable via `MOGIRI_DATA_DIR` env var.

## Data Model

- **Job**: name, command, schedule_type (cron/once), schedule_value, env_vars (JSON), is_enabled
- **Execution**: job_id (FK), status (running/success/failed/timeout), exit_code, stdout, stderr, started_at, finished_at
