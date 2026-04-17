#!/bin/bash
# AI summarization sample for mogiri jobs.
#
# Uses Claude Code CLI (claude -p) to summarize or analyze
# the output from a parent job in a workflow chain.
#
# Typical workflow:
#   [some-job] --any--> [ai_summarize] --success--> [slack_thread_post]
#
# The parent job's stdout is passed via MOGIRI_PARENT_STDOUT and
# sent to Claude for analysis. The summary is printed to stdout,
# which can be picked up by the next chained job.
#
# Required:
#   claude CLI must be installed and authenticated
#
# Optional environment variables:
#   AI_PROMPT       - Custom prompt (default: "Summarize the following output")
#   AI_SYSTEM       - System prompt for Claude
#   AI_MAX_INPUT    - Max characters from parent stdout (default: 8000)

PROMPT="${AI_PROMPT:-Summarize the following output concisely. Highlight any errors or anomalies.}"
SYSTEM="${AI_SYSTEM:-You are a concise operations assistant. Output plain text, no markdown.}"
MAX_INPUT="${AI_MAX_INPUT:-8000}"

INPUT="${MOGIRI_PARENT_STDOUT:-}"

if [ -z "$INPUT" ]; then
    echo "No parent job output available (MOGIRI_PARENT_STDOUT is empty)." >&2
    echo "This job should be chained after another job in a workflow." >&2
    exit 1
fi

# Truncate if too long
if [ ${#INPUT} -gt "$MAX_INPUT" ]; then
    INPUT="${INPUT:0:$MAX_INPUT}...(truncated)"
fi

PARENT_JOB="${MOGIRI_PARENT_JOB_NAME:-unknown}"
PARENT_STATUS="${MOGIRI_PARENT_STATUS:-unknown}"

FULL_PROMPT="Job: ${PARENT_JOB} (status: ${PARENT_STATUS})

${PROMPT}

---
${INPUT}
---"

claude -p --system-prompt "$SYSTEM" "$FULL_PROMPT"
