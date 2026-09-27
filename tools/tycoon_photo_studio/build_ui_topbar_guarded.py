"""Guarded CH Blender authoring for the City Horizon top HUD bar.

SDL3 consumes only PNG RGBA; CH Blender authors the tactile panel texture and
miniature 3D HUD icons. New art must pass preflight -> SOUTH proxy -> human
review before any runtime promotion.

Art direction for this pass: brighter classic-tycoon readability, warmer
materials, clearer category color coding and stronger small-size silhouettes.
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

    def sphere(name, location, radius, material_key, *, scale=(1.0, 1.0, 1.0),
               role="ui.topbar.detail"):
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=24, ring_count=12, radius=radius, location=location
        )
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(materials[material_key])
        scene_gate.tag(obj, role)
        authored.append(obj)
        return obj

    def torus(name, location, major_radius, minor_radius, material_key, *,
              role="ui.topbar.detail"):
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

    def icon_pedestal(prefix, face_material, *, size=(2.16, 2.06), inset_material="base_rim"):
        box(f"{prefix}Shadow", (0.0, 0.0, 0.055), (size[0] + 0.10, size[1] + 0.10, 0.11),
            "base_shadow", bevel=0.085, contact=True, role="ui.topbar.icon.base")
        box(f"{prefix}Base", (0.0, 0.0, 0.13), (size[0], size[1], 0.14),
            face_material, bevel=0.085, role="ui.topbar.icon.base")
        box(f"{prefix}Inset", (0.0, 0.0, 0.215), (size[0] - 0.24, size[1] - 0.24, 0.055),
            inset_material, bevel=0.055, role="ui.topbar.icon.base")

    if asset_id == "panel":
        # +45 degrees aligns the long axis with the fixed camera screen-horizontal direction.
        rot = 45.0
        box("TopBarShadowBase", (0.0, 0.0, 0.07), (2.92, 1.08, 0.14), "panel_shadow",
            bevel=0.10, contact=True, role="ui.topbar.panel", rotation_z=rot)
        box("TopBarOuterFrame", (0.0, 0.0, 0.17), (2.84, 1.00, 0.16), "panel_edge",
            bevel=0.085, role="ui.topbar.panel", rotation_z=rot)
        box("TopBarFace", (0.0, 0.0, 0.28), (2.66, 0.82, 0.14), "panel_face",
            bevel=0.065, role="ui.topbar.panel", rotation_z=rot)
        box("TopBarInset", (0.0, 0.0, 0.375), (2.46, 0.60, 0.075), "panel_inset",
            bevel=0.04, role="ui.topbar.panel", rotation_z=rot)
        box("TopBarGlow", (0.0, 0.0, 0.430), (2.26, 0.060, 0.045), "cyan_glow",
            bevel=0.020, role="ui.topbar.highlight", rotation_z=rot)
        box("TopBarWarmAccent", (0.0, 0.18, 0.414), (1.25, 0.040, 0.025), "gold_accent",
            bevel=0.012, role="ui.topbar.highlight", rotation_z=rot)

    elif asset_id == "funds":
        icon_pedestal("Funds", "base_green", inset_material="base_green_light")
        # Four coins form an unmistakable bright economy stack, with a green value accent.
        for index, (x, y, z, r) in enumerate(((-0.55, 0.25, 0.34, 0.40),
                                              (0.02, 0.20, 0.42, 0.45),
                                              (0.53, 0.26, 0.33, 0.37),
                                              (0.02, -0.33, 0.58, 0.53))):
            cylinder(f"Coin{index}", (x, y, z), r, 0.20, "gold", role="ui.topbar.icon.coin")
            cylinder(f"CoinInset{index}", (x, y, z + 0.106), r * 0.61, 0.028, "gold_light",
                     role="ui.topbar.icon.coin")
        box("FundsValueRibbon", (0.02, -0.67, 0.38), (1.18, 0.22, 0.18), "emerald",
            bevel=0.07, role="ui.topbar.icon.coin")
        cylinder("FundsValueDot", (0.02, -0.70, 0.50), 0.15, 0.08, "mint_light",
                 role="ui.topbar.icon.coin", rotation=(math.radians(90.0), 0.0, 0.0))

    elif asset_id == "calendar":
        icon_pedestal("Calendar", "base_sky", inset_material="base_sky_light")
        box("CalendarBody", (0.0, 0.05, 0.93), (1.64, 0.30, 1.40), "paper",
            bevel=0.09, role="ui.topbar.icon.calendar")
        box("CalendarHeader", (0.0, -0.112, 1.38), (1.67, 0.07, 0.36), "coral",
            bevel=0.03, role="ui.topbar.icon.calendar")
        for x in (-0.47, 0.47):
            box("CalendarBinderL" if x < 0 else "CalendarBinderR", (x, -0.155, 1.62),
                (0.17, 0.13, 0.30), "gold_light", bevel=0.05, role="ui.topbar.icon.calendar")
        cell_materials = ("accent_cyan", "sunny_yellow", "leaf_green")
        for row, z in enumerate((1.02, 0.70, 0.38)):
            for col, x in enumerate((-0.48, 0.0, 0.48)):
                box(f"CalendarCell{row}_{col}", (x, -0.118, z), (0.22, 0.06, 0.18),
                    cell_materials[(row + col) % len(cell_materials)], bevel=0.028,
                    role="ui.topbar.icon.calendar")

    elif asset_id == "population":
        icon_pedestal("Population", "base_mint", inset_material="base_mint_light")
        people = (
            (-0.66, 0.02, 0.80, 0.25, "shirt_coral", "skin_mid"),
            (0.0, -0.03, 0.99, 0.31, "shirt_blue", "skin_light"),
            (0.66, 0.02, 0.80, 0.25, "shirt_yellow", "skin_dark"),
        )
        for index, (x, y, head_z, radius, shirt, skin) in enumerate(people):
            body_h = 0.46 if index != 1 else 0.56
            body_w = 0.48 if index != 1 else 0.58
            box(f"PersonBody{index}", (x, y, 0.24 + body_h * 0.5),
                (body_w, 0.46, body_h), shirt, bevel=0.14, role="ui.topbar.icon.person")
            sphere(f"PersonHead{index}", (x, y, head_z), radius, skin, role="ui.topbar.icon.person")
            sphere(f"PersonHair{index}", (x, y + 0.015, head_z + radius * 0.22), radius * 0.90,
                   "hair_brown", scale=(1.0, 0.95, 0.46), role="ui.topbar.icon.person")

    elif asset_id == "pause":
        icon_pedestal("Pause", "base_blue", inset_material="base_sky_light")
        box("PauseButtonShadow", (0.0, 0.0, 0.35), (1.66, 1.58, 0.30), "button_shadow",
            bevel=0.18, role="ui.topbar.icon.button")
        box("PauseButton", (0.0, 0.0, 0.52), (1.58, 1.50, 0.42), "button_blue",
            bevel=0.17, role="ui.topbar.icon.button")
        box("PauseButtonHighlight", (0.0, -0.50, 0.76), (1.18, 0.09, 0.055), "cyan_glow",
            bevel=0.03, role="ui.topbar.icon.glyph")
        box("PauseBarLeft", (-0.29, -0.02, 0.78), (0.24, 0.72, 0.12), "white",
            bevel=0.05, role="ui.topbar.icon.glyph")
        box("PauseBarRight", (0.29, -0.02, 0.78), (0.24, 0.72, 0.12), "white",
            bevel=0.05, role="ui.topbar.icon.glyph")

    elif asset_id == "administration":
        icon_pedestal("Admin", "base_green", inset_material="lawn_green")
        box("AdminSteps", (0.0, -0.04, 0.36), (1.86, 1.36, 0.20), "stone_warm",
            bevel=0.055, role="ui.topbar.icon.building")
        box("AdminHall", (0.0, 0.12, 0.80), (1.60, 1.08, 0.72), "cream",
            bevel=0.06, role="ui.topbar.icon.building")
        for index, x in enumerate((-0.53, 0.0, 0.53)):
            cylinder(f"AdminColumn{index}", (x, -0.48, 0.87), 0.105, 0.84, "white",
                     role="ui.topbar.icon.building")
        box("AdminEntablature", (0.0, -0.02, 1.27), (1.78, 1.14, 0.21), "white",
            bevel=0.045, role="ui.topbar.icon.building")
        box("AdminRoof", (0.0, -0.01, 1.49), (1.58, 1.00, 0.26), "roof_blue",
            bevel=0.085, role="ui.topbar.icon.building")
        box("AdminDoor", (0.0, -0.445, 0.71), (0.34, 0.08, 0.47), "door_blue",
            bevel=0.035, role="ui.topbar.icon.building")
        cylinder("AdminSeal", (0.0, -0.58, 1.24), 0.14, 0.06, "gold_light",
                 role="ui.topbar.icon.building", rotation=(math.radians(90.0), 0.0, 0.0))

    elif asset_id == "settings":
        icon_pedestal("Settings", "base_purple", inset_material="base_purple_light")
        torus("GearRing", (0.0, 0.0, 0.46), 0.59, 0.19, "metal_light",
              role="ui.topbar.icon.gear")
        cylinder("GearHub", (0.0, 0.0, 0.46), 0.25, 0.30, "orange",
                 role="ui.topbar.icon.gear")
        for index in range(8):
            angle = math.radians(index * 45.0)
            x = math.cos(angle) * 0.77
            y = math.sin(angle) * 0.77
            box(f"GearTooth{index}", (x, y, 0.46), (0.31, 0.23, 0.27), "metal_light",
                bevel=0.06, role="ui.topbar.icon.gear", rotation_z=index * 45.0)
        torus("GearSmallRing", (0.64, -0.47, 0.47), 0.29, 0.105, "accent_cyan",
              role="ui.topbar.icon.gear")
        cylinder("GearSmallHub", (0.64, -0.47, 0.47), 0.115, 0.21, "sunny_yellow",
                 role="ui.topbar.icon.gear")
        box("SettingsSpark", (-0.72, 0.54, 0.48), (0.18, 0.18, 0.34), "coral",
            bevel=0.055, role="ui.topbar.icon.gear", rotation_z=45.0)

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
    receiver_material = bs.make_material(
        "ShadowReceiver", receiver["materialColor"], float(receiver.get("roughness", 1.0))
    )
    bs.add_box("ShadowReceiverPlane", receiver["location"], receiver["dimensions"], receiver_material, 0.0)

    # Smaller margin makes HUD symbols read larger at their real gameplay size.
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.12)
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
