#!/bin/bash
# Checks out a branch and validates config before caller restarts HA.
# Exit codes: 0 config ok (caller should restart) | 1 config failed (reverted to main) | 2 git error
#
# Config check runs via the Supervisor API (POST http://supervisor/core/check),
# the equivalent of `ha core check`. This script is invoked by
# shell_command.git_checkout_branch, which runs inside the HA Core container
# where the `ha` CLI is not installed but SUPERVISOR_TOKEN is available.

BRANCH="$1"
cd /config || exit 2

OUTPUT=$(git fetch origin 2>&1)
if [ $? -ne 0 ]; then
    echo "git fetch failed: $OUTPUT" >&2
    exit 2
fi

OUTPUT=$(git checkout "$BRANCH" 2>&1)
if [ $? -ne 0 ]; then
    echo "git checkout failed: $OUTPUT" >&2
    exit 2
fi
echo "Checked out $BRANCH"

HTTP_CODE=$(curl -sS -o /tmp/ha_core_check.json -w '%{http_code}' -X POST \
    -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
    http://supervisor/core/check 2>/tmp/ha_core_check.err)
if [ "$HTTP_CODE" != "200" ]; then
    echo "Config check failed. Reverting to main." >&2
    cat /tmp/ha_core_check.json /tmp/ha_core_check.err >&2
    git checkout main 2>&1
    exit 1
fi

echo "Config check passed."
exit 0
