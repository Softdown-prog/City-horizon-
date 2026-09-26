"""Render City Horizon loading key art as a storybook twilight illustration.

This renderer is intentionally presentation-only. It does not obey gameplay
camera, grid, footprints, runtime inventory, or four-direction asset rules.
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


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def material(name, color, *, roughness=0.72, metallic=0.0, emission=None, emission_strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = tuple(color)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission is not None:
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = tuple(emission)
            bsdf.inputs["Emission Strength"].default_value = emission_strength
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value = tuple(emission)
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    return m


def add_box(name, loc, size, mat, bevel=0.08, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = (size[0] * 0.5, size[1] * 0.5, size[2] * 0.5)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        obj.data.materials.append(mat)
    if bevel > 0:
        mod = obj.modifiers.new("SoftEdges", "BEVEL")
        mod.width = bevel
        mod.segments = 3
    return obj


def add_cylinder(name, loc, radius, depth, mat, vertices=24, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    if mat:
        obj.data.materials.append(mat)
    return obj


def add_uv_sphere(name, loc, scale, mat, segments=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=16, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    if mat:
        obj.data.materials.append(mat)
    return obj


def add_cylinder_between(name, a, b, radius, mat, vertices=12):
    a, b = Vector(a), Vector(b)
    d = b - a
    if d.length <= 1e-6:
        return None
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=d.length, location=(a + b) * 0.5)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    if mat:
        obj.data.materials.append(mat)
    return obj


def ribbon(name, points, width, z, mat):
    pts = [Vector((float(x), float(y), z)) for x, y in points]
    verts, faces = [], []
    for i, p in enumerate(pts):
        if i == 0:
            tangent = pts[1] - pts[0]
        elif i == len(pts) - 1:
            tangent = pts[-1] - pts[-2]
        else:
            tangent = pts[i + 1] - pts[i - 1]
        tangent.z = 0
        tangent.normalize()
        normal = Vector((-tangent.y, tangent.x, 0))
        verts += [tuple(p + normal * width * 0.5), tuple(p - normal * width * 0.5)]
    for i in range(len(pts) - 1):
        a = i * 2
        faces.append((a, a + 1, a + 3, a + 2))
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def add_arch_window(name, x, y, z, w, h, frame_mat, glass_mat):
    add_box(name + "_Glass", (x, y, z), (w, 0.08, h), glass_mat, 0.03)
    add_box(name + "_Top", (x, y - 0.015, z + h * 0.52), (w * 1.08, 0.12, 0.12), frame_mat, 0.02)


def add_story_building(name, x, y, w, d, h, body, trim, roof, glass, rng, *, tower=False):
    add_box(name + "_Body", (x, y, h * 0.5), (w, d, h), body, 0.24)
    base_h = min(0.55, h * 0.1)
    add_box(name + "_Base", (x, y - d * 0.51, base_h * 0.5), (w * 0.96, 0.22, base_h), trim, 0.05)
    if tower:
        bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=w * 0.73, radius2=0.0, depth=min(3.4, h * 0.38), location=(x, y, h + min(1.7, h * 0.19)), rotation=(0.0, 0.0, math.radians(45)))
        bpy.context.object.data.materials.append(roof)
    else:
        add_box(name + "_Roof", (x, y, h + 0.30), (w * 1.07, d * 1.07, 0.42), roof, 0.15)
        if rng.random() < 0.7:
            add_box(name + "_RoofFeature", (x + w * 0.18, y, h + 0.78), (w * 0.34, d * 0.48, 0.70), trim, 0.16)

    rows = max(2, int(h // 1.8))
    cols = max(2, int(w // 1.5))
    for r in range(rows):
        z = 1.15 + r * max(1.25, (h - 2.0) / max(1, rows - 1))
        for c in range(cols):
            xx = x - w * 0.34 + c * (w * 0.68 / max(1, cols - 1))
            add_arch_window(f"{name}_Win_{r}_{c}", xx, y - d * 0.505, z, min(0.82, w * 0.18), 0.86, trim, glass)

    if not tower and w > 3.2:
        add_box(name + "_Awning", (x, y - d * 0.63, 1.25), (w * 0.55, 0.80, 0.20), trim, 0.06, rotation=(math.radians(-8), 0.0, 0.0))


def add_tree(name, x, y, scale, trunk, leaf_a, leaf_b):
    add_cylinder(name + "_Trunk", (x, y, 1.05 * scale), 0.24 * scale, 2.1 * scale, trunk, 14)
    clusters = [(0.0, 0.0, 2.65, 1.22), (-0.70, 0.08, 2.40, 0.88), (0.66, 0.12, 2.42, 0.92), (0.12, -0.52, 2.36, 0.84), (-0.10, 0.38, 3.05, 0.74)]
    for i, (ox, oy, oz, s) in enumerate(clusters):
        add_uv_sphere(f"{name}_Leaf_{i}", (x + ox * scale, y + oy * scale, oz * scale), (s * scale, s * 0.90 * scale, s * 0.82 * scale), leaf_a if i % 2 == 0 else leaf_b, 24)


def add_lamp(name, x, y, pole_mat, glow_mat):
    add_cylinder(name + "_Pole", (x, y, 1.65), 0.07, 3.3, pole_mat, 14)
    add_uv_sphere(name + "_Globe", (x, y, 3.35), (0.28, 0.28, 0.28), glow_mat, 20)
    bpy.ops.object.light_add(type="POINT", location=(x, y, 3.35))
    light = bpy.context.object.data
    light.color = (1.0, 0.45, 0.16)
    light.energy = 180.0
    light.shadow_soft_size = 1.2


def add_banner(name, a, b, color_a, color_b, string_mat):
    add_cylinder_between(name + "_Cord", a, b, 0.025, string_mat, 8)
    a, b = Vector(a), Vector(b)
    for i in range(1, 8):
        p = a.lerp(b, i / 8.0)
        mat = color_a if i % 2 else color_b
        add_box(f"{name}_Flag_{i}", (p.x, p.y, p.z - 0.24), (0.34, 0.06, 0.46), mat, 0.02, rotation=(0.0, 0.0, math.radians((i - 4) * 1.5)))


def add_ferris_wheel(center, radius, mats):
    cx, cy, cz = center
    rim = mats["wheel_glow"]
    for depth in (-0.48, 0.48):
        for i in range(56):
            a0 = 2 * math.pi * i / 56
            a1 = 2 * math.pi * (i + 1) / 56
            p0 = (cx + math.cos(a0) * radius, cy + depth, cz + math.sin(a0) * radius)
            p1 = (cx + math.cos(a1) * radius, cy + depth, cz + math.sin(a1) * radius)
            add_cylinder_between(f"Rim_{depth}_{i}", p0, p1, 0.075, rim, 10)

    add_cylinder("WheelHub", (cx, cy, cz), 0.48, 1.6, mats["cream"], 28, rotation=(math.pi / 2, 0, 0))
    for i in range(18):
        a = 2 * math.pi * i / 18
        for depth in (-0.42, 0.42):
            p = (cx + math.cos(a) * radius, cy + depth, cz + math.sin(a) * radius)
            add_cylinder_between(f"Spoke_{i}_{depth}", (cx, cy + depth, cz), p, 0.045, rim, 9)

    cabins = [mats["coral"], mats["gold"], mats["purple"], mats["blue"]]
    for i in range(14):
        a = 2 * math.pi * i / 14 + math.radians(4)
        x = cx + math.cos(a) * radius
        z = cz + math.sin(a) * radius
        add_box(f"Cabin_{i}", (x, cy, z - 0.20), (1.10, 1.08, 0.82), cabins[i % len(cabins)], 0.18)
        add_box(f"CabinRoof_{i}", (x, cy, z + 0.30), (1.20, 1.18, 0.16), mats["cream"], 0.07)
        add_uv_sphere(f"CabinLamp_{i}", (x, cy - 0.57, z - 0.05), (0.08, 0.08, 0.08), mats["lamp"], 12)

    for sx in (-1.0, 1.0):
        add_cylinder_between(f"Support_{sx}_A", (cx + sx * 3.4, cy, 0.35), (cx + sx * 0.45, cy, cz), 0.18, mats["cream"], 16)
        add_cylinder_between(f"Support_{sx}_B", (cx + sx * 3.4, cy + 1.0, 0.35), (cx + sx * 0.45, cy + 0.12, cz), 0.18, mats["cream"], 16)
    add_box("WheelPlatform", (cx, cy, 0.16), (8.8, 3.8, 0.32), mats["dark"], 0.14)


def setup_scene(recipe, final=False):
    clear_scene()
    rng = random.Random(int(recipe.get("seed", 260926)))
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x, scene.render.resolution_y = FINAL_RES if final else PROXY_RES
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.image_settings.color_depth = "8"
    scene.render.use_file_extension = True
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass

    world = bpy.data.worlds.new("StorybookWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.035, 0.055, 0.13, 1.0)
    bg.inputs["Strength"].default_value = 0.45

    mats = {
        "ground": material("Ground", (0.08, 0.18, 0.15, 1), roughness=0.94),
        "road": material("Road", (0.045, 0.055, 0.08, 1), roughness=0.90),
        "sidewalk": material("Sidewalk", (0.52, 0.50, 0.48, 1), roughness=0.86),
        "cream": material("Cream", (0.94, 0.72, 0.48, 1), roughness=0.62),
        "coral": material("Coral", (0.88, 0.20, 0.22, 1), roughness=0.58),
        "teal": material("Teal", (0.04, 0.55, 0.58, 1), roughness=0.56),
        "blue": material("Blue", (0.06, 0.22, 0.58, 1), roughness=0.58),
        "purple": material("Purple", (0.40, 0.12, 0.58, 1), roughness=0.58),
        "gold": material("Gold", (0.96, 0.46, 0.10, 1), roughness=0.55),
        "rose": material("Rose", (0.68, 0.20, 0.38, 1), roughness=0.60),
        "dark": material("Dark", (0.035, 0.045, 0.07, 1), roughness=0.72),
        "roof": material("Roof", (0.13, 0.055, 0.09, 1), roughness=0.76),
        "trunk": material("Trunk", (0.20, 0.08, 0.035, 1), roughness=0.90),
        "leaf_a": material("LeafA", (0.08, 0.29, 0.15, 1), roughness=0.84),
        "leaf_b": material("LeafB", (0.20, 0.48, 0.22, 1), roughness=0.82),
        "glass": material("WindowGlow", (0.19, 0.40, 0.60, 1), roughness=0.28, emission=(0.35, 0.70, 1.0, 1), emission_strength=1.3),
        "lamp": material("LampGlow", (1.0, 0.56, 0.18, 1), roughness=0.30, emission=(1.0, 0.34, 0.07, 1), emission_strength=4.0),
        "wheel_glow": material("WheelGlow", (0.12, 0.78, 0.82, 1), roughness=0.36, emission=(0.06, 0.65, 0.85, 1), emission_strength=2.8),
        "skyline": material("SkylineHaze", (0.08, 0.08, 0.16, 1), roughness=0.86),
        "sun": material("Sun", (1.0, 0.28, 0.06, 1), roughness=0.25, emission=(1.0, 0.12, 0.02, 1), emission_strength=6.0),
    }

    add_box("GroundStage", (0, 6, -0.45), (48, 40, 0.9), mats["ground"], 0.0)

    far_xs = [-19, -16, -13, -10, -7, -4, -1, 2, 5, 8, 11, 14, 17]
    for i, x in enumerate(far_xs):
        h = 4.0 + (i * 1.7 % 5.5)
        w = 2.8 + (i % 3) * 0.65
        add_box(f"Far_{i}", (x, 15.5 + (i % 2) * 1.2, h * 0.5), (w, 3.4, h), mats["skyline"], 0.20)

    add_uv_sphere("SunDisk", (-12.0, 20.0, 10.8), (2.8, 0.55, 2.8), mats["sun"], 32)

    road_points = [(-19, -7), (-13, -4.5), (-7, -2.5), (-1, -1.0), (5, 0.8), (11, 3.6), (18, 7.5)]
    ribbon("Boulevard", road_points, 6.4, 0.03, mats["road"])
    ribbon("BoulevardWalkL", [(x - 0.1, y + 3.65) for x, y in road_points], 1.15, 0.08, mats["sidewalk"])
    ribbon("BoulevardWalkR", [(x + 0.1, y - 3.65) for x, y in road_points], 1.15, 0.08, mats["sidewalk"])

    bspec = [
        (-13.0, 5.0, 5.4, 4.2, 9.8, mats["rose"], mats["cream"], False),
        (-8.3, 5.8, 4.7, 4.0, 7.4, mats["teal"], mats["gold"], False),
        (-4.1, 6.9, 5.0, 4.4, 12.0, mats["blue"], mats["cream"], True),
        (1.2, 7.9, 4.8, 4.2, 8.4, mats["purple"], mats["coral"], False),
        (5.9, 9.3, 4.5, 4.0, 10.8, mats["gold"], mats["cream"], False),
    ]
    for i, (x, y, w, d, h, body, trim, tower) in enumerate(bspec):
        add_story_building(f"HeroBuilding_{i}", x, y, w, d, h, body, trim, mats["roof"], mats["glass"], rng, tower=tower)

    add_ferris_wheel((11.7, 11.5, 8.5), 7.4, mats)

    for i, (x, y, s) in enumerate([(-14, -0.6, 1.05), (-10.3, -0.2, 0.95), (-6.0, 0.1, 1.15), (-0.5, 1.5, 0.95), (4.4, 3.5, 1.10), (8.0, 5.2, 0.98), (15.0, 8.6, 1.18), (17.8, 10.2, 1.04)]):
        add_tree(f"Tree_{i}", x, y, s, mats["trunk"], mats["leaf_a"], mats["leaf_b"])

    for i, (x, y) in enumerate([(-11.8, -2.6), (-7.3, -1.2), (-2.5, 0.0), (2.2, 1.7), (6.2, 3.8), (9.2, 5.9)]):
        add_lamp(f"Lamp_{i}", x, y, mats["dark"], mats["lamp"])

    add_banner("BuntingA", (-10.0, 2.5, 7.4), (-2.5, 4.2, 7.0), mats["coral"], mats["gold"], mats["dark"])
    add_banner("BuntingB", (-1.8, 4.0, 8.0), (5.2, 5.8, 7.4), mats["teal"], mats["purple"], mats["dark"])

    add_tree("ForegroundTreeL", -18.5, -8.6, 2.5, mats["trunk"], mats["leaf_a"], mats["leaf_b"])
    add_tree("ForegroundTreeR", 18.5, -6.8, 2.2, mats["trunk"], mats["leaf_a"], mats["leaf_b"])
    add_lamp("ForegroundLamp", -7.0, -7.2, mats["dark"], mats["lamp"])

    add_uv_sphere("Balloon", (7.5, 17.5, 18.0), (1.1, 1.1, 1.5), mats["coral"], 28)
    add_box("BalloonBasket", (7.5, 17.5, 16.0), (0.65, 0.55, 0.45), mats["gold"], 0.08)
    for sx in (-0.32, 0.32):
        add_cylinder_between(f"BalloonRope_{sx}", (7.5 + sx, 17.5, 17.0), (7.5 + sx * 0.7, 17.5, 16.25), 0.022, mats["dark"], 8)

    bpy.ops.object.light_add(type="AREA", location=(-7.0, -8.0, 18.0))
    key = bpy.context.object
    key.data.energy = 1800.0
    key.data.shape = "DISK"
    key.data.size = 12.0
    key.data.color = (1.0, 0.34, 0.12)
    look_at(key, (0.0, 5.0, 3.0))

    bpy.ops.object.light_add(type="AREA", location=(16.0, -1.0, 15.0))
    fill = bpy.context.object
    fill.data.energy = 900.0
    fill.data.size = 10.0
    fill.data.color = (0.12, 0.34, 1.0)
    look_at(fill, (5.0, 7.0, 5.0))

    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(35), 0.0, math.radians(-35)))
    sun = bpy.context.object.data
    sun.energy = 1.7
    sun.color = (1.0, 0.34, 0.16)
    sun.angle = math.radians(14)

    bpy.ops.object.camera_add(location=(-1.0, -28.0, 12.2))
    camera = bpy.context.object
    camera.data.lens = float(recipe.get("camera", {}).get("lensMm", 46.0))
    look_at(camera, (0.5, 6.0, 6.6))
    camera.data.dof.use_dof = True
    camera.data.dof.focus_object = bpy.data.objects.get("HeroBuilding_2_Body")
    camera.data.dof.aperture_fstop = 4.5
    scene.camera = camera

    scene.use_nodes = True
    nt = scene.node_tree
    nt.nodes.clear()
    render = nt.nodes.new("CompositorNodeRLayers")
    glare = nt.nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    glare.quality = "HIGH"
    glare.threshold = 0.7
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

    filename = "loading_splash_final.png" if args.final else "loading_splash_proxy.png"
    scene.render.filepath = str(out / filename)
    bpy.ops.render.render(write_still=True)

    report = {
        "contract": CONTRACT,
        "artId": recipe.get("artId"),
        "status": "rendered",
        "presentationOnly": True,
        "gameplayContractsApplied": False,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "output": filename,
        "direction": "storybook_twilight_key_art"
    }
    (out / "loading_splash_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
