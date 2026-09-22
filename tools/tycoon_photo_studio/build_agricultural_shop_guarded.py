"""Guarded CH Blender authoring for the City Horizon agricultural shop.

Reference:
  Converter/file_00000000764881f5865c6948120ef88f.png

This is a new agent-authored visual asset and therefore follows the mandatory
City Horizon quality path:

    preflight -> SOUTH proxy -> human review -> final four-direction bake

The runtime remains 2D PNG. Blender/CH Blender is only the offline authoring
and pre-render environment.
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

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CH_BLENDER = REPO_ROOT / "tools" / "ch_blender"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(CH_BLENDER) not in sys.path:
    sys.path.insert(0, str(CH_BLENDER))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402

ASSET_ID = "building.agricultural_shop.01"
FOOTPRINT = {"widthTiles": 2, "depthTiles": 2}
REFERENCE_DEFAULT = "Converter/file_00000000764881f5865c6948120ef88f.png"


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--reference", default=REFERENCE_DEFAULT)
    p.add_argument("--save-blend", default=None)
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    p.add_argument("--preflight-profile", default=None)
    p.add_argument("--approval-proxy-sha", default=None)
    return p.parse_args(argv)


def _repo_path(value: str) -> Path:
    path = (REPO_ROOT / value).resolve()
    path.relative_to(REPO_ROOT)
    return path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _empty(name: str, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_mode = "XYZ"
    if parent is not None:
        obj.parent = parent
    return obj


def _parent(obj, parent):
    obj.parent = parent
    return obj


def _box(name, loc, dims, material, bevel=0.04, parent=None):
    return _parent(bs.add_box(name, loc, dims, material, bevel), parent) if parent else bs.add_box(name, loc, dims, material, bevel)


def _cylinder(name, loc, radius, depth, material, *, parent=None, vertices=24, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=loc,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    bevel = obj.modifiers.new(name="ProductionBevel", type="BEVEL")
    bevel.width = min(0.035, max(0.012, radius * 0.12))
    bevel.segments = 2
    if parent is not None:
        obj.parent = parent
    return obj


def _sphere(name, loc, radius, material, *, parent=None, scale=(1.0, 1.0, 1.0)):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=20,
        ring_count=10,
        radius=radius,
        location=loc,
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if parent is not None:
        obj.parent = parent
    return obj


def _mesh(name, verts, faces, material, *, parent=None, bevel=0.025):
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    if bevel > 0:
        mod = obj.modifiers.new(name="EdgeSoftening", type="BEVEL")
        mod.width = bevel
        mod.segments = 2
    if parent is not None:
        obj.parent = parent
    return obj


def _mix(a, b, factor):
    return tuple(float(a[i]) * (1.0 - factor) + float(b[i]) * factor for i in range(3)) + (1.0,)


def _sat(rgb):
    return max(rgb) - min(rgb)


def _lum(rgb):
    return (rgb[0] + rgb[1] + rgb[2]) / 3.0


def analyze_reference(path: Path) -> dict:
    """Sample the repository PNG to preserve some of its palette without
    pretending that one raster view can recover hidden 3D geometry.
    """
    result = {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "exists": path.exists(),
        "sha256": _sha256(path) if path.exists() else None,
        "size": None,
        "palette": [],
    }
    if not path.exists():
        return result

    try:
        image = bpy.data.images.load(str(path), check_existing=False)
        width, height = int(image.size[0]), int(image.size[1])
        result["size"] = [width, height]
        if width <= 0 or height <= 0:
            return result

        pixels = image.pixels
        target_samples = 5000
        step = max(1, int(math.sqrt((width * height) / target_samples)))
        counts = {}
        total = 0
        for y in range(0, height, step):
            for x in range(0, width, step):
                idx = (y * width + x) * 4
                r = float(pixels[idx])
                g = float(pixels[idx + 1])
                b = float(pixels[idx + 2])
                a = float(pixels[idx + 3])
                if a < 0.18:
                    continue
                rgb = (r, g, b)
                lum = _lum(rgb)
                sat = _sat(rgb)
                if sat < 0.045 and (lum > 0.90 or lum < 0.045):
                    continue
                key = tuple(round(max(0.0, min(1.0, c)) * 12.0) / 12.0 for c in rgb)
                counts[key] = counts.get(key, 0) + 1
                total += 1

        palette = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:12]
        result["palette"] = [
            {"rgb": [round(c, 4) for c in color], "count": int(count)}
            for color, count in palette
        ]
        result["sampleCount"] = total
    except Exception as exc:
        result["analysisError"] = str(exc)
    return result


def choose_palette(reference: dict) -> dict:
    fallback = {
        "wall": (0.77, 0.68, 0.49, 1.0),
        "roof": (0.18, 0.34, 0.16, 1.0),
        "accent": (0.32, 0.50, 0.18, 1.0),
    }
    rows = reference.get("palette") or []
    if not rows:
        return fallback

    colors = [(tuple(row["rgb"]), int(row["count"])) for row in rows]
    wall_candidates = [
        (rgb, count) for rgb, count in colors
        if 0.42 <= _lum(rgb) <= 0.88 and _sat(rgb) <= 0.48
    ]
    roof_candidates = [
        (rgb, count) for rgb, count in colors
        if 0.10 <= _lum(rgb) <= 0.62 and _sat(rgb) >= 0.10
    ]
    accent_candidates = [
        (rgb, count) for rgb, count in colors
        if 0.16 <= _lum(rgb) <= 0.78 and _sat(rgb) >= 0.18
    ]

    wall_rgb = max(wall_candidates, key=lambda item: item[1])[0] if wall_candidates else fallback["wall"][:3]
    roof_rgb = max(
        roof_candidates,
        key=lambda item: item[1] * (0.45 + _sat(item[0])),
    )[0] if roof_candidates else fallback["roof"][:3]
    accent_rgb = max(
        accent_candidates,
        key=lambda item: item[1] * (0.35 + 1.6 * _sat(item[0])),
    )[0] if accent_candidates else fallback["accent"][:3]

    return {
        "wall": _mix(fallback["wall"], (*wall_rgb, 1.0), 0.34),
        "roof": _mix(fallback["roof"], (*roof_rgb, 1.0), 0.42),
        "accent": _mix(fallback["accent"], (*accent_rgb, 1.0), 0.38),
    }


def materials(reference: dict):
    picked = choose_palette(reference)
    return {
        "wall": bs.make_material("FarmShop_Plaster", picked["wall"], roughness=0.82, recipe="plaster", seed=12, strength=0.42),
        "roof": bs.make_material("FarmShop_Roof", picked["roof"], roughness=0.72, metallic=0.05, recipe="metal_panel", seed=8, strength=0.34),
        "accent": bs.make_material("FarmShop_Accent", picked["accent"], roughness=0.72),
        "wood": bs.make_material("FarmShop_Timber", (0.31, 0.16, 0.07, 1.0), roughness=0.82, recipe="timber", seed=21, strength=0.38),
        "wood_light": bs.make_material("FarmShop_LightTimber", (0.55, 0.32, 0.13, 1.0), roughness=0.80, recipe="timber", seed=5, strength=0.28),
        "stone": bs.make_material("FarmShop_Stone", (0.34, 0.31, 0.25, 1.0), roughness=0.92, recipe="stone", seed=17, strength=0.32),
        "glass": bs.make_material("FarmShop_Glass", (0.20, 0.42, 0.46, 1.0), roughness=0.22, recipe="glass", seed=3, strength=0.20),
        "dark": bs.make_material("FarmShop_Dark", (0.055, 0.07, 0.06, 1.0), roughness=0.82),
        "cream": bs.make_material("FarmShop_Cream", (0.88, 0.82, 0.67, 1.0), roughness=0.82),
        "red": bs.make_material("FarmProduce_Red", (0.68, 0.075, 0.045, 1.0), roughness=0.76),
        "orange": bs.make_material("FarmProduce_Orange", (0.88, 0.35, 0.035, 1.0), roughness=0.76),
        "green": bs.make_material("FarmProduce_Green", (0.13, 0.42, 0.10, 1.0), roughness=0.78),
        "yellow": bs.make_material("FarmProduce_Yellow", (0.78, 0.61, 0.08, 1.0), roughness=0.78),
    }


def add_gable_roof(root, mats):
    width = 5.28
    depth = 4.66
    eave_z = 2.58
    ridge_z = 3.43
    half_w = width / 2.0
    half_d = depth / 2.0
    roof = _mesh(
        "MainGableRoof",
        [
            (-half_w, -half_d, eave_z),
            (0.0, -half_d, ridge_z),
            (0.0, half_d, ridge_z),
            (-half_w, half_d, eave_z),
            (half_w, -half_d, eave_z),
            (half_w, half_d, eave_z),
        ],
        [(0, 1, 2, 3), (1, 4, 5, 2)],
        mats["roof"],
        parent=root,
        bevel=0.035,
    )
    _mesh(
        "SouthGableWall",
        [(-2.38, -2.08, 2.38), (2.38, -2.08, 2.38), (0.0, -2.08, 3.27)],
        [(0, 1, 2)],
        mats["wall"],
        parent=root,
        bevel=0.018,
    )
    _mesh(
        "NorthGableWall",
        [(2.38, 2.08, 2.38), (-2.38, 2.08, 2.38), (0.0, 2.08, 3.27)],
        [(0, 1, 2)],
        mats["wall"],
        parent=root,
        bevel=0.018,
    )
    _cylinder(
        "RoofRidgeCap",
        (0.0, 0.0, ridge_z + 0.03),
        0.075,
        depth + 0.04,
        mats["accent"],
        parent=root,
        vertices=16,
        rotation=(math.radians(90), 0.0, 0.0),
    )
    _box("SouthEaveFascia", (0.0, -2.36, 2.53), (5.34, 0.11, 0.16), mats["wood"], 0.025, root)
    _box("NorthEaveFascia", (0.0, 2.36, 2.53), (5.34, 0.11, 0.16), mats["wood"], 0.025, root)
    return roof


def add_window(root, mats, name, x, y=-2.13, z=1.47, width=1.18, height=1.05):
    _box(name + "_Frame", (x, y, z), (width + 0.18, 0.12, height + 0.18), mats["wood"], 0.025, root)
    _box(name + "_Glass", (x, y - 0.066, z), (width, 0.045, height), mats["glass"], 0.012, root)
    _box(name + "_MullionV", (x, y - 0.095, z), (0.07, 0.055, height), mats["cream"], 0.010, root)
    _box(name + "_MullionH", (x, y - 0.095, z), (width, 0.055, 0.07), mats["cream"], 0.010, root)


def add_produce_crate(root, mats, idx, center, produce_mat):
    x, y = center
    z = 0.35
    _box(f"ProduceCrate_{idx}", (x, y, z), (0.92, 0.58, 0.56), mats["wood_light"], 0.035, root)
    _box(f"ProduceCrateLip_{idx}", (x, y - 0.31, z + 0.15), (0.98, 0.08, 0.30), mats["wood"], 0.018, root)
    positions = [(-0.28, -0.12), (0.0, -0.12), (0.28, -0.12), (-0.18, 0.10), (0.16, 0.10)]
    for n, (dx, dy) in enumerate(positions):
        _sphere(
            f"Produce_{idx}_{n}",
            (x + dx, y + dy, 0.69 + (n % 2) * 0.04),
            0.13,
            produce_mat,
            parent=root,
            scale=(1.0, 0.9, 0.82),
        )


def add_sprout_emblem(root, mats):
    y = -2.425
    _cylinder(
        "SignStem",
        (0.0, y, 2.48),
        0.035,
        0.42,
        mats["green"],
        parent=root,
        vertices=14,
        rotation=(math.radians(90), 0.0, 0.0),
    )
    left = _sphere("SignLeaf_L", (-0.16, y - 0.01, 2.66), 0.19, mats["green"], parent=root, scale=(1.35, 0.22, 0.70))
    right = _sphere("SignLeaf_R", (0.16, y - 0.01, 2.66), 0.19, mats["accent"], parent=root, scale=(1.35, 0.22, 0.70))
    left.rotation_euler[1] = math.radians(-24)
    right.rotation_euler[1] = math.radians(24)


def build_shop(root, mats):
    plinth = _box("BuildingPlinth", (0.0, 0.0, 0.11), (5.28, 4.54, 0.22), mats["stone"], 0.055, root)
    scene_gate.tag(plinth, "building.foundation", ground_contact=True)
    _box("MainBody", (0.0, 0.0, 1.31), (4.92, 4.18, 2.40), mats["wall"], 0.055, root)
    _box("FrontTimberBand", (0.0, -2.12, 2.18), (4.80, 0.14, 0.18), mats["wood"], 0.025, root)
    _box("RearTimberBand", (0.0, 2.12, 2.18), (4.80, 0.14, 0.18), mats["wood"], 0.025, root)
    add_gable_roof(root, mats)

    door = _box("FrontDoor", (0.0, -2.145, 1.10), (0.94, 0.16, 1.92), mats["wood"], 0.035, root)
    scene_gate.tag(door, "building.entrance")
    _box("DoorInset", (0.0, -2.238, 1.13), (0.66, 0.045, 1.50), mats["dark"], 0.015, root)
    _sphere("DoorKnob", (0.31, -2.285, 1.08), 0.055, mats["cream"], parent=root, scale=(1.0, 0.5, 1.0))
    add_window(root, mats, "FrontWindow_L", -1.52)
    add_window(root, mats, "FrontWindow_R", 1.52)

    canopy = _box("FrontCanopy", (0.0, -2.47, 2.08), (4.70, 0.78, 0.12), mats["roof"], 0.035, root)
    canopy.rotation_euler[0] = math.radians(-7.0)
    scene_gate.tag(canopy, "building.canopy")
    for x in (-2.08, 2.08):
        post = _box(f"PorchPost_{'L' if x < 0 else 'R'}", (x, -2.58, 1.02), (0.14, 0.14, 2.04), mats["wood"], 0.025, root)
        scene_gate.tag(post, "building.porch_post", ground_contact=True)
    _box("FrontStep", (0.0, -2.30, 0.19), (1.35, 0.62, 0.20), mats["stone"], 0.035, root)

    _box("FarmSignBoard", (0.0, -2.31, 2.58), (2.15, 0.16, 0.58), mats["wood_light"], 0.055, root)
    _box("FarmSignInset", (0.0, -2.405, 2.58), (1.88, 0.035, 0.42), mats["cream"], 0.020, root)
    add_sprout_emblem(root, mats)

    add_produce_crate(root, mats, 0, (-1.73, -2.49), mats["red"])
    add_produce_crate(root, mats, 1, (1.70, -2.49), mats["orange"])
    add_produce_crate(root, mats, 2, (0.98, -2.53), mats["green"])

    _cylinder("SeedBarrel", (2.25, 1.45, 0.52), 0.34, 0.90, mats["wood"], parent=root, vertices=20)
    _cylinder("SeedBarrelBandTop", (2.25, 1.45, 0.79), 0.355, 0.07, mats["dark"], parent=root, vertices=20)
    _cylinder("SeedBarrelBandBottom", (2.25, 1.45, 0.27), 0.355, 0.07, mats["dark"], parent=root, vertices=20)
    for i, z in enumerate((0.31, 0.54, 0.76)):
        sack = _sphere(
            f"GrainSack_{i}",
            (-2.23, 1.30 + i * 0.16, z),
            0.31,
            mats["cream"],
            parent=root,
            scale=(1.15, 0.72, 0.82),
        )
        sack.rotation_euler[2] = math.radians((-8, 5, -4)[i])


def _save_blend(path):
    if not path:
        return
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


def build_for_gate(args):
    studio = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    reference_path = _repo_path(args.reference)
    reference = analyze_reference(reference_path)
    (out / "reference_analysis.json").write_text(json.dumps(reference, indent=2), encoding="utf-8")

    bs.clear_scene()
    source_res = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, source_res, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    root = _empty("AssetRoot")
    root["assetId"] = ASSET_ID
    root["assetType"] = "building"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["styleContract"] = "CH_STYLIZED_PRERENDER_V1"
    root["groundIncludedInAsset"] = False
    root["runtimeRepresentation"] = "2D_RGBA_pre_rendered_sprite"
    root["footprint"] = "2x2"
    root["referencePath"] = reference["path"]
    root["referenceSha256"] = reference.get("sha256") or ""
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    mats = materials(reference)
    build_shop(root, mats)

    receiver = studio["shadowReceiver"]
    receiver_mat = bs.make_material("ShadowReceiver", receiver["materialColor"], float(receiver.get("roughness", 1.0)))
    ground = bs.add_box("ShadowReceiverPlane", receiver["location"], receiver["dimensions"], receiver_mat, 0.0)

    authored = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj != ground]
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    return studio, scene, root, ground, authored, out, reference


def render_final(studio, scene, root, ground, authored, out, reference):
    src_res = tuple(map(int, studio["render"]["sourceResolution"]))
    final_res = tuple(map(int, studio["render"]["finalResolution"]))
    directions_meta = []
    for direction in bs.DIRECTIONS:
        bs.set_direction(root, direction)
        bpy.context.view_layer.update()
        color_name = f"{ASSET_ID}_{direction['id']}_color_source.png"
        shadow_name = f"{ASSET_ID}_{direction['id']}_shadow_source.png"
        bs.render_color_pass(scene, authored, ground, str(out / color_name))
        origin_px = bs.ground_origin_source_px(scene)
        bs.render_shadow_pass(scene, authored, ground, str(out / shadow_name))
        directions_meta.append({
            "id": direction["id"],
            "quarterTurns": direction["quarterTurns"],
            "rotationDegrees": direction["rotationDegrees"],
            "colorSource": color_name,
            "shadowSource": shadow_name,
            "groundOriginSourcePx": origin_px,
        })

    metadata = {
        "sourceObject": ASSET_ID,
        "assetType": "building",
        "sourceContract": "DIRECT_CH_BLENDER_GUARDED_V1",
        "assetConfig": "tools/tycoon_photo_studio/build_agricultural_shop_guarded.py",
        "reference": {"path": reference["path"], "sha256": reference.get("sha256"), "size": reference.get("size")},
        "studioPreset": studio["id"],
        "styleContract": "CH_STYLIZED_PRERENDER_V1",
        "cameraContract": "CH_CAMERA_V1",
        "gridContract": "CH_GRID_V1",
        "projection": "orthographic_dimetric_2_to_1",
        "yawDegrees": 45.0,
        "elevationDegrees": 30.0,
        "tileWidth": 128,
        "tileHeight": 64,
        "footprint": FOOTPRINT,
        "blenderVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "renderResolution": list(src_res),
        "finalResolution": list(final_res),
        "directionOrder": [d["id"] for d in bs.DIRECTIONS],
        "rotationPolicy": {"assetRootRotates": True, "cameraRemainsFixed": True, "lightsRemainWorldFixed": True},
        "sourceSummary": {"groundIncludedInAsset": False, "referenceDrivenPalette": True, "integratedPorch": True, "farmProduceDisplay": True},
        "directions": directions_meta,
    }
    (out / "studio_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()


def main():
    args = parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    studio, scene, root, ground, authored, out, reference = build_for_gate(args)

    preflight_path = out / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=FOOTPRINT,
        profile=profile,
        asset_id=ASSET_ID,
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        _save_blend(args.save_blend)
        print(f"[CH_GATE] agricultural shop preflight PASS: {preflight_path}")
        return

    if args.stage == "proxy":
        bs.set_direction(root, bs.DIRECTIONS[0])
        bpy.context.view_layer.update()
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / "proxy_south.png",
            profile=profile,
            asset_id=ASSET_ID,
            direction="south",
        )
        (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        _save_blend(args.save_blend)
        print(f"[CH_GATE] agricultural shop proxy SOUTH ready: {proxy['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError("CH_FINAL_REQUIRES_APPROVED_PROXY: review proxy_south.png first and pass its SHA-256")

    approval_record = {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": ASSET_ID,
        "proxySha256": approval,
        "reviewed": True,
        "runtimeTarget": "2D_RGBA_pre_rendered_sprite",
    }
    (out / "proxy_approval.json").write_text(json.dumps(approval_record, indent=2), encoding="utf-8")
    render_final(studio, scene, root, ground, authored, out, reference)
    _save_blend(args.save_blend)
    print("[CH_GATE] agricultural shop final four-direction source bake complete")


if __name__ == "__main__":
    main()
