"""Guarded CH Blender authoring for the City Horizon steam-train vapor overlay.

The train is rebuilt only as a framing/reference layer. Final frames contain
only the animated vapor and share the parent train world origin and canvas.
"""
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
import build_steam_train_guarded as train_builder  # noqa: E402
import scene_gate  # noqa: E402

CONTRACT = "CITY_HORIZON_STEAM_TRAIN_VAPOR_OVERLAY_V1"
ASSET_ID = "effect.steam_train.vapor_overlay.01"
PARENT_ASSET_ID = "vehicle.steam_train.cab_7coaches.01"
DEFAULT_RECIPE = "tools/tycoon_photo_studio/assets/steam_train_vapor_overlay_v1.json"
TRAIN_RECIPE = "tools/tycoon_photo_studio/assets/steam_train_cab_7coaches_v1.train.json"


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", default=DEFAULT_RECIPE)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend", default=None)
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    p.add_argument("--preflight-profile", default=None)
    p.add_argument("--approval-proxy-sha", default=None)
    return p.parse_args(argv)


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


def _vapor_material(name: str, alpha: float):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        raise RuntimeError("CH_VAPOR_MATERIAL_ERROR: Principled BSDF missing")
    rgba = (0.88, 0.90, 0.88, alpha)
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.92
    bsdf.inputs["Alpha"].default_value = alpha
    mat.diffuse_color = rgba
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "DITHERED"
    if hasattr(mat, "use_transparency_overlap"):
        mat.use_transparency_overlap = False
    return mat


def _puff(name: str, parent, radius: float, alpha: float):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=radius, location=(0.0, 0.0, 0.0))
    obj = bpy.context.object
    obj.name = name
    obj.parent = parent
    obj.data.materials.append(_vapor_material(name + "_Mat", alpha))
    obj["runtimeLayer"] = "steam_overlay"
    obj["effectType"] = "vapor"
    obj.visible_shadow = False
    obj.visible_glossy = False
    obj.visible_transmission = False
    obj.visible_volume_scatter = False
    return obj


def _set_alpha(obj, alpha: float):
    alpha = max(0.0, min(1.0, alpha))
    mat = obj.data.materials[0]
    mat.diffuse_color[3] = alpha
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Alpha"].default_value = alpha


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _age(index: int, frame_index: int, count: int, frame_count: int) -> float:
    value = frame_index / float(frame_count) + index / float(count)
    return value - math.floor(value)


def build_vapor(root, recipe):
    overlay_root = _empty("SteamVaporOverlayRoot", root)
    overlay_root["contract"] = CONTRACT
    overlay_root["parentAssetId"] = PARENT_ASSET_ID
    overlay_root["runtimeRepresentation"] = "2D_RGBA_animated_overlay"
    stack = recipe["emitters"]["stack"]
    cylinders = recipe["emitters"]["cylinders"]
    puffs = {"stack": [], "left": [], "right": []}
    for i in range(int(stack["puffCount"])):
        puffs["stack"].append(_puff(f"StackVapor_{i:02d}", overlay_root, float(stack["startRadius"]), 0.5))
    for i in range(int(cylinders["puffCountPerSide"])):
        puffs["left"].append(_puff(f"CylinderVapor_L_{i:02d}", overlay_root, float(cylinders["startRadius"]), 0.35))
        puffs["right"].append(_puff(f"CylinderVapor_R_{i:02d}", overlay_root, float(cylinders["startRadius"]), 0.35))
    return puffs


