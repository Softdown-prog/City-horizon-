"""Guarded 16:9 loading-screen hero composition for City Horizon.

This is presentation art, not a gameplay camera/runtime 3D scene. It reuses the
frozen City Horizon studio, current Ferris wheel and small-commercial generators,
then bakes one deterministic 2D background candidate.

Gate:
    preflight -> 16:9 SOUTH proxy -> explicit human review -> final PNG
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
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

import attraction_entry_style_pass as entry_style  # noqa: E402
import build_attraction_entry_skeleton_guarded as entry_skeleton  # noqa: E402
import build_ferris_wheel as fw  # noqa: E402
import build_scene as bs  # noqa: E402
import ferris_wheel_detail_pass as ferris_detail  # noqa: E402
import ferris_wheel_maturity_pass as ferris_maturity  # noqa: E402
import generate_small_commercial_asset as commercial  # noqa: E402
import scene_gate  # noqa: E402


PROXY_RESOLUTION = (1280, 720)
FINAL_RESOLUTION = (2560, 1440)


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--save-blend", default=None)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args(argv)


def _repo_path(value: str) -> Path:
    path = (REPO_ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    path.relative_to(REPO_ROOT)
    return path


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _save_blend(value: str | None):
    if not value:
        return
    target = _repo_path(value)
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


def _new_meshes(before) -> list:
    return [
        obj for obj in bpy.context.scene.objects
        if obj.type == "MESH" and obj not in before and obj.name != "ShadowReceiverPlane"
    ]


def _material(name, rgba, roughness=0.82, metallic=0.0):
    return bs.make_material(name, rgba, roughness, metallic)


def _box(root, authored, name, location, dimensions, material, bevel=0.05, role=None):
    obj = fw.box(name, location, dimensions, material, bevel, root)
    if role:
        scene_gate.tag(obj, role, ground_contact=False)
    authored.append(obj)
    return obj


def _tree(root, authored, mats, name, x, y, scale=1.0):
    trunk = fw.cylinder(
        f"{name}_Trunk",
        (x, y, 1.15 * scale),
        0.26 * scale,
        2.30 * scale,
        mats["treeTrunk"],
        parent=root,
        vertices=14,
    )
    scene_gate.tag(trunk, "scenery.tree_trunk", ground_contact=True)
    authored.append(trunk)

    crown_specs = [
        ((x, y, 2.75 * scale), 1.18),
        ((x - 0.62 * scale, y + 0.16 * scale, 2.55 * scale), 0.88),
        ((x + 0.56 * scale, y + 0.22 * scale, 2.61 * scale), 0.92),
        ((x + 0.05 * scale, y - 0.48 * scale, 2.50 * scale), 0.86),
    ]
    for index, (location, radius) in enumerate(crown_specs):
        bpy.ops.mesh.primitive_ico_sphere_add(
            subdivisions=2,
            radius=radius * scale,
            location=location,
        )
        obj = bpy.context.object
        obj.name = f"{name}_Crown_{index:02d}"
        obj.scale.z = 0.82
        obj.data.materials.append(
            mats["treeLeafLight"] if index == 0 else mats["treeLeaf"]
        )
        obj.parent = root
        scene_gate.tag(obj, "scenery.tree_canopy", ground_contact=False)
        authored.append(obj)


def _lamp(root, authored, mats, name, x, y):
    pole = fw.cylinder(
        f"{name}_Pole",
        (x, y, 1.55),
        0.07,
        3.10,
        mats["lampMetal"],
        parent=root,
        vertices=16,
    )
    scene_gate.tag(pole, "scenery.lamp", ground_contact=True)
    authored.append(pole)
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=20,
        ring_count=12,
        radius=0.24,
        location=(x, y, 3.13),
    )
    globe = bpy.context.object
    globe.name = f"{name}_Globe"
    globe.scale.z = 0.82
    globe.data.materials.append(mats["lampGlass"])
    globe.parent = root
    authored.append(globe)


def _build_commercial(root, authored, recipe_path: Path, location, rotation_degrees=0.0):
    recipe = _load_json(recipe_path)
    asset = commercial.expand(recipe)
    before = set(bpy.context.scene.objects)
    objects = bs.build_asset(asset, asset_config_path=str(recipe_path))
    created = [obj for obj in objects if obj.type == "MESH"]
    group = fw.empty(f"Hero_{asset['assetId']}", location, root)
    group.rotation_euler[2] = math.radians(rotation_degrees)
    for obj in created:
        obj.parent = group
        scene_gate.tag(obj, "background.commercial", ground_contact=False)
    authored.extend(created)
    # Guard against future expander helpers that create meshes not returned.
    for obj in _new_meshes(before):
        if obj not in authored:
            obj.parent = group
            authored.append(obj)
    return group


def _build_ferris(root, authored, recipe_path: Path, location):
    recipe = _load_json(recipe_path)
    mats = fw.make_materials(recipe)
    group = fw.empty("Hero_FerrisWheel", location, root)
    before = set(bpy.context.scene.objects)
    fw.build_supports(group, recipe["geometry"], mats)
    rotor, gondolas = fw.build_wheel(group, recipe["geometry"], mats)
    ferris_detail.apply_detail_pass(group, rotor, gondolas, recipe["geometry"], mats, fw)
    ferris_maturity.apply_maturity_pass(group, rotor, gondolas, recipe["geometry"], mats, fw)
    fw.animate(rotor, gondolas, recipe["animation"])
    created = _new_meshes(before)
    for obj in created:
        scene_gate.tag(obj, "attraction.ferris_wheel", ground_contact=False)
    authored.extend(created)
    bpy.context.scene.frame_set(int(recipe["animation"].get("frameStart", 1)))
    return group


def _build_entry(root, authored, recipe_path: Path, location):
    recipe = _load_json(recipe_path)
    mats = entry_skeleton.make_materials(recipe)
    group = fw.empty("Hero_TicketEntry", location, root)
    before = set(bpy.context.scene.objects)
    created = entry_skeleton.build_skeleton(group, recipe, mats)
    created.extend(entry_style.apply_style_pass(group, recipe, mats, fw, scene_gate))
    seen = set(authored)
    for obj in created + _new_meshes(before):
        if obj.type == "MESH" and obj not in seen:
            scene_gate.tag(obj, "attraction.ticket_entry", ground_contact=False)
            authored.append(obj)
            seen.add(obj)
    return group


def _fit_camera_current(scene, authored, safety_margin=0.075):
    camera = scene.camera
    inv = camera.matrix_world.inverted()
    half_x = 0.0
    half_y = 0.0
    for obj in authored:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            point = inv @ (obj.matrix_world @ Vector(corner))
            half_x = max(half_x, abs(point.x))
            half_y = max(half_y, abs(point.y))
    aspect = scene.render.resolution_x / max(1.0, float(scene.render.resolution_y))
    needed = max((half_x * 2.0) / aspect, half_y * 2.0)
    camera.data.ortho_scale = needed * (1.0 + safety_margin)
    bpy.context.view_layer.update()
    return float(camera.data.ortho_scale)


def _set_world_background(scene, rgba):
    world = scene.world
    if world is None:
        return
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background:
        background.inputs["Color"].default_value = tuple(rgba)
        background.inputs["Strength"].default_value = 0.8


def build_scene(args):
    recipe_path = _repo_path(args.recipe)
    studio_path = _repo_path(args.studio_preset)
    out = _repo_path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    recipe = _load_json(recipe_path)
    if recipe.get("contract") != "CITY_HORIZON_LOADING_HERO_V1":
        raise RuntimeError("Expected CITY_HORIZON_LOADING_HERO_V1 recipe")

    studio = _load_json(studio_path)
    bs.clear_scene()
    scene = bs.configure_scene(studio, PROXY_RESOLUTION, str(out))
    scene.render.resolution_x, scene.render.resolution_y = PROXY_RESOLUTION
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    _set_world_background(scene, recipe["presentation"]["worldColor"])

    root = fw.empty("AssetRoot")
    root["assetId"] = recipe["assetId"]
    root["assetType"] = "ui_loading_background"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = studio["id"]
    root["styleContract"] = "CH_STYLIZED_PRERENDER_V1"
    root["presentationContract"] = recipe["contract"]
    root["runtimeRepresentation"] = "static_2D_loading_background"
    root["directionPolicy"] = "single_south_loading_presentation"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    mats = {
        "grass": _material("LoadingHeroGrass", [0.29, 0.49, 0.25, 1.0], 0.96),
        "parkGrass": _material("LoadingHeroParkGrass", [0.23, 0.44, 0.22, 1.0], 0.96),
        "road": _material("LoadingHeroAsphalt", [0.13, 0.15, 0.16, 1.0], 0.91),
        "sidewalk": _material("LoadingHeroSidewalk", [0.55, 0.54, 0.50, 1.0], 0.94),
        "path": _material("LoadingHeroParkPath", [0.67, 0.57, 0.43, 1.0], 0.93),
        "marking": _material("LoadingHeroRoadMarking", [0.92, 0.87, 0.69, 1.0], 0.78),
        "water": _material("LoadingHeroWater", [0.18, 0.48, 0.60, 1.0], 0.32),
        "treeTrunk": _material("LoadingHeroTreeTrunk", [0.26, 0.15, 0.08, 1.0], 0.92),
        "treeLeaf": _material("LoadingHeroTreeLeaf", [0.12, 0.32, 0.14, 1.0], 0.91),
        "treeLeafLight": _material("LoadingHeroTreeLeafLight", [0.24, 0.48, 0.20, 1.0], 0.90),
        "lampMetal": _material("LoadingHeroLampMetal", [0.10, 0.12, 0.13, 1.0], 0.62, 0.14),
        "lampGlass": _material("LoadingHeroLampGlass", [0.95, 0.82, 0.49, 1.0], 0.32),
        "roof": _material("LoadingHeroBackgroundRoof", [0.25, 0.28, 0.30, 1.0], 0.84),
        "wallA": _material("LoadingHeroBackgroundWallA", [0.72, 0.64, 0.52, 1.0], 0.88),
        "wallB": _material("LoadingHeroBackgroundWallB", [0.55, 0.67, 0.66, 1.0], 0.88),
    }
    authored = []

    ground = recipe["composition"]["ground"]
    _box(
        root, authored, "HeroGround",
        (0.0, 0.0, -0.16),
        (ground["width"], ground["depth"], 0.32),
        mats["grass"], 0.0, "loading.ground",
    )

    road = recipe["composition"]["road"]
    _box(root, authored, "HeroRoad", (road["x"], 0.0, 0.045),
         (road["width"], ground["depth"] + 0.2, 0.09), mats["road"], 0.0, "loading.road")
    sidewalk_offset = road["width"] * 0.5 + road["sidewalkWidth"] * 0.5
    for side, sign in (("West", -1.0), ("East", 1.0)):
        _box(
            root, authored, f"HeroSidewalk{side}",
            (road["x"] + sign * sidewalk_offset, 0.0, 0.075),
            (road["sidewalkWidth"], ground["depth"] + 0.2, 0.15),
            mats["sidewalk"], 0.025, "loading.sidewalk",
        )
    dash_y = -ground["depth"] * 0.5 + 2.2
    dash_index = 0
    while dash_y < ground["depth"] * 0.5 - 1.0:
        _box(root, authored, f"RoadDash_{dash_index:02d}",
             (road["x"], dash_y, 0.105), (0.18, 2.4, 0.03),
             mats["marking"], 0.01, "loading.road_marking")
        dash_y += 4.3
        dash_index += 1

    park = recipe["composition"]["park"]
    _box(
        root, authored, "CityParkLawn",
        (park["x"], park["y"], 0.055),
        (park["width"], park["depth"], 0.11),
        mats["parkGrass"], 0.20, "loading.park",
    )
    _box(
        root, authored, "CityParkMainPath",
        (park["x"], park["y"] - 2.8, 0.125),
        (park["width"] - 2.0, 2.0, 0.07),
        mats["path"], 0.32, "loading.park_path",
    )
    _box(
        root, authored, "CityParkCrossPath",
        (park["x"] - 2.2, park["y"] + 1.2, 0.126),
        (2.0, park["depth"] - 2.0, 0.07),
        mats["path"], 0.32, "loading.park_path",
    )

    pond = recipe["composition"]["pond"]
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64,
        radius=pond["radius"],
        depth=0.055,
        location=(pond["x"], pond["y"], 0.145),
    )
    pond_obj = bpy.context.object
    pond_obj.name = "CityParkPond"
    pond_obj.scale.y = pond["yScale"]
    pond_obj.data.materials.append(mats["water"])
    pond_obj.parent = root
    scene_gate.tag(pond_obj, "loading.water", ground_contact=False)
    authored.append(pond_obj)

    ferris_path = _repo_path(recipe["sources"]["ferrisWheel"])
    _build_ferris(root, authored, ferris_path, tuple(recipe["composition"]["ferrisLocation"]))

    entry_path = _repo_path(recipe["sources"]["ticketEntry"])
    _build_entry(root, authored, entry_path, tuple(recipe["composition"]["ticketEntryLocation"]))

    for building in recipe["composition"]["commercialBuildings"]:
        _build_commercial(
            root,
            authored,
            _repo_path(building["source"]),
            tuple(building["location"]),
            float(building.get("rotationDegrees", 0.0)),
        )

    # Background-only low-rise silhouettes fill the far edge without reviving
    # retired house prototypes as production assets.
    for index, spec in enumerate(recipe["composition"]["backgroundMassing"]):
        group = fw.empty(f"BackgroundMass_{index:02d}", tuple(spec["location"]), root)
        _box(group, authored, f"BackgroundMassBody_{index:02d}", (0.0, 0.0, spec["height"] * 0.5),
             (spec["width"], spec["depth"], spec["height"]),
             mats["wallA"] if index % 2 == 0 else mats["wallB"], 0.12, "background.massing")
        _box(group, authored, f"BackgroundMassRoof_{index:02d}", (0.0, 0.0, spec["height"] + 0.16),
             (spec["width"] + 0.14, spec["depth"] + 0.14, 0.32),
             mats["roof"], 0.06, "background.massing_roof")

    for index, tree in enumerate(recipe["composition"]["trees"]):
        _tree(root, authored, mats, f"HeroTree_{index:02d}",
              float(tree[0]), float(tree[1]), float(tree[2]))

    for index, lamp in enumerate(recipe["composition"]["lamps"]):
        _lamp(root, authored, mats, f"HeroLamp_{index:02d}", float(lamp[0]), float(lamp[1]))

    bpy.context.view_layer.update()
    _fit_camera_current(scene, authored, safety_margin=0.09)
    scene.frame_set(1)
    bpy.context.view_layer.update()

    context = {
        "recipe": recipe,
        "recipePath": recipe_path,
        "studio": studio,
        "studioPath": studio_path,
        "scene": scene,
        "root": root,
        "authored": authored,
        "out": out,
    }
    return context


def _render_16_9(ctx, target: Path, resolution, *, proxy: bool):
    scene = ctx["scene"]
    old = {
        "engine": scene.render.engine,
        "x": scene.render.resolution_x,
        "y": scene.render.resolution_y,
        "pct": scene.render.resolution_percentage,
        "path": scene.render.filepath,
        "transparent": scene.render.film_transparent,
        "samples": getattr(scene.cycles, "samples", None),
    }
    try:
        if proxy:
            scene.render.engine = "BLENDER_EEVEE_NEXT"
        else:
            scene.render.engine = ctx["studio"]["render"]["engine"]
            if old["samples"] is not None:
                scene.cycles.samples = min(int(ctx["studio"]["render"]["samples"]), 96)
        scene.render.resolution_x = int(resolution[0])
        scene.render.resolution_y = int(resolution[1])
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        # The hero background intentionally includes the studio world/sky so the
        # screen is fully covered. Preflight itself still runs with transparent film.
        scene.render.film_transparent = False
        scene.render.filepath = str(target)
        bpy.ops.render.render(write_still=True)
    finally:
        scene.render.engine = old["engine"]
        scene.render.resolution_x = old["x"]
        scene.render.resolution_y = old["y"]
        scene.render.resolution_percentage = old["pct"]
        scene.render.filepath = old["path"]
        scene.render.film_transparent = old["transparent"]
        if old["samples"] is not None:
            scene.cycles.samples = old["samples"]


def _write_proxy_report(ctx, target: Path):
    _render_16_9(ctx, target, PROXY_RESOLUTION, proxy=True)
    report = {
        "contract": "CH_PROXY_RENDER_V1",
        "status": "ok",
        "assetId": ctx["recipe"]["assetId"],
        "direction": "south",
        "engine": "BLENDER_EEVEE_NEXT",
        "resolution": list(PROXY_RESOLUTION),
        "path": str(target),
        "bytes": target.stat().st_size,
        "sha256": _sha256(target),
        "presentation": "16:9 loading-screen hero review",
        "safeAreas": ctx["recipe"]["presentation"]["safeAreas"],
    }
    (ctx["out"] / "proxy_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _write_final(ctx, approval_sha: str):
    target = ctx["out"] / "loading_hero_city_park_01.png"
    _render_16_9(ctx, target, FINAL_RESOLUTION, proxy=False)
    approval = {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": ctx["recipe"]["assetId"],
        "proxySha256": approval_sha,
        "reviewed": True,
        "runtimeTarget": "static_2D_loading_background",
    }
    (ctx["out"] / "proxy_approval.json").write_text(
        json.dumps(approval, indent=2) + "\n", encoding="utf-8"
    )
    final_report = {
        "contract": "CH_LOADING_HERO_BAKE_V1",
        "status": "ok",
        "assetId": ctx["recipe"]["assetId"],
        "approvedProxySha256": approval_sha,
        "file": target.name,
        "resolution": list(FINAL_RESOLUTION),
        "sha256": _sha256(target),
        "cameraContract": "CH_CAMERA_V1",
        "studioPreset": ctx["studio"]["id"],
        "runtimeRepresentation": "static_2D_loading_background",
        "safeAreas": ctx["recipe"]["presentation"]["safeAreas"],
        "sourceRecipe": ctx["recipePath"].relative_to(REPO_ROOT).as_posix(),
    }
    (ctx["out"] / "final_bake_report.json").write_text(
        json.dumps(final_report, indent=2) + "\n", encoding="utf-8"
    )


def main():
    args = parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    ctx = build_scene(args)

    preflight_path = ctx["out"] / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=ctx["scene"],
        authored=ctx["authored"],
        footprint=ctx["recipe"]["footprint"],
        profile=profile,
        asset_id=ctx["recipe"]["assetId"],
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        _save_blend(args.save_blend)
        print(f"[CH_GATE] loading hero preflight PASS: {preflight_path}")
        return

    if args.stage == "proxy":
        report = _write_proxy_report(ctx, ctx["out"] / "proxy_south.png")
        _save_blend(args.save_blend)
        print(f"[CH_GATE] loading hero 16:9 proxy ready: {report['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError(
            "CH_FINAL_REQUIRES_APPROVED_PROXY: review proxy_south.png first and pass its SHA-256"
        )
    _write_final(ctx, approval)
    _save_blend(args.save_blend)
    print("[CH_GATE] loading hero final 2560x1440 PNG complete")


if __name__ == "__main__":
    main()
