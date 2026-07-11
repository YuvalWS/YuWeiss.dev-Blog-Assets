#!/bin/bash
# Exit codes: 0 success | 1 generic failure | 2 secret detected | 3 push rejected | 4 not on main branch

MODEL_SECRETS="gemini-3.1-flash-lite"
MODEL_COMMIT="gemini-3.1-flash-lite"
REPO_DIR="/config"
SECRETS_FILE="/config/secrets.yaml"
API_KEY=$(grep "^gemini_api_key:" "$SECRETS_FILE" | sed 's/^.*: *//' | tr -d '"' | tr -d "'")

if [ -z "$API_KEY" ]; then
  echo "Error: Could not find 'gemini_api_key' in $SECRETS_FILE" >&2
  exit 1
fi

SKIP_SECRETS=0
ANY_BRANCH=0
for arg in "$@"; do
    case "$arg" in
        --skip-secrets) SKIP_SECRETS=1 ;;
        --any-branch) ANY_BRANCH=1 ;;
    esac
done

cd "$REPO_DIR" || exit 1

CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ] && [ "$ANY_BRANCH" -eq 0 ]; then
    echo "HA is on branch '$CURRENT_BRANCH' — autocommit skipped. Use 'Commit on Branch' to commit here." >&2
    exit 4
fi

git add -u
git add *.yaml www/ esphome/ \
    .storage/input_* .storage/counter .storage/lovelace* || true
DIFF=$(git diff --cached)

if [ -z "$DIFF" ]; then
    echo "No changes to commit."
    exit 0
fi

if [ "$SKIP_SECRETS" -eq 0 ]; then
    SECRETS_PAYLOAD=$(jq -n \
      --arg diff "$DIFF" \
      '{
        system_instruction: {
          parts: {
            text: "You are a security scanner. Examine the provided git diff for ADDED lines (lines starting with +) that contain real secrets: API keys, access tokens, passwords, private keys, OAuth client secrets, database connection strings with credentials, or long-lived bearer tokens. IGNORE: placeholders (xxx, REDACTED, your_key_here), variable names without values, !secret references, .gitignore patterns, example values in comments, removed lines (starting with -). Respond with EXACTLY one line. If clean: CLEAN. If a secret is found: SECRET: <short description and the offending line>. No markdown, no preamble."
          }
        },
        contents: [{
          parts: [{
            text: ("Diff to scan:\n" + $diff)
          }]
        }],
        generationConfig: {
          temperature: 0.0
        }
      }')

    SECRETS_RESPONSE=$(curl -s \
      -H "Content-Type: application/json" \
      -d "$SECRETS_PAYLOAD" \
      "https://generativelanguage.googleapis.com/v1beta/models/$MODEL_SECRETS:generateContent?key=${API_KEY}") \
      || { echo "Secrets curl failed" >&2; exit 1; }

    SECRETS_VERDICT=$(echo "$SECRETS_RESPONSE" | jq -r '.candidates[0].content.parts[0].text' | head -n1)

    if [ -z "$SECRETS_VERDICT" ] || [ "$SECRETS_VERDICT" = "null" ]; then
        echo "Secrets check returned no verdict. Response: $SECRETS_RESPONSE" >&2
        exit 1
    fi

    if [[ "$SECRETS_VERDICT" != CLEAN* ]]; then
        echo "SECRET_DETECTED: $SECRETS_VERDICT" >&2
        exit 2
    fi
fi

COMMIT_PAYLOAD=$(jq -n \
  --arg diff "$DIFF" \
  '{
    system_instruction: {
      parts: {
        text: "You are a specialized automation tool. Your ONLY job is to output a single line git commit message. Rules: 1. Read the provided git diff. 2. Understand if there is more than one change. If so, think if there is a common theme that can be summarized in a single commit message. If the changes are unrelated, mention each one of them, separated by a semicolon. 3. Summarize the changes factually (e.g. \"Add bathroom light automation\"). 4. Do not offer advice. 5. Do not output markdown. 6. If the diff looks like garbage, reply \"Update configuration\"."
      }
    },
    contents: [{
      parts: [{
        text: ("Here is the git diff data:\n" + $diff)
      }]
    }],
    generationConfig: {
      temperature: 0.0
    }
  }')

COMMIT_RESPONSE=$(curl -s \
  -H "Content-Type: application/json" \
  -d "$COMMIT_PAYLOAD" \
  "https://generativelanguage.googleapis.com/v1beta/models/$MODEL_COMMIT:generateContent?key=${API_KEY}") \
  || { echo "Commit-message curl failed" >&2; exit 1; }

COMMIT_MSG=$(echo "$COMMIT_RESPONSE" | jq -r '.candidates[0].content.parts[0].text')

if [ -n "$COMMIT_MSG" ] && [ "$COMMIT_MSG" != "null" ]; then
    echo "Committing with message: $COMMIT_MSG"
    git -c user.name="HA Autocommit" \
        -c user.email="bot@ha.io" \
        commit -m "$COMMIT_MSG" || exit 1
    PUSH_OUTPUT=$(git push origin main 2>&1)
    PUSH_EXIT=$?
    echo "$PUSH_OUTPUT"
    if [ $PUSH_EXIT -eq 0 ]; then
        echo "Pushed Successfully"
    elif echo "$PUSH_OUTPUT" | grep -qE "rejected|fetch first|non-fast-forward"; then
        echo "$PUSH_OUTPUT" >&2
        exit 3
    else
        echo "$PUSH_OUTPUT" >&2
        exit 1
    fi
else
    echo "Failed to generate commit message. Response: $COMMIT_RESPONSE" >&2
    exit 1
fi
