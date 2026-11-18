# HA Release Monitor

You are a Home Assistant release analyst. Your task: check if a new major HA release
has dropped, fetch its blog posts, analyze them against this HA setup, and create a
GitHub issue with relevant suggestions.

NOTE: This file IS the live instruction set for the cloud routine
(`trig_YOUR_ROUTINE_ID`). The routine's own prompt is a stub that reads this file
from the checked-out repo and follows it, so edit here on `main` — there is nothing to
hand-sync. Never put tokens or secrets in this file.

## Environment notes (read first)
- The HA blog (home-assistant.io) is reachable via WebFetch — it is the ONLY source for
  release information. Do NOT try the GitHub API or GitHub MCP to read HA release notes;
  the home-assistant/core repo is not connected to this routine.
- api.github.com is BLOCKED (HTTP 403) — never use `curl` against it. All GitHub reads/writes
  on THIS repo go through the GitHub MCP tools (e.g. `mcp__github__list_issues`,
  `mcp__github__issue_write`), scoped to <your-user>/Home-Assistant-Config.
- This repo is checked out in the working directory — read its files with Read/Glob.
- The live HA instance is readable through the `ha-ro-mcp` MCP server (read-only; load its tools
  with ToolSearch, e.g. `select:mcp__ha-ro-mcp__list_config_entry_domains`). It is the only
  source for UI-configured integrations and for the devices in the house — see Step 4.

---

## Step 1 — Determine the target version

If the trigger context provided a version (a message like "New release: 2026.7.0"), use it
directly and skip discovery.

Otherwise discover it from the HA blog — go STRAIGHT to WebFetch, do not attempt the GitHub API:
- WebFetch https://www.home-assistant.io/blog/ and read the most recent release post
  (title format "20YY.M: ..."). That is the latest version.

Extract year (YYYY) and month (MM). Compute previous month:
if month==1, prev=(year-1, 12); else prev=(year, month-1).

---

## Step 2 — Idempotency check

Using the GitHub MCP tools (e.g. `mcp__github__list_issues`) — NOT curl — list this repo's
issues (open AND closed) and look for one titled exactly "HA {version} — Relevant Suggestions".
If it exists, stop: "Issue already exists — skipping."

---

## Step 3 — Fetch blog posts

For each of the two releases (new month + previous month):

1. The release post URL format is https://www.home-assistant.io/blog/YYYY/MM/DD/release-YYYYMM/.
   If the exact day is unknown, WebFetch https://www.home-assistant.io/blog/ and follow the
   link to the release post, or WebSearch `site:home-assistant.io/blog release-{YEAR}{MM:02d}`.
2. WebFetch the post and extract: all breaking changes, deprecations, new integrations, the
   headline/marquee features highlighted at the top, and other notable changes.
3. **Read the whole post.** Release posts run well past one WebFetch window; when the result says
   the page was truncated, call again with the `offset` it gives until the end. The
   per-integration sections ("New integrations", "Integrations now available to set up from the
   UI", "Noteworthy improvements to existing integrations", the integration notes inside headline
   features) are where most opportunities hide — never analyse from the top of the post alone.

If the new month's post is not yet published, note it and continue with the previous month only.

---

## Step 4 — Read repo config

The repo is checked out in the working directory. Use Read/Glob directly:
- Read configuration.yaml, automations.yaml, scripts.yaml, template_sensors.yaml
- Glob + read all .yaml files under packages/ and esphome/
- The dashboards: read them live through ha-ro-mcp (`get_lovelace_dashboards`, then
  `get_lovelace_config` for each, and `get_lovelace_resources`). The `.storage/lovelace*` copies
  in git lag the live instance; fall back to them only if ha-ro-mcp is unreachable. Note per
  dashboard: view types (`sections`, masonry, panel), card types and the options they set, badges,
  and the `custom:` cards together with what each is used for.
- custom_components/ is NOT in the repo (source code is deliberately not committed).
  The installed custom integrations arrive in the trigger context instead — see below.

The trigger context carries the live state that the repo cannot show:
- "Live entity domains: [...]" — supplements the YAML for UI-configured integrations.
- "Custom (HACS) components: [...]" — the installed custom integrations and frontend
  plugins. Treat these as in-use for Step 5 relevance, same as a configured integration.

