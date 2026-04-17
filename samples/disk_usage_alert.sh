#!/bin/bash
# Disk usage alert sample for mogiri jobs.
#
# Checks disk usage and exits with error if any filesystem exceeds the threshold.
# Useful as a scheduled cron job for monitoring.
#
# Optional environment variables:
#   DISK_THRESHOLD  - Usage percentage threshold (default: 80)
#   DISK_TARGET     - Target mount point to check (default: all filesystems)

THRESHOLD="${DISK_THRESHOLD:-80}"
TARGET="${DISK_TARGET:-}"
HAS_ALERT=0

if [ -n "$TARGET" ]; then
    USAGE=$(df "$TARGET" --output=pcent | tail -1 | tr -d ' %')
    if [ "$USAGE" -ge "$THRESHOLD" ]; then
        echo "ALERT: $TARGET is at ${USAGE}% (threshold: ${THRESHOLD}%)"
        HAS_ALERT=1
    else
        echo "OK: $TARGET is at ${USAGE}%"
    fi
else
    while IFS= read -r line; do
        MOUNT=$(echo "$line" | awk '{print $6}')
        USAGE=$(echo "$line" | awk '{print $5}' | tr -d '%')
        if [ "$USAGE" -ge "$THRESHOLD" ]; then
            echo "ALERT: $MOUNT is at ${USAGE}% (threshold: ${THRESHOLD}%)"
            HAS_ALERT=1
        fi
    done < <(df -h --output=source,size,used,avail,pcent,target | tail -n +2 | grep -v tmpfs)

    if [ "$HAS_ALERT" -eq 0 ]; then
        echo "OK: All filesystems below ${THRESHOLD}%"
    fi
fi

exit $HAS_ALERT
