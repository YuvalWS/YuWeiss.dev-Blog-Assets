# Upstreaming a quirk to zigpy/zha-device-handlers

A custom quirk that works here is not yet a pull request. This is the route that got a
quirk to "ready to push" without surprises, and the mistakes it is built to avoid.

Nothing leaves the machine without the user's go-ahead: no fork, no push, no PR. The
user opens the PR themselves (see "AI policy").

## 1. Read the upstream rules in full, every time

They change, and skimming is how a rule gets missed. Read these completely, from a
fresh clone of `dev`, before touching a quirk:

- `.github/copilot-instructions.md` — the v2 API, entity rules, code style, tests, PR
  requirements. Also reachable as `AGENTS.md` / `CLAUDE.md`.
- `tuya.md` — for anything built with `TuyaQuirkBuilder`.
- `README.md` — the "Contribution Guidelines" section and the dev setup.
- `.github/PULL_REQUEST_TEMPLATE.md` — the headings are checked; a PR that skips the
  template can be closed.

Then audit the diff against them, line by line. What this has caught:

- number bounds in the wrong unit (see `quirk-authoring.md`)
- a standard attribute retyped as `enum8`, changing its wire type
- magic cluster and attribute ids instead of `Cluster.AttributeDefs.<x>`
- an unneeded manufacturer code, or a missing explicit `manufacturer_code=None`
- `translation_key` that duplicates an existing HA string

## 2. Check what is already there

```bash
gh search issues --repo zigpy/zha-device-handlers "<model>" --limit 20 \
  --json number,title,state,isPullRequest
gh pr list --repo zigpy/zha-device-handlers --state open --search "<vendor> in:title"
```

Search the model, the manufacturer string and the vendor. Open PRs for the same model
may be stale and flagged "needs changes"; that is still a conversation to have before
opening a competing one. Also grep the clone itself for the model.

## 3. Learn the maintainers' conventions from real reviews

The docs are not the whole story. Read the review threads of a few recent merged and
open quirk PRs for the same vendor (`gh pr view <n> --json reviews,comments`, and
`gh api repos/zigpy/zha-device-handlers/pulls/<n>/comments` for inline threads). Things
learned this way that no doc states:

- **One device per PR.** Faster to review, and merges the ready ones.
- **File placement follows the family, not the brand.** The docs say "by
  manufacturer"; maintainers steered a HOBEIAN contributor away from a new `hobeian/`
  package into `zhaquirks/tuya/` because those devices are Tuya-based and already live
  there. Say where you put it in the PR and offer to move it.
- **Match the Z2M converter exactly**: both fingerprints when it has two, the same DPs,
  the same bounds. Reviewers check this.
- **Prefer existing HA translation keys**, and two binary sensors over one enum sensor
  for open/closed-like states.
- **Do not add unused `.adds()` or `tuya_enchantment()`**; they get flagged. Keep
  `data_query_spell` only when the settings really would read back blank.
- An LLM review bot (`zigpy-review-bot`) comments on PRs and the maintainer relays it.
  Expect its nits to be about exactly the audit list above.

## 4. Port from Z2M, and check the write path

Match your signature against the converter (`zigbeeModel` list versus `fingerprint`,
see `sources.md`). Then read the converter's *write* path too, not only its exposes:
the type it writes with and whether it passes a manufacturer code are part of the
protocol, and a quirk that differs can look fine and be refused by the device.

Every claim you intend to make in the PR ("written without a manufacturer code",
"hides the duplicate occupancy sensor") needs a test or a read of the code behind it.
A claim carried over from memory is how a wrong sentence reaches a maintainer.

## 5. Local environment

```bash
gh repo clone zigpy/zha-device-handlers && cd zha-device-handlers
python -m pip install --user uv && python -m uv sync        # needs Python >= 3.12
python -m uv pip install --python .venv/Scripts/python.exe tzdata   # Windows only
.venv/Scripts/pre-commit install
```

