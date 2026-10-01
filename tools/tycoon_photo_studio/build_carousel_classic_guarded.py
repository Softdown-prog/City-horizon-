"""Guarded CH Blender builder for City Horizon's classic low-profile carousel.

The visual reference is the broad structure of classic tycoon carousels: low/wide
circular canopy, radial stripes, open sides and simple horses. Geometry and
proportions are original to City Horizon and follow CH_STYLIZED_PRERENDER_V1.

Pipeline:
    preflight -> SOUTH proxy -> human approval -> final four-direction animation

The runtime remains 2D RGBA sprites; Blender is offline authoring/render only.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CH_BLENDER = REPO_ROOT / "tools" / "ch_blender"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(CH_BLENDER) not in sys.path:
    sys.path.insert(0, str(CH_BLENDER))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", required=True)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend", default=None)
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    p.add_argument("--preflight-profile", default=None)
    p.add_argument("--approval-proxy-sha", default=None)
    return p.parse_args(argv)


def _save_blend(path):
    if not path:
        return
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


def _empty(name, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    obj.rotation_mode = "XYZ"
    return obj


def _material(name, spec):
    rgba = spec["rgba"]
    return bs.make_material(
        name,
        rgba,
        float(spec.get("roughness", 0.72)),
        float(spec.get("metallic", 0.0)),
        recipe=spec.get("recipe"),
        seed=int(spec.get("seed", 0)),
        strength=float(spec.get("strength", 1.0)),
    )


def _cube(name, parent, location, scale, material, bevel=0.025):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.0))
    obj = bpy.context.object
    obj.name = name
    obj.parent = parent
    obj.location = tuple(location)
    obj.scale = tuple(scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0.0:
        mod = obj.modifiers.new(name="SoftEdges", type="BEVEL")
        mod.width = bevel
        mod.segments = 2
    obj.data.materials.append(material)
    return obj


def _cylinder(name, parent, location, radius, depth, material, vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=(0.0, 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.parent = parent
    obj.location = tuple(location)
    obj.data.materials.append(material)
    return obj


def _sphere(name, parent, location, scale, material, segments=20, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        radius=1.0,
        location=(0.0, 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.parent = parent
    obj.location = tuple(location)
    obj.scale = tuple(scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def _cylinder_between(name, parent, start, end, radius, material, vertices=16):
    a = Vector(start)
    b = Vector(end)
    delta = b - a
    length = delta.length
    if length <= 1e-6:
        raise RuntimeError(f"Cannot create zero-length cylinder {name}")
    obj = _cylinder(name, parent, (0.0, 0.0, 0.0), radius, length, material, vertices)
    obj.location = (a + b) * 0.5
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    return obj


def _annular_sector(name, parent, a0, a1, r_inner, r_outer, z0, z1, material):
    """Create one solid annular sector; angles are radians."""
    pts = []
    for z in (z0, z1):
        pts.extend([
            (r_inner * math.cos(a0), r_inner * math.sin(a0), z),
            (r_inner * math.cos(a1), r_inner * math.sin(a1), z),
            (r_outer * math.cos(a1), r_outer * math.sin(a1), z),
            (r_outer * math.cos(a0), r_outer * math.sin(a0), z),
        ])
    faces = [
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(pts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    obj.data.materials.append(material)
    return obj


def _canopy_sector(name, parent, a0, a1, r_inner, r_outer, inner_z, outer_z, thickness, material):
    """Create a shallow sloped radial roof wedge with thickness."""
    top = [
        (r_inner * math.cos(a0), r_inner * math.sin(a0), inner_z),
        (r_inner * math.cos(a1), r_inner * math.sin(a1), inner_z),
        (r_outer * math.cos(a1), r_outer * math.sin(a1), outer_z),
        (r_outer * math.cos(a0), r_outer * math.sin(a0), outer_z),
    ]
    bot = [(x, y, z - thickness) for x, y, z in top]
    verts = top + bot
    faces = [
        (0, 1, 2, 3),
        (7, 6, 5, 4),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    ]
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    obj.data.materials.append(material)
    return obj


def _torus(name, parent, location, major_radius, minor_radius, material):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=64,
        minor_segments=8,
        location=(0.0, 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.parent = parent
    obj.location = tuple(location)
    obj.data.materials.append(material)
    return obj


def _build_horse(index, rotor, angle, radius, mats, geometry, frame_start, frame_end):
    horse = _empty(f"Horse_{index:02d}", rotor)
    horse.location = (radius * math.cos(angle), radius * math.sin(angle), 0.0)
    horse.rotation_euler[2] = angle + math.pi * 0.5

    z_body = float(geometry.get("horseBodyZ", 1.05))
    white = mats["horse"]
    red = mats["red"]
    dark = mats["dark"]
    gold = mats["gold"]

    _cylinder(
        f"HorsePole_{index:02d}",
        horse,
        (0.0, 0.0, 1.43),
        0.035,
        1.78,
        gold,
        vertices=12,
    )

    _sphere(
        f"HorseBody_{index:02d}",
        horse,
        (0.03, 0.0, z_body),
        (0.43, 0.18, 0.24),
        white,
    )
    _sphere(
        f"HorseChest_{index:02d}",
        horse,
        (0.30, 0.0, z_body + 0.12),
        (0.21, 0.15, 0.26),
        white,
    )
    neck = _sphere(
        f"HorseNeck_{index:02d}",
        horse,
        (0.39, 0.0, z_body + 0.30),
        (0.13, 0.12, 0.33),
        white,
    )
    neck.rotation_euler[1] = math.radians(-23.0)
    head = _sphere(
        f"HorseHead_{index:02d}",
        horse,
        (0.56, 0.0, z_body + 0.47),
        (0.22, 0.13, 0.14),
        white,
    )
    head.rotation_euler[1] = math.radians(-10.0)

    _sphere(
        f"HorseMuzzle_{index:02d}",
        horse,
        (0.72, 0.0, z_body + 0.43),
        (0.11, 0.10, 0.09),
        dark,
        segments=16,
        rings=8,
    )
    for ear_n, y in enumerate((-0.07, 0.07)):
        ear = _cube(
            f"HorseEar_{index:02d}_{ear_n}",
            horse,
            (0.48, y, z_body + 0.63),
            (0.035, 0.025, 0.09),
            white,
            bevel=0.012,
        )
        ear.rotation_euler[1] = math.radians(-18.0)

    saddle = _cube(
        f"HorseSaddle_{index:02d}",
        horse,
        (-0.02, 0.0, z_body + 0.23),
        (0.22, 0.21, 0.055),
        red,
        bevel=0.04,
    )
    saddle.rotation_euler[1] = math.radians(-4.0)

    pose = 1.0 if index % 2 == 0 else -1.0
    leg_specs = [
        ((0.24, -0.11, z_body - 0.10), (0.47, -0.11, z_body - 0.47 - 0.05 * pose)),
        ((0.18,  0.11, z_body - 0.10), (0.01,  0.11, z_body - 0.50 + 0.05 * pose)),
        ((-0.23,-0.11, z_body - 0.08), (-0.47,-0.11, z_body - 0.42 + 0.05 * pose)),
        ((-0.20, 0.11, z_body - 0.08), (-0.04, 0.11, z_body - 0.50 - 0.05 * pose)),
    ]
    for leg_n, (start, end) in enumerate(leg_specs):
        _cylinder_between(
            f"HorseLeg_{index:02d}_{leg_n}",
            horse,
            start,
            end,
            0.045,
            white,
            vertices=10,
        )

    _cylinder_between(
        f"HorseTail_{index:02d}",
        horse,
        (-0.40, 0.0, z_body + 0.03),
        (-0.62, 0.0, z_body - 0.16),
        0.045,
        white,
        vertices=10,
    )

    base_z = horse.location.z
    phase = (index % 4) / 4.0
    span = max(2, frame_end - frame_start)
    f0 = frame_start + int(round(phase * span))
    f1 = frame_start + int(round(((phase + 0.5) % 1.0) * span))
    horse.location.z = base_z + 0.07
    horse.keyframe_insert(data_path="location", index=2, frame=f0)
    horse.location.z = base_z - 0.07
    horse.keyframe_insert(data_path="location", index=2, frame=f1)
    horse.location.z = base_z + 0.07
    horse.keyframe_insert(data_path="location", index=2, frame=frame_end)
    horse.location.z = base_z

    return horse


def build_scene(recipe, studio, out):
    bs.clear_scene()
    source_res = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, source_res, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    mats = {key: _material(f"Carousel_{key}", spec) for key, spec in recipe["materials"].items()}
    geo = recipe["geometry"]

    root = _empty("AssetRoot")
    root["assetId"] = recipe["assetId"]
    root["assetType"] = "animated_attraction"
    root["styleContract"] = recipe.get("styleContract", "CH_STYLIZED_PRERENDER_V1")
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["runtimeRepresentation"] = "2D_RGBA_pre_rendered_sprite"
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    footprint = recipe["footprint"]
    root["footprint"] = f"{footprint['widthTiles']}x{footprint['depthTiles']}"

    base_radius = float(geo["baseRadius"])
    platform_z = float(geo["platformTopZ"])
    foundation = _cylinder(
        "CarouselFoundation",
        root,
        (0.0, 0.0, 0.10),
        base_radius,
        0.20,
        mats["dark_red"],
        vertices=64,
    )
    scene_gate.tag(foundation, "attraction.foundation", ground_contact=True)

    skirt_segments = int(geo.get("skirtSegments", 16))
    for i in range(skirt_segments):
        a0 = 2.0 * math.pi * i / skirt_segments
        a1 = 2.0 * math.pi * (i + 1) / skirt_segments
        mat = mats["red"] if i % 2 == 0 else mats["yellow"]
        _annular_sector(
            f"Skirt_{i:02d}",
            root,
            a0,
            a1,
            base_radius - 0.25,
            base_radius + 0.01,
            0.20,
            0.50,
            mat,
        )

    rotor = _empty("CarouselRotor", root)
    rotor["runtimeLayer"] = "motion_overlay"

    _cylinder(
        "CarouselPlatform",
        rotor,
        (0.0, 0.0, platform_z - 0.06),
        base_radius - 0.18,
        0.16,
        mats["wood"],
        vertices=64,
    )
    _torus(
        "PlatformGoldRing",
        rotor,
        (0.0, 0.0, platform_z + 0.015),
        base_radius - 0.18,
        0.035,
        mats["gold"],
    )

    _cylinder("CenterColumn", rotor, (0.0, 0.0, 1.45), 0.18, 2.05, mats["red"], vertices=32)
    _cylinder("CenterColumnLowerBand", rotor, (0.0, 0.0, 0.72), 0.24, 0.12, mats["yellow"], vertices=32)
    _cylinder("CenterColumnUpperBand", rotor, (0.0, 0.0, 2.18), 0.23, 0.12, mats["yellow"], vertices=32)

    canopy_r = float(geo["canopyRadius"])
    canopy_inner = float(geo.get("canopyInnerRadius", 0.42))
    outer_z = float(geo["canopyOuterZ"])
    inner_z = float(geo["canopyInnerZ"])
    sectors = int(geo.get("canopySegments", 20))
    roof_thickness = float(geo.get("canopyThickness", 0.055))
    for i in range(sectors):
        a0 = 2.0 * math.pi * i / sectors
        a1 = 2.0 * math.pi * (i + 1) / sectors
        mat = mats["yellow"] if i % 2 == 0 else mats["cream"]
        _canopy_sector(
            f"CanopySector_{i:02d}",
            rotor,
            a0,
            a1,
            canopy_inner,
            canopy_r,
            inner_z,
            outer_z,
            roof_thickness,
            mat,
        )

    _torus("CanopyOuterRim", rotor, (0.0, 0.0, outer_z - 0.01), canopy_r, 0.075, mats["yellow"])
    _cylinder("CanopyCenterCap", rotor, (0.0, 0.0, inner_z + 0.03), 0.50, 0.10, mats["yellow"], vertices=48)

    support_count = int(geo.get("supportCount", 12))
    support_r = float(geo.get("supportRadius", 2.55))
    for i in range(support_count):
        a = 2.0 * math.pi * i / support_count
        x, y = support_r * math.cos(a), support_r * math.sin(a)
        _cylinder(
            f"CanopySupport_{i:02d}",
            rotor,
            (x, y, (platform_z + outer_z) * 0.5),
            0.035,
            outer_z - platform_z,
            mats["gold"],
            vertices=12,
        )

    animation = recipe["animation"]
    frame_start = int(animation.get("frameStart", 1))
    frame_end = int(animation.get("frameEnd", 16))
    horse_count = int(geo.get("horseCount", 16))
    inner_ring = float(geo.get("horseInnerRadius", 1.35))
    outer_ring = float(geo.get("horseOuterRadius", 2.12))
    for i in range(horse_count):
        ring_r = outer_ring if i % 2 == 0 else inner_ring
        a = 2.0 * math.pi * i / horse_count
        _build_horse(i, rotor, a, ring_r, mats, geo, frame_start, frame_end)

    rotor.rotation_euler[2] = 0.0
    rotor.keyframe_insert(data_path="rotation_euler", index=2, frame=frame_start)
    rotor.rotation_euler[2] = 2.0 * math.pi
    rotor.keyframe_insert(data_path="rotation_euler", index=2, frame=frame_end)
    if rotor.animation_data and rotor.animation_data.action:
        for curve in rotor.animation_data.action.fcurves:
            for key in curve.keyframe_points:
                key.interpolation = "LINEAR"

    receiver = studio["shadowReceiver"]
    receiver_mat = bs.make_material(
        "ShadowReceiver",
        receiver["materialColor"],
        float(receiver.get("roughness", 1.0)),
    )
    ground = bs.add_box(
        "ShadowReceiverPlane",
        receiver["location"],
        receiver["dimensions"],
        receiver_mat,
        0.0,
    )

    authored = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj != ground]
    for obj in authored:
        current = obj.parent
        moving = False
        while current is not None:
            if current == rotor:
                moving = True
                break
            current = current.parent
        obj["runtimeLayer"] = "motion_overlay" if moving else "static_base"

    root["runtimeLayerContract"] = "CH_ATTRACTION_MOTION_OVERLAY_V1"
    root["motionActivationTrigger"] = "passenger_boarded"
    root["motionMinimumPassengers"] = 1

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    scene.frame_set(frame_start)
    bpy.context.view_layer.update()
    return scene, root, rotor, ground, authored


def _frame_metadata(recipe, studio, scene, frame, directions_meta):
    src_res = tuple(map(int, studio["render"]["sourceResolution"]))
    final_res = tuple(map(int, studio["render"]["finalResolution"]))
    animation = recipe["animation"]
    return {
        "sourceObject": recipe["assetId"],
        "assetType": "animated_attraction",
        "sourceContract": "DIRECT_CH_BLENDER_GUARDED_ANIMATED_V1",
        "assetConfig": "tools/tycoon_photo_studio/build_carousel_classic_guarded.py",
        "studioPreset": studio["id"],
        "styleContract": recipe.get("styleContract", "CH_STYLIZED_PRERENDER_V1"),
        "cameraContract": "CH_CAMERA_V1",
        "gridContract": "CH_GRID_V1",
        "projection": "orthographic_dimetric_2_to_1",
        "yawDegrees": 45.0,
        "elevationDegrees": 30.0,
        "tileWidth": 128,
        "tileHeight": 64,
        "footprint": recipe["footprint"],
        "blenderVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "renderResolution": list(src_res),
        "finalResolution": list(final_res),
        "directionOrder": [d["id"] for d in bs.DIRECTIONS],
        "rotationPolicy": {
            "assetRootRotates": True,
            "cameraRemainsFixed": True,
            "lightsRemainWorldFixed": True,
        },
        "animation": {
            "frame": frame,
            "frameStart": int(animation.get("frameStart", 1)),
            "frameEnd": int(animation.get("frameEnd", 16)),
            "fps": int(animation.get("fps", 8)),
            "looping": bool(animation.get("looping", True)),
        },
        "runtimeLayers": recipe.get("runtimeLayers"),
        "sourceSummary": {
            "groundIncludedInAsset": False,
            "runtimeRepresentation": "2D_RGBA_pre_rendered_sprite",
            "visualDirection": "low_wide_open_classic_carousel_original_city_horizon",
            "motionLayer": "CarouselRotor_and_descendants",
            "staticLayer": "foundation_and_skirt",
        },
        "directions": directions_meta,
    }


def render_final_animation(recipe, studio, scene, root, ground, authored, out, approval_sha, studio_preset_path):
    animation = recipe["animation"]
    frame_start = int(animation.get("frameStart", 1))
    frame_end = int(animation.get("frameEnd", 16))
    fps = int(animation.get("fps", 8))
    source_root = out / "final_source"
    runtime_root = out / "runtime"
    source_root.mkdir(parents=True, exist_ok=True)
    runtime_root.mkdir(parents=True, exist_ok=True)

    for frame in range(frame_start, frame_end + 1):
        frame_dir = source_root / f"frame_{frame:03d}"
        frame_dir.mkdir(parents=True, exist_ok=True)
        directions_meta = []
        scene.frame_set(frame)
        for direction in bs.DIRECTIONS:
            bs.set_direction(root, direction)
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            color_name = f"{recipe['assetId']}_{direction['id']}_color_source.png"
            shadow_name = f"{recipe['assetId']}_{direction['id']}_shadow_source.png"
            bs.render_color_pass(scene, authored, ground, str(frame_dir / color_name))
            origin_px = bs.ground_origin_source_px(scene)
            bs.render_shadow_pass(scene, authored, ground, str(frame_dir / shadow_name))
            directions_meta.append({
                "id": direction["id"],
                "quarterTurns": direction["quarterTurns"],
                "rotationDegrees": direction["rotationDegrees"],
                "colorSource": color_name,
                "shadowSource": shadow_name,
                "groundOriginSourcePx": origin_px,
            })
        metadata = _frame_metadata(recipe, studio, scene, frame, directions_meta)
        (frame_dir / "studio_metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )

    bs.set_direction(root, bs.DIRECTIONS[0])
    scene.frame_set(frame_start)
    bpy.context.view_layer.update()

    python_exe = shutil.which("python")
    if not python_exe:
        raise RuntimeError("CH_CAROUSEL_POSTPROCESS_PYTHON_NOT_FOUND: runner Python is required")
    post_script = HERE / "postprocess_ferris_animation.py"
    cmd = [
        python_exe,
        str(post_script),
        "--input", str(source_root),
        "--output", str(runtime_root),
        "--studio-preset", str(Path(studio_preset_path).resolve()),
        "--asset-id", recipe["assetId"],
        "--frame-start", str(frame_start),
        "--frame-end", str(frame_end),
        "--fps", str(fps),
        "--approved-proxy-sha", approval_sha,
    ]
    subprocess.run(cmd, check=True, cwd=str(REPO_ROOT))

    final_record = {
        "contract": "CH_CAROUSEL_FINAL_BAKE_V1",
        "status": "ok",
        "assetId": recipe["assetId"],
        "approvedProxySha256": approval_sha,
        "runtimeRepresentation": "2D_RGBA_pre_rendered_sprite",
        "backgroundIncluded": False,
        "directions": [d["id"] for d in bs.DIRECTIONS],
        "frameStart": frame_start,
        "frameEnd": frame_end,
        "frameCount": frame_end - frame_start + 1,
        "fps": fps,
        "runtimeLayers": recipe.get("runtimeLayers"),
        "runtimeDir": "runtime",
        "sourceDir": "final_source",
    }
    (out / "final_bake_report.json").write_text(json.dumps(final_record, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    recipe = json.loads(Path(args.recipe).read_text(encoding="utf-8"))
    if recipe.get("contract") != "CITY_HORIZON_CAROUSEL_V1":
        raise RuntimeError("Expected CITY_HORIZON_CAROUSEL_V1 recipe")

    studio = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    profile = scene_gate.load_profile(args.preflight_profile)

    scene, root, rotor, ground, authored = build_scene(recipe, studio, out)

    preflight_path = out / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=recipe["footprint"],
        profile=profile,
        asset_id=recipe["assetId"],
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        _save_blend(args.save_blend)
        print(f"[CH_GATE] Carousel preflight PASS: {preflight_path}")
        return

    if args.stage == "proxy":
        bs.set_direction(root, bs.DIRECTIONS[0])
        scene.frame_set(int(recipe["animation"].get("frameStart", 1)))
        bpy.context.view_layer.update()
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / "proxy_south.png",
            profile=profile,
            asset_id=recipe["assetId"],
            direction="south",
        )
        (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        _save_blend(args.save_blend)
        print(f"[CH_GATE] Carousel proxy SOUTH ready: {proxy['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError(
            "CH_FINAL_REQUIRES_APPROVED_PROXY: review proxy_south.png first and pass its SHA-256"
        )

    approval_record = {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": recipe["assetId"],
        "proxySha256": approval,
        "reviewed": True,
        "runtimeTarget": "2D_RGBA_pre_rendered_sprite",
    }
    (out / "proxy_approval.json").write_text(json.dumps(approval_record, indent=2), encoding="utf-8")

    render_final_animation(
        recipe,
        studio,
        scene,
        root,
        ground,
        authored,
        out,
        approval,
        args.studio_preset,
    )
    _save_blend(args.save_blend)
    print("[CH_GATE] Carousel final 4-direction animated runtime bake complete")


if __name__ == "__main__":
    main()
