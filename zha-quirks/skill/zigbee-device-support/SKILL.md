---
name: zigbee-device-support
description: >-
  Compare what a Zigbee device exposes under ZHA against what Zigbee2MQTT gets from
  the same hardware, and close the gap by writing and verifying a custom ZHA quirk.
  Use this whenever a Zigbee device is missing features, exposes fewer entities than
  expected, has no configuration controls, shows duplicate or oddly-named entities, or
  is advertised as "Zigbee2MQTT only" - and also before buying a Zigbee device, to
  check whether ZHA will handle it. Use it for any mention of ZHA, zigpy, quirks,
  zha-device-handlers, Zigbee2MQTT, zigbee-herdsman-converters, Tuya datapoints,
  manufacturer strings like _TZE200_ or _TZ3000_, or questions about moving between
  ZHA and Z2M, even when the word "quirk" never comes up. Also use it when preparing a
  pull request to zigpy/zha-device-handlers, forking or branching it, or reading its
  contribution guidelines or AI policy.
---

# Zigbee device support: ZHA vs Zigbee2MQTT

Both stacks speak the same Zigbee. The difference is how much of a device's
manufacturer-specific behaviour each project has bothered to decode. Z2M's converters
usually lead for cheap Tuya-family hardware; ZHA's quirks are mature for mainstream
Aqara, IKEA and Sonoff. So "Z2M only" is often just a lag, and the lag is portable:
a Z2M converter is a readable map of the device's clusters and datapoints, and porting
that knowledge into a ZHA quirk is mostly transcription.

The point of this skill is that transcription is cheap while *diagnosis* is expensive.
Spend the effort on identifying the device exactly and verifying the result.

## Which job is this?

**Audit a device you own** — you have its signature, so every answer is checkable.
This is the reliable case. Start at step 1.

**Check before buying** — you have a product name and maybe a model number, but not
the signature. Answers are necessarily approximate; say so. See "Pre-purchase" below.

**Build a quirk** — you already know there is a gap. Skip to step 4.

## Step 1 — Identify the device exactly

A device is matched by two strings: `manufacturer` and `model`, as the device itself
reports them. The product name on the box is irrelevant, and the same box is sold with
different manufacturer strings. Get the real ones.

**Names that differ by a letter are different hardware.** Vendors number siblings by
suffix: HOBEIAN's `ZG-204Z` is a PIR, `ZG-204ZK` a 24 GHz presence radar, `ZG-204ZL` a
luminance motion sensor, `ZG-204ZV` a 10 GHz radar, each with its own Z2M definition and
datapoint table. The box can differ again (a `ZG-204ZP` box held a device reporting
`ZG-204ZK`). So take the model from HA, the device registry or the diagnostics, before
opening any file, and compare it for *exact* equality with the strings a quirk declares.
A quirk in `custom_zha_quirks/` for a similarly named model proves nothing about this
device: `quirk_applied: false` in its diagnostics next to a near-match in the folder is
exactly this mistake. Do not let the entity name, the box or the quirk you found first
choose the converter.

For one device: its ZHA device page → ⋮ → **Download diagnostics**. The
`data.original_signature` block is the ground truth, and `quirk_applied` tells you
whether anything is intercepting it today. Keep this file; step 4 needs it.

⚠️ Integration-level ZHA diagnostics can contain the Zigbee **network key**. Per-device
diagnostics should not, but check before pasting either anywhere.

For the whole mesh, in **Developer Tools → Template**:

```jinja
{% set ns = namespace(devs=[]) %}
{% for e in integration_entities('zha') %}
  {% set d = device_id(e) %}
  {% if d and d not in ns.devs %}{% set ns.devs = ns.devs + [d] %}{% endif %}
{% endfor %}
{% for d in ns.devs %}
--- {{ device_attr(d, 'name_by_user') or device_attr(d, 'name') }}
manufacturer: {{ device_attr(d, 'manufacturer') }}
model: {{ device_attr(d, 'model') }}
entities ({{ device_entities(d) | count }}): {{ device_entities(d) | join(', ') }}
{% endfor %}
```

