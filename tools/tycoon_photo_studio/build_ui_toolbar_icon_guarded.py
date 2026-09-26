"""Guarded Blender authoring for the six City Horizon gameplay toolbar icons.

These are small pre-rendered UI props, not runtime 3D assets.  They deliberately
reuse CH_TYCOON_STUDIO_V1 so the toolbar carries the same light/material language
as the game while the SDL runtime continues to consume ordinary PNG RGBA icons.

Required flow for new art:
    preflight -> SOUTH proxy -> explicit human review -> later promotion
"""
from __future__ import annotations

import argparse
import json
import math
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

ICON_IDS = ("buildings", "roads", "sidewalks", "land", "agriculture", "decoration")


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--icon", required=True, choices=ICON_IDS)
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--save-blend", default=None)
    parser.add_argument("--stage", choices=("preflight", "proxy"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    return parser.parse_args(argv)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_blend(path):
    if not path:
        return
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


def add_bevel(obj, width=0.04, segments=2):
    if width <= 0.0:
        return
    bevel = obj.modifiers.new(name="IconEdgeSoftening", type="BEVEL")
    bevel.width = width
    bevel.segments = segments


def build_icon(icon_id, materials):
    authored = []

    def box(name, location, dimensions, material_key, *, bevel=0.04, role="ui.icon.detail", contact=False):
        obj = bs.add_box(name, location, dimensions, materials[material_key], bevel)
        scene_gate.tag(obj, role, ground_contact=contact)
        authored.append(obj)
        return obj

    def cylinder(name, location, radius, depth, material_key, *, role="ui.icon.detail", contact=False, vertices=20):
        bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(materials[material_key])
        add_bevel(obj, min(0.035, radius * 0.16), 2)
        scene_gate.tag(obj, role, ground_contact=contact)
        authored.append(obj)
        return obj

    def sphere(name, location, radius, material_key, *, scale=(1.0, 1.0, 1.0), role="ui.icon.detail"):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=radius, location=location)
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(materials[material_key])
        scene_gate.tag(obj, role)
        authored.append(obj)
        return obj

    def pyramid(name, location, radius, depth, material_key, *, role="ui.icon.detail", rotation_degrees=45.0):
        bpy.ops.mesh.primitive_cone_add(
            vertices=4,
            radius1=radius,
            radius2=0.0,
            depth=depth,
            location=location,
            rotation=(0.0, 0.0, math.radians(rotation_degrees)),
        )
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(materials[material_key])
        add_bevel(obj, 0.035, 2)
        scene_gate.tag(obj, role)
        authored.append(obj)
        return obj

    if icon_id == "buildings":
        box("BuildingsFoundation", (0.0, 0.0, 0.08), (2.20, 2.00, 0.16), "stone", contact=True, role="ui.icon.base")
        box("BuildingsHouseBody", (0.0, 0.0, 0.78), (1.72, 1.48, 1.34), "wall", bevel=0.07, role="ui.icon.building")
        pyramid("BuildingsRoof", (0.0, 0.0, 1.72), 1.28, 0.72, "roof", role="ui.icon.building")
        box("BuildingsDoor", (0.0, -0.765, 0.58), (0.44, 0.09, 0.82), "wood", bevel=0.025)
        box("BuildingsWindowLeft", (-0.50, -0.766, 0.91), (0.30, 0.08, 0.34), "glass", bevel=0.018)
        box("BuildingsWindowRight", (0.50, -0.766, 0.91), (0.30, 0.08, 0.34), "glass", bevel=0.018)
        box("BuildingsChimney", (0.48, 0.23, 1.80), (0.24, 0.24, 0.72), "brick", bevel=0.03)

    elif icon_id == "roads":
        box("RoadBase", (0.0, 0.0, 0.09), (2.62, 1.42, 0.18), "asphalt", bevel=0.05, contact=True, role="ui.icon.base")
        box("RoadCurbNear", (0.0, -0.67, 0.19), (2.62, 0.12, 0.13), "curb", bevel=0.025)
        box("RoadCurbFar", (0.0, 0.67, 0.19), (2.62, 0.12, 0.13), "curb", bevel=0.025)
        for index, x in enumerate((-0.82, 0.0, 0.82)):
            box(f"RoadDash{index}", (x, 0.0, 0.205), (0.42, 0.09, 0.035), "road_line", bevel=0.01)

    elif icon_id == "sidewalks":
        box("FloorTileBase", (0.0, 0.0, 0.08), (2.28, 2.28, 0.16), "stone_dark", bevel=0.06, contact=True, role="ui.icon.base")
        box("FloorTileInset", (0.0, 0.0, 0.18), (1.92, 1.92, 0.08), "stone_light", bevel=0.035)
        box("FloorJointX", (0.0, 0.0, 0.235), (1.88, 0.07, 0.025), "stone_dark", bevel=0.0)
        box("FloorJointY", (0.0, 0.0, 0.235), (0.07, 1.88, 0.025), "stone_dark", bevel=0.0)

    elif icon_id == "land":
        box("LandParcel", (0.0, 0.0, 0.08), (2.36, 2.36, 0.16), "grass", bevel=0.06, contact=True, role="ui.icon.base")
        box("LandSoilPatch", (-0.24, 0.16, 0.18), (1.35, 1.00, 0.08), "soil", bevel=0.08)
        cylinder("LandSignPost", (0.72, -0.58, 0.62), 0.075, 1.04, "wood", role="ui.icon.sign")
        box("LandSignBoard", (0.72, -0.58, 1.08), (0.74, 0.14, 0.48), "wood_light", bevel=0.05, role="ui.icon.sign")
        sphere("LandShrub", (-0.78, 0.66, 0.36), 0.30, "leaf_dark", scale=(1.0, 0.90, 0.78))

    elif icon_id == "agriculture":
        box("FarmGround", (0.0, 0.0, 0.07), (2.46, 2.28, 0.14), "soil", bevel=0.06, contact=True, role="ui.icon.base")
        box("FarmBarnBody", (-0.34, 0.18, 0.68), (1.40, 1.20, 1.16), "barn", bevel=0.06, role="ui.icon.building")
        pyramid("FarmBarnRoof", (-0.34, 0.18, 1.48), 1.03, 0.62, "roof_red", role="ui.icon.building")
        box("FarmBarnDoor", (-0.34, -0.43, 0.58), (0.48, 0.09, 0.72), "wood_dark", bevel=0.025)
        cylinder("FarmSilo", (0.78, 0.34, 0.78), 0.34, 1.42, "metal", role="ui.icon.building")
        pyramid("FarmSiloCap", (0.78, 0.34, 1.58), 0.48, 0.28, "metal_light", rotation_degrees=45.0)
        for index, y in enumerate((-0.68, -0.40, -0.12)):
            box(f"FarmCropRow{index}", (0.60, y, 0.22), (1.18, 0.10, 0.22), "crop", bevel=0.04, role="ui.icon.crop")

    elif icon_id == "decoration":
        box("DecorGround", (0.0, 0.0, 0.06), (2.18, 2.10, 0.12), "grass", bevel=0.06, contact=True, role="ui.icon.base")
        cylinder("DecorTreeTrunk", (-0.32, 0.22, 0.72), 0.16, 1.34, "wood_dark", role="ui.icon.tree")
        sphere("DecorCanopyA", (-0.32, 0.22, 1.55), 0.62, "leaf_dark", scale=(1.0, 0.90, 0.90), role="ui.icon.tree")
        sphere("DecorCanopyB", (-0.66, 0.04, 1.43), 0.46, "leaf_light", scale=(1.0, 0.90, 0.86), role="ui.icon.tree")
        sphere("DecorCanopyC", (0.03, 0.06, 1.45), 0.48, "leaf_mid", scale=(1.0, 0.92, 0.86), role="ui.icon.tree")
        box("DecorBenchSeat", (0.56, -0.54, 0.34), (0.96, 0.30, 0.14), "wood_light", bevel=0.04, role="ui.icon.bench")
        box("DecorBenchBack", (0.56, -0.42, 0.62), (0.96, 0.12, 0.44), "wood_light", bevel=0.04, role="ui.icon.bench")
        box("DecorBenchLegL", (0.22, -0.54, 0.17), (0.10, 0.18, 0.30), "metal_dark", bevel=0.025, role="ui.icon.bench")
        box("DecorBenchLegR", (0.90, -0.54, 0.17), (0.10, 0.18, 0.30), "metal_dark", bevel=0.025, role="ui.icon.bench")

    else:
        raise RuntimeError(f"Unsupported toolbar icon: {icon_id}")

    return authored


def main():
    args = parse_args()
    spec = load_json(args.spec)
    if spec.get("contract") != "CH_UI_TOOLBAR_ICON_SET_V1":
        raise RuntimeError("Expected CH_UI_TOOLBAR_ICON_SET_V1 spec")
    if args.icon not in spec.get("icons", {}):
        raise RuntimeError(f"Icon {args.icon!r} is missing from spec")

    studio = bs.load_json(args.studio_preset)
    profile = scene_gate.load_profile(args.preflight_profile)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    source_resolution = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, source_resolution, str(output))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    materials = {
        key: bs.make_material(
            value.get("name", key),
            value["rgba"],
            float(value.get("roughness", 0.72)),
            float(value.get("metallic", 0.0)),
        )
        for key, value in spec["materials"].items()
    }

    authored = build_icon(args.icon, materials)
    root = bs.create_asset_root(authored)
    asset_id = f"ui.toolbar.{args.icon}"
    root["assetId"] = asset_id
    root["assetType"] = "ui_toolbar_icon"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["visualContract"] = "CH_STYLIZED_PRERENDER_V1"
    root["runtimeRepresentation"] = "2D_RGBA_pre_rendered_ui_icon"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    root["iconSetContract"] = spec["contract"]

    receiver = studio["shadowReceiver"]
    receiver_material = bs.make_material(
        "ShadowReceiver",
        receiver["materialColor"],
        float(receiver.get("roughness", 1.0)),
    )
    bs.add_box(
        "ShadowReceiverPlane",
        receiver["location"],
        receiver["dimensions"],
        receiver_material,
        0.0,
    )

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.20)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    footprint = spec.get("footprint", {"widthTiles": 1, "depthTiles": 1})
    preflight_path = output / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=footprint,
        profile=profile,
        asset_id=asset_id,
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        save_blend(args.save_blend)
        print(f"[CH_GATE] toolbar icon {args.icon} preflight PASS: {preflight_path}")
        return

    proxy = scene_gate.render_proxy(
        scene=scene,
        authored=authored,
        output_path=output / "proxy_south.png",
        profile=profile,
        asset_id=asset_id,
        direction="south",
    )
    (output / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
    save_blend(args.save_blend)
    print(f"[CH_GATE] toolbar icon {args.icon} SOUTH proxy ready: {proxy['sha256']}")


if __name__ == "__main__":
    main()
