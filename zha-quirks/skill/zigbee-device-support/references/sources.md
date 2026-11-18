# Where the truth lives, and how to read it

Both projects are the authority on themselves, and both move weekly. Read the source
rather than recalling it — a remembered datapoint number that is wrong will be applied
confidently and produce nonsense values.

## Zigbee2MQTT: the converters

Device definitions live in `zigbee-herdsman-converters`, one TypeScript file per
vendor:

```bash
curl -sS -o /tmp/tuya.ts \
  https://raw.githubusercontent.com/Koenkk/zigbee-herdsman-converters/master/src/devices/tuya.ts
```

Useful files: `tuya.ts` (huge — most cheap hardware), `lumi.ts` (Aqara/Xiaomi),
`sonoff.ts`, `third_reality.ts`, `ikea.ts`. When unsure which vendor file holds a
device, fetch a likely one and grep for the manufacturer string; vendor attribution in
the filename does not always match the brand on the box.

Shared definitions matter too. `src/lib/exposes.ts` defines what an expose like
`e.dry()` means — including its polarity, which you need before inverting anything.
`src/lib/tuya.ts` defines the reusable Tuya exposes (`tuya.exposes.soilWarning()` and
friends) with their real min/max/step and units, which is where to get the bounds for
a config entity rather than inventing them.

## ZHA: the quirks

```bash
git clone --depth 1 https://github.com/zigpy/zha-device-handlers /tmp/zha-quirks
grep -rl "<model-or-manufacturer>" /tmp/zha-quirks/zhaquirks --include=*.py
```

A full clone is worth it over fetching single files: you will want to grep for similar
devices to copy patterns from, and to read the builder's source when a keyword's
meaning is unclear. `zhaquirks/tuya/builder/__init__.py` is the `TuyaQuirkBuilder` API;
`zhaquirks/builder/builder.py` is the generic one underneath it.

## Home Assistant: naming and device classes

```bash
curl -sS https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/zha/strings.json
curl -sS https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/zha/entity.py
```

`strings.json` lists every translation key ZHA can resolve. `entity.py` holds the
naming precedence that decides what your entity is actually called — see
`quirk-authoring.md`, this one is a trap.

## The rendered docs

`https://www.zigbee2mqtt.io/devices/<MODEL>.html` is the human-readable page for a
device: the exposes list, the firmware notes, the whitelabels. Good for a quick
supported-or-not answer and for writing up a comparison. It is a rendering of the
converter, though, so when you need datapoint numbers or the matching rules, read the
source — the page does not show them.

## When a fetch is blocked

Network egress varies by environment, so try before assuming. When something is
refused, **ask for it to be allowlisted and start on a fallback in the same breath**.
The ask costs nothing if the fallback turns out to be fine, and quietly routing around
a block can leave you reading a worse source than the one you were denied — which the
user would have opened in seconds had they known.

Fallbacks that have worked:

- `zigbee2mqtt.io` refused → converter source on `raw.githubusercontent.com`. Strictly
  more informative, just less pleasant to read. If asking for this one to be
  allowlisted, ask for **`www.zigbee2mqtt.io`**: the bare domain 301-redirects there,
  so allowing only `zigbee2mqtt.io` still leaves every page unreachable.
- `api.github.com` gated → `raw.githubusercontent.com` and `git clone` still worked, so
  fetch known paths directly or clone and grep instead of listing via the API.
- Everything refused → say so plainly and work from what the user can paste. Never
  guess a datapoint table; a wrong number produces values that look like readings.

## How Z2M picks a converter — the trap

This is the mistake that produces a plausible-looking but wrong datapoint table.

A Z2M definition matches a device in one of two ways:

- `zigbeeModel: ["ABC-123"]` — matches on the device's **modelID** alone.
- `fingerprint: tuya.fingerprint("TS0601", ["_TZE200_xxxxxxxx"])` — matches on
  **modelID *and* manufacturerName** together.

Two definitions can carry the same human-readable `model:` name and match completely
different hardware. A real example: searching for `ZG-303Z` finds one definition named
`ZG-303Z` (fingerprinted on modelID `TS0601` + `_TZE200_wqashyqo`) and a second whose
`zigbeeModel` list contains `"ZG-303Z"` but whose `model:` is `CS-201Z`. A device
reporting modelID `ZG-303Z` matches the *second* one. The two use different datapoints
for temperature, soil moisture and battery — picking the wrong one yields values that
look like readings but are not.

So: match against your device's actual signature, not against the name you searched
for. If `zigbeeModel` contains your modelID, that definition wins regardless of what
it is called. If you are relying on a `fingerprint`, the manufacturer string has to
match exactly too.

When both candidate tables agree on some datapoints and differ on others, the agreeing
ones are well-corroborated and the differing ones are where to be careful.

## Tuya manufacturer strings

`_TZE200_`, `_TZE204_`, `_TZ3000_` and friends are the real identity of Tuya-family
hardware. The same physical product ships under many of them — vendors re-flash and
re-badge freely. Consequences worth stating to the user:

- Two units of "the same" sensor can need different converters.
- A pre-purchase check cannot be definitive (see SKILL.md).
- A quirk written for one manufacturer string will not match another. `applies_to()`
  adds more, and upstream quirks often list a dozen.
