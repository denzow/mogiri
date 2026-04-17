"""Claude Code usage/rate limit checker for mogiri jobs.

Combines Claude CLI rate_limit_event with ccusage token/cost data
to estimate remaining quota in the current 5-hour window.

Required:
  - claude CLI must be installed and authenticated
  - npx (Node.js) for ccusage

Optional environment variables:
  CLAUDE_MODEL          - Model to check (default: uses CLI default)
  CLAUDE_5H_LIMIT_USD   - Estimated 5-hour cost limit in USD (default: 148)
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone


def get_rate_limits():
    """Call claude CLI and extract rate_limit_event."""
    cmd = [
        "claude", "-p", "say OK",
        "--output-format", "stream-json", "--verbose",
    ]
    model = os.environ.get("CLAUDE_MODEL")
    if model:
        cmd.extend(["--model", model])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    output = result.stdout

    rate_limits = []
    for line in output.strip().split("\n"):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("type") == "rate_limit_event":
            rate_limits.append(data.get("rate_limit_info", {}))

    return rate_limits


def get_ccusage_block():
    """Call ccusage blocks and return the active block."""
    try:
        result = subprocess.run(
            ["npx", "ccusage@latest", "blocks", "--json"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        for block in data.get("blocks", []):
            if block.get("isActive"):
                return block
    except Exception:
        pass
    return None


def main():
    limit_usd = float(os.environ.get("CLAUDE_5H_LIMIT_USD", "148"))

    now = datetime.now(timezone.utc)
    print(f"Claude Code Usage Report ({now.astimezone().strftime('%Y-%m-%d %H:%M %Z')})")
    print("=" * 60)

    # --- Rate limit status from CLI ---
    rate_limits = get_rate_limits()
    if rate_limits:
        for rl in rate_limits:
            limit_type = rl.get("rateLimitType", "unknown")
            status = rl.get("status", "unknown")
            resets_at = rl.get("resetsAt")

            type_label = {
                "five_hour": "5-Hour Window",
                "four_hour": "4-Hour Window",
                "weekly": "Weekly",
                "daily": "Daily",
            }.get(limit_type, limit_type)

            if resets_at:
                reset_dt = datetime.fromtimestamp(resets_at, tz=timezone.utc)
                reset_local = reset_dt.astimezone()
                remaining = reset_dt - now
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                if remaining.total_seconds() > 0:
                    reset_str = f"{reset_local.strftime('%H:%M %Z')} ({hours}h {minutes}m)"
                else:
                    reset_str = "already reset"
            else:
                reset_str = "unknown"

            status_label = "OK" if status == "allowed" else "LIMIT REACHED"
            print(f"\n{type_label}:")
            print(f"  Status: {status_label}")
            print(f"  Resets: {reset_str}")
    else:
        print("\n  Rate limit info: unavailable")

    # --- Token/cost usage from ccusage ---
    block = get_ccusage_block()
    if block:
        cost = block.get("costUSD", 0)
        total_tokens = block.get("totalTokens", 0)
        token_counts = block.get("tokenCounts", {})
        burn_rate = block.get("burnRate", {})
        projection = block.get("projection", {})
        models = block.get("models", [])

        used_pct = (cost / limit_usd) * 100 if limit_usd > 0 else 0
        remaining_usd = max(0, limit_usd - cost)
        remaining_pct = max(0, 100 - used_pct)

        print(f"\nCurrent Window Usage (estimated limit: ${limit_usd:.0f}):")
        print(f"  Cost:      ${cost:.2f} / ${limit_usd:.0f} ({used_pct:.1f}% used)")
        print(f"  Remaining: ${remaining_usd:.2f} ({remaining_pct:.1f}%)")
        print(f"  Tokens:    {total_tokens:,}")

        input_t = token_counts.get("inputTokens", 0)
        output_t = token_counts.get("outputTokens", 0)
        cache_create = token_counts.get("cacheCreationInputTokens", 0)
        cache_read = token_counts.get("cacheReadInputTokens", 0)
        print(f"    Input: {input_t:,}  Output: {output_t:,}")
        print(f"    Cache create: {cache_create:,}  Cache read: {cache_read:,}")

        if models:
            print(f"  Models:    {', '.join(models)}")

        if burn_rate and burn_rate.get("costPerHour"):
            cph = burn_rate["costPerHour"]
            hours_left = remaining_usd / cph if cph > 0 else float("inf")
            print(f"\n  Burn Rate: ${cph:.2f}/hour")
            if hours_left < 100:
                print(f"  At this rate, budget lasts: {hours_left:.1f} hours")

        if projection and projection.get("totalCost"):
            proj_cost = projection["totalCost"]
            proj_pct = (proj_cost / limit_usd) * 100 if limit_usd > 0 else 0
            print(f"  Projected window total: ${proj_cost:.2f} ({proj_pct:.0f}%)")
    else:
        print("\n  ccusage data: unavailable (npx ccusage not found?)")

    print()

    # Exit with error if any limit is reached
    if rate_limits and any(rl.get("status") != "allowed" for rl in rate_limits):
        print("WARNING: One or more rate limits reached!")
        sys.exit(1)


if __name__ == "__main__":
    main()
