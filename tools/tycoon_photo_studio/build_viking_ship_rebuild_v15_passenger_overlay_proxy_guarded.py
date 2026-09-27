"""V15 Viking ship swing proxy with a 20-seat CHActor passenger overlay study.

Review-only. The approved V12 ride geometry and V14 12-frame pendulum stay intact.
Twenty deterministic seated CHActor-style riders are parented to BoatRoot so they
share the exact SwingPivot transform. The script emits both occupied composite
frames and transparent passenger-only frames; runtime promotion remains gated on
human review and a final depth-clipped four-direction bake.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

import build_ferris_wheel as fw
import build_scene as bs
import build_viking_ship_guarded as base
import build_viking_ship_rebuild_v12_hull_finish_guarded as v12gate  # noqa: F401
import scene_gate
import viking_ship_rebuild_v9_ship_overhaul_geometry as v9

ANIMATION_CONTRACT = "CH_VIKING_SWING_CH_ACTOR_PASSENGER_PROXY_V1"
PASSENGER_CONTRACT = "CH_VIKING_PASSENGER_OVERLAY_V1"
FRAME_COUNT = 12
FPS = 8
AMPLITUDE_DEGREES = 35.0
CAPACITY = 20

JACKET_COLORS = (
    (0.08, 0.50, 0.24, 1.0),  # canonical CHActor green
    (0.10, 0.36, 0.72, 1.0),
    (0.74, 0.16, 0.18, 1.0),
    (0.86, 0.55, 0.08, 1.0),
    (0.34, 0.20, 0.58, 1.0),
)
PANTS_COLORS = (
    (0.09, 0.25, 0.58, 1.0),
    (0.12, 0.16, 0.22, 1.0),
    (0.23, 0.30, 0.36, 1.0),
    (0.18, 0.36, 0.35, 1.0),
)
SKIN = (0.965, 0.69, 0.53, 1.0)
HAIR = (0.25, 0.13, 0.075, 1.0)
SHOES = (0.06, 0.075, 0.095, 1.0)


def _material(name: str, rgba: tuple[float, float, float, float]):
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    return bs.make_material(name, list(rgba), 0.76, 0.0)


def _sphere(name, location, radius, material, parent):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=radius, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    obj.parent = parent
    return obj


def _limb(name: str, a, b, radius, material, parent):
    return fw.cylinder_between(name, a, b, radius, material, parent, vertices=10)


def _build_seated_actor(parent, slot: int, x: float, y: float, side: int, mats: dict):
    """Compact seated version of CHActor: jacket, pants, hair and articulated limbs."""
    tag = f"CHR_V15_CHActor_{slot:02d}"
    jacket = mats[f"jacket_{slot % len(JACKET_COLORS)}"]
    pants = mats[f"pants_{slot % len(PANTS_COLORS)}"]
    skin = mats["skin"]
    hair = mats["hair"]
    shoes = mats["shoes"]

    # V10 seats face toward -X; keep the rider inside the padded shell and lap bar.
    pelvis = Vector((x - 0.01, y, -0.72))
    chest = Vector((x - 0.015, y, -0.22))
    head = Vector((x - 0.03, y, 0.16))

    torso = fw.box(f"{tag}_Torso", tuple(chest), (0.28, 0.34, 0.46), jacket, 0.075, parent)
    torso.rotation_euler[1] = math.radians(-5.0)
    _sphere(f"{tag}_Head", tuple(head), 0.145, skin, parent)
    _sphere(f"{tag}_Hair", (head.x + 0.015, head.y, head.z + 0.075), 0.151, hair, parent)

    # Arms rest toward the lap restraint. The near/far arm spacing follows each seat bank.
    for arm_side in (-1, 1):
        sy = y + arm_side * 0.16
        shoulder = (chest.x - 0.005, sy, chest.z + 0.12)
        elbow = (chest.x - 0.16, sy, chest.z - 0.04)
        hand = (chest.x - 0.23, sy, chest.z - 0.20)
        _limb(f"{tag}_UpperArm_{arm_side:+d}", shoulder, elbow, 0.055, jacket, parent)
        _limb(f"{tag}_ForeArm_{arm_side:+d}", elbow, hand, 0.045, jacket, parent)
        _sphere(f"{tag}_Hand_{arm_side:+d}", hand, 0.052, skin, parent)

    # Seated thighs extend toward -X, knees bend down, feet stay above the foot rail.
    for leg_side in (-1, 1):
        ly = y + leg_side * 0.105
        hip = (pelvis.x, ly, pelvis.z)
        knee = (pelvis.x - 0.27, ly, pelvis.z - 0.10)
        ankle = (pelvis.x - 0.30, ly, pelvis.z - 0.39)
        toe = (pelvis.x - 0.39, ly, pelvis.z - 0.42)
        _limb(f"{tag}_Thigh_{leg_side:+d}", hip, knee, 0.067, pants, parent)
        _limb(f"{tag}_Shin_{leg_side:+d}", knee, ankle, 0.058, pants, parent)
        _limb(f"{tag}_Shoe_{leg_side:+d}", ankle, toe, 0.060, shoes, parent)

    parent_slot = bpy.data.objects.new(f"{tag}_SlotMarker", None)
    bpy.context.scene.collection.objects.link(parent_slot)
    parent_slot.parent = parent
    parent_slot.location = (x, y, -0.72)
    parent_slot["seatSlot"] = slot
    parent_slot["occupantType"] = "CHActor"
    parent_slot["shirtPaletteIndex"] = slot % len(JACKET_COLORS)
    parent_slot["bank"] = "near" if side < 0 else "far"
    return parent_slot


def _add_passengers(g):
    boat_root = bpy.data.objects.get("BoatRoot")
    if boat_root is None:
        raise RuntimeError("CH_VIKING_V15_BOAT_ROOT_MISSING")

    passenger_root = bpy.data.objects.new("CHR_V15_PassengerOverlayRoot", None)
    bpy.context.scene.collection.objects.link(passenger_root)
    passenger_root.parent = boat_root
    passenger_root["contract"] = PASSENGER_CONTRACT
    passenger_root["capacity"] = CAPACITY
    passenger_root["runtimeLayer"] = "passenger_overlay"
    passenger_root["actorSource"] = "CHActor"
    passenger_root["seatedPose"] = True

    mats = {"skin": _material("CHR_V15_CHActor_Skin", SKIN),
            "hair": _material("CHR_V15_CHActor_Hair", HAIR),
            "shoes": _material("CHR_V15_CHActor_Shoes", SHOES)}
    for index, rgba in enumerate(JACKET_COLORS):
        mats[f"jacket_{index}"] = _material(f"CHR_V15_CHActor_Jacket_{index}", rgba)
    for index, rgba in enumerate(PANTS_COLORS):
        mats[f"pants_{index}"] = _material(f"CHR_V15_CHActor_Pants_{index}", rgba)

    length = v9._ship_length(g)
    half_w = float(g["shipHalfWidth"])
    span = length * 0.50
    bank_y = half_w * 0.50
    slots = []
    slot = 0
    for row in range(10):
        x = -span * 0.5 + span * row / 9.0
        for side in (-1, 1):
            y = side * bank_y
            marker = _build_seated_actor(passenger_root, slot, x, y, side, mats)
            slots.append({
                "slotId": slot,
                "row": row,
                "bank": "near" if side < 0 else "far",
                "localPosition": [round(x, 5), round(y, 5), -0.72],
                "paletteIndex": slot % len(JACKET_COLORS),
            })
            slot += 1
    if slot != CAPACITY:
        raise RuntimeError(f"CH_VIKING_V15_CAPACITY_MISMATCH:{slot}!={CAPACITY}")
    return passenger_root, slots


def _angles():
    return [AMPLITUDE_DEGREES * math.sin((2.0 * math.pi * i) / FRAME_COUNT) for i in range(FRAME_COUNT)]


def _set_passenger_visibility(visible: bool):
    for obj in bpy.context.scene.objects:
        if obj.name.startswith("CHR_V15_CHActor_"):
            obj.hide_render = not visible


def _render(scene, authored, output: Path, profile, asset_id, direction="south"):
    return scene_gate.render_proxy(scene=scene, authored=authored, output_path=output,
                                   profile=profile, asset_id=asset_id, direction=direction)


def main():
    args = base.parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    recipe, studio, scene, root, pivot, ground, authored, out = base.build_for_gate(args)
    out = Path(out)
    passenger_root, slots = _add_passengers(recipe["geometry"])

    root["animationContract"] = ANIMATION_CONTRACT
    root["passengerOverlayContract"] = PASSENGER_CONTRACT
    root["rideCapacity"] = CAPACITY
    root["swingProxyFrameCount"] = FRAME_COUNT
    root["swingProxyFps"] = FPS
    root["swingAmplitudeDegrees"] = AMPLITUDE_DEGREES
    pivot["rotationAxis"] = "Y"
    pivot["motionProfile"] = "pendulum_sinusoidal"

    base.write_metadata(recipe, scene, out)
    metadata_path = out / "studio_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update({
        "stage": "viking_swing_chactor_passenger_overlay_proxy_v15",
        "builder": "tools/tycoon_photo_studio/build_viking_ship_rebuild_v15_passenger_overlay_proxy_guarded.py",
        "animationContract": ANIMATION_CONTRACT,
        "passengerOverlayContract": PASSENGER_CONTRACT,
        "capacity": CAPACITY,
        "seatSlots": slots,
        "actorSource": "assets/characters/ch_actor_green_01",
        "paletteSource": "CHActor clothing-mask runtime concept",
        "runtimePromoted": False,
        "overlayOcclusion": "review_only_passenger_layer_final_bake_requires_depth_clip",
    })
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (out / "passenger_overlay_manifest.json").write_text(json.dumps({
        "contract": PASSENGER_CONTRACT,
        "assetId": "attraction.park_viking_ship.01",
        "capacity": CAPACITY,
        "seatSlots": slots,
        "fillPolicy": "queue_order_next_free_slot",
        "occupancyRange": [0, CAPACITY],
        "actorSource": "CHActor",
        "paletteMode": "stable_per_visitor",
        "parent": "BoatRoot",
        "motionParent": "SwingPivot",
        "runtimePromoted": False,
    }, indent=2), encoding="utf-8")

    pivot.rotation_euler[1] = 0.0
    bpy.context.view_layer.update()
    preflight = scene_gate.run_preflight(scene=scene, authored=None, footprint=recipe["footprint"],
                                         profile=profile, asset_id=recipe["assetId"],
                                         report_path=out / "preflight_report.json")
    scene_gate.require_pass(preflight)
    if args.stage == "preflight":
        base.save_blend(args.save_blend)
        return
    if args.stage != "proxy":
        raise RuntimeError("CH_VIKING_V15_PROXY_ONLY: passenger overlay requires human review")

    angles = _angles()
    composite_names = []
    overlay_names = []
    reports = []
    for index, angle in enumerate(angles):
        pivot.rotation_euler[1] = math.radians(angle)
        bpy.context.view_layer.update()
        composite = f"occupied_south_{index:02d}.png"
        report = _render(scene, None, out / composite, profile, recipe["assetId"])
        reports.append(report)
        composite_names.append(composite)

        # Passenger-only transparent diagnostic layer. Final runtime bake will depth-clip
        # this layer against the hull before promotion, just like other CH overlays.
        base_visibility = []
        for obj in scene.objects:
            if obj.type != "MESH":
                continue
            is_passenger = obj.name.startswith("CHR_V15_CHActor_")
            base_visibility.append((obj, obj.hide_render))
            obj.hide_render = not is_passenger
        overlay = f"passengers_south_{index:02d}.png"
        _render(scene, None, out / overlay, profile, recipe["assetId"])
        overlay_names.append(overlay)
        for obj, hidden in base_visibility:
            obj.hide_render = hidden

    neutral = out / composite_names[0]
    (out / "proxy_south.png").write_bytes(neutral.read_bytes())
    canonical = dict(reports[0]); canonical["path"] = str(out / "proxy_south.png")
    (out / "proxy_report.json").write_text(json.dumps(canonical, indent=2), encoding="utf-8")
    (out / "swing_passenger_proxy_report.json").write_text(json.dumps({
        "contract": ANIMATION_CONTRACT,
        "status": "ok",
        "capacity": CAPACITY,
        "frameCount": FRAME_COUNT,
        "fps": FPS,
        "amplitudeDegrees": AMPLITUDE_DEGREES,
        "anglesDegrees": [round(v, 6) for v in angles],
        "compositeFrames": composite_names,
        "passengerOverlayFrames": overlay_names,
        "runtimePromoted": False,
    }, indent=2), encoding="utf-8")
    (out / "animation_preview_manifest.json").write_text(json.dumps({
        "contract": "CH_ANIMATION_PREVIEW_V1",
        "id": "attraction.park_viking_ship.01.swing_chactor_passengers_v15",
        "reviewOnly": True,
        "frames": composite_names,
        "durationMs": int(round(1000.0 / FPS)),
        "loop": 0,
        "pingPong": False,
        "output": "viking_ship_chactor_passengers_preview.gif",
        "contactSheet": "viking_ship_chactor_passengers_contact_sheet.png",
        "background": [24, 30, 36],
    }, indent=2), encoding="utf-8")

    pivot.rotation_euler[1] = 0.0
    bpy.context.view_layer.update()
    base.save_blend(args.save_blend)
    print("[CH_GATE] Viking V15 20-seat CHActor passenger overlay proxy ready")


if __name__ == "__main__":
    main()
