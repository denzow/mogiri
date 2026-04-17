"""mogiricli - CLI client for mogiri job manager.

Wraps the mogiri REST API for use from the terminal or Claude Code.
"""

import json
import os
import sys
import urllib.error
import urllib.request

import click


class MogiriClient:
    def __init__(self, base_url=None):
        self.base_url = (
            base_url or os.environ.get("MOGIRI_URL", "http://127.0.0.1:8899")
        ).rstrip("/")

    def _request(self, method, path, data=None):
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            try:
                msg = json.loads(error_body).get("error", error_body)
            except (json.JSONDecodeError, AttributeError):
                msg = error_body
            raise click.ClickException(f"Server error ({e.code}): {msg}")
        except urllib.error.URLError:
            raise click.ClickException(
                f"Cannot connect to mogiri at {self.base_url}. Is the server running?"
            )

    def get(self, path):
        return self._request("GET", path)

    def post(self, path, data=None):
        return self._request("POST", path, data)

    def patch(self, path, data):
        return self._request("PATCH", path, data)

    def put(self, path, data):
        return self._request("PUT", path, data)

    def delete(self, path):
        return self._request("DELETE", path)


def _output(ctx, data):
    """Output data as JSON or human-readable text."""
    if ctx.obj.get("json"):
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        if isinstance(data, dict):
            click.echo(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            click.echo(data)


def _table(rows, headers):
    """Print a simple aligned table."""
    if not rows:
        click.echo("(none)")
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    click.echo(fmt.format(*headers))
    click.echo(fmt.format(*["-" * w for w in widths]))
    for row in rows:
        click.echo(fmt.format(*[str(v) for v in row]))


def _short_id(uid):
    return uid[:8] if uid else ""


# ---------- Top-level group ----------

@click.group()
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.option("--url", envvar="MOGIRI_URL", default="http://127.0.0.1:8899",
              help="mogiri server URL")
@click.pass_context
def cli(ctx, use_json, url):
    """mogiricli - CLI client for mogiri job manager."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json
    ctx.obj["client"] = MogiriClient(url)


# ---------- Jobs ----------

@cli.group()
def jobs():
    """Manage jobs."""
    pass


@jobs.command("list")
@click.pass_context
def jobs_list(ctx):
    """List all jobs."""
    client = ctx.obj["client"]
    data = client.get("/api/jobs")
    if ctx.obj["json"]:
        _output(ctx, data)
        return
    rows = []
    for j in data:
        rows.append([
            _short_id(j["id"]),
            j["name"],
            j["command_type"],
            j["schedule_type"],
            "Yes" if j["is_enabled"] else "No",
        ])
    _table(rows, ["ID", "NAME", "TYPE", "SCHEDULE", "ENABLED"])


@jobs.command("get")
@click.argument("job_id")
@click.pass_context
def jobs_get(ctx, job_id):
    """Get job details."""
    client = ctx.obj["client"]
    j = client.get(f"/api/jobs/{job_id}")
    if ctx.obj["json"]:
        _output(ctx, j)
        return
    click.echo(f"Job: {j['name']}")
    click.echo(f"  ID:           {j['id']}")
    click.echo(f"  Command Type: {j['command_type']}")
    click.echo(f"  Schedule:     {j['schedule_type']} ({j['schedule_value'] or 'N/A'})")
    if j.get("working_dir"):
        click.echo(f"  Working Dir:  {j['working_dir']}")
    click.echo(f"  Enabled:      {'Yes' if j['is_enabled'] else 'No'}")
    if j.get("env_vars"):
        click.echo(f"  Env Vars:     {json.dumps(j['env_vars'])}")
    click.echo(f"  Created:      {j['created_at']}")
    click.echo(f"\n--- command ---")
    click.echo(j["command"])


@jobs.command("create")
@click.option("--name", required=True)
@click.option("--command", "cmd", required=True)
@click.option("--command-type", type=click.Choice(["shell", "python"]), default="shell")
@click.option("--schedule-type", type=click.Choice(["cron", "once", "none"]), default="none")
@click.option("--schedule-value", default="")
@click.option("--working-dir", default="")
@click.option("--description", default="")
@click.option("--env-vars", default=None, help="JSON object string")
@click.pass_context
def jobs_create(ctx, name, cmd, command_type, schedule_type, schedule_value,
                working_dir, description, env_vars):
    """Create a new job."""
    client = ctx.obj["client"]
    data = {
        "name": name,
        "command": cmd,
        "command_type": command_type,
        "schedule_type": schedule_type,
        "schedule_value": schedule_value,
        "working_dir": working_dir,
        "description": description,
    }
    if env_vars:
        data["env_vars"] = json.loads(env_vars)
    j = client.post("/api/jobs", data)
    if ctx.obj["json"]:
        _output(ctx, j)
    else:
        click.echo(f"Created job: {j['name']} ({j['id']})")


@jobs.command("update")
@click.argument("job_id")
@click.option("--name", default=None)
@click.option("--command", "cmd", default=None)
@click.option("--command-type", type=click.Choice(["shell", "python"]), default=None)
@click.option("--schedule-type", type=click.Choice(["cron", "once", "none"]), default=None)
@click.option("--schedule-value", default=None)
@click.option("--working-dir", default=None)
@click.option("--description", default=None)
@click.option("--enabled/--disabled", default=None)
@click.pass_context
def jobs_update(ctx, job_id, name, cmd, command_type, schedule_type,
                schedule_value, working_dir, description, enabled):
    """Update a job."""
    client = ctx.obj["client"]
    data = {}
    if name is not None:
        data["name"] = name
    if cmd is not None:
        data["command"] = cmd
    if command_type is not None:
        data["command_type"] = command_type
    if schedule_type is not None:
        data["schedule_type"] = schedule_type
    if schedule_value is not None:
        data["schedule_value"] = schedule_value
    if working_dir is not None:
        data["working_dir"] = working_dir
    if description is not None:
        data["description"] = description
    if enabled is not None:
        data["is_enabled"] = enabled
    if not data:
        raise click.ClickException("No fields to update")
    j = client.patch(f"/api/jobs/{job_id}", data)
    if ctx.obj["json"]:
        _output(ctx, j)
    else:
        click.echo(f"Updated job: {j['name']} ({j['id']})")


@jobs.command("delete")
@click.argument("job_id")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def jobs_delete(ctx, job_id, yes):
    """Delete a job."""
    client = ctx.obj["client"]
    if not yes:
        click.confirm(f"Delete job {job_id}?", abort=True)
    result = client.delete(f"/api/jobs/{job_id}")
    if ctx.obj["json"]:
        _output(ctx, result)
    else:
        click.echo(result["message"])


@jobs.command("run")
@click.argument("job_id")
@click.pass_context
def jobs_run(ctx, job_id):
    """Trigger a job run."""
    client = ctx.obj["client"]
    result = client.post(f"/api/jobs/{job_id}/run")
    if ctx.obj["json"]:
        _output(ctx, result)
    else:
        click.echo(result["message"])


# ---------- Workflows ----------

@cli.group()
def workflows():
    """Manage workflows."""
    pass


@workflows.command("list")
@click.pass_context
def workflows_list(ctx):
    """List all workflows."""
    client = ctx.obj["client"]
    data = client.get("/api/workflows")
    if ctx.obj["json"]:
        _output(ctx, data)
        return
    rows = []
    for wf in data:
        rows.append([
            _short_id(wf["id"]),
            wf["name"],
            wf["schedule_type"],
            len(wf.get("edges", [])),
            "Yes" if wf["is_enabled"] else "No",
        ])
    _table(rows, ["ID", "NAME", "SCHEDULE", "EDGES", "ENABLED"])


@workflows.command("get")
@click.argument("workflow_id")
@click.pass_context
def workflows_get(ctx, workflow_id):
    """Get workflow details."""
    client = ctx.obj["client"]
    wf = client.get(f"/api/workflows/{workflow_id}")
    if ctx.obj["json"]:
        _output(ctx, wf)
        return
    click.echo(f"Workflow: {wf['name']}")
    click.echo(f"  ID:       {wf['id']}")
    click.echo(f"  Schedule: {wf['schedule_type']} ({wf['schedule_value'] or 'N/A'})")
    click.echo(f"  Enabled:  {'Yes' if wf['is_enabled'] else 'No'}")
    if wf.get("description"):
        click.echo(f"  Desc:     {wf['description']}")
    if wf.get("edges"):
        click.echo(f"\n  Edges ({len(wf['edges'])}):")
        for e in wf["edges"]:
            click.echo(f"    {_short_id(e['source_job_id'])} --{e['trigger_condition']}--> {_short_id(e['target_job_id'])}")


@workflows.command("create")
@click.option("--name", required=True)
@click.option("--description", default="")
@click.option("--schedule-type", type=click.Choice(["cron", "once", "none"]), default="none")
@click.option("--schedule-value", default="")
@click.pass_context
def workflows_create(ctx, name, description, schedule_type, schedule_value):
    """Create a new workflow."""
    client = ctx.obj["client"]
    wf = client.post("/api/workflows", {
        "name": name,
        "description": description,
        "schedule_type": schedule_type,
        "schedule_value": schedule_value,
    })
    if ctx.obj["json"]:
        _output(ctx, wf)
    else:
        click.echo(f"Created workflow: {wf['name']} ({wf['id']})")


@workflows.command("delete")
@click.argument("workflow_id")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def workflows_delete(ctx, workflow_id, yes):
    """Delete a workflow."""
    client = ctx.obj["client"]
    if not yes:
        click.confirm(f"Delete workflow {workflow_id}?", abort=True)
    result = client.delete(f"/api/workflows/{workflow_id}")
    if ctx.obj["json"]:
        _output(ctx, result)
    else:
        click.echo(result["message"])


@workflows.command("run")
@click.argument("workflow_id")
@click.pass_context
def workflows_run(ctx, workflow_id):
    """Trigger a workflow run."""
    client = ctx.obj["client"]
    result = client.post(f"/api/workflows/{workflow_id}/run")
    if ctx.obj["json"]:
        _output(ctx, result)
    else:
        click.echo(result["message"])


# ---------- Executions ----------

@cli.group()
def executions():
    """View execution history."""
    pass


@executions.command("list")
@click.option("--job-id", default=None, help="Filter by job ID")
@click.option("--workflow-id", default=None, help="Filter by workflow ID")
@click.option("--limit", default=20, type=int, help="Max results")
@click.pass_context
def executions_list(ctx, job_id, workflow_id, limit):
    """List executions."""
    client = ctx.obj["client"]
    params = [f"limit={limit}"]
    if job_id:
        params.append(f"job_id={job_id}")
    if workflow_id:
        params.append(f"workflow_id={workflow_id}")
    qs = "&".join(params)
    data = client.get(f"/api/executions?{qs}")
    if ctx.obj["json"]:
        _output(ctx, data)
        return
    rows = []
    for ex in data:
        started = (ex["started_at"] or "")[:19].replace("T", " ")
        duration = ""
        if ex.get("started_at") and ex.get("finished_at"):
            from datetime import datetime
            s = datetime.fromisoformat(ex["started_at"])
            f = datetime.fromisoformat(ex["finished_at"])
            secs = int((f - s).total_seconds())
            duration = f"{secs}s"
        rows.append([
            _short_id(ex["id"]),
            ex["job_name"] or _short_id(ex["job_id"]),
            ex["status"],
            started,
            duration,
        ])
    _table(rows, ["ID", "JOB", "STATUS", "STARTED", "DURATION"])


@executions.command("get")
@click.argument("execution_id")
@click.pass_context
def executions_get(ctx, execution_id):
    """Get execution details with output."""
    client = ctx.obj["client"]
    ex = client.get(f"/api/executions/{execution_id}")
    if ctx.obj["json"]:
        _output(ctx, ex)
        return
    click.echo(f"Execution: {ex['id']}")
    click.echo(f"  Job:       {ex['job_name'] or 'N/A'} ({ex['job_id']})")
    click.echo(f"  Status:    {ex['status']}")
    click.echo(f"  Exit Code: {ex['exit_code']}")
    click.echo(f"  Started:   {ex['started_at']}")
    click.echo(f"  Finished:  {ex['finished_at']}")
    if ex.get("workflow_id"):
        click.echo(f"  Workflow:  {ex['workflow_id']}")
    stdout = ex.get("stdout", "")
    stderr = ex.get("stderr", "")
    click.echo(f"\n--- stdout ---")
    click.echo(stdout if stdout else "(empty)")
    if stderr:
        click.echo(f"\n--- stderr ---")
        click.echo(stderr)


# ---------- Settings ----------

@cli.group()
def settings():
    """Manage settings."""
    pass


@settings.command("get")
@click.argument("key")
@click.pass_context
def settings_get(ctx, key):
    """Get a setting value."""
    client = ctx.obj["client"]
    result = client.get(f"/api/settings/{key}")
    if ctx.obj["json"]:
        _output(ctx, result)
    else:
        click.echo(f"{result['key']}: {result['value']}")


@settings.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def settings_set(ctx, key, value):
    """Set a setting value."""
    client = ctx.obj["client"]
    result = client.put(f"/api/settings/{key}", {"value": value})
    if ctx.obj["json"]:
        _output(ctx, result)
    else:
        click.echo(f"Set {result['key']} = {result['value']}")


if __name__ == "__main__":
    cli()
