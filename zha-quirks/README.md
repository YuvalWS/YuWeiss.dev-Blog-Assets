# ZHA quirks and the skill that writes them

Companion files for [Thinking of Migrating From ZHA to Zigbee2MQTT? Don't Migrate, Quirk!](https://yuweiss.dev/zha-quirk-instead-of-migrating-to-zigbee2mqtt/)

| Folder / file | What it is |
|---|---|
| [`skill/zigbee-device-support/`](skill/zigbee-device-support/) | A Claude Code skill. Compares what a Zigbee device exposes under ZHA with what Zigbee2MQTT gets from the same hardware, and closes the gap by writing and verifying a custom ZHA quirk. |
| [`custom-quirks/hobeian_zg303z.py`](custom-quirks/hobeian_zg303z.py) | The HOBEIAN ZG-303Z soil moisture sensor quirk, exactly as I run it. |

## Install the skill

Copy the folder into your Home Assistant config repo (or into `~/.claude/skills/` to have it in every project):

```bash
mkdir -p .claude/skills
cp -r skill/zigbee-device-support .claude/skills/
```

The skill's own files:

| File | What it does |
|---|---|
| `SKILL.md` | The method: identify the device, read both sides, classify the gap, build the quirk, verify. |
| `references/quirk-authoring.md` | The v2 quirk builder, and the gotchas that cost real time (entity naming, empty Tuya settings, scaling, polarity). |
| `references/sources.md` | Where to read the truth (Z2M converters, ZHA quirks, HA naming code) and how Z2M picks a converter. |
| `references/upstreaming.md` | Turning a working local quirk into a pull request to zigpy/zha-device-handlers: what to read first, the review mistakes to audit for, and the AI policy. |
| `scripts/verify_quirk.py` | Rebuilds a device from its ZHA diagnostics and applies the quirk the way ZHA does. Needs the `zha` and `zha-quirks` versions your HA runs, the docstring has the venv setup. |

## Use a custom quirk

ZHA loads quirks from the folder named in `configuration.yaml`. The folder has to exist before Home Assistant starts, and Home Assistant has to restart to pick up a change:

```yaml
zha:
  custom_quirks_path: /config/custom_zha_quirks/
```

Put the `.py` file in that folder. If new entities don't show up, use **Reconfigure** on the device's page.

## Pull requests

The quirks for the three devices in the post are sent upstream to [zigpy/zha-device-handlers](https://github.com/zigpy/zha-device-handlers). Once a release that carries one lands in your Home Assistant, delete the local copy.

| Device | Pull request |
|---|---|
| HOBEIAN ZG-204Z PIR motion sensor | [#5442](https://github.com/zigpy/zha-device-handlers/pull/5442) (open) |
| HOBEIAN ZG-210Z pressure strap | _to be added_ |
| HOBEIAN ZG-303Z soil moisture sensor | _to be added_ |

`hobeian_zg303z.py` here is the version I run locally. The pull request version of the same quirk differs slightly: it hides the duplicate humidity entity with `prevent_default_entity_creation` instead of removing the cluster, and some entity names changed to match the project's conventions.

## Licensing

The datapoint numbers and scaling come from the [Zigbee2MQTT converters](https://github.com/Koenkk/zigbee-herdsman-converters) (MIT). They are facts about the devices, and the code is a rewrite in Python against [zha-device-handlers](https://github.com/zigpy/zha-device-handlers) (Apache-2.0).
