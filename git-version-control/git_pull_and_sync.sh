#!/bin/bash
# Pulls remote changes and retries the push after a rejected autocommit.
#
# Flow:
#   1. stash any unstaged UI changes (no-op if none)
#   2. git pull --rebase  — replays our committed-but-rejected commit on top of remote
#   3. git stash pop      — restores unstaged UI changes (NOT pushed; next autocommit picks them up)
#   4. git push
#
# Exit codes:
#   0  success
#   1  unresolvable conflict (pull conflict or stash-pop conflict) — repo left clean, SSH to resolve
#   2  other failure (push failed for non-conflict reason, cd failed, etc.)

REPO_DIR="/config"
cd "$REPO_DIR" || exit 2

# Stash unstaged changes so pull --rebase doesn't refuse to run
STASH_OUTPUT=$(git stash 2>&1)
STASH_EXIT=$?
if [ $STASH_EXIT -ne 0 ]; then
    echo "$STASH_OUTPUT" >&2
    exit 2
fi
HAD_STASH=0
echo "$STASH_OUTPUT" | grep -q "No local changes" || HAD_STASH=1

PULL_OUTPUT=$(git pull --rebase origin main 2>&1)
PULL_EXIT=$?

if [ $PULL_EXIT -ne 0 ]; then
    git rebase --abort 2>/dev/null
    [ $HAD_STASH -eq 1 ] && git stash pop 2>/dev/null
    echo "$PULL_OUTPUT" >&2
    exit 1
fi

if [ $HAD_STASH -eq 1 ]; then
    POP_OUTPUT=$(git stash pop 2>&1)
    POP_EXIT=$?
    if [ $POP_EXIT -ne 0 ]; then
        # Stash pop conflicted — drop the stash to restore clean state
        git stash drop 2>/dev/null
        echo "Stash pop failed (UI changes conflict with pulled remote changes):" >&2
        echo "$POP_OUTPUT" >&2
        exit 1
    fi
fi

echo "Pull succeeded. Pushing..."
PUSH_OUTPUT=$(git push origin main 2>&1)
PUSH_EXIT=$?
echo "$PUSH_OUTPUT"

if [ $PUSH_EXIT -ne 0 ]; then
    echo "$PUSH_OUTPUT" >&2
    exit 2
fi

echo "Pushed successfully."
