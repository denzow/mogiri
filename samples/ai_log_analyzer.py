"""AI log analyzer sample for mogiri jobs.

Reads a log file and uses Claude Code CLI (claude -p) to analyze it,
detecting errors, warnings, and anomalies.

Useful as a daily cron job to review application logs.

Required:
  claude CLI must be installed and authenticated

Required environment variables:
  LOG_FILE  - Path to the log file to analyze

Optional environment variables:
  LOG_TAIL      - Number of recent lines to analyze (default: 200)
  AI_PROMPT     - Custom analysis prompt
  AI_SYSTEM     - System prompt for Claude
  LOG_PATTERNS  - Comma-separated patterns to focus on (default: error,warn,fail,exception)
"""

import os
import subprocess
import sys


def main():
    log_file = os.environ.get("LOG_FILE", "")
    log_tail = int(os.environ.get("LOG_TAIL", "200"))
    patterns = os.environ.get("LOG_PATTERNS", "error,warn,fail,exception")
    custom_prompt = os.environ.get("AI_PROMPT", "")
    system_prompt = os.environ.get(
        "AI_SYSTEM",
        "You are a log analysis assistant. Be concise. "
        "List issues by severity. If nothing notable is found, say so briefly.",
    )

    if not log_file:
        print("Error: LOG_FILE is required.", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(log_file):
        print(f"Error: {log_file} not found.", file=sys.stderr)
        sys.exit(1)

    # Read recent lines
    with open(log_file, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    tail_lines = lines[-log_tail:]
    total_lines = len(lines)

    # Filter lines matching patterns for context
    pattern_list = [p.strip().lower() for p in patterns.split(",") if p.strip()]
    matched = [
        line for line in tail_lines
        if any(p in line.lower() for p in pattern_list)
    ]

    # Build prompt
    if custom_prompt:
        prompt = custom_prompt + "\n\n"
    else:
        prompt = (
            f"Analyze the following log excerpt from '{log_file}' "
            f"(last {len(tail_lines)} of {total_lines} total lines).\n"
            f"Focus on: {patterns}\n"
            f"Found {len(matched)} matching lines out of {len(tail_lines)} reviewed.\n\n"
        )

    if matched:
        prompt += "Lines matching patterns:\n```\n"
        prompt += "".join(matched[-50:])  # Limit to 50 matched lines
        prompt += "```\n\n"

    prompt += "Full excerpt:\n```\n"
    # Limit total size sent to Claude
    excerpt = "".join(tail_lines)
    if len(excerpt) > 8000:
        excerpt = excerpt[:8000] + "\n...(truncated)"
    prompt += excerpt
    prompt += "```"

    # Call Claude
    result = subprocess.run(
        ["claude", "-p", "--system-prompt", system_prompt, prompt],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"claude CLI error: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(result.stdout)

    # Exit with error if significant issues were found in matched lines
    error_patterns = ["error", "fatal", "exception", "panic"]
    has_errors = any(
        any(p in line.lower() for p in error_patterns)
        for line in matched
    )
    if has_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
