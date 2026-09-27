"""Guarded CH Blender authoring for the City Horizon top HUD bar.

SDL3 consumes only PNG RGBA; CH Blender authors the tactile panel texture and
miniature 3D HUD icons. New art must pass preflight -> SOUTH proxy -> human
review before any runtime promotion.
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
for path in (HERE, CH_BLENDER):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402

ASSET_IDS = ("panel", "funds", "calendar", "population", "pause", "administration", "settings")


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--asset", required=True, choices=ASSET_IDS)
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


def add_bevel(obj, width=0.035, segments=2):
    if width <= 0.0:
        return
    bevel = obj.modifiers.new(name="HudEdgeSoftening", type="BEVEL")
    bevel.width = width
    bevel.segments = segments


def build_asset(asset_id, materials):
    authored = []

    def box(name, location, dimensions, material_key, *, bevel=0.035,
            role="ui.topbar.detail", contact=False, rotation_z=0.0):
        obj = bs.add_box(name, location, dimensions, materials[material_key], bevel)
        if rotation_z:
            obj.rotation_euler[2] = math.radians(rotation_z)
            bpy.context.view_layer.update()
        scene_gate.tag(obj, role, ground_contact=contact)
        authored.append(obj)
        return obj

    def cylinder(name, location, radius, depth, material_key, *, vertices=32,
                 role="ui.topbar.detail", rotation=(0.0, 0.0, 0.0)):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=vertices, radius=radius, depth=depth,
            location=location, rotation=rotation,
        )
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(materials[material_key])
        add_bevel(obj, min(0.035, radius * 0.18), 2)
        scene_gate.tag(obj, role)
        authored.append(obj)
        return obj

    def sphere(name, location, radius, material_key, *, scale=(1.0, 1.0, 1.0), role="ui.topbar.detail"):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius, location=location)
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(materials[material_key])
        scene_gate.tag(obj, role)
        authored.append(obj)
        return obj

    def torus(name, location, major_radius, minor_radius, material_key, *, role="ui.topbar.detail"):
        bpy.ops.mesh.primitive_torus_add(
            major_radius=major_radius, minor_radius=minor_radius,
            major_segments=32, minor_segments=10, location=location,
        )
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(materials[material_key])
        scene_gate.tag(obj, role)
        authored.append(obj)
        return obj

    if asset_id == "panel":
        # +45 degrees aligns the long axis with the fixed camera screen-horizontal direction.
        rot = 45.0
        box("TopBarShadowBase", (0.0, 0.0, 0.08), (2.82, 1.02, 0.16), "panel_shadow",
            bevel=0.09, contact=True, role="ui.topbar.panel", rotation_z=rot)
        box("TopBarOuterFrame", (0.0, 0.0, 0.18), (2.74, 0.94, 0.16), "panel_edge",
            bevel=0.075, role="ui.topbar.panel", rotation_z=rot)
        box("TopBarFace", (0.0, 0.0, 0.28), (2.56, 0.76, 0.12), "panel_face",
            bevel=0.06, role="ui.topbar.panel", rotation_z=rot)
        box("TopBarInset", (0.0, 0.0, 0.355), (2.36, 0.56, 0.055), "panel_inset",
            bevel=0.035, role="ui.topbar.panel", rotation_z=rot)
        box("TopBarHighlight", (0.0, 0.0, 0.397), (2.18, 0.055, 0.035), "cyan_glow",
            bevel=0.018, role="ui.topbar.highlight", rotation_z=rot)

    elif asset_id == "funds":
        box("FundsBase", (0.0, 0.0, 0.07), (2.15, 2.05, 0.14), "icon_base",
            bevel=0.07, contact=True, role="ui.topbar.icon.base")
        for index, (x, y, z) in enumerate(((-0.48, 0.20, 0.23), (0.06, 0.08, 0.32), (0.50, 0.24, 0.23))):
            cylinder(f"Coin{index}", (x, y, z), 0.45, 0.18, "gold", role="ui.topbar.icon.coin")
            cylinder(f"CoinInset{index}", (x, y, z + 0.095), 0.28, 0.025, "gold_light", role="ui.topbar.icon.coin")
        cylinder("FundsMedallion", (0.02, -0.30, 0.50), 0.56, 0.18, "gold", role="ui.topbar.icon.coin")
        cylinder("FundsMedallionInset", (0.02, -0.30, 0.595), 0.33, 0.035, "gold_light", role="ui.topbar.icon.coin")

    elif asset_id == "calendar":
        box("CalendarBase", (0.0, 0.0, 0.07), (2.15, 2.05, 0.14), "icon_base",
            bevel=0.07, contact=True, role="ui.topbar.icon.base")
        # Thin standing card: reads as a calendar rather than a miniature building.
        box("CalendarBody", (0.0, 0.05, 0.82), (1.58, 0.28, 1.36), "paper",
            bevel=0.08, role="ui.topbar.icon.calendar")
        box("CalendarHeader", (0.0, -0.105, 1.28), (1.60, 0.06, 0.34), "accent_blue",
            bevel=0.025, role="ui.topbar.icon.calendar")
        for x in (-0.46, 0.46):
            box("CalendarBinderL" if x < 0 else "CalendarBinderR", (x, -0.15, 1.52),
                (0.16, 0.12, 0.28), "metal_light", bevel=0.045, role="ui.topbar.icon.calendar")
        for row, z in enumerate((0.94, 0.64, 0.34)):
            for col, x in enumerate((-0.48, 0.0, 0.48)):
                box(f"CalendarCell{row}_{col}", (x, -0.105, z), (0.20, 0.055, 0.16), "accent_cyan",
                    bevel=0.025, role="ui.topbar.icon.calendar")

    elif asset_id == "population":
        box("PopulationBase", (0.0, 0.0, 0.07), (2.15, 2.05, 0.14), "icon_base",
            bevel=0.07, contact=True, role="ui.topbar.icon.base")
        people = ((-0.68, -0.06, 0.66, 0.27), (0.0, -0.04, 0.84, 0.34), (0.68, -0.06, 0.66, 0.27))
        for index, (x, y, head_z, radius) in enumerate(people):
            body_h = 0.40 if index != 1 else 0.50
            box(f"PersonBody{index}", (x, y, 0.14 + body_h * 0.5),
                (0.44 if index != 1 else 0.54, 0.42, body_h),
                "person_teal" if index == 1 else "person_blue",
                bevel=0.12, role="ui.topbar.icon.person")
            sphere(f"PersonHead{index}", (x, y, head_z), radius, "skin", role="ui.topbar.icon.person")

    elif asset_id == "pause":
        box("PauseBase", (0.0, 0.0, 0.07), (2.08, 2.00, 0.14), "icon_base",
            bevel=0.10, contact=True, role="ui.topbar.icon.base")
        box("PauseButton", (0.0, 0.0, 0.36), (1.58, 1.50, 0.44), "button_blue",
            bevel=0.16, role="ui.topbar.icon.button")
        # Low relief bars sit on the button face so the pause glyph reads immediately.
        box("PauseBarLeft", (-0.28, -0.02, 0.63), (0.22, 0.70, 0.10), "accent_cyan",
            bevel=0.045, role="ui.topbar.icon.glyph")
        box("PauseBarRight", (0.28, -0.02, 0.63), (0.22, 0.70, 0.10), "accent_cyan",
            bevel=0.045, role="ui.topbar.icon.glyph")

    elif asset_id == "administration":
        box("AdminBase", (0.0, 0.0, 0.07), (2.20, 2.08, 0.14), "icon_base",
            bevel=0.07, contact=True, role="ui.topbar.icon.base")
        box("AdminSteps", (0.0, -0.04, 0.22), (1.78, 1.30, 0.20), "stone", bevel=0.05, role="ui.topbar.icon.building")
        box("AdminHall", (0.0, 0.12, 0.66), (1.55, 1.04, 0.72), "stone_light", bevel=0.055, role="ui.topbar.icon.building")
        for index, x in enumerate((-0.52, 0.0, 0.52)):
            cylinder(f"AdminColumn{index}", (x, -0.46, 0.73), 0.10, 0.82, "stone_white", role="ui.topbar.icon.building")
        box("AdminEntablature", (0.0, -0.02, 1.13), (1.72, 1.10, 0.20), "stone_white", bevel=0.04, role="ui.topbar.icon.building")
        box("AdminRoof", (0.0, -0.01, 1.34), (1.52, 0.96, 0.24), "accent_blue", bevel=0.08, role="ui.topbar.icon.building")

    elif asset_id == "settings":
        box("SettingsBase", (0.0, 0.0, 0.07), (2.12, 2.04, 0.14), "icon_base",
            bevel=0.08, contact=True, role="ui.topbar.icon.base")
        torus("GearRing", (0.0, 0.0, 0.28), 0.58, 0.18, "metal_light", role="ui.topbar.icon.gear")
        cylinder("GearHub", (0.0, 0.0, 0.28), 0.24, 0.28, "accent_blue", role="ui.topbar.icon.gear")
        for index in range(8):
            angle = math.radians(index * 45.0)
            x = math.cos(angle) * 0.76
            y = math.sin(angle) * 0.76
            box(f"GearTooth{index}", (x, y, 0.28), (0.30, 0.22, 0.26), "metal_light",
                bevel=0.055, role="ui.topbar.icon.gear", rotation_z=index * 45.0)
        torus("GearSmallRing", (0.62, -0.45, 0.30), 0.28, 0.10, "accent_cyan", role="ui.topbar.icon.gear")
        cylinder("GearSmallHub", (0.62, -0.45, 0.30), 0.11, 0.20, "panel_face", role="ui.topbar.icon.gear")

    else:
        raise RuntimeError(f"Unsupported topbar asset: {asset_id}")

    return authored


def main():
    args = parse_args()
    spec = load_json(args.spec)
    if spec.get("contract") != "CH_UI_TOPBAR_SET_V1":
        raise RuntimeError("Expected CH_UI_TOPBAR_SET_V1 spec")
    if args.asset not in spec.get("assets", {}):
        raise RuntimeError(f"Asset {args.asset!r} is missing from spec")

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
            value.get("name", key), value["rgba"],
            float(value.get("roughness", 0.72)), float(value.get("metallic", 0.0)),
        )
        for key, value in spec["materials"].items()
    }

    authored = build_asset(args.asset, materials)
    root = bs.create_asset_root(authored)
    asset_id = f"ui.topbar.{args.asset}"
    root["assetId"] = asset_id
    root["assetType"] = "ui_topbar_art"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["visualContract"] = "CH_STYLIZED_PRERENDER_V1"
    root["runtimeRepresentation"] = "2D_RGBA_pre_rendered_ui"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    root["uiSetContract"] = spec["contract"]

    receiver = studio["shadowReceiver"]
    receiver_material = bs.make_material("ShadowReceiver", receiver["materialColor"], float(receiver.get("roughness", 1.0)))
    bs.add_box("ShadowReceiverPlane", receiver["location"], receiver["dimensions"], receiver_material, 0.0)

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.20)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    preflight_path = output / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=spec.get("footprint", {"widthTiles": 1, "depthTiles": 1}),
        profile=profile,
        asset_id=asset_id,
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        save_blend(args.save_blend)
        print(f"[CH_GATE] topbar {args.asset} preflight PASS: {preflight_path}")
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
    print(f"[CH_GATE] topbar {args.asset} proxy PASS: {output / 'proxy_south.png'}")


if __name__ == "__main__":
    main()
