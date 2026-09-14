# Home Assistant Configuration - Agent Instructions

## General Rules

1. **No YAML comments in UI-managed files** (`automations.yaml`, `scripts.yaml`, `scenes.yaml`). Comments there are hidden from the HA UI and might get lost on duplication or UI edits. In YAML-only files (`configuration.yaml`, `packages/`, `blueprints/`, `esphome/`, shell scripts) comments are fine and encouraged. In UI-managed files, use HA's built-in documentation fields instead:
   - `alias` — label for a step, trigger, or condition **only when it is not self-explanatory on its own**. Template conditions always need one (the expression doesn't speak for itself); simple state conditions (e.g. `state: locked`) usually don't.
   - `note` on a step — (HA 2026.6+) explain *why* a step works the way it does: non-obvious logic, constraints, or decisions. Don't restate what the step does.
   - `description` on an automation/script/scene — overall description of the whole entity; only add when the alias alone isn't enough. Most don't need one — prefer a better `alias` first.
2. **Reduce templating.** Templates are powerful, but harder to understand in comparison to other UI blocks. Using templates might be unavoidable on triggers, but when defining conditions, prefer using logical blocks when possible. Use template conditions only if using a function which the UI blocks lack, or if you are certain that a template will be more readable than nested blocks.
3. **Keep it simple.** Easy to understand, easy to debug, easy to maintain.
4. **Think of resources.** HA runs on a Raspberry Pi. Avoid heavy polling, complex templates that run frequently, or anything that exhausts CPU/memory.
5. **Avoid duplication.** If similar logic appears in multiple automations, offer to extract it into a script or blueprint.
6. **Avoid long delays and `wait_for_trigger`.** These won't restore after a reboot. Especially dangerous when the running state involves water, heating, or appliances. Use timeouts and `continue_on_timeout` when waits are necessary. Exception: a short delay/`wait_for_trigger` (under an hour) is fine when losing the off command isn't critical — i.e. the running state doesn't involve water, heating, or another safety-relevant appliance (a vent or light left on is a minor inconvenience, not a hazard).
7. **No dead code.** If code is disabled or unused, offer to delete it. It can always be recreated from git history. If it's worth keeping for reference, move it to the `archive/` folder. Exception: commented-out debug/dev toggles are intentional — leave them.
8. **Separate secrets from code.** Never commit secrets. Use `!secret` references and `secrets.yaml`.
9. **Don't reinvent the wheel.** Use known integrations or HACS resources when a reliable implementation exists.
10. **Avoid helpers that drive behaviour.** Don't introduce a helper whose purpose is to *decide* something — an `input_boolean` the user flips to enable a mode, an `input_select` that picks what an automation does. Those turn automation back into UI management; derive the state from sensors, presence, or the calendar instead. Helpers that *parametrise* a decision the house already makes on its own are a different thing — see rule 13.
11. **Dismiss notifications.** Mobile notifications are a good tool to send updates and draw attention. To reduce distractions, dismiss notifications when they are no longer relevant (i.e. if the problem was solved or a task was done). Since this specific behavior is "nice to have", it is OK to implement it using a long `wait_for_trigger` despite the general "Avoid `wait_for_trigger`" rule.
12. **Handle Errors.** Some actions may return an error, and you need to take that into consideration. If a critical action fails (like closing a valve), ensure an alert is sent via notification. In the case of multiple actions within the same automation, if there is no dependence between them and there is value in running the remaining actions, use `continue_on_error` so a single failure won't block the entire flow.
13. **Avoid magic numbers.** A bare number in an automation — a setpoint, a duration, a threshold, an offset — is fine when it appears once and isn't something the household re-tunes. But once the same parameter shows up in **more than one automation**, or the user has already changed it once by editing YAML, offer to move it into an `input_number` helper: one place to change it, adjustable from the dashboard, and no chance of updating three copies and missing the fourth. Before writing a number inline, check whether a helper already covers it — `grep -rhoE "input_number\.[a-z0-9_]+" *.yaml | sort -u`, and read `.storage/input_number` for its min/max/step. **Never create or edit a helper by hand:** HA owns `.storage` and rewrites it at runtime, so ask the user to add it via the HA UI rather than inventing the value. The tracked copy also lags the live instance, so a helper you can't find there may still exist — ask before concluding it doesn't. Read a helper with a fallback — `{{ states('input_number.x') | float(<sane default>) }}` — so an unavailable helper during a reload can't fail the action. Numbers that are facts rather than preferences stay inline: device limits, protocol constants, short debounces, and anything a scene sets (scenes can't hold templates).

14. **Name externally-reachable webhooks with a reserved prefix.** The edge refuses inbound traffic to HA by default, with one rule letting through `/api/webhook/` IDs that start with a prefix reserved for exactly that purpose (`public_` in this published copy - pick your own word and keep it to yourself). A webhook that must be callable from outside the house - a CI job, a cloud service, a callback - needs a `webhook_id` starting with that prefix. The prefix is the *only* thing exposing it: anything named that way is open to the whole internet, protected by nothing but the secrecy of the ID. Generate it with `python3 -c "import secrets; print('public_' + secrets.token_urlsafe(24))"` and store it via `!secret`. Leave the prefix off everything else - an unprefixed webhook is still refused at the edge, which is what you want for anything with a physical effect, and it also means a webhook some integration created on its own can never be reachable by accident. See `network.md`.

15. **Template sensors live in git.** Define every template sensor and binary sensor in `template_sensors.yaml`, never as a UI template helper — a helper in `.storage` is invisible to git, to review and to CI, and no agent session can read it. UI helpers are limited to `input_*` (`input_select`, `input_number`, `input_boolean`, `input_datetime`, `input_text`), which rule 13 still says the user creates by hand.

## Entity IDs & Renaming

- **Never rename entity_ids or unique_ids** to fix typos. References exist in UI-managed config, dashboards, and `.storage` files that are not tracked in git. Renaming will silently break things.
- Only fix typos in display text: `name`, `friendly_name`, `alias`, `description`.
- If a fix requires editing `.storage` or UI-managed config, ask the user to do it via the HA UI.

## Workflow

- **Don't commit on `main` without explicit user consent.** Keeps `main` clean; it should change through a reviewed PR.
- **On any other branch, commit and push automatically once a plan is approved** — no need to ask again, so the change can be reviewed as a PR.
- **Keep dedicated-branch history clean.** Squash/amend follow-up fixes and small edits into the existing feature commit (force-push-with-lease). When the user asks for an additional, separate feature on the branch, keep it as its own commit — they'll decide whether to squash at merge time.
- Use `dev` branch for cleanup and maintenance work.
- If making a change not locally on the HA server, pull main and merge to dev before starting work. If there are unstaged changes, ask the user if they want to commit, stash or discard them before merging.
- For big new features: offer to create a dedicated branch and open a PR to `main`.
- Validate YAML syntax before committing: `yamllint -c .yamllint.yml <file>` (a PostToolUse hook also lints every YAML file Claude edits). CI runs yamllint plus a full HA config check (`frenck/action-home-assistant`) on pushes to `main` and on PRs.
- Before planning changes that involve automations or scripts, inventory what already exists: `grep -E "^  alias:|^  description:" automations.yaml scripts.yaml`
- **In plan mode: ask upfront, don't assume.** Before drafting a plan, identify any design constants (time thresholds, entity preferences, feature scope) and ask about them in a single batch. If a request is underspecified, push back with questions rather than guessing and revising later.
- **Where to record rules:** When a generic instruction, coding rule, or workflow preference is established in conversation, write it to CLAUDE.md (or `~/.claude/CLAUDE.md` if it applies to all projects) — not to memory. Memory is for device/entity-specific facts and temporary project state. Personal household context goes in `home_context.md`. Never duplicate a rule that already exists in CLAUDE.md by also writing it to memory.

## Repository Structure

- `configuration.yaml` - Main config, integrations, includes
- `automations.yaml` - All automations (HA UI-managed format)
- `scripts.yaml` - Reusable scripts
- `scenes.yaml` - Scene definitions
- `template_sensors.yaml` - Template sensors and binary sensors
- `climate.md` - Map of every AC/fan automation, the day/night scene split, setpoint conventions, and the Shabbat-hosting invariant. **Keep it updated** whenever a climate automation is added, removed, or has its triggers/conditions changed.
- `frigate.md` - Frigate NVR deployment record: the Proxmox LXC, the container, `config.yml`, the HA integration wiring, and the **backup design**. Frigate runs off-Pi, so nothing about it is captured by HA backups or by this repo's YAML. **Keep it updated** whenever the Frigate container, its config, its go2rtc streams, its LXC, or the HA integration changes — and any new Frigate feature must also classify its state in that file's Backup section. Automations that merely consume Frigate entities do not need mirroring there.
- `network.md` - How HA is reached from outside the house: the edge rules, which sources are allowed to reach it, the tunnel and proxy path, and which HTTP status code means the edge refused a request rather than HA. **Read it before adding anything that calls into HA from the internet** - a webhook, an OAuth callback, a CI job - because those are refused by default and need a rule allowing them through. **Keep it updated** whenever an edge rule, the tunnel, the proxy, or the set of externally reachable endpoints changes.
- `blueprints/` - Automation blueprints
- `esphome/` - ESPHome device configs
- `secrets.yaml` - Secrets (gitignored, never commit)
- `autocommit_gemini.sh` - Auto git backup script (in active use)

## Personal Home Context
The file mentioned below includes the personal context of the physical house, the family, and our smart home preferences.
@.claude/home_context.md
