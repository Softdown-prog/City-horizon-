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
    bpy.context.view_layer.update()
    return obj


def add_wheel(name, location, rubber, rim):
    # Vehicle longitudinal axis is Y; wheel axle is X. Cylinder primitive starts
    # on Z, so rotate it 90 degrees around Y.
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=20,
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
        vertices=20,
        radius=0.225,
        depth=0.255,
        location=(location[0] + side * 0.004, location[1], location[2]),
        rotation=(0.0, math.radians(90.0), 0.0),
    )
    hub = bpy.context.object
    hub.name = f"{name}_Rim"
    hub.data.materials.append(rim)
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

    # SOUTH = nose toward -Y. Broad simple masses are intentional: at the
    # eventual ~50-60 px gameplay size the silhouette must read before trim.
    lower = add_box("SUV_LowerBody", (0.0, 0.0, 0.66), (1.84, 4.18, 0.58), body, 0.11)
    belt = add_box("SUV_BeltBody", (0.0, 0.05, 1.02), (1.76, 3.72, 0.48), body, 0.10)
    hood = add_box("SUV_Hood", (0.0, -1.45, 1.18), (1.66, 1.02, 0.28), body, 0.09,
                   (math.radians(-3.0), 0.0, 0.0))
    cabin = add_box("SUV_Cabin", (0.0, 0.20, 1.48), (1.58, 2.18, 0.72), body, 0.12)
    roof = add_box("SUV_Roof", (0.0, 0.27, 1.82), (1.42, 1.76, 0.16), body, 0.08)
    authored.extend((lower, belt, hood, cabin, roof))
    for obj in (lower, belt, hood, cabin, roof):
        scene_gate.tag(obj, "vehicle.body")

    # Dark glazing: windshield/rear glass plus uninterrupted side glass bands.
    windshield = add_box("SUV_Windshield", (0.0, -0.91, 1.53), (1.39, 0.055, 0.48), glass, 0.025,
                         (math.radians(-12.0), 0.0, 0.0))
    rear_window = add_box("SUV_RearWindow", (0.0, 1.29, 1.50), (1.38, 0.055, 0.44), glass, 0.025,
                          (math.radians(8.0), 0.0, 0.0))
    left_windows = add_box("SUV_LeftWindows", (-0.805, 0.19, 1.50), (0.045, 1.79, 0.43), glass, 0.018)
    right_windows = add_box("SUV_RightWindows", (0.805, 0.19, 1.50), (0.045, 1.79, 0.43), glass, 0.018)
    authored.extend((windshield, rear_window, left_windows, right_windows))
    for obj in (windshield, rear_window, left_windows, right_windows):
        scene_gate.tag(obj, "vehicle.glass")

    # B pillars break up the glass without introducing a second body colour.
    for x in (-0.824, 0.824):
        pillar = add_box(f"SUV_B_Pillar_{'L' if x < 0 else 'R'}", (x, 0.22, 1.50),
                         (0.052, 0.13, 0.48), bumper, 0.01)
        authored.append(pillar)
        scene_gate.tag(pillar, "vehicle.trim")

    # Black bumpers and grille are deliberately chunky enough to survive
    # downsampling. Head/tail lamps are unlit materials; future weather/night
    # lighting will use overlays instead of emissive geometry.
    front_bumper = add_box("SUV_FrontBumper", (0.0, -2.12, 0.66), (1.72, 0.16, 0.24), bumper, 0.045)
    rear_bumper = add_box("SUV_RearBumper", (0.0, 2.12, 0.66), (1.72, 0.16, 0.24), bumper, 0.045)
    grille = add_box("SUV_FrontGrille", (0.0, -2.205, 0.89), (0.72, 0.055, 0.28), bumper, 0.02)
    authored.extend((front_bumper, rear_bumper, grille))
    for obj in (front_bumper, rear_bumper, grille):
        scene_gate.tag(obj, "vehicle.bumper")

    for x in (-0.55, 0.55):
        light = add_box(f"SUV_Headlamp_{'L' if x < 0 else 'R'}", (x, -2.205, 1.03),
                        (0.42, 0.052, 0.18), headlamp, 0.025)
        authored.append(light)
        scene_gate.tag(light, "vehicle.light.front")
        tail = add_box(f"SUV_Taillamp_{'L' if x < 0 else 'R'}", (x, 2.205, 1.00),
                       (0.34, 0.052, 0.22), taillamp, 0.025)
        authored.append(tail)
        scene_gate.tag(tail, "vehicle.light.rear")

    # Four independent wheels with grey iron rims, matching the requested
    # simple tyre/body material separation for later recolour masks.
    for x in (-0.91, 0.91):
        for y in (-1.36, 1.36):
            authored.extend(add_wheel(
                f"SUV_Wheel_{'L' if x < 0 else 'R'}_{'F' if y < 0 else 'R'}",
                (x, y, 0.48), rubber, iron,
            ))

    # Compact body-colour mirrors; no chrome or extra paint region.
    for x in (-0.98, 0.98):
        mirror = add_box(f"SUV_Mirror_{'L' if x < 0 else 'R'}", (x, -0.52, 1.39),
                         (0.22, 0.28, 0.13), body, 0.055)
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
