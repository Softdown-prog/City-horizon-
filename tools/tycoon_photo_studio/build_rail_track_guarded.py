"""Guarded CH Blender authoring for City Horizon modular rail sprites."""
from __future__ import annotations

import argparse
import json
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


def _box(name, location, dimensions, material, parent, role: str, ground_contact=False):
    obj = bs.add_box(name, location, dimensions, material, 0.0)
    obj.parent = parent
    scene_gate.tag(obj, role, ground_contact=ground_contact)
    return obj


def _asset_id(recipe) -> str:
    asset_id = str(recipe.get("assetId") or LEGACY_ASSET_ID).strip()
    if not asset_id or not re.fullmatch(r"[A-Za-z0-9._-]+", asset_id):
        raise RuntimeError("CH_RAIL_ASSET_ID_INVALID: recipe assetId must be a safe non-empty identifier")
    return asset_id


def build_track(root, recipe):
    spec = recipe["module"]
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

    steel = _material("RailSteel", (0.20, 0.22, 0.22, 1.0), 0.34, 0.72)
    steel_side = _material("RailSteelDark", (0.105, 0.12, 0.12, 1.0), 0.46, 0.56)
    timber = _material("SleeperTimber", (0.26, 0.155, 0.085, 1.0), 0.82, 0.0)
    ballast = _material("Ballast", (0.285, 0.275, 0.245, 1.0), 0.94, 0.0)

    # Continuous authoring module: geometry reaches the tile boundary so the
    # resulting pre-rendered sprites can be placed seam-to-seam by the 2D graph.
    _box(
        "BallastBed", (0.0, 0.0, ballast_h * 0.5),
        (tile, ballast_w, ballast_h), ballast, root,
        "rail.ballast", ground_contact=True,
    )

    spacing = tile / sleeper_count
    start = -tile * 0.5 + spacing * 0.5
    for index in range(sleeper_count):
        x = start + spacing * index
        _box(
            f"Sleeper_{index:02d}", (x, 0.0, ballast_h + sleeper_h * 0.5),
            (sleeper_w, sleeper_len, sleeper_h), timber, root,
            "rail.sleeper", ground_contact=False,
        )

    rail_z = ballast_h + sleeper_h + rail_h * 0.5
    for side, y in (("L", -gauge * 0.5), ("R", gauge * 0.5)):
        _box(
            f"Rail_{side}", (0.0, y, rail_z),
            (tile, rail_w, rail_h), steel, root,
            "rail.steel", ground_contact=False,
        )
        _box(
            f"RailWeb_{side}", (0.0, y, rail_z - rail_h * 0.34),
            (tile, rail_w * 0.52, rail_h * 0.72), steel_side, root,
            "rail.steel_web", ground_contact=False,
        )


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
