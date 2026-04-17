"""Pushover notification sample for mogiri jobs.

Sends a push notification via Pushover API.
Useful for alerting on job failures or completions.

Required environment variables:
  PUSHOVER_TOKEN  - Pushover Application API Token
  PUSHOVER_USER   - Pushover User Key

Optional environment variables:
  PUSHOVER_TITLE    - Notification title (default: "mogiri Job Alert")
  PUSHOVER_MESSAGE  - Notification body (default: auto-generated from parent job)
  PUSHOVER_PRIORITY - Priority: -2(lowest) to 2(emergency) (default: 0)
  PUSHOVER_SOUND    - Notification sound (default: pushover)
  PUSHOVER_DEVICE   - Target device name (default: all devices)

Pushover setup:
  1. Create an account at https://pushover.net/
  2. Create an Application/API Token
  3. Note your User Key from the dashboard

Usage in mogiri:
  - Set PUSHOVER_TOKEN and PUSHOVER_USER as global env vars in Settings
  - Chain after another job to receive notifications on success/failure
  - MOGIRI_PARENT_STATUS and MOGIRI_PARENT_JOB_NAME are auto-populated
    when used in a workflow chain
"""

import json
import os
import sys
import urllib.request


def main():
    token = os.environ.get("PUSHOVER_TOKEN")
    user = os.environ.get("PUSHOVER_USER")

    if not token or not user:
        print("Error: PUSHOVER_TOKEN and PUSHOVER_USER are required.", file=sys.stderr)
        sys.exit(1)

    parent_job = os.environ.get("MOGIRI_PARENT_JOB_NAME", "")
    parent_status = os.environ.get("MOGIRI_PARENT_STATUS", "")
    parent_stdout = os.environ.get("MOGIRI_PARENT_STDOUT", "")

    title = os.environ.get("PUSHOVER_TITLE", "")
    message = os.environ.get("PUSHOVER_MESSAGE", "")
    priority = int(os.environ.get("PUSHOVER_PRIORITY", "0"))

    if not title:
        if parent_job:
            status_label = parent_status.upper() if parent_status else "UNKNOWN"
            title = f"mogiri: {parent_job} [{status_label}]"
        else:
            title = "mogiri Job Alert"

    if not message:
        if parent_stdout:
            # Pushover max message length is 1024
            message = parent_stdout[:1024]
        else:
            message = f"Job status: {parent_status or 'unknown'}"

    payload = {
        "token": token,
        "user": user,
        "title": title,
        "message": message,
        "priority": priority,
    }

    sound = os.environ.get("PUSHOVER_SOUND")
    if sound:
        payload["sound"] = sound

    device = os.environ.get("PUSHOVER_DEVICE")
    if device:
        payload["device"] = device

    # Emergency priority requires retry and expire
    if priority == 2:
        payload["retry"] = 60
        payload["expire"] = 300

    req = urllib.request.Request(
        "https://api.pushover.net/1/messages.json",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        if result.get("status") == 1:
            print(f"Notification sent: {title}")
        else:
            print(f"Pushover error: {result}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Failed to send notification: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