The entity count is the cheap gap detector: a device showing 4 entities where Z2M
exposes 12 is worth investigating. Two things distort it, so read it as a hint rather
than a measurement. Other integrations add entities to the same device — Battery Notes
contributes `battery_plus`, `battery_type` and friends, which are not ZHA's doing. And
the template derives devices from their entities, so a device whose entities are all
disabled will be missing entirely; if the count looks low, read
`.storage/core.device_registry` instead.

## Ask for what you cannot see

Only the user can see the running system, and almost every question here is settled
faster by asking than by inferring. Things worth requesting, with a reason attached so
the user knows why it is worth their two minutes:

- the device's ZHA diagnostics — the single most useful artefact
- the template output above, for a fleet-wide pass
- what an entity currently reads, and what it read yesterday
- what happens to a reading under a physical test: wet the probe, open the door,
  press the button
- ZHA debug logs with `zigpy` or `zigpy.quirks` raised, when you need to see which
  quirk matched or what a Tuya MCU is actually sending

Blocked from fetching something? Ask for the domain to be allowlisted *and* look for a
fallback at the same time. The request costs nothing if the fallback works, and
silently routing around a block can leave you reading a worse source than the one you
were denied.

## Do not infer state from a single snapshot

Diagnostics are one instant. A cluster reading `0` may be a dead cluster the device
never populates, or a perfectly good sensor looking at dry soil. These are opposite
conclusions with opposite fixes, and nothing in the snapshot separates them.

This is not hypothetical: reading `measured_value: 0` as "the device advertises this
cluster but never populates it" led to a quirk that would have replaced a working
sensor with months of history behind it. The user knew within seconds that the reading
was real, because they had watched it move.

So when a value looks degenerate — zero, unchanging, implausible — ask what it has
been doing, or propose a physical test. Treat a snapshot as one sample, and say
"this reads 0 right now, is that normal?" rather than concluding anything from it.

## Step 2 — Read what each side actually does

Do not answer from memory about any specific device; both projects change weekly, and
a confident wrong datapoint number is worse than an admission of uncertainty. Read the
source. `references/sources.md` has the fetch recipes, the fallbacks for when the
obvious URL is blocked, and — most importantly — **how Z2M decides which converter
matches**, which is the single most common way to end up with the wrong datapoint
table.

## Step 3 — Compare and classify

Put each device in one of these. The classification is the deliverable; it tells the
user whether to act at all.

- **Parity** — nothing to gain. Most mainstream devices. Say so plainly and stop.
- **ZHA ahead** — happens more than people expect. Worth stating, because it argues
  against a migration the user may be contemplating.
- **Cosmetic gap** — Z2M exposes an extra diagnostic counter or a raw voltage. Report
  it, recommend against the work.
- **Real gap** — missing entities, missing configuration, or a wrong domain or device
  class. Worth a quirk. Go to step 4.
- **Not quirk-fixable** — some Z2M support lives below the converter layer, in
  zigbee-herdsman itself: interview workarounds, nonstandard joins. A quirk cannot
  reach those; it would need a zigpy change. Say so rather than attempting it.

Before building anything, check whether the work is already done: search
`zha-device-handlers` for the model, and check its open pull requests and issues.
Half-finished quirks get pasted into issue threads constantly.

But an existing quirk is not proof the gap is closed — compare what it *implements*
against the Z2M converter, attribute by attribute. Upstream's Sonoff SWV quirk maps
two attributes on cluster 0xFC11; Z2M reads nine off the same cluster, including the
daily water total. A device can show fourteen entities and still be missing most of
what the hardware offers, which is also why the entity count in step 1 is only a hint.

## Step 4 — Build the quirk

Read `references/quirk-authoring.md`. It covers the v2 builder API, and a set of
gotchas that each cost real debugging time: entity naming (why `fallback_name` gets
ignored), why Tuya config values read back empty, raw-versus-display scaling, and the
type names that differ from what you would guess.

Two habits that matter more than the API details:

**Be additive first.** Add what is missing before replacing what exists. A cluster
that already produces a working entity has history behind it and probably an
automation pointing at it. Replacing it is a separate, deliberate decision — and when
you do make it, move every reference in the same commit, or the user restarts into a
broken automation.

