"""Guarded CH Blender authoring for the City Horizon steam train.

Asset scope for v1:
    1 steam locomotive with driver cab + 7 passenger coaches.

Planned but intentionally not implemented in this pass:
    - animated steam/smoke overlay
    - coach recolor mask

This is a new agent-authored visual asset and therefore follows:
    preflight -> SOUTH proxy -> human review -> final four-direction bake

The game runtime remains 2D RGBA sprites. Blender/CH Blender is authoring only.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CH_BLENDER = REPO_ROOT / "tools" / "ch_blender"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(CH_BLENDER) not in sys.path:
    sys.path.insert(0, str(CH_BLENDER))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402

CONTRACT = "CITY_HORIZON_STEAM_TRAIN_V1"
ASSET_ID = "vehicle.steam_train.cab_7coaches.01"
DEFAULT_RECIPE = "tools/tycoon_photo_studio/assets/steam_train_cab_7coaches_v1.train.json"


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", default=DEFAULT_RECIPE)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend", default=None)
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    p.add_argument("--preflight-profile", default=None)
    p.add_argument("--approval-proxy-sha", default=None)
    return p.parse_args(argv)


def _empty(name: str, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_mode = "XYZ"
    if parent is not None:
        obj.parent = parent
    return obj


def _box(name, loc, dims, material, bevel=0.04, parent=None):
    obj = bs.add_box(name, loc, dims, material, bevel)
    if parent is not None:
        obj.parent = parent
    return obj


def _cylinder(name, loc, radius, depth, material, *, parent=None, vertices=24, rotation=(0.0, 0.0, 0.0), bevel=0.025):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=loc,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    if bevel > 0:
        mod = obj.modifiers.new(name="ProductionBevel", type="BEVEL")
        mod.width = bevel
        mod.segments = 2
    if parent is not None:
        obj.parent = parent
    return obj


def _cone(name, loc, radius1, radius2, depth, material, *, parent=None, vertices=24):
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=radius1,
        radius2=radius2,
        depth=depth,
        location=loc,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    mod = obj.modifiers.new(name="ProductionBevel", type="BEVEL")
    mod.width = 0.025
    mod.segments = 2
    if parent is not None:
        obj.parent = parent
    return obj


def _sphere(name, loc, radius, material, *, parent=None, scale=(1.0, 1.0, 1.0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=10, radius=radius, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if parent is not None:
        obj.parent = parent
    return obj


def materials():
    return {
        "boiler": bs.make_material("Train_Boiler", (0.045, 0.055, 0.050, 1.0), roughness=0.63, metallic=0.52),
        "black": bs.make_material("Train_BlackMetal", (0.025, 0.028, 0.030, 1.0), roughness=0.70, metallic=0.55),
        "frame": bs.make_material("Train_Frame", (0.085, 0.095, 0.090, 1.0), roughness=0.76, metallic=0.42),
        "red": bs.make_material("Train_RedAccent", (0.48, 0.045, 0.030, 1.0), roughness=0.70, metallic=0.20),
        "brass": bs.make_material("Train_Brass", (0.72, 0.48, 0.12, 1.0), roughness=0.42, metallic=0.72),
        "coach": bs.make_material("Train_CoachBody", (0.075, 0.26, 0.17, 1.0), roughness=0.72, metallic=0.12),
        "coach_dark": bs.make_material("Train_CoachLower", (0.035, 0.09, 0.065, 1.0), roughness=0.78, metallic=0.20),
        "cream": bs.make_material("Train_CreamTrim", (0.82, 0.75, 0.58, 1.0), roughness=0.76),
        "wood": bs.make_material("Train_Wood", (0.28, 0.13, 0.055, 1.0), roughness=0.82, recipe="timber", seed=31, strength=0.24),
        "glass": bs.make_material("Train_Glass", (0.12, 0.31, 0.36, 1.0), roughness=0.24, recipe="glass", seed=9, strength=0.16),
        "roof": bs.make_material("Train_Roof", (0.075, 0.075, 0.072, 1.0), roughness=0.77, metallic=0.18),
        "lamp": bs.make_material("Train_Lamp", (0.95, 0.71, 0.26, 1.0), roughness=0.36, metallic=0.22),
    }


def add_wheel(root, mats, name, x, y, radius, width, driving=False):
    wheel = _cylinder(
        name,
        (x, y, radius),
        radius,
        width,
        mats["black"],
        parent=root,
        vertices=28,
        rotation=(math.radians(90.0), 0.0, 0.0),
        bevel=0.018,
    )
    scene_gate.tag(wheel, "train.wheel", ground_contact=True)
    _cylinder(
        name + "_Hub",
        (x, y + (-0.015 if y < 0 else 0.015), radius),
        radius * 0.30,
        width + 0.035,
        mats["red"] if driving else mats["frame"],
        parent=root,
        vertices=20,
        rotation=(math.radians(90.0), 0.0, 0.0),
        bevel=0.012,
    )
    return wheel


def add_coupler(root, mats, name, x):
    _box(name + "_Beam", (x, 0.0, 0.56), (0.42, 0.16, 0.15), mats["black"], 0.025, root)
    _sphere(name + "_Head", (x + (0.20 if x > 0 else -0.20), 0.0, 0.56), 0.105, mats["black"], parent=root, scale=(1.25, 0.70, 0.75))


def build_locomotive(root, mats, recipe):
    g = recipe["geometry"]
    wheel_r = float(g["wheelRadius"])
    wheel_w = float(g["wheelWidth"])
    unit = _empty("LocomotiveRoot", root)
    x0 = -16.0

    # Chassis and pilot.
    frame = _box("Loco_Frame", (x0, 0.0, 0.72), (5.25, 1.72, 0.32), mats["frame"], 0.055, unit)
    scene_gate.tag(frame, "train.locomotive_frame")
    _box("Loco_RunningBoard", (x0 - 0.30, 0.0, 1.02), (4.45, 2.02, 0.14), mats["red"], 0.025, unit)
    _box("Loco_FrontBuffer", (x0 - 2.72, 0.0, 0.66), (0.20, 1.82, 0.28), mats["black"], 0.03, unit)

    # Boiler axis follows the train X axis.
    boiler = _cylinder(
        "Loco_Boiler",
        (x0 - 0.48, 0.0, 1.72),
        0.69,
        3.55,
        mats["boiler"],
        parent=unit,
        vertices=32,
        rotation=(0.0, math.radians(90.0), 0.0),
        bevel=0.03,
    )
    scene_gate.tag(boiler, "train.boiler")
    _cylinder("Loco_SmokeboxFront", (x0 - 2.29, 0.0, 1.72), 0.72, 0.18, mats["black"], parent=unit, vertices=32, rotation=(0.0, math.radians(90.0), 0.0), bevel=0.02)
    _cylinder("Loco_FrontRing", (x0 - 2.40, 0.0, 1.72), 0.76, 0.08, mats["brass"], parent=unit, vertices=32, rotation=(0.0, math.radians(90.0), 0.0), bevel=0.012)

    # Stack, steam dome and bell create the classic steam silhouette.
    _cone("Loco_StackLower", (x0 - 1.62, 0.0, 2.66), 0.34, 0.24, 0.70, mats["black"], parent=unit, vertices=24)
    stack = _cone("Loco_StackFlare", (x0 - 1.62, 0.0, 3.08), 0.42, 0.25, 0.24, mats["black"], parent=unit, vertices=24)
    scene_gate.tag(stack, "train.smokestack")
    _sphere("Loco_SteamDome", (x0 - 0.55, 0.0, 2.48), 0.31, mats["brass"], parent=unit, scale=(0.90, 0.90, 1.15))
    _cylinder("Loco_DomeBase", (x0 - 0.55, 0.0, 2.22), 0.32, 0.16, mats["brass"], parent=unit, vertices=24)
    _sphere("Loco_Bell", (x0 + 0.25, 0.0, 2.43), 0.18, mats["brass"], parent=unit, scale=(1.0, 0.75, 0.85))

    # Driver cab with readable windows on both sides.
    cab_x = x0 + 1.72
    cab = _box("Loco_CabBody", (cab_x, 0.0, 1.74), (1.55, 1.82, 2.12), mats["coach"], 0.055, unit)
    scene_gate.tag(cab, "train.driver_cab")
    _box("Loco_CabRoof", (cab_x, 0.0, 2.88), (1.82, 2.12, 0.20), mats["roof"], 0.065, unit)
    for side, y in (("Near", -0.94), ("Far", 0.94)):
        for i, wx in enumerate((cab_x - 0.32, cab_x + 0.34)):
            _box(f"Loco_CabWindow_{side}_{i}", (wx, y, 2.05), (0.48, 0.045, 0.68), mats["glass"], 0.012, unit)
            _box(f"Loco_CabWindowTrim_{side}_{i}", (wx, y + (-0.025 if y < 0 else 0.025), 2.05), (0.56, 0.055, 0.77), mats["cream"], 0.014, unit)
            _box(f"Loco_CabWindowGlass_{side}_{i}", (wx, y + (-0.055 if y < 0 else 0.055), 2.05), (0.45, 0.035, 0.64), mats["glass"], 0.008, unit)

    # Integrated coal bunker behind cab, still part of locomotive rather than an extra tender car.
    _box("Loco_CoalBunker", (x0 + 2.42, 0.0, 1.34), (0.60, 1.60, 1.08), mats["black"], 0.04, unit)
    for i in range(5):
        _sphere(f"Loco_Coal_{i}", (x0 + 2.37 + (i % 2) * 0.12, -0.48 + i * 0.22, 1.93 + (i % 2) * 0.05), 0.16, mats["black"], parent=unit, scale=(1.15, 0.85, 0.60))

    # Wheels: three large driving axles and one small leading axle.
    for side_y in (-0.93, 0.93):
        add_wheel(unit, mats, f"Loco_LeadWheel_{'L' if side_y < 0 else 'R'}", x0 - 2.03, side_y, 0.34, wheel_w, False)
        for idx, wx in enumerate((x0 - 1.05, x0 - 0.10, x0 + 0.85)):
            add_wheel(unit, mats, f"Loco_DriveWheel_{idx}_{'L' if side_y < 0 else 'R'}", wx, side_y, wheel_r, wheel_w, True)

    # Side rods are oversized enough to survive downsampling.
    for side_y in (-1.055, 1.055):
        _box(f"Loco_SideRod_{'L' if side_y < 0 else 'R'}", (x0 - 0.10, side_y, wheel_r), (2.72, 0.075, 0.10), mats["brass"], 0.018, unit)

    # Headlamp and coupler.
    _box("Loco_HeadlampHousing", (x0 - 2.48, 0.0, 2.38), (0.30, 0.42, 0.40), mats["black"], 0.035, unit)
    _box("Loco_HeadlampLens", (x0 - 2.645, 0.0, 2.38), (0.035, 0.29, 0.27), mats["lamp"], 0.008, unit)
    add_coupler(unit, mats, "Loco_RearCoupler", x0 + 2.86)
    return x0 + 3.15


def build_coach(root, mats, index, center_x, recipe):
    g = recipe["geometry"]
    length = float(g["coachLength"])
    width = float(g["coachWidth"])
    wheel_r = 0.34
    wheel_w = float(g["wheelWidth"])
    coach = _empty(f"Coach_{index:02d}_Root", root)

    lower = _box(f"Coach_{index:02d}_Lower", (center_x, 0.0, 0.82), (length, width, 0.36), mats["coach_dark"], 0.045, coach)
    scene_gate.tag(lower, "train.passenger_coach")
    _box(f"Coach_{index:02d}_Body", (center_x, 0.0, 1.53), (length - 0.18, width - 0.10, 1.18), mats["coach"], 0.055, coach)
    _box(f"Coach_{index:02d}_Belt", (center_x, -width * 0.505, 1.16), (length - 0.28, 0.075, 0.12), mats["cream"], 0.018, coach)
    _box(f"Coach_{index:02d}_BeltFar", (center_x, width * 0.505, 1.16), (length - 0.28, 0.075, 0.12), mats["cream"], 0.018, coach)
    _box(f"Coach_{index:02d}_Roof", (center_x, 0.0, 2.23), (length + 0.06, width + 0.20, 0.24), mats["roof"], 0.085, coach)

    # Four strong windows per side; readable at proxy/gameplay scale.
    window_xs = [center_x - 1.25, center_x - 0.42, center_x + 0.42, center_x + 1.25]
    for side, y in (("Near", -width * 0.505), ("Far", width * 0.505)):
        out_y = y + (-0.035 if y < 0 else 0.035)
        for wi, wx in enumerate(window_xs):
            _box(f"Coach_{index:02d}_WindowFrame_{side}_{wi}", (wx, y, 1.68), (0.62, 0.055, 0.64), mats["cream"], 0.012, coach)
            _box(f"Coach_{index:02d}_Window_{side}_{wi}", (wx, out_y, 1.68), (0.50, 0.030, 0.52), mats["glass"], 0.006, coach)

    # End platforms and doors give separation between cars.
    for end, ex in (("Front", center_x - length * 0.5 + 0.08), ("Rear", center_x + length * 0.5 - 0.08)):
        _box(f"Coach_{index:02d}_{end}Door", (ex, -0.01, 1.48), (0.10, 0.88, 1.22), mats["wood"], 0.018, coach)
        _box(f"Coach_{index:02d}_{end}Platform", (ex + (-0.16 if end == "Front" else 0.16), 0.0, 0.82), (0.28, width + 0.05, 0.12), mats["frame"], 0.02, coach)

    for side_y in (-width * 0.53, width * 0.53):
        for axle, wx in enumerate((center_x - 1.18, center_x + 1.18)):
            add_wheel(coach, mats, f"Coach_{index:02d}_Wheel_{axle}_{'L' if side_y < 0 else 'R'}", wx, side_y, wheel_r, wheel_w, False)

    # Underframe detail avoids a floating box silhouette.
    _box(f"Coach_{index:02d}_Underframe", (center_x, 0.0, 0.56), (length - 0.50, 1.15, 0.16), mats["black"], 0.025, coach)
    return coach


def build_train(root, mats, recipe):
    trailing_start = build_locomotive(root, mats, recipe)
    g = recipe["geometry"]
    length = float(g["coachLength"])
    gap = float(g["coachGap"])
    first_center = trailing_start + gap + length * 0.5
    for idx in range(7):
        cx = first_center + idx * (length + gap)
        build_coach(root, mats, idx + 1, cx, recipe)
        if idx < 6:
            add_coupler(root, mats, f"CoachCoupler_{idx + 1:02d}", cx + length * 0.5 + gap * 0.5)


def _save_blend(path):
    if not path:
        return
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


def build_for_gate(args):
    recipe = bs.load_json(args.recipe)
    if recipe.get("contract") != CONTRACT:
        raise RuntimeError(f"Expected {CONTRACT} recipe")
    if int(recipe.get("composition", {}).get("passengerCoachCount", 0)) != 7:
        raise RuntimeError("Steam train v1 requires exactly 7 passenger coaches")

    studio = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    source_res = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, source_res, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    root = _empty("AssetRoot")
    root["assetId"] = recipe["assetId"]
    root["assetType"] = "vehicle_train"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["styleContract"] = "CH_STYLIZED_PRERENDER_V1"
    root["groundIncludedInAsset"] = False
    root["runtimeRepresentation"] = "2D_RGBA_pre_rendered_sprite"
    root["footprint"] = f"{recipe['footprint']['widthTiles']}x{recipe['footprint']['depthTiles']}"
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    root["steamOverlayPlanned"] = True
    root["steamOverlayEnabled"] = False
    root["coachColorMaskPlanned"] = True
    root["coachColorMaskEnabled"] = False

    mats = materials()
    build_train(root, mats, recipe)

    receiver = studio["shadowReceiver"]
    receiver_mat = bs.make_material("ShadowReceiver", receiver["materialColor"], float(receiver.get("roughness", 1.0)))
    ground = bs.add_box("ShadowReceiverPlane", receiver["location"], receiver["dimensions"], receiver_mat, 0.0)

    authored = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj != ground]
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.16)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    return recipe, studio, scene, root, ground, authored, out


def render_final(recipe, studio, scene, root, ground, authored, out):
    src_res = tuple(map(int, studio["render"]["sourceResolution"]))
    final_res = tuple(map(int, studio["render"]["finalResolution"]))
    directions_meta = []
    for direction in bs.DIRECTIONS:
        bs.set_direction(root, direction)
        bpy.context.view_layer.update()
        color_name = f"{ASSET_ID}_{direction['id']}_color_source.png"
        shadow_name = f"{ASSET_ID}_{direction['id']}_shadow_source.png"
        bs.render_color_pass(scene, authored, ground, str(out / color_name))
        origin_px = bs.ground_origin_source_px(scene)
        bs.render_shadow_pass(scene, authored, ground, str(out / shadow_name))
        directions_meta.append({
            "id": direction["id"],
            "quarterTurns": direction["quarterTurns"],
            "rotationDegrees": direction["rotationDegrees"],
            "colorSource": color_name,
            "shadowSource": shadow_name,
            "groundOriginSourcePx": origin_px,
        })

    metadata = {
        "sourceObject": ASSET_ID,
        "assetType": "vehicle_train",
        "sourceContract": "DIRECT_CH_BLENDER_GUARDED_V1",
        "assetConfig": "tools/tycoon_photo_studio/build_steam_train_guarded.py",
        "recipe": DEFAULT_RECIPE,
        "studioPreset": studio["id"],
        "styleContract": "CH_STYLIZED_PRERENDER_V1",
        "cameraContract": "CH_CAMERA_V1",
        "gridContract": "CH_GRID_V1",
        "projection": "orthographic_dimetric_2_to_1",
        "yawDegrees": 45.0,
        "elevationDegrees": 30.0,
        "tileWidth": 128,
        "tileHeight": 64,
        "footprint": recipe["footprint"],
        "blenderVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "renderResolution": list(src_res),
        "finalResolution": list(final_res),
        "directionOrder": [d["id"] for d in bs.DIRECTIONS],
        "rotationPolicy": {"assetRootRotates": True, "cameraRemainsFixed": True, "lightsRemainWorldFixed": True},
        "composition": recipe["composition"],
        "futureLayers": recipe.get("futureLayers"),
        "directions": directions_meta,
    }
    (out / "studio_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()


def main():
    args = parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    recipe, studio, scene, root, ground, authored, out = build_for_gate(args)

    preflight_path = out / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=recipe["footprint"],
        profile=profile,
        asset_id=recipe["assetId"],
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        _save_blend(args.save_blend)
        print(f"[CH_GATE] steam train preflight PASS: {preflight_path}")
        return

    if args.stage == "proxy":
        bs.set_direction(root, bs.DIRECTIONS[0])
        bpy.context.view_layer.update()
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / "proxy_south.png",
            profile=profile,
            asset_id=recipe["assetId"],
            direction="south",
        )
        (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        _save_blend(args.save_blend)
        print(f"[CH_GATE] steam train proxy SOUTH ready: {proxy['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError("CH_FINAL_REQUIRES_APPROVED_PROXY: review proxy_south.png first and pass its SHA-256")

    approval_record = {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": recipe["assetId"],
        "proxySha256": approval,
        "reviewed": True,
        "runtimeTarget": "2D_RGBA_pre_rendered_sprite",
    }
    (out / "proxy_approval.json").write_text(json.dumps(approval_record, indent=2), encoding="utf-8")
    render_final(recipe, studio, scene, root, ground, authored, out)
    _save_blend(args.save_blend)
    print("[CH_GATE] steam train final four-direction source bake complete")


if __name__ == "__main__":
    main()