- Windows needs `tzdata` in the venv or `tests/test_tuya.py` cannot import.
  `uv pip install` without `--python` installs into the wrong interpreter; `uv sync`
  removes it again, so reinstall after a sync.
- Run natively on Windows. An earlier session found the test run slow when the repo
  sat on a WSL mount of a Windows folder.
- Record the baseline on untouched `dev` before changing anything. On Windows, eight
  tests fail on their own (Inovelli path separators, two Tuya set-time tests). Report
  them as the baseline, never as yours.
- Per branch: the full suite, and `pre-commit run --all-files`, not just changed files.
- Put the quirk where the maintainers do, add tests for custom logic, and write
  entity-metadata tests even for declarative ones (upstream: "tests should verify
  entity creation").

Useful test shapes, all with `zigpy_device_from_v2_quirk(manufacturer, model, ...)`
(note the argument order; many existing tests name them the other way round):

- Tuya datapoint decode: `ep.tuya_manufacturer.deserialize(msg)` then `handle_get_data`.
- Entity metadata: `DEVICE_REGISTRY.match_entry(device).zha_device_factory
  .quirk_definition.entity_metadata` and `.disabled_default_entities`.
- Wire format: the mocked-request test in `quirk-authoring.md`.

## 6. Test on the real device, then again after any change

The checklist box "tested and work correctly" is a statement about the pushed code, so
it must be true of that code. Generate a standalone custom-quirk copy of the branch
version (imports plus the classes and builder, no other changes), drop it over the old
custom quirk file under the *same file name* so two quirks do not register for one
device, restart HA, change each setting and see it stick, then download diagnostics.

Any code change after a hardware test — even a "no-op" refactor — means a retest and a
fresh dump. In this work a review of the docs after the first test changed the wire
type of two attributes; the push waited for the second test.

Load the standalone file once on a tree without the in-tree quirk and assert it matches,
so a copy error does not cost a round trip to the Pi.

## 7. Diagnostics file

- Device diagnostics (device page, three dots), not integration-level: the latter can
  contain the network key.
- A dump taken with the quirk applied is accepted and shows the result;
  `original_signature` is what upstream rebuilds from.
- HA redacts the device IEEE but **not** `cie_addr` (the coordinator's EUI-64). Replace
  it with zeros in a copy and say so.
- Check the dump against the branch before attaching: `zcl_type` of the attributes,
  the entity list, translation keys, and which entities are absent.
- A dump reflects one instant (motion, battery). It proves reads, not writes.

## 8. Branches and the push

- One branch per device off the latest `dev`; rebase onto `dev` just before pushing and
  rerun the checks. Other branches can wait; do not rebase them speculatively.
- Fork without cloning: `gh repo fork zigpy/zha-device-handlers --clone=false`
  (`--remote` is rejected when a repository is named), wait for it to exist, add it as
  a remote, push **only** the one branch.
- Commit author is the user's git identity and becomes public; confirm it.
- Keep drafts and notes out of tracked files (`.git/info/exclude`).

## AI policy (Open Home Foundation)

Covers every repository in the `home-assistant` and `home-assistant-libs` orgs; zigpy
is not named, and the repo has no `AI_POLICY.md`, so follow it anyway. In short:

- AI help is allowed, and the human must understand and be able to explain every change.
- PR descriptions and replies to maintainers are in the contributor's **own words**.
  Using AI to polish grammar of your own text is fine; using it to answer a maintainer's
  question is not.
- Autonomous PRs and issues are closed.
- Context quoted from an AI must be marked as such.

So: prepare a fact sheet (what changed, what was verified and how, what is breaking,
open questions for the maintainers) and let the user write the PR text. A brief
disclosure line is customary and has been accepted on comparable PRs. The agent does
not open the PR; it hands over the compare URL.

## What a good PR description has

Template headings, then: what the device is and what was missing; what the quirk adds
and hides; what is breaking for existing installs (entities that disappear); where the
file is and an offer to move it; what the user tested and how; the diagnostics.
Anything inferred, such as a datapoint whose meaning is only known from a Z2M name,
is labelled as inferred.
