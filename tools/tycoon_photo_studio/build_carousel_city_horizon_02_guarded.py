#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CH = ROOT / "tools" / "ch_blender"
for p in (HERE, CH):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import build_scene as bs
import scene_gate

CONTRACT = "CITY_HORIZON_CAROUSEL_V2"
ASSET_ID = "attraction.park_carousel_city_horizon_02"


def args():
    av = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", required=True)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend")
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    p.add_argument("--preflight-profile")
    return p.parse_args(av)


def mat(name, spec):
    return bs.make_material(
        name,
        spec["rgba"],
        float(spec.get("roughness", 0.65)),
        float(spec.get("metallic", 0.0)),
    )


def empty(name, parent=None):
    o = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(o)
    o.parent = parent
    return o


def cube(name, parent, loc, dims, material, bevel=0.03):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    o = bpy.context.object
    o.name = name
    o.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(material)
    o.parent = parent
    if bevel:
        m = o.modifiers.new("SoftEdge", "BEVEL")
        m.width = bevel
        m.segments = 2
    return o


def cyl(name, parent, loc, radius, depth, material, vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(material)
    o.parent = parent
    return o


def sphere(name, parent, loc, scale, material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=18, ring_count=10, radius=1.0, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(material)
    o.parent = parent
    for poly in o.data.polygons:
        poly.use_smooth = True
    return o


def cylinder_between(name, parent, a, b, radius, material, vertices=12):
    a = Vector(a)
    b = Vector(b)
    v = b - a
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=v.length, location=(a + b) * 0.5)
    o = bpy.context.object
    o.name = name
    o.rotation_euler = v.to_track_quat("Z", "Y").to_euler()
    o.data.materials.append(material)
    o.parent = parent
    return o


def canopy_wedge(name, parent, a0, a1, r0, r1, zi, zo, thickness, material):
    top = [
        (r0 * math.cos(a0), r0 * math.sin(a0), zi),
        (r0 * math.cos(a1), r0 * math.sin(a1), zi),
        (r1 * math.cos(a1), r1 * math.sin(a1), zo),
        (r1 * math.cos(a0), r1 * math.sin(a0), zo),
    ]
    bot = [(x, y, z - thickness) for x, y, z in top]
    verts = top + bot
    faces = [(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
    me = bpy.data.meshes.new(name + "Mesh")
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.parent = parent
    o.data.materials.append(material)
    return o


def simple_horse(i, parent, angle, radius, z, M):
    root = empty(f"Horse_{i:02d}", parent)
    root.location = (radius * math.cos(angle), radius * math.sin(angle), 0.0)
    root.rotation_euler[2] = angle + math.pi * 0.5
    cyl(f"HorsePole_{i:02d}", root, (0, 0, 1.45), 0.03, 1.70, M["gold"], 10)
    sphere(f"HorseBody_{i:02d}", root, (0.0, 0.0, z), (0.40, 0.16, 0.22), M["horse"])
    sphere(f"HorseNeck_{i:02d}", root, (0.30, 0.0, z + 0.27), (0.12, 0.10, 0.28), M["horse"])
    sphere(f"HorseHead_{i:02d}", root, (0.48, 0.0, z + 0.43), (0.19, 0.11, 0.12), M["horse"])
    sphere(f"HorseMane_{i:02d}", root, (0.23, 0.0, z + 0.28), (0.08, 0.13, 0.25), M["brown"])
    cube(f"HorseSaddle_{i:02d}", root, (-0.02, 0.0, z + 0.20), (0.28, 0.22, 0.08), M["red"], 0.025)
    pose = 1 if i % 2 == 0 else -1
    legs = [
        ((0.22,-0.08,z-0.09),(0.40,-0.08,z-0.42-0.04*pose)),
        ((0.15, 0.08,z-0.09),(0.02, 0.08,z-0.44+0.04*pose)),
        ((-0.20,-0.08,z-0.07),(-0.38,-0.08,z-0.38+0.04*pose)),
        ((-0.18, 0.08,z-0.07),(-0.04, 0.08,z-0.44-0.04*pose)),
    ]
    for n, (a, b) in enumerate(legs):
        cylinder_between(f"HorseLeg_{i:02d}_{n}", root, a, b, 0.04, M["horse"], 8)
    cylinder_between(f"HorseTail_{i:02d}", root, (-0.35,0,z+0.02), (-0.55,0,z-0.12), 0.04, M["brown"], 8)
    return root


def build(recipe, studio, out):
    bs.clear_scene()
    scene = bs.configure_scene(studio, tuple(map(int, studio["render"]["sourceResolution"])), str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    M = {k: mat("Carousel_" + k, v) for k, v in recipe["materials"].items()}
    g = recipe["geometry"]

    root = empty("AssetRoot")
    root["assetId"] = ASSET_ID
    root["cameraContract"] = "CH_CAMERA_V1"
    root["styleContract"] = recipe["styleContract"]
    root["lifecycleStatus"] = recipe["lifecycle"]["status"]
    root["exemplarStatus"] = recipe["lifecycle"]["exemplarStatus"]
    root["footprint"] = "7x7"

    base_r = float(g["baseRadius"])
    base_h = float(g["baseHeight"])
    platform_z = float(g["platformTopZ"])

    foundation = cyl("CarouselFoundation", root, (0,0,base_h*0.5), base_r, base_h, M["dark_red"], 64)
    cyl("CarouselBaseTrim", root, (0,0,base_h+0.04), base_r+0.03, 0.08, M["cream"], 64)

    rotor = empty("CarouselRotor", root)
    cyl("CarouselPlatform", rotor, (0,0,platform_z-0.07), base_r-0.10, 0.16, M["red"], 64)

    center_r = float(g["centerColumnRadius"])
    cyl("CenterColumn", rotor, (0,0,1.45), center_r, 1.85, M["gold"], 40)
    cyl("CenterColumnCore", rotor, (0,0,1.45), center_r*0.72, 1.72, M["red"], 40)

    segs = int(g["canopySegments"])
    canopy_r = float(g["canopyRadius"])
    inner_r = float(g["canopyInnerRadius"])
    outer_z = float(g["canopyOuterZ"])
    inner_z = float(g["canopyInnerZ"])
    thick = float(g["canopyThickness"])
    for i in range(segs):
        a0 = 2*math.pi*i/segs
        a1 = 2*math.pi*(i+1)/segs
        canopy_wedge(
            f"Canopy_{i:02d}", rotor, a0, a1, inner_r, canopy_r,
            inner_z, outer_z, thick, M["red"] if i % 2 == 0 else M["cream"]
        )

    cyl("CanopyCenterCap", rotor, (0,0,inner_z+0.02), 0.48, 0.10, M["gold"], 40)

    val_h = float(g["valanceHeight"])
    for i in range(segs):
        a = 2*math.pi*(i+0.5)/segs
        x, y = (canopy_r-0.05)*math.cos(a), (canopy_r-0.05)*math.sin(a)
        panel = cube(
            f"Valance_{i:02d}", rotor, (x,y,outer_z-val_h*0.5),
            (0.62,0.08,val_h), M["gold"] if i % 4 == 0 else M["red"], 0.015
        )
        panel.rotation_euler[2] = a + math.pi*0.5

    support_count = int(g["supportCount"])
    sr = float(g["supportRadius"])
    for i in range(support_count):
        a = 2*math.pi*i/support_count
        x, y = sr*math.cos(a), sr*math.sin(a)
        cyl(f"Support_{i:02d}", rotor, (x,y,(platform_z+outer_z)*0.5), 0.035, outer_z-platform_z, M["gold"], 12)

    horse_count = int(g["horseCount"])
    for i in range(horse_count):
        r = float(g["horseOuterRadius"] if i % 2 == 0 else g["horseInnerRadius"])
        simple_horse(i, rotor, 2*math.pi*i/horse_count, r, float(g["horseBodyZ"]), M)

    # Two simple opposite stair entries, intentionally low-detail.
    stair_w = float(g["stairWidth"])
    stair_d = float(g["stairDepth"])
    stair_h = float(g["stairHeight"])
    for idx, side in enumerate((-1, 1)):
        y = side * (base_r + stair_d*0.36)
        cube(f"Stair_{idx}_0", root, (0,y,stair_h*0.25), (stair_w,stair_d,stair_h*0.5), M["red"], 0.02)
        cube(f"Stair_{idx}_1", root, (0,y-side*stair_d*0.28,stair_h*0.67), (stair_w,stair_d*0.58,stair_h*0.35), M["red"], 0.02)

    # Small crown and flag, simple enough to remain readable at runtime scale.
    cyl("CrownStem", rotor, (0,0,inner_z+0.44), 0.045, 0.78, M["gold"], 12)
    sphere("CrownBall", rotor, (0,0,inner_z+0.84), (0.10,0.10,0.10), M["gold"])
    pole = cube("Flag", rotor, (0.20,0,inner_z+0.75), (0.34,0.03,0.16), M["red"], 0.01)
    pole.rotation_euler[2] = 0.12

    recv = studio["shadowReceiver"]
    rm = bs.make_material("ShadowReceiver", recv["materialColor"], float(recv.get("roughness",1)))
    ground = bs.add_box("ShadowReceiverPlane", recv["location"], recv["dimensions"], rm, 0.0)
    authored = [o for o in bpy.context.scene.objects if o.type == "MESH" and o != ground]

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    return scene, root, ground, authored


def main():
    a = args()
    recipe = json.loads(Path(a.recipe).read_text(encoding="utf-8"))
    if recipe.get("contract") != CONTRACT:
        raise RuntimeError("Expected CITY_HORIZON_CAROUSEL_V2 recipe")
    if recipe.get("lifecycle", {}).get("status") != "draft":
        raise RuntimeError("This builder currently accepts only draft carousel recipes")
    if recipe.get("lifecycle", {}).get("exemplarStatus") != "not_approved_exemplar":
        raise RuntimeError("Draft carousel must not be treated as an approved exemplar")

    studio = bs.load_json(a.studio_preset)
    out = Path(a.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    scene, root, ground, authored = build(recipe, studio, out)

    meta = {
        "contract": "CH_CAROUSEL_DRAFT_METADATA_V1",
        "assetId": ASSET_ID,
        "status": "draft",
        "exemplarStatus": "not_approved_exemplar",
        "reference": recipe["reference"],
        "designIntent": recipe["designIntent"],
    }
    (out / "draft_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    profile = scene_gate.load_profile(a.preflight_profile)
    pre = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=recipe["footprint"],
        profile=profile,
        asset_id=ASSET_ID,
        report_path=out / "preflight_report.json",
    )
    scene_gate.require_pass(pre)

    if a.stage == "preflight":
        print(f"[CH_GATE] Carousel V2 draft preflight PASS: {out/'preflight_report.json'}")
    elif a.stage == "proxy":
        rep = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / "proxy_south.png",
            profile=profile,
            asset_id=ASSET_ID,
            direction="south",
        )
        (out / "proxy_report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
        print(f"[CH_GATE] Carousel V2 draft proxy ready: {rep['sha256']}")
    else:
        raise RuntimeError("CH_FINAL_BLOCKED_DRAFT: explicit human approval and a dedicated final job are required")

    if a.save_blend:
        p = Path(a.save_blend).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(p))


if __name__ == "__main__":
    main()