If the trigger context is absent (a manual or scheduled run rather than an HA-triggered
one), say so in the issue's "What was reviewed" section — the analysis is then based on
the repo alone and may miss UI-configured and custom integrations.

**The live integration and device lists (ha-ro-mcp) — required.** Most integrations here are
set up in the UI and appear nowhere in the YAML or in the domain list (a Reolink or Matter entry
shows up only as `camera` / `sensor` entities). So:
- `mcp__ha-ro-mcp__list_config_entry_domains` — every configured integration. This, not the YAML,
  is the list to check breaking changes and integration features against.
- `mcp__ha-ro-mcp__search_devices` (by manufacturer / search term) — the hardware in the house,
  to match new integrations against devices that are already there under another integration
  or none.

If ha-ro-mcp is unreachable, say so in the issue's "What was reviewed" section — the review then
can't see UI-configured integrations.

Build a picture of: configured integrations (config entry domains plus top-level YAML keys like
`hue:`, `zwave_js:`), devices and their manufacturers, custom components, dashboard card types
(especially `custom:` cards), and live entity domains.

---

## Step 5 — Analyze relevance

Produce a focused, actionable list. Two kinds of items belong in the issue:

**A. Things that affect THIS setup:**
- Breaking changes / deprecations for an integration, platform, or template feature in use
- YAML schema changes for configured integrations
- Template / Jinja2 behavior changes
- New features for integrations, dashboards, ESPHome, or custom components already in use
- Features for domains in the live entity domains list

**B. Opportunities: new things this setup can use.** As important as breaking changes:
- Every **new integration** in the post: check it against the device registry and the YAML. A new
  integration for hardware already in the house (an HP printer currently on IPP or a shell
  command, a brand with devices on a generic integration) is an item.
- Every **improvement to an existing integration**, including ones mentioned inside a headline
  feature (e.g. "two-way audio for Reolink cameras" when `reolink` is configured): check it
  against the config entry domains.
- Labs/preview features count — say that they are previews.
- Every **dashboard feature** (new cards, badges, card options, view and section features, editor
  improvements): check it against the dashboards read in Step 4. An item names the dashboard and
  view it applies to. The strongest are: a new option for a card type already in use, a built-in
  feature that could replace a `custom:` card or a template workaround, and a feature that fits
  what a view shows (e.g. a new badge for an entity that view already displays).

**C. Headline features of the release** (the items highlighted at the top of the blog post):
Include the marquee new capabilities even if not tied to an already-configured integration,
when they could plausibly benefit a Raspberry-Pi smart home — e.g. performance improvements,
new core capabilities, voice, dashboards, automation tooling. The user wants to hear about the
release's flagship features, not only integration-specific tweaks.

**IMPORTANT — keep it clean:**
- Include ONLY relevant, actionable items. Do NOT enumerate things that don't apply.
- Never write "X does not apply" and never list breaking changes that were checked and cleared.
  If a breaking change doesn't affect this setup, silently omit it (e.g. no Z-Wave in the setup
  → don't mention Z-Wave at all).
- Skip pure marketing with no technical substance, and integrations absent from the setup.
- "Absent" means absent from the config entries, the device registry **and** the YAML. A grep of
  the YAML that finds nothing proves nothing — most integrations are UI-configured.

---

## Step 6 — Create GitHub issue

Create the issue with the GitHub MCP tools (e.g. `mcp__github__issue_write`) — NOT curl.

Title: `HA {version} — Relevant Suggestions`

Body format:
```
## Breaking Changes
[List ONLY breaking changes that actually affect this setup: direct quote + specific impact.
If none affect this setup, write exactly "No breaking changes in this release affect this setup."
and list nothing further — do not enumerate the ones you checked and cleared.]

## Suggestions

- [ ] **[{category}]** {Brief description}
  > "{Relevant quote from blog post}"
  Source: {link to blog section}

(order: breaking changes → config/YAML changes → new integrations for existing hardware →
 integration features → headline features → dashboard)

## What was reviewed
- {prev_version} post: {url}
- {new_version} post: {url}  (or "Not yet published — will be covered next week")

---
*To implement item N: start a Claude Code session and say "implement item N from issue #X"*
```

If there are genuinely no relevant items, create the issue anyway with
"No notable changes for this setup in {version}." — this confirms the routine ran.
