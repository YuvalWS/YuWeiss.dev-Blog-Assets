# HA AI workflow

Companion files for [My AI Workflow for Home Assistant Config](https://yuweiss.dev/home-assistant-ai-workflow/).

These are the files that let an AI agent work on a Home Assistant config through git
instead of against the live instance, plus the checks that run on what it writes.

| File | Goes in your HA config repo at | What it does |
|---|---|---|
| `CLAUDE.md` | `CLAUDE.md` | Standing instructions for the agent: coding rules, entity-ID safety, workflow. |
| `claude_settings.json` | `.claude/settings.json` | Registers the `PostToolUse` yamllint hook. |
| `yamllint.sh` | `.claude/hooks/yamllint.sh` | The hook itself — lints YAML the agent just wrote and feeds errors back in the same turn. |
| `yamllint.yml` | `.yamllint.yml` | The yamllint ruleset all three layers share. |
| `pre-commit-config.yaml` | `.pre-commit-config.yaml` | Runs the same lint before a commit is created. |
| `validate.yml` | `.github/workflows/validate.yml` | CI: yamllint, a full HA config check, and the webhook that notifies HA when a PR goes green. |

`validate.yml` expects a repository secret `HA_CI_WEBHOOK_URL` pointing at a Home Assistant
webhook. The HA side of that (the `Git: PR CI passed` automation and the checkout scripts)
lives in [`git-version-control/`](../git-version-control/).

The personal context file the post mentions (`.claude/home_context.md`) is deliberately not
here — it is specific to one house. `CLAUDE.md` is written to stay generic so it can be shared.
