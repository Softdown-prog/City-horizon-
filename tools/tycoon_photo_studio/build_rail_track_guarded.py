"""Guarded CH Blender authoring for City Horizon modular rail sprites."""
from __future__ import annotations

import argparse
import json
import math
import re
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

CONTRACT = "CITY_HORIZON_RAIL_TRACK_V1"
LEGACY_ASSET_ID = "transport.rail_track.classic.01"
DEFAULT_RECIPE = "tools/tycoon_photo_studio/assets/rail_track_classic_01.track.json"


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--save-blend", default=None)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args(argv)


def _empty(name: str, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_mode = "XYZ"
    if parent is not None:
        obj.parent = parent
    return obj


def _save_blend(path):
    if path:
        target = Path(path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(target))


def _material(name: str, rgba, roughness: float, metallic: float = 0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        raise RuntimeError("CH_RAIL_MATERIAL_ERROR: Principled BSDF missing")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    mat.diffuse_color = rgba
    return mat


def _box(name, location, dimensions, material, parent, role: str, ground_contact=False, rotation_z=0.0):
    obj = bs.add_box(name, location, dimensions, material, 0.0)
    obj.parent = parent
    obj.rotation_euler[2] = float(rotation_z)
    scene_gate.tag(obj, role, ground_contact=ground_contact)
    return obj


def _arc_prism(
    name: str,
    center,
    radius: float,
    width: float,
    z_base: float,
    height: float,
    start_angle: float,
    end_angle: float,
    segments: int,
    material,
    parent,
    role: str,
    ground_contact=False,
):
    if segments < 4 or radius <= width * 0.5 or width <= 0.0 or height <= 0.0:
        raise RuntimeError("CH_RAIL_CURVE_GEOMETRY_INVALID")
    inner = radius - width * 0.5
    outer = radius + width * 0.5
    verts = []
    faces = []
    for i in range(segments + 1):
        t = i / segments
        angle = start_angle + (end_angle - start_angle) * t
        c = math.cos(angle)
        s = math.sin(angle)
        for z in (z_base, z_base + height):
            verts.append((center[0] + inner * c, center[1] + inner * s, z))
            verts.append((center[0] + outer * c, center[1] + outer * s, z))

    for i in range(segments):
        a = i * 4
        b = (i + 1) * 4
        # bottom, top, inner wall, outer wall
        faces.append((a, b, b + 1, a + 1))
        faces.append((a + 2, a + 3, b + 3, b + 2))
        faces.append((a, a + 2, b + 2, b))
        faces.append((a + 1, b + 1, b + 3, a + 3))
    # deterministic end caps
    first = 0
    last = segments * 4
    faces.append((first, first + 1, first + 3, first + 2))
    faces.append((last, last + 2, last + 3, last + 1))

    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    obj.data.materials.append(material)
    scene_gate.tag(obj, role, ground_contact=ground_contact)
    return obj


def _asset_id(recipe) -> str:
    asset_id = str(recipe.get("assetId") or LEGACY_ASSET_ID).strip()
    if not asset_id or not re.fullmatch(r"[A-Za-z0-9._-]+", asset_id):
        raise RuntimeError("CH_RAIL_ASSET_ID_INVALID: recipe assetId must be a safe non-empty identifier")
    return asset_id


def _materials():
    return {
        "steel": _material("RailSteel", (0.20, 0.22, 0.22, 1.0), 0.34, 0.72),
        "steel_side": _material("RailSteelDark", (0.105, 0.12, 0.12, 1.0), 0.46, 0.56),
        "timber": (
            _material("SleeperTimberWarm", (0.30, 0.18, 0.105, 1.0), 0.82, 0.0),
            _material("SleeperTimberMid", (0.255, 0.145, 0.078, 1.0), 0.84, 0.0),
            _material("SleeperTimberDark", (0.215, 0.115, 0.060, 1.0), 0.86, 0.0),
        ),
        "timber_grain": _material("SleeperTimberGrain", (0.145, 0.072, 0.035, 1.0), 0.90, 0.0),
        "ballast": _material("Ballast", (0.285, 0.275, 0.245, 1.0), 0.94, 0.0),
    }


def _painted_sleeper(root, mats, index, location, rotation_z, sleeper_w, sleeper_len, sleeper_h, ballast_h):
    timber = mats["timber"][index % len(mats["timber"])]
    sleeper = _box(
        f"Sleeper_{index:02d}", location,
        (sleeper_w, sleeper_len, sleeper_h), timber, root,
        "rail.sleeper", ground_contact=False, rotation_z=rotation_z,
    )
    sleeper["paintVariant"] = index % len(mats["timber"])

    if index % 3 != 1:
        offset = (-0.22 if index % 2 == 0 else 0.18) * sleeper_len
        nx = -math.sin(rotation_z)
        ny = math.cos(rotation_z)
        grain_location = (
            location[0] + nx * offset,
            location[1] + ny * offset,
            ballast_h + sleeper_h + 0.004,
        )
        _box(
            f"SleeperGrain_{index:02d}", grain_location,
            (sleeper_w * 0.70, sleeper_len * 0.28, 0.008),
            mats["timber_grain"], root,
            "rail.sleeper_paint", ground_contact=False, rotation_z=rotation_z,
        )


def _build_straight_track(root, spec, mats):
    tile = float(spec["tileWorldSize"])
    gauge = float(spec["railGauge"])
    rail_w = float(spec["railWidth"])
    rail_h = float(spec["railHeight"])
    sleeper_len = float(spec["sleeperLength"])
    sleeper_w = float(spec["sleeperWidth"])
    sleeper_h = float(spec["sleeperHeight"])
    sleeper_count = int(spec["sleeperCount"])
    ballast_w = float(spec["ballastWidth"])
    ballast_h = float(spec["ballastHeight"])

    _box(
        "BallastBed", (0.0, 0.0, ballast_h * 0.5),
        (tile, ballast_w, ballast_h), mats["ballast"], root,
        "rail.ballast", ground_contact=True,
    )

    spacing = tile / sleeper_count
    start = -tile * 0.5 + spacing * 0.5
    for index in range(sleeper_count):
        x = start + spacing * index
        _painted_sleeper(
            root, mats, index,
            (x, 0.0, ballast_h + sleeper_h * 0.5), 0.0,
            sleeper_w, sleeper_len, sleeper_h, ballast_h,
        )

    rail_z = ballast_h + sleeper_h + rail_h * 0.5
    for side, y in (("L", -gauge * 0.5), ("R", gauge * 0.5)):
        _box(
            f"Rail_{side}", (0.0, y, rail_z),
            (tile, rail_w, rail_h), mats["steel"], root,
            "rail.steel", ground_contact=False,
        )
        _box(
            f"RailWeb_{side}", (0.0, y, rail_z - rail_h * 0.34),
            (tile, rail_w * 0.52, rail_h * 0.72), mats["steel_side"], root,
            "rail.steel_web", ground_contact=False,
        )


def _build_curve_track(root, spec, mats):
    tile = float(spec["tileWorldSize"])
    gauge = float(spec["railGauge"])
    rail_w = float(spec["railWidth"])
    rail_h = float(spec["railHeight"])
    sleeper_len = float(spec["sleeperLength"])
    sleeper_w = float(spec["sleeperWidth"])
    sleeper_h = float(spec["sleeperHeight"])
    sleeper_count = int(spec["sleeperCount"])
    ballast_w = float(spec["ballastWidth"])
    ballast_h = float(spec["ballastHeight"])
    radius = float(spec.get("curveRadius", tile * 0.5))
    segments = int(spec.get("curveSegments", 32))
    turn = str(spec.get("turnDirection", "left")).lower()

    if abs(radius - tile * 0.5) > 1.0e-6:
        raise RuntimeError("CH_RAIL_CURVE_TILE_ENDPOINT_MISMATCH: canonical 1x1 quarter curve requires radius=tileWorldSize/2")
    if turn not in {"left", "right"}:
        raise RuntimeError("CH_RAIL_CURVE_TURN_INVALID")

    start = (-tile * 0.5, 0.0)
    if turn == "left":
        center = (-tile * 0.5, tile * 0.5)
        start_angle = -math.pi * 0.5
        end_angle = 0.0
        tangent_sign = 1.0
    else:
        center = (-tile * 0.5, -tile * 0.5)
        start_angle = math.pi * 0.5
        end_angle = 0.0
        tangent_sign = -1.0

    _arc_prism(
        "BallastBed", center, radius, ballast_w, 0.0, ballast_h,
        start_angle, end_angle, segments, mats["ballast"], root,
        "rail.ballast", ground_contact=True,
    )

    for index in range(sleeper_count):
        t = (index + 0.5) / sleeper_count
        angle = start_angle + (end_angle - start_angle) * t
        x = center[0] + radius * math.cos(angle)
        y = center[1] + radius * math.sin(angle)
        rotation_z = angle + tangent_sign * math.pi * 0.5
        _painted_sleeper(
            root, mats, index,
            (x, y, ballast_h + sleeper_h * 0.5), rotation_z,
            sleeper_w, sleeper_len, sleeper_h, ballast_h,
        )

    rail_base = ballast_h + sleeper_h
    for index, rail_radius in enumerate((radius - gauge * 0.5, radius + gauge * 0.5)):
        side = "Inner" if index == 0 else "Outer"
        _arc_prism(
            f"Rail_{side}", center, rail_radius, rail_w, rail_base, rail_h,
            start_angle, end_angle, segments, mats["steel"], root,
            "rail.steel", ground_contact=False,
        )
        _arc_prism(
            f"RailWeb_{side}", center, rail_radius, rail_w * 0.52,
            rail_base, rail_h * 0.72,
            start_angle, end_angle, segments, mats["steel_side"], root,
            "rail.steel_web", ground_contact=False,
        )

    root["curveStart"] = [start[0], start[1], 0.0]
    root["curveRadius"] = radius
    root["curveTurn"] = turn
    root["curveDegrees"] = 90.0


def build_track(root, recipe):
    spec = recipe["module"]
    kind = str(spec.get("kind", "straight"))
    mats = _materials()
    if kind == "straight":
        _build_straight_track(root, spec, mats)
    elif kind in {"curve_left_90", "curve_right_90"}:
        expected = "left" if kind == "curve_left_90" else "right"
        actual = str(spec.get("turnDirection", expected)).lower()
        if actual != expected:
            raise RuntimeError("CH_RAIL_CURVE_KIND_DIRECTION_MISMATCH")
        _build_curve_track(root, spec, mats)
    else:
        raise RuntimeError(f"CH_RAIL_MODULE_KIND_UNSUPPORTED: {kind}")


def build_for_gate(args):
    recipe = bs.load_json(args.recipe)
    if recipe.get("contract") != CONTRACT:
        raise RuntimeError(f"Expected {CONTRACT}")
    asset_id = _asset_id(recipe)

    studio = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    source_res = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, source_res, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    root = _empty("AssetRoot")
    root["assetId"] = asset_id
    root["assetType"] = str(recipe.get("assetType") or "rail_track_module")
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["styleContract"] = "CH_STYLIZED_PRERENDER_V1"
    root["gridContract"] = "CH_GRID_V1"
    root["runtimeRepresentation"] = str(recipe.get("runtimeRepresentation") or "2D_RGBA_modular_track")
    root["footprint"] = "1x1"
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    root["seamPolicy"] = "continuous_geometry_to_tile_boundary"

    build_track(root, recipe)

    receiver = studio["shadowReceiver"]
    receiver_mat = bs.make_material(
        "ShadowReceiver", receiver["materialColor"], float(receiver.get("roughness", 1.0))
    )
    ground = bs.add_box(
        "ShadowReceiverPlane", receiver["location"], receiver["dimensions"], receiver_mat, 0.0
    )
    authored = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj != ground]
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.10)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    return recipe, asset_id, scene, root, ground, authored, out