Find those references before you decide, because some are not yours to edit:

```bash
grep -rn "<entity_id>" --include=*.yaml .
grep -rln "<entity_id>" .storage/
```

YAML is yours. Anything in `.storage` — dashboards, UI-managed config — is owned by HA
and has to be changed by the user in the UI, so it becomes a hand-off you name
explicitly rather than a step you complete. Removing an entity also orphans its
recorder history under the old id; that is usually acceptable, but it is the user's
call, not yours.

**Stage the writable entities.** A wrong datapoint number on a read-only sensor gives
a wrong reading, which is obvious and harmless. The same mistake on a writable number
can misconfigure the hardware. Land the read-only side, confirm it on the real device,
then add the controls.

## Step 5 — Verify before it reaches the user

A quirk that imports cleanly can still fail to match, or match and silently displace a
working cluster. Neither shows up until HA restarts and something is missing, so check
first:

```bash
scripts/verify_quirk.py --quirk <file> --diagnostics <device-diagnostics.json> \
    --dp 3=37 --dp-bool 106=1
```

It rebuilds the device from its own signature, applies the quirk through the same
registry ZHA uses, and prints a cluster diff, the entities the quirk adds (bounds, names)
and hides, and the attributes your datapoints set.
Run it with the `zha` and `zha-quirks` versions the target HA runs — read them from
`integration_manifest.requirements` in the diagnostics file; the script's docstring has
the venv setup.

This step has repeatedly caught things reasoning alone did not. Treat a failure as
information about the device, not an obstacle.

It proves the quirk matches and builds the right clusters. It does not prove the
device accepts a write, so for writable entities also change them on the real device
and look at the result.

## Step 6 — Upstream it

A quirk that is worth keeping is worth a pull request, and a PR has its own failure
modes that a working local quirk does not show: bounds in the wrong unit, a wire type
that differs from Z2M's, magic ids, an existing PR for the same model, house style the
maintainers enforce in review. Read `references/upstreaming.md` and audit against it
before anything is pushed.

Three rules from doing this once:

- **Read the upstream contribution docs in full, then audit the diff against them.**
  Skimming them is how the number-bounds and wire-type mistakes got through.
- **Retest on the real device after every code change**, including "harmless"
  refactors, and attach a diagnostics file taken from the code you push.
- **Nothing is forked, pushed or opened without the user's go-ahead, and the PR text
  is the user's own words.** Prepare a fact sheet; the AI policy asks for the rest.

## Pre-purchase checks, honestly

You can establish that a model family is supported by one or both stacks. You cannot
establish what the unit in the box will report, because the manufacturer string is the
matching key and sellers ship the same product under different ones. So the useful
answer has this shape: "Z2M supports several variants under this model; ZHA has a
quirk for two of them; if yours reports a manufacturer string outside that set it will
need a quirk, which is about an hour's work given the Z2M converter."

Do not flatten that into a yes or no. The uncertainty is the finding.

## Reporting

Lead with the classification, not the investigation. For a fleet audit, a table of
device → verdict, with the handful of real gaps expanded underneath. Name the exact
datapoints or clusters involved so the user can check your work — and so a future
session does not have to rediscover them.

Do not explain what a setting *does* from its Z2M label alone. Z2M often exposes just
"Static detection sensitivity" with no description. Find a manual or a hands-on review, or
say the meaning is unknown and suggest a test the user can run.

When you state a gap, say how you know. "Z2M's converter maps dp 110 and ZHA's quirk
has no equivalent attribute" is checkable. "Z2M has better Tuya support" is not.

## In this repo

Quirks live in `custom_zha_quirks/`, loaded via `custom_quirks_path` in
`configuration.yaml`. That directory's README carries the gotchas as they are found —
add to it when a new one costs you time. A quirk worth keeping is worth a pull request
to `zigpy/zha-device-handlers`, which is how it stops being ours to maintain — step 6
and `references/upstreaming.md` are the route. Once it is merged and shipped in the
HA release the Pi runs, delete the local copy, as the README's "Upstreaming" section
says.
