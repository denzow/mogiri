<p align="center">
  <img src="docs/images/logo.png" alt="mogiri" width="160">
</p>

<h1 align="center">mogiri</h1>

<p align="center">
  <em>Simple local job manager with Web UI</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/UI-htmx%20%2B%20Pico-orange" alt="UI">
</p>

<p align="center">
  <a href="README.md">日本語</a> | English
</p>

---

A simple job manager that runs locally. Create jobs, schedule them with cron, and view execution logs — all from a Web UI.

## Screenshots

<table>
  <tr>
    <td align="center"><strong>Dashboard</strong></td>
    <td align="center"><strong>Job Detail</strong></td>
  </tr>
  <tr>
    <td><img src="docs/images/dashboard.png" width="400"></td>
    <td><img src="docs/images/job-detail.png" width="400"></td>
  </tr>
  <tr>
    <td align="center"><strong>Job Form (with cron editor)</strong></td>
    <td align="center"><strong>Execution Log</strong></td>
  </tr>
  <tr>
    <td><img src="docs/images/job-form.png" width="400"></td>
    <td><img src="docs/images/execution.png" width="400"></td>
  </tr>
</table>

## Features

| Feature | Description |
|---------|-------------|
| **Cron / One-time / Manual** | Schedule jobs with cron expressions, one-time datetime, or run manually |
| **Shell & Python** | Execute shell commands or Python scripts |
| **Workflows** | Chain multiple jobs as a DAG with success/failure conditional branching |
| **AI Assistant** | Generate scripts with Claude / Gemini CLI from the job creation form |
| **Environment Variables** | Global, per-job, and per-workflow-node env vars. Chain jobs auto-inject parent job results |
| **Execution Logs** | Save stdout/stderr and browse from Web UI. Auto-rotation supported |
| **Job Timeout** | Per-job configurable timeout to prevent runaway processes |
| **REST API** | JSON API for jobs, workflows, executions, and settings |
| **CLI Client** | `mogiricli` command for terminal / Claude Code integration |
| **Security** | CSRF protection, API token auth, optional password login |
| **Sample Scripts** | Slack notifications, DB backup, health checks, and more |

## Quick Start

```bash
# Install
pip install -e .

# Generate config file (optional)
mogiri init

# Start server
mogiri serve
```

Open **http://127.0.0.1:8899** in your browser.

```bash
# Options
mogiri serve --host 0.0.0.0 --port 9000 --debug
mogiri serve --config /path/to/config.yaml
```

> **Warning**: `--host 0.0.0.0` binds to all network interfaces. Since mogiri can execute arbitrary shell commands, do not use this on untrusted networks. A password must be configured. See [SECURITY.md](SECURITY.md).

---

## CLI Client (`mogiricli`)

A CLI tool that wraps the mogiri REST API. Manage jobs and workflows from the terminal or Claude Code.

```bash
# Set server URL (default: http://127.0.0.1:8899)
export MOGIRI_URL=http://127.0.0.1:8899
```

### Jobs

```bash
mogiricli jobs list                          # List all
mogiricli jobs get <id>                      # Details
mogiricli jobs create --name "Backup" \
  --command "pg_dump mydb" \
  --command-type shell                       # Create
mogiricli jobs update <id> --name "New Name" # Update
mogiricli jobs delete <id> --yes             # Delete
mogiricli jobs run <id>                      # Run now
```

### Workflows

```bash
mogiricli workflows list                     # List all
mogiricli workflows create --name "My Flow"  # Create
mogiricli workflows run <id>                 # Run
mogiricli workflows delete <id> --yes        # Delete
```

### Executions

```bash
mogiricli executions list --limit 10         # Recent executions
mogiricli executions list --job-id <id>      # Filter by job
mogiricli executions get <execution-id>      # Details (stdout/stderr)
```

### Settings

```bash
mogiricli settings get ai_provider           # Get
mogiricli settings set ai_provider gemini    # Set
```

### JSON Output

Use the `--json` flag for JSON output. Useful for scripting and Claude Code integration.

```bash
mogiricli --json jobs list
mogiricli --json executions get <id>
```

---

## REST API

The JSON API used internally by `mogiricli`. Can also be accessed directly with curl.

