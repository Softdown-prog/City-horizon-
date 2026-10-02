"""Guarded seated-passenger overlay for the approved Flame coaster car.

Reuses the reviewed CHActor seated-passenger visual recipe from Viking V15, but fits
it to the two actual Flame car seats and the CH_COASTER_CAR_V1 pose system. The
proxy emits both an occupied composite and a transparent passenger-only diagnostic
layer. Final runtime baking stays gated behind human review, like the Viking ride.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "tools" / "ch_blender"))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402
import shape_authoring as shape  # noqa: E402
import build_coaster_car_flame_pose_atlas_v1_guarded as atlas  # noqa: E402

v5 = atlas.v5
track = atlas.track

ASSET_ID = "ride.coaster.car_flame_passenger_overlay_v1"
PASSENGER_CONTRACT = "CH_COASTER_PASSENGER_OVERLAY_V1"
CAR_CONTRACT = atlas.CAR_CONTRACT
TRACK_CONTRACT = atlas.TRACK_CONTRACT
STYLE_ID = atlas.STYLE_ID
CAPACITY = 2
FOOTPRINT = atlas.FOOTPRINT
PROXY_HEADING_DEG = 45.0
PROXY_PITCH_DEG = 0.0

# Same restrained CHActor palette family used by the reviewed Viking V15 overlay.
JACKET_COLORS = (
    (0.08, 0.50, 0.24, 1.0),
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


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args(argv)


def _material(name: str, rgba):
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    return bs.make_material(name, list(rgba), 0.76, 0.0)


def _sphere(name: str, location, radius: float, material):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=12,
        ring_count=8,
        radius=radius,
        location=location,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    obj["ch.semanticRole"] = "coaster.passenger"
    obj["passengerOverlayContract"] = PASSENGER_CONTRACT
    return obj


def _limb(name: str, a, b, radius: float, material):
    return v5.add_bar_between(
        name,
        a,
        b,
        radius,
        material,
        "coaster.passenger",
        vertices=10,
    )


def _make_passenger_materials():
    mats = {
        "skin": _material("CoasterPassengerSkin", SKIN),
        "hair": _material("CoasterPassengerHair", HAIR),
        "shoes": _material("CoasterPassengerShoes", SHOES),
    }
    for index, rgba in enumerate(JACKET_COLORS):
        mats[f"jacket_{index}"] = _material(f"CoasterPassengerJacket{index}", rgba)
    for index, rgba in enumerate(PANTS_COLORS):
        mats[f"pants_{index}"] = _material(f"CoasterPassengerPants{index}", rgba)
    return mats


def _build_seated_actor(slot: int, seat_x: float, seat_y: float, mats: dict):
    """Compact Viking-V15-style CHActor, reoriented to face Flame car +Y."""
    tag = f"CHR_CoasterPassenger_{slot:02d}"
    jacket = mats[f"jacket_{slot % len(JACKET_COLORS)}"]
    pants = mats[f"pants_{slot % len(PANTS_COLORS)}"]
    skin = mats["skin"]
    hair = mats["hair"]
    shoes = mats["shoes"]

    pelvis = Vector((seat_x, seat_y + v5.CAR_LENGTH * 0.012, v5.FLOOR_Z + 0.29))
    chest = Vector((seat_x, seat_y + v5.CAR_LENGTH * 0.020, v5.FLOOR_Z + 0.57))
    head = Vector((seat_x, seat_y + v5.CAR_LENGTH * 0.030, v5.FLOOR_Z + 0.86))

    authored = []
    torso = shape.add_rounded_box(
        f"{tag}_Torso",
        location=tuple(chest),
        dimensions=(v5.CAR_WIDTH * 0.115, v5.CAR_LENGTH * 0.105, 0.32),
        material=jacket,
        role="coaster.passenger",
        bevel=0.045,
    )
    torso.rotation_euler[0] = math.radians(-4.0)
    authored.append(torso)
    authored.append(_sphere(f"{tag}_Head", tuple(head), 0.115, skin))
    authored.append(_sphere(
        f"{tag}_Hair",
        (head.x, head.y - 0.006, head.z + 0.055),
        0.120,
        hair,
    ))

    # Arms bend forward/down into the existing over-shoulder restraint/lap area.
    for side in (-1, 1):
        x = chest.x + side * v5.CAR_WIDTH * 0.060
        shoulder = (x, chest.y, chest.z + 0.055)
        elbow = (x, chest.y + v5.CAR_LENGTH * 0.060, chest.z - 0.075)
        hand = (x, chest.y + v5.CAR_LENGTH * 0.090, chest.z - 0.165)
        authored.append(_limb(f"{tag}_UpperArm_{side:+d}", shoulder, elbow, 0.040, jacket))
        authored.append(_limb(f"{tag}_ForeArm_{side:+d}", elbow, hand, 0.034, jacket))
        authored.append(_sphere(f"{tag}_Hand_{side:+d}", hand, 0.039, skin))

    # Thighs point toward the front of the car (+Y), then shins drop into the footwell.
    for side in (-1, 1):
        x = pelvis.x + side * v5.CAR_WIDTH * 0.038
        hip = (x, pelvis.y, pelvis.z)
        knee = (x, pelvis.y + v5.CAR_LENGTH * 0.125, pelvis.z - 0.045)
        ankle = (x, pelvis.y + v5.CAR_LENGTH * 0.145, v5.FLOOR_Z + 0.13)
        toe = (x, pelvis.y + v5.CAR_LENGTH * 0.205, v5.FLOOR_Z + 0.12)
        authored.append(_limb(f"{tag}_Thigh_{side:+d}", hip, knee, 0.050, pants))
        authored.append(_limb(f"{tag}_Shin_{side:+d}", knee, ankle, 0.043, pants))
        authored.append(_limb(f"{tag}_Shoe_{side:+d}", ankle, toe, 0.046, shoes))

    marker = bpy.data.objects.new(f"{tag}_SeatMarker", None)
    bpy.context.scene.collection.objects.link(marker)
    marker.location = tuple(pelvis)
    marker["seatSlot"] = slot
    marker["occupantType"] = "CHActor"
    marker["paletteIndex"] = slot % len(JACKET_COLORS)
    return authored, marker


def add_passengers():
    mats = _make_passenger_materials()
    seat_y = -v5.CAR_LENGTH * 0.11
    passengers = []
    slots = []
    markers = []
    for slot, seat_x in enumerate((-v5.CAR_WIDTH * 0.19, v5.CAR_WIDTH * 0.19)):
        meshes, marker = _build_seated_actor(slot, seat_x, seat_y, mats)
        passengers.extend(meshes)
        markers.append(marker)
        slots.append({
            "slotId": slot,
            "seatColumn": slot,
            "localPosition": [round(seat_x, 5), round(seat_y, 5), round(v5.FLOOR_Z + 0.29, 5)],
            "forwardAxis": "+Y",
            "paletteIndex": slot % len(JACKET_COLORS),
        })
    return passengers, markers, slots


def _set_visibility(meshes, visible: bool):
    for obj in meshes:
        obj.hide_render = not visible


def _render(scene, authored, profile, output: Path, name: str, direction: str):
    return scene_gate.render_proxy(
        scene=scene,
        authored=authored,
        output_path=output / name,
        profile=profile,
        asset_id=ASSET_ID,
        direction=direction,
    )


def _write_manifest(output: Path, slots: list[dict], *, stage: str):
    payload = {
        "contract": PASSENGER_CONTRACT,
        "assetId": ASSET_ID,
        "carContract": CAR_CONTRACT,
        "trackContract": TRACK_CONTRACT,
        "styleId": STYLE_ID,
        "capacityPerCar": CAPACITY,
        "seatSlots": slots,
        "actorSource": "CHActor",
        "visualRecipeSource": "CH_VIKING_PASSENGER_OVERLAY_V1",
        "paletteMode": "stable_per_visitor",
        "fillPolicy": "left_to_right_next_free_slot",
        "motionParent": "car_pose_centerline_sample",
        "posePolicy": "passengers_share_exact_car_heading_pitch_transform",
        "stage": stage,
        "runtimePromoted": False,
    }
    (output / "passenger_overlay_manifest.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    studio = bs.load_json(args.studio_preset)
    profile = scene_gate.load_profile(args.preflight_profile)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    shape.load_contract()
    bs.clear_scene()
    scene = bs.configure_scene(studio, (512, 512), str(output))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    car_meshes = atlas.build_generic_car()
    passenger_meshes, markers, slots = add_passengers()
    authored = car_meshes + passenger_meshes
    root = bs.create_asset_root(authored + markers)
    root["assetId"] = ASSET_ID
    root["cameraContract"] = "CH_CAMERA_V1"
    root["trackContract"] = TRACK_CONTRACT
    root["carContract"] = CAR_CONTRACT
    root["passengerOverlayContract"] = PASSENGER_CONTRACT
    root["rideCapacityPerCar"] = CAPACITY
    root["styleId"] = STYLE_ID
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    base_matrices = atlas.capture_base_matrices(authored)
    atlas.apply_pose(authored, base_matrices, PROXY_HEADING_DEG, PROXY_PITCH_DEG)
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.34)
    bpy.context.view_layer.update()

    _write_manifest(output, slots, stage=args.stage)
    (output / "studio_metadata.json").write_text(json.dumps({
        "contract": "CH_STUDIO_METADATA_V1",
        "assetId": ASSET_ID,
        "cameraContract": "CH_CAMERA_V1",
        "studioPreset": str(args.studio_preset),
        "qualityStage": args.stage,
        "runtimeRepresentation": "2D_RGBA_pre_rendered_passenger_overlay",
        "poseContract": CAR_CONTRACT,
        "passengerOverlayContract": PASSENGER_CONTRACT,
        "capacityPerCar": CAPACITY,
        "reviewPose": {"headingDegrees": PROXY_HEADING_DEG, "pitchDegrees": PROXY_PITCH_DEG},
    }, indent=2), encoding="utf-8")

    report = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=FOOTPRINT,
        profile=profile,
        asset_id=ASSET_ID,
        report_path=output / "preflight_report.json",
    )
    scene_gate.require_pass(report)

    if args.stage == "preflight":
        return
    if args.stage == "proxy":
        composite = _render(scene, authored, profile, output, "occupied_proxy_south.png", "south")
        (output / "proxy_south.png").write_bytes((output / "occupied_proxy_south.png").read_bytes())
        composite["path"] = str(output / "proxy_south.png")
        composite["pose"] = {"headingDegrees": PROXY_HEADING_DEG, "pitchDegrees": PROXY_PITCH_DEG}
        composite["capacityPerCar"] = CAPACITY
        composite["visualRecipeSource"] = "CH_VIKING_PASSENGER_OVERLAY_V1"
        (output / "proxy_report.json").write_text(json.dumps(composite, indent=2), encoding="utf-8")

        # Diagnostic transparent rider layer, matching the Viking V15 review flow.
        old_car = [obj.hide_render for obj in car_meshes]
        _set_visibility(car_meshes, False)
        _set_visibility(passenger_meshes, True)
        _render(scene, passenger_meshes, profile, output, "passengers_proxy_south.png", "south")
        for obj, hidden in zip(car_meshes, old_car):
            obj.hide_render = hidden
        return

    raise RuntimeError(
        "CH_COASTER_PASSENGER_OVERLAY_V1_FINAL_GATED: review proxy before baking all 40 occupied poses")


if __name__ == "__main__":
    main()
