"""Slack thread posting sample for mogiri jobs.

Posts a parent message to a Slack channel, then replies in the thread.
Useful for posting job results with detailed logs in a thread.

Required environment variables:
  SLACK_BOT_TOKEN  - Slack Bot token (xoxb-...)
  SLACK_CHANNEL    - Channel ID (e.g. C01234567)

Optional environment variables:
  SLACK_TITLE      - Parent message text (default: "mogiri Job Report")
  SLACK_BODY       - Thread reply text (default: reads from stdin or uses a placeholder)

Slack App setup:
  1. Create a Slack App at https://api.slack.com/apps
  2. Add Bot Token Scope: chat:write
  3. Install the app to your workspace
  4. Copy the Bot User OAuth Token (xoxb-...)
  5. Invite the bot to the target channel: /invite @your-bot

Usage in mogiri:
  - Set SLACK_BOT_TOKEN and SLACK_CHANNEL as global env vars in Settings
  - Create a job with command_type=python using this script
  - Or chain it after another job to post results via MOGIRI_PARENT_STDOUT

Example for chained jobs:
  The script automatically picks up MOGIRI_PARENT_STDOUT and
  MOGIRI_PARENT_JOB_NAME from the parent execution when used
  in a workflow chain.
"""

import json
import os
import sys
import urllib.request


def post_message(token, channel, text, thread_ts=None):
    """Post a message to Slack and return the response."""
    payload = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts

    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    if not result.get("ok"):
        print(f"Slack API error: {result.get('error')}", file=sys.stderr)
        sys.exit(1)

    return result


def main():
    token = os.environ.get("SLACK_BOT_TOKEN")
    channel = os.environ.get("SLACK_CHANNEL")

    if not token or not channel:
        print("Error: SLACK_BOT_TOKEN and SLACK_CHANNEL are required.", file=sys.stderr)
        sys.exit(1)

    # Build message content
    parent_job = os.environ.get("MOGIRI_PARENT_JOB_NAME", "")
    parent_stdout = os.environ.get("MOGIRI_PARENT_STDOUT", "")
    parent_status = os.environ.get("MOGIRI_PARENT_STATUS", "")

    title = os.environ.get("SLACK_TITLE", "")
    body = os.environ.get("SLACK_BODY", "")

    if not title:
        if parent_job:
            status_emoji = ":white_check_mark:" if parent_status == "success" else ":x:"
            title = f"{status_emoji} mogiri Job Report: {parent_job}"
        else:
            title = "mogiri Job Report"

    if not body:
        if parent_stdout:
            body = f"```\n{parent_stdout}\n```"
        else:
            body = "No details available."

    # Post parent message
    result = post_message(token, channel, title)
    ts = result["ts"]
    print(f"Posted parent message: ts={ts}")

    # Post thread reply with details
    post_message(token, channel, body, thread_ts=ts)
    print("Posted thread reply.")


if __name__ == "__main__":
    main()
