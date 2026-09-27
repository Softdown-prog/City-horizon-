"""Guarded CH Blender authoring for City Horizon camera-rotation HUD buttons.

These are offline-authored 3D controls baked to transparent PNG RGBA for SDL3.
They deliberately share the bright classic-tycoon material language of the
existing topbar set. Runtime never depends on Blender.

Promotion contract remains: preflight -> SOUTH proxy -> human review -> final.
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

ASSET_IDS = ("camera_left", "camera_right")


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
    bevel = obj.modifiers.new(name="CameraControlEdgeSoftening", type="BEVEL")
    bevel.width = width
    bevel.segments = segments


def build_asset(asset_id, materials):
    authored = []
    left = asset_id == "camera_left"

    def box(name, location, dimensions, material_key, *, bevel=0.035,
            role="ui.camera_rotation.detail", contact=False, rotation_z=0.0):
        obj = bs.add_box(name, location, dimensions, materials[material_key], bevel)
        if rotation_z:
            obj.rotation_euler[2] = math.radians(rotation_z)
            bpy.context.view_layer.update()
        scene_gate.tag(obj, role, ground_contact=contact)
        authored.append(obj)
        return obj

    def cylinder(name, location, radius, depth, material_key, *, vertices=40,
                 role="ui.camera_rotation.detail", rotation=(0.0, 0.0, 0.0)):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=vertices,
            radius=radius,
            depth=depth,
            location=location,
            rotation=rotation,
        )
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(materials[material_key])
        add_bevel(obj, min(0.05, radius * 0.12), 2)
        scene_gate.tag(obj, role)
        authored.append(obj)
        return obj

    def triangle_prism(name, location, radius, depth, material_key, rotation_z,
                       role="ui.camera_rotation.glyph"):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=3,
            radius=radius,
            depth=depth,
            location=location,
            rotation=(0.0, 0.0, math.radians(rotation_z)),
        )
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(materials[material_key])
        add_bevel(obj, 0.028, 2)
        scene_gate.tag(obj, role)
        authored.append(obj)
        return obj

    def arc_curve(name, angles_deg, radius, z, material_key,
                  role="ui.camera_rotation.glyph"):
        curve = bpy.data.curves.new(name=f"{name}Curve", type="CURVE")
        curve.dimensions = "3D"
        curve.resolution_u = 2
        curve.bevel_depth = 0.105
        curve.bevel_resolution = 4
        spline = curve.splines.new("POLY")
        spline.points.add(len(angles_deg) - 1)
        for point, angle_deg in zip(spline.points, angles_deg):
            angle = math.radians(angle_deg)
            point.co = (math.cos(angle) * radius, math.sin(angle) * radius, z, 1.0)
        obj = bpy.data.objects.new(name, curve)
        bpy.context.collection.objects.link(obj)
        obj.data.materials.append(materials[material_key])
        scene_gate.tag(obj, role)
        authored.append(obj)
        return obj

    accent_base = "base_cyan" if left else "base_coral"
    accent_button = "button_cyan" if left else "button_coral"
    accent_rim = "rim_blue" if left else "rim_orange"

    # Chunky tactile pedestal: deliberately wider than the glyph so the final
    # 32-36 px runtime icon still reads as a physical button rather than a flat
    # symbol pasted onto the HUD.
    box("CameraControlShadow", (0.0, 0.0, 0.055), (2.22, 2.12, 0.11),
        "base_shadow", bevel=0.10, contact=True, role="ui.camera_rotation.base")
    box("CameraControlBase", (0.0, 0.0, 0.14), (2.10, 2.00, 0.16),
        accent_base, bevel=0.10, role="ui.camera_rotation.base")
    box("CameraControlInset", (0.0, 0.0, 0.235), (1.86, 1.76, 0.07),
        "base_light", bevel=0.075, role="ui.camera_rotation.base")

    cylinder("CameraControlButtonShadow", (0.0, 0.0, 0.38), 0.84, 0.26,
             "button_shadow", role="ui.camera_rotation.button")
    cylinder("CameraControlButton", (0.0, 0.0, 0.54), 0.78, 0.30,
             accent_button, role="ui.camera_rotation.button")
    cylinder("CameraControlButtonFace", (0.0, 0.0, 0.705), 0.67, 0.045,
             accent_rim, role="ui.camera_rotation.highlight")

    # Proxy v1 read too much like a gauge at HUD size. V2 uses one continuous,
    # thick C-arrow occupying most of the button face, plus a much larger gold
    # arrowhead. Direction must be legible even after downsampling to ~34 px.
    if left:
        arc_angles = tuple(-45.0 + 17.5 * index for index in range(15))
        end_angle_deg = arc_angles[-1]
        tangent_deg = end_angle_deg + 90.0
    else:
        arc_angles = tuple(225.0 - 17.5 * index for index in range(15))
        end_angle_deg = arc_angles[-1]
        tangent_deg = end_angle_deg - 90.0

    arc_curve("CameraRotationArc", arc_angles, 0.49, 0.805, "arrow_white")

    end_angle = math.radians(end_angle_deg)
    arrow_x = math.cos(end_angle) * 0.54
    arrow_y = math.sin(end_angle) * 0.54
    triangle_prism(
        "CameraArrowHead",
        (arrow_x, arrow_y, 0.825),
        0.37,
        0.15,
        "arrow_gold",
        tangent_deg,
    )

    # Small central compass jewel gives the two controls individual color while
    # remaining subordinate to the large white/gold rotation glyph.
    cylinder("CameraCompassRing", (0.0, 0.0, 0.81), 0.20, 0.075,
             "arrow_gold", role="ui.camera_rotation.highlight")
    cylinder("CameraCompassGem", (0.0, 0.0, 0.855), 0.115, 0.075,
             "gem_teal" if left else "gem_purple",
             role="ui.camera_rotation.highlight")

    # Small warm highlight on the front edge gives both controls the same toy-
    # like polished read as the existing CH Blender topbar icons.
    box("CameraControlWarmHighlight", (0.0, -0.74, 0.39), (0.90, 0.10, 0.08),
        "sunny_yellow", bevel=0.035, role="ui.camera_rotation.highlight")

    return authored


def main():
    args = parse_args()
    spec = load_json(args.spec)
    if spec.get("contract") != "CH_UI_CAMERA_ROTATION_CONTROLS_V1":
        raise RuntimeError("Expected CH_UI_CAMERA_ROTATION_CONTROLS_V1 spec")
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
            value.get("name", key),
            value["rgba"],
            float(value.get("roughness", 0.72)),
            float(value.get("metallic", 0.0)),
        )
        for key, value in spec["materials"].items()
    }

    authored = build_asset(args.asset, materials)
    root = bs.create_asset_root(authored)
    asset_id = f"ui.camera_rotation.{args.asset}"
    root["assetId"] = asset_id
    root["assetType"] = "ui_camera_rotation_control"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["visualContract"] = "CH_STYLIZED_PRERENDER_V1"
    root["runtimeRepresentation"] = "2D_RGBA_pre_rendered_ui"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    root["uiSetContract"] = spec["contract"]

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

    # Tight crop is intentional: these controls render around 34 px in-game.
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.10)
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
        print(f"[CH_GATE] camera control {args.asset} preflight PASS: {preflight_path}")
        return

    proxy = scene_gate.render_proxy(
        scene=scene,
        authored=authored,
        output_path=output / "proxy_south.png",
        profile=profile,
        asset_id=asset_id,
        direction="south",
    )
    (output / "proxy_report.json").write_text(
        json.dumps(proxy, indent=2), encoding="utf-8"
    )
    save_blend(args.save_blend)
    print(f"[CH_GATE] camera control {args.asset} proxy PASS: {output / 'proxy_south.png'}")


if __name__ == "__main__":
    main()