API token authentication is required. The token is auto-generated at `~/.mogiri/api_token` and `mogiricli` reads it automatically.

<details>
<summary>API Endpoints</summary>

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/jobs` | List jobs |
| `GET` | `/api/jobs/<id>` | Get job |
| `POST` | `/api/jobs` | Create job |
| `PATCH` | `/api/jobs/<id>` | Update job |
| `DELETE` | `/api/jobs/<id>` | Delete job |
| `POST` | `/api/jobs/<id>/run` | Run job |
| `GET` | `/api/workflows` | List workflows |
| `GET` | `/api/workflows/<id>` | Get workflow |
| `POST` | `/api/workflows` | Create workflow |
| `PATCH` | `/api/workflows/<id>` | Update workflow |
| `DELETE` | `/api/workflows/<id>` | Delete workflow |
| `POST` | `/api/workflows/<id>/run` | Run workflow |
| `GET` | `/api/executions` | List executions (`?job_id=`, `?workflow_id=`, `?limit=`) |
| `GET` | `/api/executions/<id>` | Get execution (stdout/stderr) |
| `GET` | `/api/settings/<key>` | Get setting |
| `PUT` | `/api/settings/<key>` | Set setting |

</details>

<details>
<summary>curl examples</summary>

```bash
# Create job (include API token)
TOKEN=$(cat ~/.mogiri/api_token)

curl -s -X POST http://127.0.0.1:8899/api/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name": "Hello", "command": "echo hello", "schedule_type": "none"}'

# Run job
curl -s -X POST http://127.0.0.1:8899/api/jobs/<id>/run \
  -H "Authorization: Bearer $TOKEN"

# Get execution result
curl -s http://127.0.0.1:8899/api/executions?job_id=<id>&limit=1 \
  -H "Authorization: Bearer $TOKEN"
```

</details>

---

## Sample Scripts

The `samples/` directory contains ready-to-use scripts for common tasks. The AI Chat feature also references these samples when generating scripts.

| Script | Description |
|--------|-------------|
| [`slack_thread_post.py`](samples/slack_thread_post.py) | Post to Slack threads |
| [`pushover_notify.py`](samples/pushover_notify.py) | Pushover push notifications |
| [`db_backup.py`](samples/db_backup.py) | PostgreSQL / MySQL backup |
| [`http_health_check.py`](samples/http_health_check.py) | HTTP health check |
| [`disk_usage_alert.sh`](samples/disk_usage_alert.sh) | Disk usage monitoring |
| [`ai_summarize.sh`](samples/ai_summarize.sh) | Summarize previous job output with Claude CLI |
| [`ai_log_analyzer.py`](samples/ai_log_analyzer.py) | Analyze log files with Claude CLI |
| [`claude_usage_check.py`](samples/claude_usage_check.py) | Check Claude Code usage / rate limits |

See [samples/README.md](samples/README.md) for details.

---

## Job Environment Variables

Environment variables automatically set by mogiri when executing jobs.

### Environment Variable Priority

When the same key is defined at multiple levels, later levels override earlier ones (highest priority last):

1. OS environment (`os.environ`)
2. Global env vars (Settings page)
3. Per-job env vars (Job edit form)
4. Per-workflow-node env vars (Workflow editor)

### All Jobs

| Variable | Description |
|---|---|
| `MOGIRI_OUTPUT` | Path to output file. Content written here is passed to the next workflow job as `MOGIRI_PARENT_OUTPUT` |

### Workflow Chain Jobs (only when triggered by a parent job)

| Variable | Description |
|---|---|
| `MOGIRI_PARENT_OUTPUT` | Content written to `MOGIRI_OUTPUT` by the parent job |
| `MOGIRI_PARENT_JOB_NAME` | Parent job name |
| `MOGIRI_PARENT_STATUS` | Parent job status (`success` / `failed` / `timeout`) |
| `MOGIRI_PARENT_EXIT_CODE` | Parent job exit code |
| `MOGIRI_PARENT_STDOUT` | Parent job stdout (last 4000 chars) |
| `MOGIRI_PARENT_STDERR` | Parent job stderr (last 4000 chars) |
| `MOGIRI_PARENT_EXECUTION_ID` | Parent job Execution ID |

### Workflow Data Passing Example

```bash
# Job A (parent)
echo "backup completed: /tmp/backup_20240418.sql" >> $MOGIRI_OUTPUT

