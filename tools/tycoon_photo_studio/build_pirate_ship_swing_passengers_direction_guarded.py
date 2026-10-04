#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Vector

import build_pirate_ship_swing_passengers_direction as directional

V16_FRAME_COUNT = 28
V16_FPS = 8
V16_AMPLITUDE_DEGREES = 35.0
V16_MOTION_PROFILE = "slow_ascent_peak_dwell_fast_descent_v1"
V16_APPROVAL = "Viking V16 / human-approved slower pendulum timing"


def _arg_value(flag: str) -> str:
    argv = sys.argv
    if flag not in argv:
        raise RuntimeError(f"CH_PIRATE_DIRECTIONAL_GUARD_REQUIRED_ARG:{flag}")
    index = argv.index(flag)
    if index + 1 >= len(argv):
        raise RuntimeError(f"CH_PIRATE_DIRECTIONAL_GUARD_MISSING_VALUE:{flag}")
    return argv[index + 1]


def _v16_angles() -> list[float]:
    values: list[float] = [0.0]
    for i in range(1, 9):
        t = i / 8.0
        values.append(V16_AMPLITUDE_DEGREES * math.sin(0.5 * math.pi * t))
    values.extend([V16_AMPLITUDE_DEGREES, V16_AMPLITUDE_DEGREES])
    for i in range(1, 5):
        t = i / 4.0
        values.append(V16_AMPLITUDE_DEGREES * math.cos(0.5 * math.pi * t))
    for i in range(1, 9):
        t = i / 8.0
        values.append(-V16_AMPLITUDE_DEGREES * math.sin(0.5 * math.pi * t))
    values.extend([-V16_AMPLITUDE_DEGREES, -V16_AMPLITUDE_DEGREES])
    for i in range(1, 4):
        t = i / 4.0
        values.append(-V16_AMPLITUDE_DEGREES * math.cos(0.5 * math.pi * t))
    if len(values) != V16_FRAME_COUNT:
        raise RuntimeError(f"CH_PIRATE_V16_FRAME_COUNT_MISMATCH:{len(values)}!={V16_FRAME_COUNT}")
    return values


def _install_v16_timing() -> None:
    core = directional.core
    core.FRAME_COUNT = V16_FRAME_COUNT
    core.FPS = V16_FPS
    core.AMPLITUDE_DEGREES = V16_AMPLITUDE_DEGREES
    core.APPROVED_SWING_ANGLES = _v16_angles()
    core.ANIMATION_CONTRACT = "CH_PIRATE_SHIP_SWING_PASSENGER_V2"


def _install_overlay_and_mask_fixes() -> None:
    core = directional.core
    def stable_preserve_reparent(obj, parent):
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
        passenger_objects = [obj for obj in bpy.context.scene.objects if obj.name.startswith("CHR_PiratePassenger_")]
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

    def assert_passenger_binding_scaled(recipe):
        scale = float(recipe.get("modelScale", 1.0))
        cz = float(recipe["dimensions"]["shipCenterZ"]) * scale
        passengers = [
            obj for obj in bpy.context.scene.objects
            if obj.type == "MESH" and obj.name.startswith("CHR_PiratePassenger_")
        ]
        if not passengers:
            raise RuntimeError("CH_PIRATE_PASSENGER_OVERLAY_EMPTY")
        world_z = [
            (obj.matrix_world @ Vector(corner)).z
            for obj in passengers for corner in obj.bound_box
        ]
        zmin, zmax = min(world_z), max(world_z)
        lower = cz + 0.20 * scale
        upper = cz + 2.40 * scale
        if zmin < lower or zmax > upper:
            raise RuntimeError(
                f"CH_PIRATE_PASSENGER_BINDING_OUT_OF_BOAT:z={zmin:.3f}..{zmax:.3f}:shipCenterZ={cz:.3f}:scale={scale:.3f}"
            )
        return {"status": "ok", "worldZMin": round(zmin, 4), "worldZMax": round(zmax, 4), "modelScale": scale}
    core._assert_passenger_binding = assert_passenger_binding_scaled

    def primary_mask_name(name: str) -> bool:
        return name.startswith(("NearSide_", "FarSide_", "TransversePivotAxle", "NearBearingHousing", "NearBearingHub", "FarBearingHousing", "FarBearingHub", "PivotColorCap_", "TopCenterSign", "PirateHat", "BoardingDeckFrontFascia", "BoardingDeckPanel_", "BoardingDeckTopAccent"))
    core._primary_mask_name = primary_mask_name


def _patch_json(path: Path, patcher) -> None:
    if not path.is_file(): return
    data = json.loads(path.read_text(encoding="utf-8"))
    patcher(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _patch_manifests(output: Path, direction: str) -> None:
    cycle_ms = 3500
    angles = [round(v, 6) for v in _v16_angles()]
    def common(data):
        data["frameCount"] = V16_FRAME_COUNT
        data["frameCountPerDirection"] = V16_FRAME_COUNT
        data["fps"] = V16_FPS
        data["cycleDurationMs"] = cycle_ms
        data["amplitudeDegrees"] = V16_AMPLITUDE_DEGREES
        data["anglesDegrees"] = angles
        data["motionProfile"] = V16_MOTION_PROFILE
        data["swingApproval"] = V16_APPROVAL
    def color(data):
        common(data)
        data.setdefault("primaryColor", {})["target"] = "fixed A-frame bases / muletas + fixed carnival decorations"
        data.setdefault("secondaryColor", {})["target"] = "boat hull, seats and boat-mounted decoration"
        data["maskSeparation"] = "primary_and_secondary_disjoint"
    def overlay(data):
        common(data)
        data["motionParent"] = "DominantPassengerShip"
        data["bindingMode"] = "explicit_boat_parent_with_parent_inverse"
        data["direction"] = direction
    def metadata(data):
        common(data)
        data["animationContract"] = "CH_PIRATE_SHIP_SWING_PASSENGER_V2"
        data["passengerMotionParent"] = "DominantPassengerShip"
        data.setdefault("colorMasks", {})["primary"] = "fixed A-frame bases / muletas + fixed carnival decorations"
        data["colorMasks"]["secondary"] = "boat hull, seats and boat-mounted decoration"
    def swing(data):
        common(data)
        data["contract"] = "CH_PIRATE_SHIP_SWING_PASSENGER_V2"
        data["totalOccupiedFrames"] = V16_FRAME_COUNT * 4
        data["totalPassengerOverlayFrames"] = V16_FRAME_COUNT * 4
    _patch_json(output / "color_mask_manifest.json", color)
    _patch_json(output / "passenger_overlay_manifest.json", overlay)
    _patch_json(output / "studio_metadata.json", metadata)
    _patch_json(output / "swing_frames_manifest.json", swing)
    _patch_json(output / f"swing_frames_{direction}.json", swing)


def _canonicalize_proxy(output: Path, direction: str) -> None:
    source = output / f"proxy_{direction}.png"
    canonical = output / "proxy_south.png"
    if not source.is_file(): raise RuntimeError(f"CH_PIRATE_DIRECTIONAL_PROXY_MISSING:{source}")
    if source != canonical: shutil.copyfile(source, canonical)
    report_path = output / "proxy_report.json"
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["path"] = str(canonical)
        report["sha256"] = hashlib.sha256(canonical.read_bytes()).hexdigest()
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> None:
    direction = _arg_value("--direction").lower()
    output = Path(_arg_value("--output")).resolve()
    _install_v16_timing()
    _install_overlay_and_mask_fixes()
    directional.main()
    _patch_manifests(output, direction)
    _canonicalize_proxy(output, direction)

if __name__ == "__main__":
    main()
