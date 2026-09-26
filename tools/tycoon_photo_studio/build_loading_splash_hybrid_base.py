"""Build the 3D foundation for a City Horizon loading-screen key art.

This is presentation art, not gameplay.  It deliberately ignores CH_CAMERA_V1,
footprints, runtime asset inventory and four-direction rules.  The result is a
cinematic 3D foundation intended to receive a separate 2D paint-over pass.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_loading_splash_storybook import (  # noqa: E402
    add_box,
    add_cylinder,
    add_cylinder_between,
    add_ferris_wheel,
    add_lamp,
    add_tree,
    add_uv_sphere,
    clear_scene,
    look_at,
    material,
    ribbon,
)

CONTRACT = "CH_LOADING_SPLASH_ART_V1"
PROXY_RES = (1280, 720)
FINAL_RES = (2560, 1440)


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--final", action="store_true")
    return p.parse_args(argv)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def add_tower(name, x, y, radius, height, body, glass, crown, rng):
    # Tapered stacked tower: deliberately illustration-like rather than realistic.
    tiers = 5
    for i in range(tiers):
        z0 = height * i / tiers
        h = height / tiers + 0.08
        r = radius * (1.0 - 0.065 * i)
        add_cylinder(f"{name}_Tier_{i}", (x, y, z0 + h * 0.5), r, h, body, 16)
        if i > 0:
            band_z = z0 + h * 0.18
            add_cylinder(f"{name}_Band_{i}", (x, y - r * 0.86, band_z), r * 0.86, 0.12, glass, 16, rotation=(math.pi / 2, 0, 0))
    add_cylinder(f"{name}_Crown", (x, y, height + 0.35), radius * 0.55, 0.7, crown, 16)
    add_cylinder_between(f"{name}_Spire", (x, y, height + 0.7), (x, y, height + 2.2), 0.08, crown, 10)


def add_rowhouse(name, x, y, w, d, h, body, trim, glass, roof):
    add_box(f"{name}_Body", (x, y, h * 0.5), (w, d, h), body, 0.18)
    add_box(f"{name}_Roof", (x, y, h + 0.28), (w * 1.06, d * 1.06, 0.42), roof, 0.10)
    # Wide storefront at ground level.
    add_box(f"{name}_Store", (x, y - d * 0.515, 1.0), (w * 0.72, 0.10, 1.25), glass, 0.06)
    add_box(f"{name}_Awning", (x, y - d * 0.66, 1.65), (w * 0.78, 0.65, 0.16), trim, 0.05, rotation=(math.radians(-7), 0, 0))
    rows = max(2, int(h // 1.7))
    cols = max(2, int(w // 1.5))
    for r in range(rows - 1):
        z = 2.5 + r * 1.55
        for c in range(cols):
            xx = x - w * 0.34 + c * (w * 0.68 / max(1, cols - 1))
            add_box(f"{name}_Window_{r}_{c}", (xx, y - d * 0.516, z), (0.62, 0.09, 0.78), glass, 0.04)


def add_bridge(name, x, y, length, width, deck, rail, glow):
    add_box(f"{name}_Deck", (x, y, 0.65), (length, width, 0.55), deck, 0.10, rotation=(0, 0, math.radians(-9)))
    # Four simple pylons + luminous rails.
    for sx in (-0.42, 0.42):
        for sy in (-0.42, 0.42):
            px = x + sx * length
            py = y + sy * width
            add_cylinder(f"{name}_Pylon_{sx}_{sy}", (px, py, 2.1), 0.11, 3.1, rail, 12)
    for side in (-1, 1):
        a = (x - length * 0.48, y + side * width * 0.43, 1.15)
        b = (x + length * 0.48, y + side * width * 0.43, 1.15)
        add_cylinder_between(f"{name}_GlowRail_{side}", a, b, 0.055, glow, 10)


def add_crane(name, x, y, scale, metal, accent):
    z_top = 10.5 * scale
    add_box(f"{name}_Mast", (x, y, z_top * 0.5), (0.55 * scale, 0.55 * scale, z_top), metal, 0.05)
    add_cylinder_between(f"{name}_Jib", (x, y, z_top), (x + 8.5 * scale, y, z_top), 0.10 * scale, accent, 8)
    add_cylinder_between(f"{name}_BackJib", (x, y, z_top), (x - 3.2 * scale, y, z_top), 0.11 * scale, metal, 8)
    add_cylinder_between(f"{name}_Cable", (x + 5.5 * scale, y, z_top), (x + 5.5 * scale, y, 4.5 * scale), 0.025 * scale, metal, 8)
    add_box(f"{name}_Load", (x + 5.5 * scale, y, 4.15 * scale), (1.4 * scale, 0.85 * scale, 0.6 * scale), accent, 0.08)


def add_people_cluster(prefix, points, mats):
    # Tiny, abstract citizens. They sell scale without becoming character assets.
    colors = [mats["coral"], mats["gold"], mats["cyan"], mats["violet"], mats["cream"]]
    for i, (x, y, s) in enumerate(points):
        m = colors[i % len(colors)]
        add_cylinder(f"{prefix}_{i}_Body", (x, y, 0.52 * s), 0.12 * s, 0.75 * s, m, 12)
        add_uv_sphere(f"{prefix}_{i}_Head", (x, y, 1.02 * s), (0.15 * s, 0.15 * s, 0.15 * s), mats["skin"], 16)


def setup_scene(recipe, final=False):
    clear_scene()
    rng = random.Random(int(recipe.get("seed", 26092604)))
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x, scene.render.resolution_y = FINAL_RES if final else PROXY_RES
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.render.use_file_extension = True
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass

    world = bpy.data.worlds.new("HybridSplashWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.045, 0.075, 0.15, 1.0)
    bg.inputs["Strength"].default_value = 0.55

    mats = {
        "ground": material("Ground", (0.09, 0.24, 0.16, 1), roughness=0.92),
        "water": material("Water", (0.025, 0.22, 0.38, 1), roughness=0.28, metallic=0.05),
        "road": material("Road", (0.055, 0.065, 0.09, 1), roughness=0.90),
        "walk": material("Walk", (0.64, 0.55, 0.48, 1), roughness=0.84),
        "cream": material("Cream", (0.95, 0.78, 0.57, 1), roughness=0.58),
        "coral": material("Coral", (0.92, 0.23, 0.20, 1), roughness=0.54),
        "gold": material("Gold", (1.0, 0.56, 0.12, 1), roughness=0.52),
        "cyan": material("Cyan", (0.05, 0.62, 0.68, 1), roughness=0.50),
        "blue": material("Blue", (0.06, 0.24, 0.62, 1), roughness=0.56),
        "violet": material("Violet", (0.44, 0.16, 0.62, 1), roughness=0.56),
        "mint": material("Mint", (0.20, 0.60, 0.42, 1), roughness=0.62),
        "dark": material("Dark", (0.035, 0.042, 0.065, 1), roughness=0.72),
        "roof": material("Roof", (0.17, 0.06, 0.08, 1), roughness=0.72),
        "trunk": material("Trunk", (0.18, 0.075, 0.03, 1), roughness=0.88),
        "leaf_a": material("LeafA", (0.075, 0.30, 0.16, 1), roughness=0.83),
        "leaf_b": material("LeafB", (0.18, 0.48, 0.23, 1), roughness=0.80),
        "glass": material("GlassGlow", (0.20, 0.44, 0.62, 1), roughness=0.24, emission=(0.30, 0.72, 1.0, 1), emission_strength=1.65),
        "lamp": material("Lamp", (1.0, 0.60, 0.20, 1), roughness=0.28, emission=(1.0, 0.40, 0.09, 1), emission_strength=5.0),
        "wheel_glow": material("WheelGlow", (0.11, 0.76, 0.84, 1), roughness=0.30, emission=(0.07, 0.66, 0.95, 1), emission_strength=3.5),
        "haze": material("SkylineHaze", (0.11, 0.12, 0.22, 1), roughness=0.88),
        "skin": material("Skin", (0.70, 0.42, 0.28, 1), roughness=0.80),
    }

    # Large stage, river and curving boulevard create depth instead of a flat facade wall.
    add_box("Ground", (0, 8, -0.55), (64, 48, 1.0), mats["ground"], 0.0)
    river = [(-30, -12), (-20, -9), (-10, -7), (0, -6), (10, -4), (20, -1), (30, 3)]
    ribbon("River", river, 9.5, 0.02, mats["water"])
    boulevard = [(-26, 3), (-18, 3.2), (-10, 4.0), (-2, 5.5), (7, 7.6), (16, 10.7), (27, 15.5)]
    ribbon("Boulevard", boulevard, 6.3, 0.10, mats["road"])
    ribbon("WalkA", [(x, y + 3.75) for x, y in boulevard], 1.4, 0.16, mats["walk"])
    ribbon("WalkB", [(x, y - 3.75) for x, y in boulevard], 1.4, 0.16, mats["walk"])

    add_bridge("RiverBridge", 3.0, -5.0, 12.5, 4.2, mats["walk"], mats["dark"], mats["lamp"])

    # Distant skyline: silhouettes only. 2D pass will push these further into haze.
    for i, x in enumerate(range(-28, 29, 4)):
        h = 4.0 + (i * 1.37 % 7.0)
        add_box(f"Skyline_{i}", (x, 22 + (i % 3) * 1.8, h * 0.5), (3.0 + (i % 2), 3.6, h), mats["haze"], 0.14)

    # Midground neighborhood with varied heights and storefront rhythm.
    bodies = [mats["coral"], mats["cyan"], mats["violet"], mats["gold"], mats["mint"], mats["blue"]]
    x = -19.5
    for i in range(7):
        w = 4.0 + (i % 2) * 0.7
        h = 5.6 + (i * 1.25 % 4.8)
        y = 10.4 + i * 0.75
        add_rowhouse(f"Block_{i}", x, y, w, 4.2, h, bodies[i % len(bodies)], mats["cream"], mats["glass"], mats["roof"])
        x += w * 0.92

    # Hero skyline pieces.
    add_tower("CivicTower", -2.0, 15.0, 2.25, 16.2, mats["cyan"], mats["glass"], mats["cream"], rng)
    add_tower("BlueTower", 6.5, 17.5, 1.85, 12.8, mats["blue"], mats["glass"], mats["gold"], rng)
    add_crane("ConstructionCrane", -17.5, 18.5, 1.0, mats["dark"], mats["gold"])

    # Park district and wheel live on the right but no longer dominate the whole image.
    add_ferris_wheel((17.0, 14.0, 7.2), 6.3, mats)
    for i, (tx, ty, s) in enumerate([
        (-22, 0.5, 1.15), (-17, 0.9, 0.95), (-12, 1.8, 1.05), (-6, 2.6, 0.9),
        (2, 4.0, 1.0), (8, 6.5, 1.1), (12, 8.4, 0.95), (21, 11.5, 1.2), (25, 14.2, 1.0),
    ]):
        add_tree(f"Tree_{i}", tx, ty, s, mats["trunk"], mats["leaf_a"], mats["leaf_b"])

    for i, (lx, ly) in enumerate([(-20, 1.6), (-14, 2.2), (-8, 3.2), (-1, 5.0), (5, 6.8), (11, 9.1), (16, 11.3)]):
        add_lamp(f"Lamp_{i}", lx, ly, mats["dark"], mats["lamp"])

    add_people_cluster("People", [
        (-14.5, 0.6, 1.0), (-13.8, 0.9, 0.95), (-7.0, 2.0, 1.05), (-5.9, 2.35, 0.92),
        (1.7, 4.2, 0.95), (2.4, 4.5, 1.0), (9.0, 7.4, 0.92), (10.0, 7.8, 1.02),
    ], mats)

    # Foreground framing shapes add cinematic depth.
    add_tree("ForegroundTreeL", -27.0, -8.8, 2.8, mats["trunk"], mats["leaf_a"], mats["leaf_b"])
    add_tree("ForegroundTreeR", 27.0, -4.8, 2.45, mats["trunk"], mats["leaf_a"], mats["leaf_b"])
    add_lamp("ForegroundLamp", -9.5, -5.5, mats["dark"], mats["lamp"])

    # Lighting: warm sunset from left, cool city fill from right.
    bpy.ops.object.light_add(type="AREA", location=(-18.0, -10.0, 24.0))
    key = bpy.context.object
    key.data.energy = 2200.0
    key.data.size = 14.0
    key.data.color = (1.0, 0.34, 0.10)
    look_at(key, (0.0, 8.0, 4.0))

    bpy.ops.object.light_add(type="AREA", location=(22.0, -2.0, 17.0))
    fill = bpy.context.object
    fill.data.energy = 1050.0
    fill.data.size = 12.0
    fill.data.color = (0.10, 0.34, 1.0)
    look_at(fill, (6.0, 9.0, 5.0))

    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(32), 0.0, math.radians(-52)))
    sun = bpy.context.object.data
    sun.energy = 1.45
    sun.color = (1.0, 0.45, 0.20)
    sun.angle = math.radians(18)

    # Aerial 3/4 perspective: still cinematic, but clearly different from gameplay iso.
    cam_cfg = recipe.get("camera", {})
    bpy.ops.object.camera_add(location=tuple(cam_cfg.get("location", [-22.0, -31.0, 22.0])))
    camera = bpy.context.object
    camera.data.lens = float(cam_cfg.get("lensMm", 44.0))
    look_at(camera, tuple(cam_cfg.get("target", [0.5, 7.5, 4.7])))
    camera.data.dof.use_dof = True
    camera.data.dof.focus_object = bpy.data.objects.get("CivicTower_Tier_2")
    camera.data.dof.aperture_fstop = 5.2
    scene.camera = camera

    scene.use_nodes = True
    nt = scene.node_tree
    nt.nodes.clear()
    render = nt.nodes.new("CompositorNodeRLayers")
    glare = nt.nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    glare.quality = "HIGH"
    glare.threshold = 0.9
    glare.size = 6
    comp = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(render.outputs["Image"], glare.inputs["Image"])
    nt.links.new(glare.outputs["Image"], comp.inputs["Image"])
    return scene


def main():
    args = parse_args()
    recipe = load_json(args.recipe)
    if recipe.get("contract") != CONTRACT:
        raise RuntimeError(f"Expected {CONTRACT}")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    scene = setup_scene(recipe, args.final)
    filename = "loading_splash_base_final.png" if args.final else "loading_splash_base.png"
    scene.render.filepath = str(out / filename)
    bpy.ops.render.render(write_still=True)
    report = {
        "contract": CONTRACT,
        "artId": recipe.get("artId"),
        "status": "3d_base_rendered",
        "presentationOnly": True,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "output": filename,
        "nextPass": "2d_paintover",
    }
    (out / "loading_splash_base_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
