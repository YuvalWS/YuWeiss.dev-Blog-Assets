"""HOBEIAN ZG-303Z soil moisture sensor.

ZHA ships no quirk for this device, so it resolved as a bare temperature sensor and
the Tuya MCU cluster (0xEF00) in its signature was ignored entirely. Everything the
sensor offers beyond temperature, humidity and battery rides on that cluster.

The soil reading itself already reached HA on the standard humidity cluster (0x0405),
and datapoint 3 carries the identical value at the identical scale -- both read 1900
(19.0%) at the same instant. Two entities for one measurement, one of them labelled
as air humidity, which it is not. So 0x0405 is removed here and the reading is taken
from the datapoint onto the soil moisture cluster (0x0408) instead, where the device
class and naming are right. Anything referring to the old humidity entity has to move
with it: the watering automation does so in the same commit, and the kitchen
dashboard card is in .storage, so it is changed by hand in the HA UI.

The datapoints also carry the device's own configuration: the threshold below which
it calls the soil dry, a soil calibration offset, a temperature trim, and the two
sampling intervals that govern how hard it works its battery. The dry flag read
"true" at 19%, so that stored threshold sits above 19 and was previously unreachable.

Datapoint numbering is ported from the Zigbee2MQTT converter that matches this
device's signature: `zigbeeModel: ["ZG-303Z", "AY-303Z", "AY-302Z"]` (model CS-201Z)
in zigbee-herdsman-converters `src/devices/tuya.ts`. Beware that a *second* converter
there is also called ZG-303Z but fingerprints on modelID TS0601 with manufacturer
_TZE200_wqashyqo, and carries a different datapoint table (temperature 103, soil 107,
battery 108). Ours reports modelID "ZG-303Z", so the table below is the right one.

Left alone deliberately: temperature (0x0402) and battery (0x0001) both report
correctly on their stock clusters, and re-sourcing them from datapoints would risk a
working entity to gain nothing. Datapoint 105 (humidity calibration) is dropped along
with the humidity entity it would have trimmed.

Every entity here carries a translation_key even though none of them exist in ZHA's
strings.json, and that is deliberate rather than an oversight. HA's naming order (see
`zha/entity.py`) is: a resolved translation, else the device class name, else
fallback_name. An entity with a device class and no translation_key therefore takes
the device class name and ignores fallback_name entirely -- which is how two sliders
both ended up called "Moisture" and two boxes both called "Duration". Setting a key
that does not resolve pushes HA down to fallback_name, which is the path its own code
comments mark as being for custom quirks.
"""

import zigpy.types as t
from zigpy.zcl import foundation

from zhaquirks.builder import (
    PERCENTAGE,
    BinarySensorDeviceClass,
    EntityType,
    NumberDeviceClass,
    UnitOfTemperature,
    UnitOfTime,
)
from zhaquirks.tuya import TUYA_CLUSTER_ID
from zhaquirks.tuya.builder import TuyaQuirkBuilder

(
    TuyaQuirkBuilder("HOBEIAN", "ZG-303Z")
    # dp 3 -- soil moisture, raw percent, onto the standard soil moisture cluster
    # (0x0408) that the device does not itself advertise.
    .tuya_soil_moisture(dp_id=3)
    # The same measurement also arrives on the standard humidity cluster, mislabelled
    # as air humidity. Dropping it leaves one entity for one reading.
    .removes(0x0405)
    # dp 106 -- the device's own verdict on whether the soil is dry, judged against
    # the threshold in dp 110 below. Inverted on the way in: the datapoint is a "dry"
    # flag, whereas HA's moisture device class reads on as "Wet", and that device
    # class is what renders the state as Wet/Dry rather than Problem/OK.
    .tuya_dp_attribute(
        dp_id=106,
        attribute_name="soil_wet",
        type=t.Bool,
        converter=lambda x: t.Bool(not x),
        access=foundation.ZCLAttributeAccess.Read
        | foundation.ZCLAttributeAccess.Report,
    )
    .binary_sensor(
        "soil_wet",
        TUYA_CLUSTER_ID,
        device_class=BinarySensorDeviceClass.MOISTURE,
        entity_type=EntityType.STANDARD,
        translation_key="soil_condition",
        fallback_name="Soil",
    )
    # dp 110 -- the moisture level below which the device calls the soil dry. This is
    # what drives the flag above, so it is the one knob that changes the device's own
    # behaviour rather than just how a number is presented.
    .tuya_number(
        dp_id=110,
        type=t.uint16_t,
        attribute_name="soil_warning",
        min_value=0,
        max_value=100,
        step=1,
        unit=PERCENTAGE,
        device_class=NumberDeviceClass.MOISTURE,
        translation_key="soil_dry_threshold",
        fallback_name="Dry threshold",
    )
    # dp 102 -- an offset added to the soil reading. Worth knowing before reaching for
    # it: this shifts the band, it does not widen it, so it cannot fix a reading whose
    # range looks compressed.
    .tuya_number(
        dp_id=102,
        type=t.int16s,
        attribute_name="soil_calibration",
        min_value=-30,
        max_value=30,
        step=1,
        unit=PERCENTAGE,
        device_class=NumberDeviceClass.MOISTURE,
        translation_key="soil_calibration",
        fallback_name="Soil calibration",
    )
    # dp 104 -- temperature trim. The device sends this one in tenths, so the bounds
    # below are raw and the multiplier turns them into the +/-2.0 degrees it accepts.
    .tuya_number(
        dp_id=104,
        type=t.int16s,
        attribute_name="temperature_calibration",
        min_value=-20,
        max_value=20,
        step=0.1,
        multiplier=0.1,
        unit=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
        translation_key="temperature_calibration",
        fallback_name="Temperature calibration",
    )
    # dp 112 / dp 111 -- how often the device samples. These are the battery knobs:
    # the probe is the expensive part, so soil sampling costs more than temperature.
    .tuya_number(
        dp_id=112,
        type=t.uint16_t,
        attribute_name="soil_sampling",
        min_value=5,
        max_value=3600,
        step=1,
        unit=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        translation_key="soil_sampling_interval",
        fallback_name="Soil sampling interval",
    )
    .tuya_number(
        dp_id=111,
        type=t.uint16_t,
        attribute_name="temperature_sampling",
        min_value=5,
        max_value=3600,
        step=1,
        unit=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        translation_key="temperature_sampling_interval",
        fallback_name="Temperature sampling interval",
    )
    # The MCU only volunteers a datapoint when it changes, so the config values above
    # start blank and would stay that way. The data query spell asks it to dump every
    # datapoint it holds, which is the only way to learn the settings already on the
    # device -- there is no ZCL attribute read that reaches them.
    .tuya_enchantment(data_query_spell=True)
    # Sleepy battery device: it is not awake for the usual bind-and-configure-
    # reporting pass, and attempting it just delays startup.
    .skip_configuration()
    .add_to_registry()
)