def _write_metadata(scene, recipe, asset_id: str, recipe_path: str, out: Path):
    metadata = {
        "sourceObject": asset_id,
        "assetType": str(recipe.get("assetType") or "rail_track_module"),
        "sourceContract": "DIRECT_CH_BLENDER_GUARDED_V1",
        "assetConfig": "tools/tycoon_photo_studio/build_rail_track_guarded.py",
        "recipe": recipe_path,
        "studioPreset": "CH_TYCOON_STUDIO_V1",
        "styleContract": "CH_STYLIZED_PRERENDER_V1",
        "cameraContract": "CH_CAMERA_V1",
        "gridContract": "CH_GRID_V1",
        "projection": "orthographic_dimetric_2_to_1",
        "yawDegrees": 45.0,
        "elevationDegrees": 30.0,
        "footprint": recipe["footprint"],
        "renderResolution": [int(scene.render.resolution_x), int(scene.render.resolution_y)],
        "transparentBackground": True,
        "runtimeRepresentation": str(recipe.get("runtimeRepresentation") or "2D_RGBA_modular_track"),
        "moduleKind": recipe["module"]["kind"],
        "catalog": recipe.get("catalog"),
        "runtimePlan": recipe["runtimePlan"],
    }
    (out / "studio_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def render_final(scene, root, ground, recipe, asset_id: str, recipe_path: str, out):
    ground.hide_render = True
    directions = []
    for direction in bs.DIRECTIONS:
        bs.set_direction(root, direction)
        filename = f"{asset_id}_{direction['id']}_source.png"
        scene.render.filepath = str(out / filename)
        bpy.ops.render.render(write_still=True)
        directions.append({
            "id": direction["id"],
            "rotationDegrees": direction["rotationDegrees"],
            "file": filename,
        })
    _write_metadata(scene, recipe, asset_id, recipe_path, out)
    (out / "rail_track_source_manifest.json").write_text(json.dumps({
        "contract": "CH_RAIL_TRACK_SOURCE_BAKE_V1",
        "assetId": asset_id,
        "catalogContract": (recipe.get("catalog") or {}).get("contract"),
        "directionOrder": [d["id"] for d in bs.DIRECTIONS],
        "directions": directions,
        "seamPolicy": "continuous_geometry_to_tile_boundary",
    }, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    recipe, asset_id, scene, root, ground, authored, out = build_for_gate(args)
    report_path = out / "preflight_report.json"
    report = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=recipe["footprint"],
        profile=profile,
        asset_id=asset_id,
        report_path=report_path,
    )
    scene_gate.require_pass(report)

    if args.stage == "preflight":
        _save_blend(args.save_blend)
        print(f"[CH_GATE] rail track preflight PASS: {report_path}")
        return

    if args.stage == "proxy":
        bs.set_direction(root, bs.DIRECTIONS[0])
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / "proxy_south.png",
            profile=profile,
            asset_id=asset_id,
            direction="south",
        )
        (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        _save_blend(args.save_blend)
        print(f"[CH_GATE] rail track proxy SOUTH ready: {proxy['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError(
            "CH_FINAL_REQUIRES_APPROVED_PROXY: review proxy_south.png first and pass its SHA-256"
        )
    (out / "proxy_approval.json").write_text(json.dumps({
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": asset_id,
        "proxySha256": approval,
        "reviewed": True,
        "runtimeTarget": str(recipe.get("runtimeRepresentation") or "2D_RGBA_modular_track"),
    }, indent=2), encoding="utf-8")
    render_final(scene, root, ground, recipe, asset_id, args.recipe, out)
    _save_blend(args.save_blend)
    print("[CH_GATE] rail track final four-direction source bake complete")


if __name__ == "__main__":
    main()
