"""Guarded CH Blender authoring pass for the first City Horizon road SUV.

This asset intentionally stops at preflight/SOUTH proxy review. Runtime traffic,
headlight overlays and recolor masks are separate follow-up stages after the
silhouette and gameplay scale are approved.
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "tools" / "ch_blender"))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402

ASSET_ID = "vehicle.road.suv_01"


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=("preflight", "proxy"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    return parser.parse_args(argv)


def add_box(name, location, dimensions, material, bevel=0.05, rotation=(0.0, 0.0, 0.0)):
    obj = bs.add_box(name, location, dimensions, material, bevel=bevel)
    obj.rotation_euler = tuple(rotation)
    for modifier in obj.modifiers:
        if modifier.type == "BEVEL":
            modifier.segments = max(modifier.segments, 2)
    bpy.context.view_layer.update()
    return obj


def add_cabin_shell(material):
    """Create a compact trapezoidal SUV greenhouse/body shell.

    The lower cabin remains broad while the upper corners taper inward and both
    the windshield and rear header slope toward the roof. This keeps the proxy
    readable at gameplay scale without the box-on-box silhouette of V1.
    """
    x_bottom = 0.79
    x_top = 0.69
    y_front_bottom = -0.90
    y_rear_bottom = 1.22
    y_front_top = -0.53
    y_rear_top = 0.96
    z_bottom = 1.18
    z_top = 1.80
    vertices = [
        (-x_bottom, y_front_bottom, z_bottom),
        (x_bottom, y_front_bottom, z_bottom),
        (x_bottom, y_rear_bottom, z_bottom),
        (-x_bottom, y_rear_bottom, z_bottom),
        (-x_top, y_front_top, z_top),
        (x_top, y_front_top, z_top),
        (x_top, y_rear_top, z_top),
        (-x_top, y_rear_top, z_top),
    ]
    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    ]
    mesh = bpy.data.meshes.new("SUV_CabinShellMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    cabin = bpy.data.objects.new("SUV_CabinShell", mesh)
    bpy.context.collection.objects.link(cabin)
    cabin.data.materials.append(material)
    bevel = cabin.modifiers.new("CabinEdgeSoftening", "BEVEL")
    bevel.width = 0.075
    bevel.segments = 2
    scene_gate.tag(cabin, "vehicle.body")
    return cabin


def add_wheel(name, location, rubber, rim):
    # Vehicle longitudinal axis is Y; wheel axle is X. Cylinder primitive starts
    # on Z, so rotate it 90 degrees around Y.
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=24,
        radius=0.39,
        depth=0.24,
        location=location,
        rotation=(0.0, math.radians(90.0), 0.0),
    )
    tire = bpy.context.object
    tire.name = f"{name}_Tire"
    tire.data.materials.append(rubber)
    bevel = tire.modifiers.new("TireEdgeSoftening", "BEVEL")
    bevel.width = 0.035
    bevel.segments = 2
    scene_gate.tag(tire, "vehicle.wheel.tire")

    side = -1.0 if location[0] < 0.0 else 1.0
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=24,
        radius=0.225,
        depth=0.255,
        location=(location[0] + side * 0.004, location[1], location[2]),
        rotation=(0.0, math.radians(90.0), 0.0),
    )
    hub = bpy.context.object
    hub.name = f"{name}_Rim"
    hub.data.materials.append(rim)
    hub_bevel = hub.modifiers.new("RimEdgeSoftening", "BEVEL")
    hub_bevel.width = 0.018
    hub_bevel.segments = 2
    scene_gate.tag(hub, "vehicle.wheel.rim")
    return [tire, hub]


def build_suv():
    # One body colour by design. Black glass/rubber/bumpers and neutral metal
    # remain separate semantic materials so a future body-colour mask is trivial.
    body = bs.make_material("SUV_BodyColor", (0.88, 0.90, 0.92, 1.0), 0.38, 0.03)
    glass = bs.make_material("SUV_GlassDark", (0.025, 0.035, 0.045, 1.0), 0.20, 0.05)
    rubber = bs.make_material("SUV_Rubber", (0.018, 0.020, 0.022, 1.0), 0.88, 0.0)
    bumper = bs.make_material("SUV_BumperBlack", (0.028, 0.030, 0.032, 1.0), 0.76, 0.0)
    iron = bs.make_material("SUV_Iron", (0.38, 0.41, 0.44, 1.0), 0.34, 0.68)
    headlamp = bs.make_material("SUV_Headlamp", (0.82, 0.88, 0.86, 1.0), 0.18, 0.05)
    taillamp = bs.make_material("SUV_Taillamp", (0.48, 0.025, 0.018, 1.0), 0.24, 0.03)

    authored = []

    # SOUTH = nose toward -Y. The V2 silhouette keeps the same overall footprint
    # but uses a more tapered upper body and slightly softer major transitions.
    lower = add_box("SUV_LowerBody", (0.0, 0.0, 0.66), (1.84, 4.18, 0.58), body, 0.13)
    belt = add_box("SUV_BeltBody", (0.0, 0.03, 1.00), (1.76, 3.68, 0.44), body, 0.11)
    hood = add_box("SUV_Hood", (0.0, -1.47, 1.17), (1.64, 1.06, 0.25), body, 0.10,
                   (math.radians(-5.0), 0.0, 0.0))
    cabin = add_cabin_shell(body)
    roof = add_box("SUV_Roof", (0.0, 0.22, 1.84), (1.34, 1.44, 0.13), body, 0.09)
    authored.extend((lower, belt, hood, cabin, roof))
    for obj in (lower, belt, hood, roof):
        scene_gate.tag(obj, "vehicle.body")

    # Subtle body-colour shoulders over the wheel positions make the wheel arches
    # read as designed fenders rather than wheels intersecting a rectangular slab.
    for x in (-0.82, 0.82):
        for y in (-1.36, 1.36):
            shoulder = add_box(
                f"SUV_FenderShoulder_{'L' if x < 0 else 'R'}_{'F' if y < 0 else 'R'}",
                (x, y, 0.87), (0.22, 0.88, 0.24), body, 0.075,
            )
            authored.append(shoulder)
            scene_gate.tag(shoulder, "vehicle.body")

    # Dark glazing follows the new sloped greenhouse. Lamps remain non-emissive;
    # later night/rain lighting can be a separate overlay without changing body art.
    windshield = add_box("SUV_Windshield", (0.0, -0.715, 1.49), (1.36, 0.052, 0.50), glass, 0.022,
                         (math.radians(-30.0), 0.0, 0.0))
    rear_window = add_box("SUV_RearWindow", (0.0, 1.085, 1.49), (1.34, 0.052, 0.46), glass, 0.022,
                          (math.radians(24.0), 0.0, 0.0))
    left_windows = add_box("SUV_LeftWindows", (-0.735, 0.20, 1.50), (0.038, 1.56, 0.40), glass, 0.016)
    right_windows = add_box("SUV_RightWindows", (0.735, 0.20, 1.50), (0.038, 1.56, 0.40), glass, 0.016)
    authored.extend((windshield, rear_window, left_windows, right_windows))
    for obj in (windshield, rear_window, left_windows, right_windows):
        scene_gate.tag(obj, "vehicle.glass")

    # Pillars and restrained door seams improve readability at 50-60 px without
    # introducing a second paint colour or fine texture noise.
    for x in (-0.752, 0.752):
        side_name = "L" if x < 0 else "R"
        pillar = add_box(f"SUV_B_Pillar_{side_name}", (x, 0.20, 1.50),
                         (0.045, 0.12, 0.46), bumper, 0.008)
        seam_front = add_box(f"SUV_DoorSeamFront_{side_name}", (x, -0.38, 1.03),
                             (0.028, 0.025, 0.36), bumper, 0.005)
        seam_rear = add_box(f"SUV_DoorSeamRear_{side_name}", (x, 0.70, 1.03),
                            (0.028, 0.025, 0.36), bumper, 0.005)
        handle_front = add_box(f"SUV_HandleFront_{side_name}", (x, -0.20, 1.22),
                               (0.032, 0.24, 0.045), iron, 0.008)
        handle_rear = add_box(f"SUV_HandleRear_{side_name}", (x, 0.66, 1.22),
                              (0.032, 0.24, 0.045), iron, 0.008)
        authored.extend((pillar, seam_front, seam_rear, handle_front, handle_rear))
        for obj in (pillar, seam_front, seam_rear, handle_front, handle_rear):
            scene_gate.tag(obj, "vehicle.trim")

    # Black bumpers plus a simple grille pattern are deliberately chunky enough
    # to survive downsampling.
    front_bumper = add_box("SUV_FrontBumper", (0.0, -2.12, 0.66), (1.70, 0.16, 0.23), bumper, 0.055)
    rear_bumper = add_box("SUV_RearBumper", (0.0, 2.12, 0.66), (1.70, 0.16, 0.23), bumper, 0.055)
    grille = add_box("SUV_FrontGrille", (0.0, -2.205, 0.89), (0.72, 0.052, 0.25), bumper, 0.018)
    authored.extend((front_bumper, rear_bumper, grille))
    for obj in (front_bumper, rear_bumper, grille):
        scene_gate.tag(obj, "vehicle.bumper")
    for x in (-0.22, 0.0, 0.22):
        bar = add_box(f"SUV_GrilleBar_{x:+.2f}", (x, -2.238, 0.89),
                      (0.035, 0.025, 0.20), iron, 0.006)
        authored.append(bar)
        scene_gate.tag(bar, "vehicle.trim")

    for x in (-0.55, 0.55):
        light = add_box(f"SUV_Headlamp_{'L' if x < 0 else 'R'}", (x, -2.205, 1.03),
                        (0.40, 0.050, 0.17), headlamp, 0.025)
        authored.append(light)
        scene_gate.tag(light, "vehicle.light.front")
        tail = add_box(f"SUV_Taillamp_{'L' if x < 0 else 'R'}", (x, 2.205, 1.00),
                       (0.32, 0.050, 0.21), taillamp, 0.025)
        authored.append(tail)
        scene_gate.tag(tail, "vehicle.light.rear")

    # Four independent wheels with neutral grey rims, preserving clean material
    # separation for the future body-colour mask.
    for x in (-0.91, 0.91):
        for y in (-1.36, 1.36):
            authored.extend(add_wheel(
                f"SUV_Wheel_{'L' if x < 0 else 'R'}_{'F' if y < 0 else 'R'}",
                (x, y, 0.48), rubber, iron,
            ))

    # Compact body-colour mirrors; no chrome or extra paint region.
    for x in (-0.96, 0.96):
        mirror = add_box(f"SUV_Mirror_{'L' if x < 0 else 'R'}", (x, -0.51, 1.39),
                         (0.20, 0.26, 0.12), body, 0.055)
        authored.append(mirror)
        scene_gate.tag(mirror, "vehicle.body")

    return authored


def main():
    args = parse_args()
    studio = bs.load_json(args.studio_preset)
    profile = scene_gate.load_profile(args.preflight_profile)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    scene = bs.configure_scene(studio, (512, 512), str(output))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    authored = build_suv()
    root = bs.create_asset_root(authored)
    root["assetId"] = ASSET_ID
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["visualContract"] = "CH_STYLIZED_PRERENDER_V1"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    root["vehicleClass"] = "compact_suv"
    root["proxyRevision"] = 2
    root["bodyColorMaskReady"] = True
    root["runtimeTrafficReady"] = False
    root["headlightOverlayReady"] = False

    # Keep the frozen camera instead of auto-filling the frame. At the runtime
    # 128px canvas this preserves the intended visual scale against ~64px actors.
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    report = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint={"widthTiles": 1, "depthTiles": 2},
        profile=profile,
        asset_id=ASSET_ID,
        report_path=output / "preflight_report.json",
    )
    scene_gate.require_pass(report)

    if args.stage == "proxy":
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=output / "proxy_south.png",
            profile=profile,
            asset_id=ASSET_ID,
            direction="south",
        )
        (output / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
