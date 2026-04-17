"""Claude Code usage/rate limit checker for mogiri jobs.

Runs a minimal Claude CLI call with stream-json output to extract
rate limit information (4-hour and weekly quotas).

Required:
  claude CLI must be installed and authenticated

Optional environment variables:
  CLAUDE_MODEL  - Model to check (default: uses CLI default)
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone


def main():
    cmd = [
        "claude", "-p", "say OK",
        "--output-format", "stream-json", "--verbose",
    ]
    model = os.environ.get("CLAUDE_MODEL")
    if model:
        cmd.extend(["--model", model])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        # Check if it's a rate limit error
        stderr = result.stderr.strip()
        if stderr:
            print(f"CLI error: {stderr}", file=sys.stderr)
        # Still try to parse output for rate limit info
        output = result.stdout
    else:
        output = result.stdout

    rate_limits = []
    usage_info = None

    for line in output.strip().split("\n"):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        if data.get("type") == "rate_limit_event":
            rate_limits.append(data.get("rate_limit_info", {}))
        elif data.get("type") == "result":
            usage_info = data.get("usage", {})

    if not rate_limits:
        print("No rate limit information found.")
        print("Make sure claude CLI is authenticated and working.")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    print(f"Claude Code Usage Report ({now.strftime('%Y-%m-%d %H:%M:%S UTC')})")
    print("=" * 55)

    for rl in rate_limits:
        limit_type = rl.get("rateLimitType", "unknown")
        status = rl.get("status", "unknown")
        resets_at = rl.get("resetsAt")
        overage_status = rl.get("overageStatus", "")
        is_overage = rl.get("isUsingOverage", False)

        # Format limit type for display
        type_label = {
            "five_hour": "5-Hour Limit",
            "four_hour": "4-Hour Limit",
            "weekly": "Weekly Limit",
            "daily": "Daily Limit",
        }.get(limit_type, limit_type)

        # Format reset time
        if resets_at:
            reset_dt = datetime.fromtimestamp(resets_at, tz=timezone.utc)
            reset_local = reset_dt.astimezone()
            remaining = reset_dt - now
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            if remaining.total_seconds() > 0:
                reset_str = f"resets at {reset_local.strftime('%Y-%m-%d %H:%M %Z')} ({hours}h {minutes}m remaining)"
            else:
                reset_str = "already reset"
        else:
            reset_str = "unknown"

        status_icon = "OK" if status == "allowed" else "LIMIT REACHED"

        print(f"\n{type_label}:")
        print(f"  Status:  {status_icon}")
        print(f"  Reset:   {reset_str}")
        if is_overage:
            print(f"  Overage: active")
        if overage_status and overage_status != "rejected":
            print(f"  Overage policy: {overage_status}")

    if usage_info:
        print(f"\nThis check used:")
        input_tokens = usage_info.get("input_tokens", 0)
        output_tokens = usage_info.get("output_tokens", 0)
        cache_read = usage_info.get("cache_read_input_tokens", 0)
        print(f"  Input: {input_tokens} tokens, Output: {output_tokens} tokens, Cache read: {cache_read} tokens")

    print()

    # Exit with error if any limit is reached
    if any(rl.get("status") != "allowed" for rl in rate_limits):
        print("WARNING: One or more rate limits reached!")
        sys.exit(1)


if __name__ == "__main__":
    main()
