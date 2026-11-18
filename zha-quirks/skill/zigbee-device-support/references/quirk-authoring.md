# Writing a ZHA quirk (v2 builder)

Quirks v2 is declarative chaining. A Tuya datapoint quirk is close to a transcription
of the Z2M datapoint table, which is why porting is cheap once the table is right.

```python
import zigpy.types as t
from zigpy.zcl import foundation

from zhaquirks.builder import BinarySensorDeviceClass, EntityType, NumberDeviceClass
from zhaquirks.tuya import TUYA_CLUSTER_ID
from zhaquirks.tuya.builder import TuyaQuirkBuilder

(
    TuyaQuirkBuilder("<manufacturer>", "<model>")
    .tuya_soil_moisture(dp_id=3)
    .tuya_temperature(dp_id=5, scale=10)
    .tuya_battery(dp_id=15)
    .skip_configuration()
    .add_to_registry()
)
```

`.applies_to("<other-manufacturer>", "<model>")` adds more matching strings.
Non-Tuya devices use `QuirkBuilder` with `.replaces()` / `.adds()` and a
`CustomCluster` carrying the manufacturer attributes.

## Licensing

`zigbee-herdsman-converters` is MIT, `zha-device-handlers` is Apache-2.0 — compatible,
and keep the notice on anything copied verbatim. In practice nothing is copied: you
are transferring facts (cluster IDs, datapoint numbers, scaling), which are not
copyrightable, and JS to Python is a rewrite regardless. Upstreaming a Z2M-derived
quirk is routine and welcome.

## Gotchas that cost real time

### Entity naming: always pass a translation_key

HA names an entity from a resolved translation, **then the device class**, then
`fallback_name` (`homeassistant/components/zha/entity.py`). An entity with a device
class and no `translation_key` therefore takes the device class name and ignores
`fallback_name` entirely — which is how five distinct controls end up displayed as
"Duration", "Duration", "Moisture", "Moisture" and "Temperature delta".

Pass a `translation_key` even though yours will not exist in ZHA's `strings.json`. An
unresolvable key is exactly what makes HA fall through to `fallback_name`; HA's own
code comments mark that branch as the custom-quirk path. Check `strings.json` first if
a real key fits — a resolved key gets proper translations. Upstream's maintainers ask
for this explicitly on PRs: reuse an existing key when its string is right
(`motion_sensitivity`, `temperature_offset`, `humidity_offset`, ...), and do not add
device prefixes to new ones. Keys are looked up per platform, so a `number` key does
not exist for a `select`.

Keep `fallback_name` in sentence case ("Soil moisture", not "Soil Moisture") and
`translation_key` and `fallback_name` last in every entity call.

Number entities additionally *require* a `device_class` or a `translation_key`, and
will raise at registration without one.

### Tuya config values read back empty

A Tuya MCU only volunteers a datapoint when it changes, and no ZCL attribute read
reaches a datapoint — they are not real attributes. A setting already stored on the
device is therefore invisible: the entity exists but has no value.

`.tuya_enchantment(data_query_spell=True)` asks the MCU to dump everything it holds.
It coexists with `.skip_configuration()` (they run in different phases). On a sleepy
battery device the request lands on the next check-in, not immediately, so blank boxes
right after a restart are expected.

### Raw versus display scaling

Two different conventions, easy to mix up:

- `tuya_temperature(dp_id=5, scale=10)` — `scale` converts the datapoint to the ZCL
  cluster's unit. ZCL temperature is hundredths of a degree, so a value the device
  sends in tenths needs `scale=10`.
- `tuya_number(min_value=-2, max_value=2, step=0.1, multiplier=0.1)` — `min_value`,
  `max_value` and `step` are in **display (HA) units**, and `multiplier` is the
  raw-to-display factor. The entity shows `raw * multiplier` and writes
  `int(value / multiplier)`. A device that takes raw ±20 in tenths of a degree is
  therefore `min_value=-2, max_value=2`.

An earlier version of this file said the bounds were raw. That was wrong, and it
shipped `-20..20` with `multiplier=0.1`: HA then offers ±20 °C and would write raw ±200.
Upstream's `.github/copilot-instructions.md` ("Number `multiplier` semantics") and
`zha/application/platforms/number/__init__.py` (`_attr_native_min_value = min_value`)
both agree on display units.

Get bounds from Z2M's `src/lib/tuya.ts` exposes rather than inventing them, then
convert them to display units. Pin it in a test, because a mistake here type-checks and
only shows up as a slider with the wrong range:

```python
number = by_suffix["temperature_calibration"]  # NumberMetadata
assert (number.min, number.max) == (-2, 2) and number.multiplier == 0.1
```

### Enum entities: keep the wire type of the attribute

`.enum(enum_class=...)` only supplies the options of the select. Do not retype a
standard attribute as `t.enum8` to get an enum class: zigpy then writes it as ZCL type
`0x30`, while the standard attribute (IAS zone `0x0013`) and Z2M's write use `uint8`
(`0x20`). A strict device may refuse the mismatch, and nothing at import or in a
snapshot shows it.

Leave a standard attribute as it is. For a private one, declare it with the type
Z2M writes — read the converter, `{61441: {value, type: 0x20}}` means `t.uint8_t`:

```python
keep_time: Final = ZCLAttributeDef(id=0xF001, type=t.uint8_t, manufacturer_code=None)
```

ZHA's select maps the cached integer through the enum on read and writes the enum
member, which serialises by the attribute's type, so the entity works either way.

`zigpy.zcl.foundation.DataType.from_python_type(cls).type_id` tells you the wire type
of any class. Check what actually goes out with a mocked request, not by reading code:

```python
with mock.patch.object(cluster, "request", new=mock.AsyncMock(return_value=[[
        foundation.WriteAttributesStatusRecord(foundation.Status.SUCCESS)]])) as request:
    await cluster.write_attributes({"keep_time": MyEnum.Long})
assert request.call_args.kwargs["manufacturer"] is None
assert cluster.find_attribute("keep_time").type is t.uint8_t
```

### Manufacturer code

A private attribute is read and written with a manufacturer code only if the
definition says so. `manufacturer_code=0x117C` sends one; `manufacturer_code=None`
states, explicitly, that none is sent (even on a manufacturer-specific cluster). The
older `is_manufacturer_specific=True` is deprecated. Attribute ids at `0x8000` and above
on a standard cluster look manufacturer-specific, so upstream's review bot asks about
them — decide from what the Z2M converter does (`entity.write(cluster, {...}, {manufacturerCode})`
or not), say so in a comment, and prove it with the mocked request above.

### No magic numbers

Upstream's style guide rejects bare cluster, attribute and command ids. Use
`IasZone.cluster_id`, `IasZone.AttributeDefs.current_zone_sensitivity_level.name` or
`.id`, `OccupancySensing.AttributeDefs.pir_o_to_u_delay.name` (also for
`unique_id_suffix`). The one place a literal id is right is the definition of a new
private attribute.

### Types

zigpy's signed types are `t.int16s`, `t.int32s` — not `int16_t`, which exists only
unsigned (`t.uint16_t`). Guessing here fails at import.

### Polarity

Check what a Z2M expose means before inverting it. `src/lib/exposes.ts` has the
definition: `dry: () => new Binary("dry", access.STATE, true, false)` means `true` is
dry. HA's `moisture` binary device class is the opposite convention — it renders *on*
as "Wet" — and it is the only device class that renders Wet/Dry at all. So a "dry"
datapoint surfaced through it needs inverting:

```python
.tuya_dp_attribute(
    dp_id=106, attribute_name="soil_wet", type=t.Bool,
    converter=lambda x: t.Bool(not x),
    access=foundation.ZCLAttributeAccess.Read | foundation.ZCLAttributeAccess.Report,
)
.binary_sensor("soil_wet", TUYA_CLUSTER_ID,
               device_class=BinarySensorDeviceClass.MOISTURE,
               translation_key="soil_condition", fallback_name="Soil")
```

### Sleepy devices

Battery end devices (`mac_capability_flags` without rx-on-when-idle) are not awake for
the bind-and-configure-reporting pass. `.skip_configuration()` avoids a startup delay
that achieves nothing. Most upstream battery-device quirks use it.

The catch: ZHA gates its initial attribute read on the same flag, so a quirk with config
entities over real ZCL attributes (a select on an IAS zone attribute, say) and
`.skip_configuration()` shows them blank for ever -- nothing ever asks the device. Tuya
datapoint quirks are unaffected, since datapoints are not readable anyway and rely on
`data_query_spell`. For ZCL-attribute entities leave the flag out: the value is read once
when the device is first awake after a Reconfigure or a return from unavailable, then
served from zigpy's cache, and with no reporting configured nothing polls the battery.

A sleepy device also applies a written setting at its next check-in, which can take
minutes, and some settings are write-only so the box stays blank or stale. Neither is a
failed write. Judge a write by an effect the user can see (an LED switch, a keep time),
not by the entity reading back.

### Mirrored entities: keep the one whose label is true

ZHA builds one entity per cluster, so a presence sensor often shows one signal twice: the
IAS zone (device class `motion`) and OccupancySensing (`occupancy`) flip together, about
200 ms apart. The history of the two entities confirms it. Neither is more accurate, so
keep the one whose device class matches what the hardware measures (a presence radar is
`occupancy`, not `motion`) and hide the other. Do not keep the old one just because the
user already renamed it.

```python
.prevent_default_entity_creation(endpoint_id=1, cluster_id=IasZone.cluster_id)
# Hide only some entities of a cluster, e.g. its config numbers but not its sensor:
.removes_entity(EntityFilter(platform=EntityPlatform.NUMBER, endpoint_id=1,
                             cluster_id=OccupancySensing.cluster_id))
```

`EntityFilter` and `EntityPlatform` come from `zhaquirks.builder`. A hidden entity is
orphaned in the registry, so tell the user to delete it and rename the one that stays
(same hand-off as an attribute rename). Hiding the entity does not stop ZHA configuring
the cluster, so leave `.skip_configuration()` out when the kept entity relies on it.

### Renaming an attribute orphans its entity

The attribute name is part of the entity's unique_id. Renaming one in a published
quirk leaves the old entity stranded and creates a fresh one, losing its history. Fine
early on; tell the user to delete the orphan.

### Resolving in a test

`DEVICE_REGISTRY.resolve(device)` from `zha.quirks`, after `zhaquirks.setup()`.
`zigpy.quirks.get_device` is deprecated and reaches the legacy v1 registry, so a v2
quirk will appear not to match. `scripts/verify_quirk.py` does this correctly.

## Deploying

Quirks load from the directory named by `custom_quirks_path` under `zha:` in
`configuration.yaml`. The path is validated with `cv.isdir`, so it must exist before
HA starts — keep a README in it so git tracks the folder. HA must restart to pick up a
change; new entities occasionally need the device re-interviewed ("Reconfigure" on its
page). HA writes `__pycache__/` there, which belongs in `.gitignore`.

Enable `zigpy.quirks` debug logging to confirm which quirk matched a device.

## When a quirk is not the answer

Some Z2M support lives in zigbee-herdsman rather than a converter — interview
workarounds, nonstandard join behaviour, stack-level responses a device needs to
complete pairing. A quirk cannot reach those. Recognise it and say so; the fix is a
zigpy change, or running that device on Z2M.
