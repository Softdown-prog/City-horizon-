"""Render City Horizon loading-screen key art.

This is deliberately NOT a gameplay asset baker. The scene is free to use a
perspective camera, exaggerated scale, loading-only geometry and non-runtime
objects. See docs/LOADING_SPLASH_ART.md.
"""
from __future__ import annotations

import argparse
import json
import math
import os
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
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        pass


def mat(name, color, roughness=0.72, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = tuple(color)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = tuple(color)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
    return m


def add_box(name, loc, scale, material, bevel=0.10):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = (scale[0] * 0.5, scale[1] * 0.5, scale[2] * 0.5)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        o.data.materials.append(material)
    if bevel > 0:
        mod = o.modifiers.new("SoftEdges", "BEVEL")
        mod.width = bevel
        mod.segments = 3
    return o


def add_uv_sphere(name, loc, scale, material, segments=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=16, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    if material:
        o.data.materials.append(material)
    return o


def add_cylinder_between(name, a, b, radius, material, vertices=16):
    a = Vector(a)
    b = Vector(b)
    d = b - a
    length = d.length
    if length <= 1e-6:
        raise RuntimeError(f"degenerate segment {name}")
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=length, location=(a + b) * 0.5)
    o = bpy.context.object
    o.name = name
    o.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    if material:
        o.data.materials.append(material)
    return o


def ribbon(name, points, width, z, material):
    pts = [Vector((float(x), float(y), z)) for x, y in points]
    verts = []
    faces = []
    for i, p in enumerate(pts):
        if i == 0:
            tangent = pts[1] - pts[0]
        elif i == len(pts) - 1:
            tangent = pts[-1] - pts[-2]
        else:
            tangent = pts[i + 1] - pts[i - 1]
        tangent.z = 0
        tangent.normalize()
        normal = Vector((-tangent.y, tangent.x, 0.0))
        verts.append(tuple(p + normal * width * 0.5))
        verts.append(tuple(p - normal * width * 0.5))
    for i in range(len(pts) - 1):
        a = i * 2
        faces.append((a, a + 1, a + 3, a + 2))
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_building(rng, name, x, y, w, d, h, body, trim, glass, roof):
    add_box(name + "_Body", (x, y, h * 0.5), (w, d, h), body, 0.18)
    add_box(name + "_Roof", (x, y, h + 0.24), (w * 1.05, d * 1.05, 0.36), roof, 0.12)
    # Broad windows survive illustration scale; they are decorative, not runtime-authored facades.
    rows = max(2, int(h // 1.6))
    cols = max(2, int(w // 1.35))
    for r in range(rows):
        z = 0.85 + r * min(1.35, (h - 1.2) / max(1, rows - 1))
        for c in range(cols):
            xx = x - w * 0.36 + c * (w * 0.72 / max(1, cols - 1))
            add_box(f"{name}_WindowF_{r}_{c}", (xx, y - d * 0.505, z), (0.62, 0.08, 0.72), glass, 0.03)
    # Cartoon rooftop prop.
    if rng.random() < 0.72:
        add_box(name + "_RoofProp", (x + w * 0.18, y, h + 0.62), (0.65, 0.65, 0.54), trim, 0.08)


def add_tree(name, x, y, z, scale, trunk_mat, leaf_mats, rng):
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.20 * scale, depth=1.8 * scale, location=(x, y, z + 0.9 * scale))
    trunk = bpy.context.object
    trunk.name = name + "_Trunk"
    trunk.data.materials.append(trunk_mat)
    for i, off in enumerate(((0,0,0),(-0.55,0.10,-0.10),(0.48,0.16,-0.02),(0.05,-0.45,-0.12))):
        material = leaf_mats[(i + int(rng.random() * 9)) % len(leaf_mats)]
        add_uv_sphere(name + f"_Crown_{i}", (x + off[0]*scale, y + off[1]*scale, z + (2.05 + off[2]) * scale), (0.92*scale,0.82*scale,0.76*scale), material, 24)


def add_cloud(name, loc, scale, material):
    x, y, z = loc
    for i, off in enumerate(((0,0,0),(-1.0,0.0,-0.1),(0.9,0.05,-0.08),(-0.2,0.0,0.45),(0.5,0.0,0.35))):
        add_uv_sphere(name + str(i), (x + off[0]*scale, y + off[1]*scale, z + off[2]*scale), (1.2*scale,0.55*scale,0.72*scale), material, 24)


def add_balloon(name, loc, scale, balloon_mat, basket_mat, rope_mat):
    x, y, z = loc
    add_uv_sphere(name + "_Balloon", (x, y, z), (0.85*scale,0.85*scale,1.15*scale), balloon_mat, 32)
    add_box(name + "_Basket", (x, y, z - 1.45*scale), (0.58*scale,0.50*scale,0.42*scale), basket_mat, 0.06)
    for sx in (-0.28, 0.28):
        add_cylinder_between(name + f"_Rope_{sx}", (x + sx*scale, y, z - 0.7*scale), (x + sx*0.75*scale, y, z - 1.25*scale), 0.02*scale, rope_mat, 8)


def add_ferris_wheel(center, radius, mats):
    cx, cy, cz = center
    # Two artistic rims for depth.
    for depth in (-0.42, 0.42):
        for i in range(48):
            a0 = 2 * math.pi * i / 48
            a1 = 2 * math.pi * (i + 1) / 48
            p0 = (cx + math.cos(a0) * radius, cy + depth, cz + math.sin(a0) * radius)
            p1 = (cx + math.cos(a1) * radius, cy + depth, cz + math.sin(a1) * radius)
            add_cylinder_between(f"WheelRim_{depth}_{i}", p0, p1, 0.085, mats["wheel"], 12)
    # Hub and spokes.
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.42, depth=1.35, location=(cx, cy, cz), rotation=(math.pi/2,0,0))
    bpy.context.object.data.materials.append(mats["hub"])
    for i in range(16):
        ang = 2 * math.pi * i / 16
        for depth in (-0.38, 0.38):
            rim = (cx + math.cos(ang) * radius, cy + depth, cz + math.sin(ang) * radius)
            add_cylinder_between(f"Spoke_{i}_{depth}", (cx, cy + depth, cz), rim, 0.045, mats["wheel"], 10)
    # Cabins exaggerated and colorful.
    cabin_mats = mats["cabins"]
    for i in range(12):
        ang = 2 * math.pi * i / 12 + math.radians(7)
        x = cx + math.cos(ang) * radius
        z = cz + math.sin(ang) * radius
        body = add_box(f"Cabin_{i}", (x, cy, z - 0.25), (1.05, 1.05, 0.78), cabin_mats[i % len(cabin_mats)], 0.16)
        add_box(f"CabinRoof_{i}", (x, cy, z + 0.20), (1.15, 1.12, 0.18), mats["cream"], 0.08)
        add_cylinder_between(f"CabinHang_{i}", (x, cy, z + 0.85), (x, cy, z + 0.28), 0.035, mats["dark"], 10)
    # A-frame supports and platform.
    for sx in (-1.0, 1.0):
        add_cylinder_between(f"SupportA_{sx}", (cx + sx*3.2, cy, 0.25), (cx + sx*0.45, cy, cz), 0.16, mats["cream"], 16)
        add_cylinder_between(f"SupportB_{sx}", (cx + sx*3.2, cy + 0.85, 0.25), (cx + sx*0.45, cy + 0.15, cz), 0.16, mats["cream"], 16)
    add_box("FerrisPlatform", (cx, cy, 0.15), (7.8, 3.4, 0.30), mats["platform"], 0.16)


def setup_scene(recipe, final=False):
    clear_scene()
    rng = random.Random(int(recipe.get("seed", 2609)))
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x, scene.render.resolution_y = FINAL_RES if final else PROXY_RES
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.use_file_extension = True
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    scene.render.image_settings.color_depth = "8"

    world = bpy.data.worlds.new("LoadingSplashWorld") if scene.world is None else scene.world
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.055, 0.10, 0.18, 1.0)
    bg.inputs["Strength"].default_value = 0.55

    # Materials intentionally more illustrative/saturated than gameplay.
    mats = {
        "ground": mat("SplashGround", (0.16,0.30,0.25,1), 0.90),
        "park": mat("SplashPark", (0.22,0.50,0.28,1), 0.88),
        "road": mat("SplashRoad", (0.055,0.075,0.095,1), 0.92),
        "sidewalk": mat("SplashSidewalk", (0.62,0.67,0.66,1), 0.88),
        "water": mat("SplashWater", (0.06,0.38,0.62,1), 0.24, 0.05),
        "cream": mat("SplashCream", (0.92,0.78,0.49,1), 0.62),
        "coral": mat("SplashCoral", (0.92,0.24,0.24,1), 0.58),
        "teal": mat("SplashTeal", (0.05,0.72,0.68,1), 0.55),
        "blue": mat("SplashBlue", (0.08,0.31,0.74,1), 0.58),
        "purple": mat("SplashPurple", (0.46,0.19,0.70,1), 0.60),
        "orange": mat("SplashOrange", (0.96,0.47,0.10,1), 0.60),
        "dark": mat("SplashDark", (0.045,0.055,0.075,1), 0.72, 0.08),
        "glass": mat("SplashGlass", (0.16,0.52,0.75,1), 0.25, 0.05),
        "trunk": mat("SplashTrunk", (0.28,0.12,0.055,1), 0.92),
        "leaf1": mat("SplashLeaf1", (0.10,0.37,0.16,1), 0.86),
        "leaf2": mat("SplashLeaf2", (0.18,0.56,0.20,1), 0.84),
        "leaf3": mat("SplashLeaf3", (0.34,0.70,0.24,1), 0.82),
        "cloud": mat("SplashCloud", (0.92,0.95,0.98,1), 0.78),
        "sun": mat("SplashSun", (1.0,0.52,0.12,1), 0.44),
    }
    mats["wheel"] = mats["teal"]
    mats["hub"] = mats["cream"]
    mats["platform"] = mats["dark"]
    mats["cabins"] = [mats["coral"], mats["orange"], mats["purple"], mats["blue"]]

    # Ground is a stylized stage, not a gameplay map.
    add_box("ArtStage", (0,3,-0.45), (38,30,0.9), mats["ground"], 0.45)
    add_box("ParkPlate", (6.5,4,0.04), (18,13,0.22), mats["park"], 0.40)
    # Lake/river foreground.
    add_box("WaterBand", (-5.5,10.4,-0.03), (24,5.5,0.16), mats["water"], 0.45)

    road_points = [(-15,-9),(-10,-5),(-5,-2),(0,0),(5,1.5),(11,1.9),(17,2.2)]
    ribbon("RoadShoulder", road_points, 6.5, 0.10, mats["sidewalk"])
    ribbon("Road", road_points, 4.9, 0.16, mats["road"])
    # Road center marks.
    for i in range(1, len(road_points)-1):
        x,y = road_points[i]
        add_box(f"Mark_{i}", (x,y,0.205), (1.7,0.15,0.035), mats["cream"], 0.02)

    # Dramatic skyline, deliberately not constrained to current buildable assets.
    body_mats = [mats["blue"], mats["coral"], mats["purple"], mats["teal"], mats["orange"]]
    skyline = [
        (-10,5.8,4.8,4.1,7.4),(-6.2,6.7,3.4,3.6,9.0),(-2.4,6.0,4.2,3.6,6.3),
        (1.1,7.2,3.0,3.2,11.5),(4.1,7.5,2.8,3.0,8.1),(7.3,7.0,3.4,3.2,10.0)
    ]
    for idx,(x,y,w,d,h) in enumerate(skyline):
        add_building(rng, f"Skyline_{idx}", x,y,w,d,h, body_mats[idx%len(body_mats)], mats["cream"], mats["glass"], mats["dark"])

    # Secondary whimsical low-rise district.
    lows = [(-12,-0.4,3.3,3.0,3.5),(-7.9,-0.8,3.7,3.2,4.2),(-3.7,-1.2,3.4,3.0,3.6),(1.0,-0.8,3.9,3.1,4.5)]
    for idx,(x,y,w,d,h) in enumerate(lows):
        add_building(rng, f"Low_{idx}", x,y,w,d,h, body_mats[(idx+2)%len(body_mats)], mats["cream"], mats["glass"], mats["cream"])

    # Large landmark dominates the right side like poster art.
    add_ferris_wheel((10.5,4.3,6.1), 5.15, mats)

    # Trees in three depth bands, including oversized foreground framing.
    leaves = [mats["leaf1"], mats["leaf2"], mats["leaf3"]]
    for i,(x,y,s) in enumerate([(-13,3,1.3),(-8,3.2,1.0),(-3,3.8,0.9),(4,3.4,1.0),(15,5.0,1.25),(6,-3.2,1.1),(13,-2.4,1.0)]):
        add_tree(f"Tree_{i}",x,y,0.1,s,mats["trunk"],leaves,rng)
    add_tree("ForegroundTreeL", -14.0,-7.0,0.1,2.3,mats["trunk"],leaves,rng)
    add_tree("ForegroundTreeR", 15.5,-5.5,0.1,2.0,mats["trunk"],leaves,rng)

    # Loading-only fantasy elements: balloons, cloud banks and an oversized sun.
    add_uv_sphere("Sun", (-9.0,13.0,14.5), (3.4,0.55,3.4), mats["sun"], 48)
    add_cloud("CloudA", (-9.5,11.0,12.7), 1.4, mats["cloud"])
    add_cloud("CloudB", (2.2,13.0,15.3), 1.0, mats["cloud"])
    add_cloud("CloudC", (12.5,12.0,13.5), 1.25, mats["cloud"])
    add_balloon("BalloonA", (-3.0,12.0,14.0), 0.75, mats["coral"], mats["cream"], mats["dark"])
    add_balloon("BalloonB", (7.2,14.0,16.2), 0.52, mats["purple"], mats["cream"], mats["dark"])

    # Camera is intentionally cinematic/perspective and NOT CH_CAMERA_V1.
    cam_data = bpy.data.cameras.new("SplashCamera")
    cam = bpy.data.objects.new("SplashCamera", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    cam.location = (22.0,-27.0,16.0)
    cam.data.type = "PERSP"
    cam.data.lens = float(recipe.get("camera", {}).get("lensMm", 52.0))
    look_at(cam, (1.5,3.0,5.4))

    # Key/fill/rim lighting chosen for poster depth, not gameplay matching.
    bpy.ops.object.light_add(type="AREA", location=(-7,-10,18))
    key = bpy.context.object
    key.name = "SplashKey"
    key.data.energy = 1450
    key.data.shape = "DISK"
    key.data.size = 9.0
    key.data.color = (1.0,0.69,0.48)
    look_at(key, (2,3,4))
    bpy.ops.object.light_add(type="AREA", location=(14,-2,13))
    fill = bpy.context.object
    fill.name = "SplashFill"
    fill.data.energy = 950
    fill.data.size = 8.0
    fill.data.color = (0.35,0.60,1.0)
    look_at(fill, (6,4,4))
    bpy.ops.object.light_add(type="AREA", location=(2,12,16))
    rim = bpy.context.object
    rim.name = "SplashRim"
    rim.data.energy = 1250
    rim.data.size = 7.0
    rim.data.color = (0.55,0.75,1.0)
    look_at(rim, (3,5,5))

    return scene


def main():
    args = parse_args()
    recipe = load_json(args.recipe)
    if recipe.get("contract") != CONTRACT:
        raise RuntimeError(f"Expected {CONTRACT}")
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    scene = setup_scene(recipe, args.final)
    target = out / ("loading_splash_final.png" if args.final else "loading_splash_proxy.png")
    scene.render.filepath = str(target)
    bpy.ops.render.render(write_still=True)
    meta = {
        "contract": CONTRACT,
        "status": "ok",
        "mode": "final" if args.final else "proxy",
        "resolution": list(FINAL_RES if args.final else PROXY_RES),
        "camera": "freeform_perspective_loading_only",
        "gameplayAsset": False,
        "runtimeRepresentation": "2D_loading_background",
        "output": target.name,
    }
    (out / "loading_splash_report.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"[CH_LOADING_SPLASH] wrote {target}")


if __name__ == "__main__":
    main()
