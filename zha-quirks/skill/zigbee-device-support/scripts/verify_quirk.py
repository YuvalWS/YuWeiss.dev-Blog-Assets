#!/usr/bin/env python3
"""Resolve a custom ZHA quirk against a real device signature and report what it did.

A quirk that imports cleanly can still fail to match the device, or match and quietly
replace a cluster that was working. Both are invisible until HA restarts and something
is missing, so this rebuilds the device from its ZHA diagnostics and applies the quirk
the same way ZHA does, before any of it reaches the Pi.

Needs zha and zha-quirks at the versions the target HA runs -- read them out of the
diagnostics file under integration_manifest.requirements and pin them in a venv:

    uv venv --python 3.13 /tmp/zhaenv
    uv pip install --python /tmp/zhaenv/bin/python "zha==X.Y.Z" "zha-quirks==X.Y.Z"

Usage:
    verify_quirk.py --quirk PATH --diagnostics PATH [--dp N=V ...] [--dp-bool N=V ...]

Exits non-zero if the quirk fails to match, which makes it usable as a pre-commit gate.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from unittest import mock

import attrs
import zigpy.device
import zigpy.types as t
import zigpy.zdo.types as zdo_t

import zhaquirks
from zha.quirks import DEVICE_REGISTRY
from zhaquirks.builder.builder import QuirkBuilder


def load_quirk(path: Path) -> list[QuirkBuilder]:
    """Import a quirk file the way ZHA's custom_quirks_path loader does.

    Returns the builders the file registered. The registry entry does not keep the
    entity definitions in a readable form, the builder does, so capture it on the way.
    """
    builders: list[QuirkBuilder] = []
    original = QuirkBuilder.add_to_registry

    def spy(self, *args, **kwargs):
        builders.append(self)
        return original(self, *args, **kwargs)

    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load quirk from {path}")
    with mock.patch.object(QuirkBuilder, "add_to_registry", spy):
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
    return builders


def print_entities(builders: list[QuirkBuilder]) -> None:
    """Show the entities the quirk adds and the default ones it hides.

    This is where a wrong bound, a missing translation key or an over-broad hide
    filter shows up. Number bounds are in display units.
    """
    shown = (
        "attribute_name", "entity_platform", "entity_type", "device_class",
        "min", "max", "step", "multiplier", "unit", "translation_key",
        "fallback_name",
    )
    print("\nEntities the quirk adds:")
    for builder in builders:
        for meta in builder.entity_metadata:
            fields = {
                k: getattr(meta, k) for k in shown if getattr(meta, k, None) is not None
            }
            print(f"    {type(meta).__name__}: {fields}")
    print("\nDefault entities the quirk hides:")
    for builder in builders:
        for entity_filter in builder.disabled_default_entities:
            fields = {
                k: v
                for k, v in attrs.asdict(entity_filter, recurse=False).items()
                if v is not None
            }
            print(f"    {fields}")


def build_device(diag: dict) -> zigpy.device.Device:
    """Rebuild the device from the 'original_signature' block of ZHA diagnostics.

    The original signature is used rather than the live 'endpoints' block because the
    latter already reflects any quirk currently applied -- feeding that back in would
    test the quirk against its own output.
    """
    data = diag.get("data", diag)
    sig = data["original_signature"]
    ep_id, ep_sig = next(iter(sig["endpoints"].items()))

    dev = zigpy.device.Device(
        mock.MagicMock(), t.EUI64.convert("00:11:22:33:44:55:66:77"), 0x1234
    )
    dev.node_desc = zdo_t.NodeDescriptor(**sig["node_desc"])

    ep = dev.add_endpoint(int(ep_id))
    ep.profile_id = int(ep_sig["profile_id"], 16)
    ep.device_type = int(ep_sig["device_type"], 16)
    for cid in ep_sig["input_clusters"]:
        ep.add_input_cluster(int(cid, 16))
    for cid in ep_sig["output_clusters"]:
        ep.add_output_cluster(int(cid, 16))

    dev.manufacturer = sig["manufacturer"]
    dev.model = sig["model"]
    return dev


def tuya_frame(dp: int, value: int, *, boolean: bool, seq: int) -> bytes:
    """Encode one Tuya datapoint report as the MCU would send it."""
    if boolean:
        return bytes([0x09, seq, 0x02, 0x00, seq, dp, 0x01, 0x00, 0x01, value])
    return bytes([0x09, seq, 0x02, 0x00, seq, dp, 0x02, 0x00, 0x04]) + value.to_bytes(
        4, "big"
    )


def parse_dp(pairs: list[str]) -> list[tuple[int, int]]:
    out = []
    for pair in pairs:
        dp, _, value = pair.partition("=")
        out.append((int(dp), int(value)))
    return out


async def feed_datapoints(ep, values, booleans) -> None:
    cluster = getattr(ep, "tuya_manufacturer", None)
    if cluster is None:
        if values or booleans:
            print("  no Tuya cluster on this device -- nothing to feed")
        return

    def snapshot() -> dict:
        """Read every defined attribute on every cluster, tolerating unset ones.

        Datapoints often land on a standard cluster rather than the Tuya one -- a soil
        or temperature mapping writes to 0x0408 or 0x0402 -- so watching only the Tuya
        cluster would miss the mappings that matter most.
        """
        out = {}
        for cid, cl in ep.in_clusters.items():
            for attr in cl.attributes.values():
                try:
                    value = cl.get(attr.name)
                except (KeyError, AttributeError):
                    continue
                if value is not None:
                    out[f"0x{cid:04x}.{attr.name}"] = value
        return out

    before = snapshot()
    for seq, (dp, value) in enumerate(values, start=1):
        hdr, args = cluster.deserialize(tuya_frame(dp, value, boolean=False, seq=seq))
        cluster.handle_message(hdr, args)
    for seq, (dp, value) in enumerate(booleans, start=len(values) + 1):
        hdr, args = cluster.deserialize(tuya_frame(dp, value, boolean=True, seq=seq))
        cluster.handle_message(hdr, args)

    changed = {k: v for k, v in snapshot().items() if before.get(k) != v}
    if changed:
        print("\nAttributes those datapoints set:")
        for name, value in sorted(changed.items()):
            print(f"    {name:32} = {value}")
    else:
        print(
            "\nNo attribute changed. Either the datapoint numbers are wrong for this "
            "device, or the quirk does not map them."
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quirk", required=True, type=Path)
    ap.add_argument("--diagnostics", required=True, type=Path)
    ap.add_argument("--dp", action="append", default=[], metavar="N=VALUE",
                    help="feed a numeric Tuya datapoint, e.g. --dp 3=37")
    ap.add_argument("--dp-bool", action="append", default=[], metavar="N=0|1",
                    help="feed a boolean Tuya datapoint, e.g. --dp-bool 106=1")
    args = ap.parse_args()

    zhaquirks.setup()
    builders = load_quirk(args.quirk)

    diag = json.loads(args.diagnostics.read_text())
    dev = build_device(diag)

    print(f"device        : {dev.manufacturer} / {dev.model}")
    before = {
        cid: type(c).__name__ for cid, c in dev.endpoints[1].in_clusters.items()
    }

    quirked = DEVICE_REGISTRY.resolve(dev)
    applied = type(quirked) is not zigpy.device.Device
    print(f"quirk applied : {applied}")
    print(f"quirk class   : {type(quirked).__module__}.{type(quirked).__name__}")
    if not applied:
        print(
            "\nThe quirk did not match. Check that the manufacturer and model strings "
            "in the quirk exactly equal the ones above, including case and any "
            "trailing spaces."
        )
        return 1

    ep = quirked.endpoints[1]
    after = {cid: type(c).__name__ for cid, c in ep.in_clusters.items()}

    print("\nendpoint 1 clusters (-- removed, ++ added, ~~ replaced):")
    for cid in sorted(set(before) | set(after)):
        was, now = before.get(cid), after.get(cid)
        if was == now:
            mark, shown = "  ", now
        elif was is None:
            mark, shown = "++", now
        elif now is None:
            mark, shown = "--", was
        else:
            mark, shown = "~~", f"{was} -> {now}"
        print(f"  {mark} 0x{cid:04x}  {shown}")

    replaced = [
        c
        for c in before
        if c in after and before[c] != after[c] and before[c] != "Cluster"
    ]
    if replaced:
        print(
            "\nNote: "
            + ", ".join(f"0x{c:04x}" for c in replaced)
            + " was replaced. If that cluster already produced a working entity, this "
            "changes where its value comes from -- make sure that is intended."
        )

    print_entities(builders)
    asyncio.run(feed_datapoints(ep, parse_dp(args.dp), parse_dp(args.dp_bool)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