def set_vapor_frame(recipe, puffs, frame: int):
    animation = recipe["animation"]
    frame_count = int(animation["frameCount"])
    frame_index = (frame - int(animation["frameStart"])) % frame_count

    stack = recipe["emitters"]["stack"]
    ox, oy, oz = map(float, stack["origin"])
    for i, obj in enumerate(puffs["stack"]):
        age = _age(i, frame_index, len(puffs["stack"]), frame_count)
        eased = _smoothstep(age)
        radius = float(stack["startRadius"]) + (float(stack["endRadius"]) - float(stack["startRadius"])) * eased
        alpha = float(stack["startAlpha"]) + (float(stack["endAlpha"]) - float(stack["startAlpha"])) * eased
        lateral = math.sin(i * 1.83 + age * math.tau) * float(stack["spreadY"]) * (0.25 + 0.75 * age)
        obj.location = (ox + float(stack["driftX"]) * age, oy + lateral, oz + float(stack["rise"]) * age)
        obj.scale = (radius, radius * (0.92 + 0.18 * age), radius * (1.05 + 0.35 * age))
        _set_alpha(obj, alpha)

    cylinders = recipe["emitters"]["cylinders"]
    for side_index, key in enumerate(("left", "right")):
        sx, sy, sz = map(float, cylinders["origins"][side_index])
        sign = -1.0 if side_index == 0 else 1.0
        phase_frame = (frame_index + (0 if side_index == 0 else frame_count // 2)) % frame_count
        for i, obj in enumerate(puffs[key]):
            age = _age(i, phase_frame, len(puffs[key]), frame_count)
            eased = _smoothstep(age)
            radius = float(cylinders["startRadius"]) + (float(cylinders["endRadius"]) - float(cylinders["startRadius"])) * eased
            alpha = float(cylinders["startAlpha"]) + (float(cylinders["endAlpha"]) - float(cylinders["startAlpha"])) * eased
            obj.location = (
                sx + float(cylinders["driftX"]) * age,
                sy + sign * float(cylinders["outward"]) * age,
                sz + float(cylinders["rise"]) * age,
            )
            obj.scale = (radius * 1.15, radius, radius * 0.86)
            _set_alpha(obj, alpha)
    bpy.context.view_layer.update()


def build_for_gate(args):
    recipe = bs.load_json(args.recipe)
    if recipe.get("contract") != CONTRACT:
        raise RuntimeError(f"Expected {CONTRACT}")
    if recipe.get("parentAssetId") != PARENT_ASSET_ID:
        raise RuntimeError(f"Expected parentAssetId {PARENT_ASSET_ID}")

    train_recipe = bs.load_json(TRAIN_RECIPE)
    studio = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    source_res = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, source_res, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    root = _empty("AssetRoot")
    root["assetId"] = recipe["assetId"]
    root["assetType"] = "animated_effect_overlay"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["styleContract"] = "CH_STYLIZED_PRERENDER_V1"
    root["groundIncludedInAsset"] = False
    root["runtimeRepresentation"] = "2D_RGBA_animated_overlay"
    root["footprint"] = f"{recipe['footprint']['widthTiles']}x{recipe['footprint']['depthTiles']}"
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    root["parentAssetId"] = PARENT_ASSET_ID

    train_builder.build_train(root, train_builder.materials(), train_recipe)
    receiver = studio["shadowReceiver"]
    receiver_mat = bs.make_material("ShadowReceiver", receiver["materialColor"], float(receiver.get("roughness", 1.0)))
    ground = bs.add_box("ShadowReceiverPlane", receiver["location"], receiver["dimensions"], receiver_mat, 0.0)

    train_authored = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj != ground]
    bs.calibrate_ortho_scale(scene, train_authored, safety_margin=0.16)

    puffs = build_vapor(root, recipe)
    set_vapor_frame(recipe, puffs, int(recipe["animation"]["frameStart"]))
    all_authored = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj != ground]
    vapor_authored = [obj for obj in all_authored if obj.get("runtimeLayer") == "steam_overlay"]
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    return recipe, scene, root, ground, train_authored, vapor_authored, all_authored, puffs, out


def render_overlay_only(scene, root, train_authored, vapor_authored, ground, recipe, puffs, out):
    animation = recipe["animation"]
    frame_start = int(animation["frameStart"])
    frame_end = int(animation["frameEnd"])
    for obj in train_authored:
        obj.hide_render = True
    ground.hide_render = True
    for obj in vapor_authored:
        obj.hide_render = False

    directions_meta = []
    for direction in bs.DIRECTIONS:
        bs.set_direction(root, direction)
        frames = []
        for frame in range(frame_start, frame_end + 1):
            set_vapor_frame(recipe, puffs, frame)
            filename = f"{ASSET_ID}_{direction['id']}_{frame:02d}_source.png"
            scene.render.filepath = str(out / filename)
            bpy.ops.render.render(write_still=True)
            frames.append(filename)
        directions_meta.append({"id": direction["id"], "rotationDegrees": direction["rotationDegrees"], "frames": frames})

    metadata = {
        "contract": "CH_STEAM_TRAIN_VAPOR_SOURCE_BAKE_V1",
        "assetId": ASSET_ID,
        "parentAssetId": PARENT_ASSET_ID,
        "runtimeRepresentation": "2D_RGBA_animated_overlay",
        "cameraContract": "CH_CAMERA_V1",
        "transparentBackground": True,
        "sourceResolution": [int(scene.render.resolution_x), int(scene.render.resolution_y)],
        "animation": animation,
        "directionOrder": [d["id"] for d in bs.DIRECTIONS],
        "anchorPolicy": "same_world_origin_and_canvas_as_parent_train",
        "directions": directions_meta,
    }
    (out / "steam_vapor_overlay_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    recipe, scene, root, ground, train_authored, vapor_authored, all_authored, puffs, out = build_for_gate(args)
    preflight_path = out / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=scene,
        authored=all_authored,
        footprint=recipe["footprint"],
        profile=profile,
        asset_id=recipe["assetId"],
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        _save_blend(args.save_blend)
        print(f"[CH_GATE] steam vapor preflight PASS: {preflight_path}")
        return

    if args.stage == "proxy":
        bs.set_direction(root, bs.DIRECTIONS[0])
        set_vapor_frame(recipe, puffs, 3)
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=all_authored,
            output_path=out / "proxy_south.png",
            profile=profile,
            asset_id=recipe["assetId"],
            direction="south",
        )
        (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        _save_blend(args.save_blend)
        print(f"[CH_GATE] steam vapor composite proxy SOUTH ready: {proxy['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError("CH_FINAL_REQUIRES_APPROVED_PROXY: review proxy_south.png first and pass its SHA-256")
    (out / "proxy_approval.json").write_text(json.dumps({
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": recipe["assetId"],
        "proxySha256": approval,
        "reviewed": True,
        "runtimeTarget": "2D_RGBA_animated_overlay"
    }, indent=2), encoding="utf-8")
    render_overlay_only(scene, root, train_authored, vapor_authored, ground, recipe, puffs, out)
    _save_blend(args.save_blend)
    print("[CH_GATE] steam vapor final 4-direction x 8-frame source bake complete")


if __name__ == "__main__":
    main()
