# HA release monitor

Companion files for [Let AI Read the Home Assistant Release Notes](https://yuweiss.dev/home-assistant-release-notes-ai/).

A Claude routine that wakes up when Home Assistant offers an update, reads the release
blog posts against your actual config, and opens a GitHub issue with only the parts that
affect you.

| File | Goes in | What it does |
|---|---|---|
| `ha_release_monitor.md` | `.claude/routines/ha_release_monitor.md` in your HA config repo | The real instruction set. The routine's own prompt is a four-line stub that reads this file, so the instructions stay in version control. |
| `rest_command.yaml` | `configuration.yaml` | Fires the routine, passing the version plus the live entity domains and HACS components the repo can't show. |
| `trigger_automation.yaml` | `automations.yaml` | Triggers that `rest_command` on a major (X.Y.0) release. |
| `routine_prompt.md` | the routine's Instructions box in the Claude interface | The stub. |

Set `claude_routine_authorization` in `secrets.yaml` to `Bearer <your routine token>`, and
replace `trig_YOUR_ROUTINE_ID` in `rest_command.yaml` with your own routine ID.