# Job B (child) — uses parent output
echo "Parent output: $MOGIRI_PARENT_OUTPUT"
```

```python
# Job A (parent, Python)
import os
with open(os.environ["MOGIRI_OUTPUT"], "a") as f:
    f.write("processed 1234 records\n")

# Job B (child, Python)
import os
parent_output = os.environ.get("MOGIRI_PARENT_OUTPUT", "")
print(f"Parent said: {parent_output}")
```

---

## Configuration

Run `mogiri init` to generate a sample `~/.mogiri/config.yaml`.

```yaml
server:
  host: "127.0.0.1"
  port: 8899

log:
  retention_days: 30    # 0 = keep forever
  max_per_job: 100      # 0 = unlimited

auth:
  enabled: true         # API token auth (false to disable)
  password: ""          # Web UI password (required for --host 0.0.0.0)
```

| Environment Variable | Description |
|---|---|
| `MOGIRI_DATA_DIR` | Data directory (default: `~/.mogiri`) |
| `MOGIRI_LOG_RETENTION_DAYS` | Log retention days |
| `MOGIRI_LOG_MAX_PER_JOB` | Max executions per job |
| `MOGIRI_PASSWORD` | Web UI password (overrides config.yaml) |
| `MOGIRI_SECRET_KEY` | Flask session signing key |

Priority: defaults < YAML < environment variables < CLI flags

### Cron Expression Examples

| Expression | Meaning |
|---|---|
| `* * * * *` | Every minute |
| `*/5 * * * *` | Every 5 minutes |
| `0 * * * *` | Every hour at :00 |
| `0 0 * * *` | Every day at midnight |
| `0 0 * * 0` | Every Sunday at midnight |
| `0 0 1 * *` | First day of every month at midnight |

---

## Autostart (systemd)

To auto-start mogiri on boot (Linux/Ubuntu), use a systemd user service.

### 1. Copy the sample unit file

```bash
mkdir -p ~/.config/systemd/user
cp docs/mogiri.service ~/.config/systemd/user/mogiri.service
```

### 2. Verify the ExecStart path

Set the full path to the `mogiri` command in the unit file.

```bash
# pyenv
pyenv which mogiri
# Example: /home/youruser/.pyenv/versions/mogiri/bin/mogiri

# pip install
which mogiri
```

Edit the unit file if the path differs.

> **Note**: systemd does not load shell profiles (`~/.bashrc`, etc.). If your jobs use commands like `claude` or `node`, add `Environment=PATH=...` to the unit file. Check your current PATH with `echo $PATH`.
>
> ```ini
> Environment=PATH=/home/youruser/.nvm/versions/node/v22.20.0/bin:/home/youruser/.pyenv/versions/mogiri/bin:/usr/local/bin:/usr/bin:/bin
> ```

### 3. Enable and start

```bash
systemctl --user daemon-reload
systemctl --user start mogiri
systemctl --user status mogiri
systemctl --user enable mogiri
```

### 4. Start without login

By default, user services only run while logged in. Enable **linger** to start at boot:

```bash
sudo loginctl enable-linger $(whoami)
```

> **Warning**: If using `--host 0.0.0.0` in the service, the server is exposed to all network interfaces. Configure firewall or VPN accordingly. See [SECURITY.md](SECURITY.md).

### Logs

```bash
journalctl --user -u mogiri -f
journalctl --user -u mogiri --since "1 hour ago"
```

### Stop / Disable

```bash
systemctl --user stop mogiri
systemctl --user disable mogiri
```

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check src/ tests/
```

### DB Migrations

```bash
# Generate migration after model changes
FLASK_APP=mogiri.app flask db migrate -m "add new column"

# Apply migrations
FLASK_APP=mogiri.app flask db upgrade
```

Pending migrations are auto-applied when `mogiri serve` starts.

---

## Data

All data is stored in `~/.mogiri/`:

- `mogiri.db` -- SQLite database (job definitions, execution history)
- `config.yaml` -- Configuration file
- `api_token` -- API authentication token (auto-generated)

## License

MIT
