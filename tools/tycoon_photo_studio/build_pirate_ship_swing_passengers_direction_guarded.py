#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import bpy

import build_pirate_ship_swing_passengers_direction as directional


def _arg_value(flag: str) -> str:
    argv = sys.argv
    if flag not in argv:
        raise RuntimeError(f"CH_PIRATE_DIRECTIONAL_GUARD_REQUIRED_ARG:{flag}")
    index = argv.index(flag)
    if index + 1 >= len(argv):
        raise RuntimeError(f"CH_PIRATE_DIRECTIONAL_GUARD_MISSING_VALUE:{flag}")
    return argv[index + 1]


def _install_overlay_and_mask_fixes() -> None:
    core = directional.core

    def stable_preserve_reparent(obj, parent):
        # Preserve the exact world transform and explicitly establish parent
        # inverse. This prevents the passenger overlay from inheriting the
        # swing pivot translation twice when the hierarchy is evaluated.
        world = obj.matrix_world.copy()
        obj.parent = parent
        obj.matrix_parent_inverse = parent.matrix_world.inverted_safe()
        obj.matrix_world = world

    core._preserve_reparent = stable_preserve_reparent

    original_add_passengers = core._add_passengers

    def add_passengers_bound_to_boat(pivot, recipe):
        slots = original_add_passengers(pivot, recipe)
        hull = bpy.data.objects.get("DominantPassengerShip")
        if hull is None:
            raise RuntimeError("CH_PIRATE_OVERLAY_HULL_MISSING")

        passenger_objects = [
            obj for obj in bpy.context.scene.objects
            if obj.name.startswith("CHR_PiratePassenger_")
        ]
        if not passenger_objects:
            raise RuntimeError("CH_PIRATE_OVERLAY_OBJECTS_MISSING")

        for obj in passenger_objects:
            stable_preserve_reparent(obj, hull)
            obj["ch.motionParent"] = "DominantPassengerShip"

        bpy.context.view_layer.update()
        detached = [obj.name for obj in passenger_objects if obj.parent != hull]
        if detached:
            raise RuntimeError(f"CH_PIRATE_OVERLAY_NOT_BOUND_TO_BOAT:{detached[:8]}")
        return slots

    core._add_passengers = add_passengers_bound_to_boat

    def primary_mask_name(name: str) -> bool:
        # PRIMARY COLOR = fixed A-frame bases/muletas plus the fixed carnival
        # decoration carried by that structure. Boat geometry is deliberately
        # excluded so PRIMARY and SECONDARY stay disjoint.
        fixed_prefixes = (
            "NearSide_", "FarSide_", "TransversePivotAxle",
            "NearBearingHousing", "NearBearingHub",
            "FarBearingHousing", "FarBearingHub", "PivotColorCap_",
            "TopCenterSign", "PirateHat",
            "BoardingDeckFrontFascia", "BoardingDeckPanel_",
            "BoardingDeckTopAccent",
        )
        return name.startswith(fixed_prefixes)

    core._primary_mask_name = primary_mask_name


def _patch_manifests(output: Path, direction: str) -> None:
    color_manifest = output / "color_mask_manifest.json"
    if color_manifest.is_file():
        data = json.loads(color_manifest.read_text(encoding="utf-8"))
        primary = data.setdefault("primaryColor", {})
        primary["target"] = "fixed A-frame bases / muletas + fixed carnival decorations"
        secondary = data.setdefault("secondaryColor", {})
        secondary["target"] = "boat hull, seats and boat-mounted decoration"
        data["maskSeparation"] = "primary_and_secondary_disjoint"
        color_manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    overlay_manifest = output / "passenger_overlay_manifest.json"
    if overlay_manifest.is_file():
        data = json.loads(overlay_manifest.read_text(encoding="utf-8"))
        data["motionParent"] = "DominantPassengerShip"
        data["bindingMode"] = "explicit_boat_parent_with_parent_inverse"
        data["direction"] = direction
        overlay_manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    studio_metadata = output / "studio_metadata.json"
    if studio_metadata.is_file():
        data = json.loads(studio_metadata.read_text(encoding="utf-8"))
        masks = data.setdefault("colorMasks", {})
        masks["primary"] = "fixed A-frame bases / muletas + fixed carnival decorations"
        masks["secondary"] = "boat hull, seats and boat-mounted decoration"
        data["passengerMotionParent"] = "DominantPassengerShip"
        studio_metadata.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    # Capture these before the delegated builder consumes --direction.
    direction = _arg_value("--direction").lower()
    output = Path(_arg_value("--output")).resolve()

    _install_overlay_and_mask_fixes()
    directional.main()
    _patch_manifests(output, direction)

    # CH Blender's guarded proxy contract always checks for proxy_south.png.
    # Directional workers additionally emit proxy_<direction>.png; keep that
    # authoritative directional file and provide this compatibility alias so a
    # successful directional bake is not reported as EXPECTED_OUTPUT_MISSING.
    source = output / f"proxy_{direction}.png"
    canonical = output / "proxy_south.png"
    if not source.is_file():
        raise RuntimeError(f"CH_PIRATE_DIRECTIONAL_PROXY_MISSING:{source}")
    if source != canonical:
        shutil.copyfile(source, canonical)


if __name__ == "__main__":
    main()
