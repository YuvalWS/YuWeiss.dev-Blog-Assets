# Home Assistant Git Version Control

The full set of scripts and Home Assistant config that back the git-backup series on
[yuweiss.dev](https://yuweiss.dev):

1. [Use git with AI for the best HA version history](https://yuweiss.dev/home-assistant-ai-github-backup/) — the original setup: get your config into git with AI-generated commit messages.
2. [My Home Assistant git workflow, a few months later](https://yuweiss.dev/home-assistant-git-workflow-upgrades/) — secret scanning, safe pushes, and a branch-based deploy panel.
3. [Letting Claude edit my HA config without breaking my house](https://yuweiss.dev/home-assistant-claude-config/) — the AI-editing side, tests, and human review.

## What's here

| File | What it is | Where it goes |
|---|---|---|
| `autocommit_gemini.sh` | The nightly backup engine: stages changes, scans the diff for secrets, asks Gemini for a commit message, commits and pushes. | `/config/` |
| `git_pull_and_sync.sh` | Recovers from a rejected push: stash → rebase → pop → push. | `/config/scripts/` |
| `git_checkout_branch.sh` | Checks out a branch and validates the config via the Supervisor API before restart; reverts to `main` if the check fails. | `/config/scripts/` |
| `git_refresh_branches.sh` | Fetches remote branches into a temp file for the dashboard selector. | `/config/scripts/` |
| `git_ops.yaml` | The Home Assistant [package](https://www.home-assistant.io/docs/configuration/packages/): branch sensor, dashboard buttons, scripts, and the branch-workflow automations. | `/config/packages/` |
| `nightly_backup_automation.yaml` | The scheduled 2 AM backup automation, with per-exit-code notifications (secret detected, push rejected, etc.). | your `automations.yaml` |
| `configuration_shell_commands.yaml` | The three `git_autocommit*` shell_command entries. | under `shell_command:` in `configuration.yaml` |

## Exit codes (`autocommit_gemini.sh`)

| Code | Meaning |
|---|---|
| 0 | Success (or nothing to commit) |
| 1 | Generic failure |
| 2 | Secret detected in the diff — commit aborted |
| 3 | Push rejected — remote has commits you don't (run Git Sync) |
| 4 | Not on `main` — autocommit skipped (use Commit on Branch) |

## Prerequisites

- The [SSH deploy-key + `git init` setup](https://yuweiss.dev/home-assistant-ai-github-backup/) from post 1.
- A free [Google AI Studio](https://aistudio.google.com/) API key in `secrets.yaml` as `gemini_api_key`.
- `git_checkout_branch.sh` relies on `SUPERVISOR_TOKEN`, available inside the HA Core
  container — so it runs on Home Assistant OS / Supervised installs.
