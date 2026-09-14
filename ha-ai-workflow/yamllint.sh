#!/usr/bin/env bash
# PostToolUse hook: run yamllint on any YAML file Claude just edited or wrote.
# Injects errors back as additionalContext so they're visible in the same turn.
#
# Requires: python3 (stdlib json — any Python 3 install works)
#           yamllint on PATH (skips silently if missing)

INPUT=$(cat)

# Extract file path from hook stdin JSON using stdlib json — no jq/pip deps
f=$(printf '%s' "$INPUT" | python3 -c \
    "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" \
    2>/dev/null) || exit 0

# Only lint YAML files
case "$f" in
    *.yaml|*.yml) ;;
    *) exit 0 ;;
esac

# Skip silently if yamllint is not installed on this machine
command -v yamllint >/dev/null 2>&1 || exit 0

# Run yamllint; exit 0 = clean, non-zero = errors to report
out=$(yamllint -c .yamllint.yml "$f" 2>&1) && exit 0

# Return errors as additionalContext so Claude sees them immediately
python3 -c "
import sys, json
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'additionalContext': 'yamllint errors:\n' + sys.argv[1]}}))
" "$out"
