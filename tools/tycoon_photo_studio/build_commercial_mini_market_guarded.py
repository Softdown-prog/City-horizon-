"""Guarded CH Blender authoring for commercial_mini_market_3x2_01.

The user-supplied grocery storefront image is used as art direction only.
This builder creates original City Horizon geometry and keeps the normal gate:

    preflight -> SOUTH proxy -> human approval -> final four-direction source bake

Runtime remains 2D PNG; Blender is offline authoring only.
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
ROOT = HERE.parents[1]
CH_BLENDER = ROOT / "tools" / "ch_blender"
for path in (HERE, CH_BLENDER):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402
import ch_architecture_modules as arch  # noqa: E402

ASSET_ID = "commercial_mini_market_3x2_01"
DEFAULT_RECIPE = "tools/tycoon_photo_studio/assets/commercial_mini_market_3x2_01.shop.json"


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    parser.add_argument("--save-blend", default=None)
    return parser.parse_args(argv)


def repo_path(value):
    path = (ROOT / value).resolve()
    path.relative_to(ROOT)
    return path


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def empty(name, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_mode = "XYZ"
    obj.parent = parent
    return obj


def box(name, loc, dims, material, parent, bevel=0.035):
    obj = bs.add_box(name, loc, dims, material, bevel)
    obj.parent = parent
    return obj


def sphere(name, loc, radius, material, parent, scale=(1, 1, 1), seg=16, rings=8):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=radius, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.parent = parent
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    return obj


def cylinder(name, loc, radius, depth, material, parent, vertices=24,
             rotation=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0), bevel=0.025):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.parent = parent
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel > 0:
        modifier = obj.modifiers.new("EdgeSoftening", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
    return obj


def load_recipe(path):
    recipe = json.loads(Path(path).read_text(encoding="utf-8"))
    if recipe.get("contract") != "CITY_HORIZON_COMMERCIAL_BUILDING_V1":
        raise RuntimeError("CH_MINI_MARKET_RECIPE_CONTRACT")
    if recipe.get("assetId") != ASSET_ID:
        raise RuntimeError("CH_MINI_MARKET_ASSET_ID")
    if recipe.get("footprint") != {"widthTiles": 3, "depthTiles": 2}:
        raise RuntimeError("CH_MINI_MARKET_FOOTPRINT: pilot must remain 3x2")
    return recipe


def make_materials(recipe):
    materials = {}
    for key, spec in recipe["materials"].items():
        materials[key] = bs.make_material(
            spec["name"], spec["rgba"], float(spec.get("roughness", 0.78)),
            float(spec.get("metallic", 0.0)), recipe=spec.get("recipe", "solid"),
            seed=int(spec.get("seed", 0)), strength=float(spec.get("strength", 0.05)),
        )
    arch.configure_warm_emission(materials["glass"], recipe["materials"]["glass"]["rgba"], 0.62)
    return materials


def add_front_window(root, mats, name, x, front_y, z, width, height):
    box(name + "Frame", (x, front_y, z), (width + 0.18, 0.12, height + 0.18), mats["frame"], root, 0.022)
    box(name + "Glass", (x, front_y - 0.072, z), (width, 0.042, height), mats["glass"], root, 0.010)
    box(name + "MullionV", (x, front_y - 0.104, z), (0.065, 0.04, height), mats["frame"], root, 0.008)
    box(name + "MullionH", (x, front_y - 0.104, z), (width, 0.04, 0.065), mats["frame"], root, 0.008)
    box(name + "Sill", (x, front_y - 0.075, z - height * 0.56), (width + 0.22, 0.18, 0.10), mats["trim"], root, 0.016)


def add_side_window_east(root, mats, name, x, y, z, width, height):
    box(name + "Frame", (x, y, z), (0.12, width + 0.18, height + 0.18), mats["frame"], root, 0.022)
    box(name + "Glass", (x + 0.072, y, z), (0.042, width, height), mats["glass"], root, 0.010)
    box(name + "MullionV", (x + 0.104, y, z), (0.04, 0.065, height), mats["frame"], root, 0.008)
    box(name + "MullionH", (x + 0.104, y, z), (0.04, width, 0.065), mats["frame"], root, 0.008)
    box(name + "Sill", (x + 0.075, y, z - height * 0.56), (0.18, width + 0.22, 0.10), mats["trim"], root, 0.016)


def add_double_door(root, mats, entry, front_y):
    x = float(entry["centerX"])
    width = float(entry["doorWidth"])
    height = float(entry["doorHeight"])
    z = float(entry["doorCenterZ"])
    frame = box("EntranceFrame", (x, front_y, z), (width + 0.22, 0.16, height + 0.18), mats["frame"], root, 0.024)
    scene_gate.tag(frame, "building.entrance")
    box("EntranceGlass", (x, front_y - 0.095, z), (width, 0.045, height), mats["glass"], root, 0.010)
    box("EntranceCenterBar", (x, front_y - 0.128, z), (0.075, 0.04, height), mats["frame"], root, 0.008)
    for side, sx in (("L", x - width * 0.28), ("R", x + width * 0.28)):
        box("EntranceHandle" + side, (sx, front_y - 0.158, z + 0.03), (0.05, 0.04, 0.50), mats["darkMetal"], root, 0.010)
    box("PrivateEntryMat", (x, front_y - 0.52, 0.035),
        (float(entry["matWidth"]), float(entry["matDepth"]), 0.07), mats["mat"], root, 0.018)


def add_south_awning(root, mats, name, center_x, front_y, width, depth, center_z, striped=False, stripes=7):
    if striped:
        stripe_count = max(3, int(stripes))
        stripe_w = width / stripe_count
        for i in range(stripe_count):
            material = mats["green"] if i % 2 == 0 else mats["wall"]
            x = center_x - width / 2 + stripe_w * (i + 0.5)
            panel = box(f"{name}Stripe{i}", (x, front_y - depth * 0.44, center_z),
                        (stripe_w * 0.98, depth, 0.085), material, root, 0.010)
            panel.rotation_euler[0] = math.radians(-12.0)
            box(f"{name}Skirt{i}", (x, front_y - depth * 0.89, center_z - 0.16),
                (stripe_w * 0.98, 0.085, 0.28), material, root, 0.008)
    else:
        panel = box(name + "Canopy", (center_x, front_y - depth * 0.44, center_z),
                    (width, depth, 0.10), mats["green"], root, 0.020)
        panel.rotation_euler[0] = math.radians(-12.0)
        box(name + "Skirt", (center_x, front_y - depth * 0.89, center_z - 0.16),
            (width, 0.09, 0.28), mats["green"], root, 0.010)


def add_east_awning(root, mats, name, east_x, y, width, depth, center_z):
    panel = box(name + "Canopy", (east_x + depth * 0.44, y, center_z),
                (depth, width, 0.10), mats["green"], root, 0.020)
    panel.rotation_euler[1] = math.radians(12.0)
    box(name + "Skirt", (east_x + depth * 0.89, y, center_z - 0.16),
        (0.09, width, 0.28), mats["green"], root, 0.010)


def add_sign_crown(root, mats, facade, front_y):
    z = float(facade["signCenterZ"])
    width = float(facade["signWidth"])
    height = float(facade["signHeight"])
    radius = float(facade["signRoundRadius"])
    cylinder("SignRoundBack", (0.0, front_y - 0.135, z + 0.17), radius, 0.15, mats["green"], root,
             vertices=36, rotation=(math.radians(90), 0.0, 0.0), scale=(1.22, 0.72, 1.0), bevel=0.018)
    box("SignLowerGreen", (0.0, front_y - 0.14, z - 0.12), (width + 0.18, 0.16, height * 0.62), mats["green"], root, 0.035)
    box("SignCreamFace", (0.0, front_y - 0.235, z + 0.02), (width, 0.045, height * 0.74), mats["wall"], root, 0.030)
    emblem_y = front_y - 0.272
    box("BasketTop", (0.0, emblem_y, z + 0.08), (0.90, 0.035, 0.085), mats["green"], root, 0.008)
    box("BasketBase", (0.0, emblem_y, z - 0.16), (0.68, 0.035, 0.38), mats["green"], root, 0.018)
    for x in (-0.22, 0.0, 0.22):
        box(f"BasketCut{x:+.2f}", (x, emblem_y - 0.024, z - 0.16), (0.07, 0.018, 0.30), mats["wall"], root, 0.004)
    for x, tilt in ((-0.22, -26.0), (0.22, 26.0)):
        handle = box("BasketHandleL" if x < 0 else "BasketHandleR",
                     (x, emblem_y, z + 0.38), (0.08, 0.035, 0.58), mats["green"], root, 0.008)
        handle.rotation_euler[1] = math.radians(tilt)


def add_produce_crate(root, mats, index, x, y, kind):
    box(f"ProduceCrate{index}", (x, y, 0.33), (0.70, 0.56, 0.56), mats["wood"], root, 0.028)
    for row, z in enumerate((0.20, 0.42)):
        box(f"ProduceCrateSlat{index}_{row}", (x, y - 0.30, z), (0.64, 0.045, 0.075), mats["trim"], root, 0.006)
    produce_mat = mats["greenLight"] if kind == "green" else mats[kind]
    for n, (dx, dy) in enumerate(((-0.22, -0.12), (0.0, -0.12), (0.22, -0.12), (-0.12, 0.10), (0.14, 0.10))):
        sphere(f"Produce{index}_{n}", (x + dx, y + dy, 0.69 + (n % 2) * 0.035),
               0.105, produce_mat, root, (1.0, 0.92, 0.86), 12, 6)


def add_planter(root, mats, index, x, y):
    box(f"Planter{index}", (x, y, 0.28), (0.62, 0.50, 0.56), mats["trim"], root, 0.032)
    for n, (dx, dy) in enumerate(((-0.17, -0.05), (0.14, -0.08), (-0.05, 0.10), (0.14, 0.10))):
        sphere(f"PlanterLeaf{index}_{n}", (x + dx, y + dy, 0.66), 0.18,
               mats["greenLight" if n == 2 else "leaf"], root, (0.80, 0.68, 1.25), 12, 7)


def add_hvac_unit(root, mats, index, spec, roof_z):
    x, y = float(spec["x"]), float(spec["y"])
    width, depth, height = float(spec["width"]), float(spec["depth"]), float(spec["height"])
    z = roof_z + height / 2 + 0.08
    box(f"HVAC{index}Body", (x, y, z), (width, depth, height), mats["metal"], root, 0.040)
    box(f"HVAC{index}Top", (x, y, z + height / 2 + 0.06), (width + 0.08, depth + 0.08, 0.12), mats["trim"], root, 0.030)
    front = y - depth / 2 - 0.025
    for slat in range(5):
        sx = x - width * 0.34 + slat * width * 0.17
        box(f"HVAC{index}Grille{slat}", (sx, front, z), (0.045, 0.03, height * 0.62), mats["darkMetal"], root, 0.004)
    if index == 0:
        cylinder("HVACFanRing", (x, y, z + height / 2 + 0.135), min(width, depth) * 0.30, 0.045,
                 mats["darkMetal"], root, vertices=28, scale=(1.0, 1.0, 0.45), bevel=0.006)


def build_market(root, mats, recipe):
    mass = recipe["mass"]
    roof = recipe["roof"]
    facade = recipe["facade"]
    entry = recipe["entry"]
    windows = recipe["windows"]
    awnings = recipe["awnings"]

    fw = float(mass["foundationWidth"])
    fd = float(mass["foundationDepth"])
    fh = float(mass["foundationHeight"])
    bw = float(mass["bodyWidth"])
    bd = float(mass["bodyDepth"])
    wh = float(mass["wallHeight"])
    z0 = float(mass["wallBaseZ"])

    foundation = box("BuildingFoundation", (0, 0, fh / 2), (fw, fd, fh), mats["trim"], root, 0.050)
    scene_gate.tag(foundation, "building.foundation", ground_contact=True)
    box("MarketBody", (0, 0, z0 + wh / 2), (bw, bd, wh), mats["wall"], root, 0.045)

    band_z = float(facade["frontBandCenterZ"])
    band_h = float(facade["frontBandHeight"])
    box("SouthGreenBand", (0, -bd / 2 - 0.045, band_z), (bw - 0.20, 0.09, band_h), mats["green"], root, 0.018)
    box("EastGreenBand", (bw / 2 + 0.045, 0, band_z), (0.09, bd - 0.20, band_h), mats["green"], root, 0.018)
    box("WestGreenBand", (-bw / 2 - 0.045, 0, band_z), (0.09, bd - 0.20, band_h), mats["green"], root, 0.018)
    box("NorthGreenBand", (0, bd / 2 + 0.045, band_z), (bw - 0.20, 0.09, band_h), mats["green"], root, 0.018)

    for x in (-bw / 2 - 0.055, bw / 2 + 0.055):
        for y in (-bd / 2 - 0.055, bd / 2 + 0.055):
            box(f"CornerPilaster_{'E' if x > 0 else 'W'}_{'N' if y > 0 else 'S'}",
                (x, y, z0 + wh / 2), (0.22, 0.22, wh + 0.10), mats["trim"], root, 0.018)
    kick_h = float(facade["woodKickHeight"])
    box("SouthWoodKick", (0, -bd / 2 - 0.066, z0 + kick_h / 2), (bw - 0.38, 0.08, kick_h), mats["wood"], root, 0.010)
    box("EastWoodKick", (bw / 2 + 0.066, 0, z0 + kick_h / 2), (0.08, bd - 0.38, kick_h), mats["wood"], root, 0.010)

    slab_z = float(roof["slabZ"])
    slab_h = float(roof["slabHeight"])
    rw = float(roof["slabWidth"])
    rd = float(roof["slabDepth"])
    box("FlatRoofSlab", (0, 0, slab_z), (rw, rd, slab_h), mats["roof"], root, 0.025)
    parapet_h = float(roof["parapetHeight"])
    parapet_t = float(roof["parapetThickness"])
    parapet_z = slab_z + slab_h / 2 + parapet_h / 2
    for name, loc, dims in (
        ("ParapetSouth", (0, -rd / 2 + parapet_t / 2, parapet_z), (rw, parapet_t, parapet_h)),
        ("ParapetNorth", (0, rd / 2 - parapet_t / 2, parapet_z), (rw, parapet_t, parapet_h)),
        ("ParapetEast", (rw / 2 - parapet_t / 2, 0, parapet_z), (parapet_t, rd, parapet_h)),
        ("ParapetWest", (-rw / 2 + parapet_t / 2, 0, parapet_z), (parapet_t, rd, parapet_h)),
    ):
        box(name, loc, dims, mats["trim"], root, 0.018)
    cap_h = float(roof["parapetCapHeight"])
    box("ParapetCapSouth", (0, -rd / 2 + parapet_t / 2, parapet_z + parapet_h / 2),
        (rw + 0.08, parapet_t + 0.06, cap_h), mats["wall"], root, 0.015)
    box("ParapetCapNorth", (0, rd / 2 - parapet_t / 2, parapet_z + parapet_h / 2),
        (rw + 0.08, parapet_t + 0.06, cap_h), mats["wall"], root, 0.015)

    front_y = -bd / 2 - 0.065
    add_sign_crown(root, mats, facade, front_y)
    for index, x in enumerate(windows["frontCentersX"]):
        add_front_window(root, mats, f"FrontWindow{index}", float(x), front_y,
                         float(windows["frontCenterZ"]), float(windows["frontWidth"]), float(windows["frontHeight"]))
    add_double_door(root, mats, entry, front_y)

    add_south_awning(root, mats, "CenterAwning", 0.0, front_y,
                     float(awnings["centerWidth"]), float(awnings["centerDepth"]),
                     float(awnings["centerCenterZ"]), striped=True, stripes=int(awnings["centerStripes"]))
    add_south_awning(root, mats, "LeftAwning", float(windows["frontCentersX"][0]), front_y,
                     float(awnings["sideWidth"]), float(awnings["sideDepth"]),
                     float(awnings["sideCenterZ"]), striped=False)
    add_south_awning(root, mats, "RightAwning", float(windows["frontCentersX"][1]), front_y,
                     float(awnings["sideWidth"]), float(awnings["sideDepth"]),
                     float(awnings["sideCenterZ"]), striped=False)

    east_x = bw / 2 + 0.065
    add_side_window_east(root, mats, "EastWindow", east_x, float(windows["sideCenterY"]),
                         float(windows["sideCenterZ"]), float(windows["sideWidth"]), float(windows["sideHeight"]))
    add_east_awning(root, mats, "EastAwning", east_x, float(windows["sideCenterY"]),
                    float(awnings["sideWidth"]), float(awnings["sideDepth"]), float(awnings["sideCenterZ"]))

    rear_y = bd / 2 + 0.065
    box("RearServiceDoor", (-1.80, rear_y, 1.15), (1.00, 0.15, 1.92), mats["frame"], root, 0.028)
    box("RearServiceDoorInset", (-1.80, rear_y + 0.09, 1.15), (0.76, 0.045, 1.55), mats["metal"], root, 0.012)
    box("RearUtilityPanel", (1.75, rear_y + 0.09, 1.22), (0.84, 0.05, 0.96), mats["metal"], root, 0.018)

    for index, lamp_x in enumerate((-2.72, 0.0, 2.72)):
        arch.add_wall_lamp(box=box, root=root, materials=mats, name=f"FrontLamp{index}",
                           x=lamp_x, y=front_y - 0.11, z=2.38,
                           frame_material="darkMetal", glow_material="glass")

    for index, spec in enumerate(recipe["roofEquipment"]["hvacUnits"]):
        add_hvac_unit(root, mats, index, spec, slab_z + slab_h / 2)
    vent = recipe["roofEquipment"]["roundVent"]
    vent_z = slab_z + slab_h / 2 + float(vent["height"]) / 2 + 0.04
    cylinder("RoundRoofVent", (float(vent["x"]), float(vent["y"]), vent_z),
             float(vent["radius"]), float(vent["height"]), mats["metal"], root, vertices=28, bevel=0.018)
    cylinder("RoundRoofVentCap", (float(vent["x"]), float(vent["y"]), vent_z + float(vent["height"]) / 2),
             float(vent["radius"]) * 1.16, 0.10, mats["trim"], root, vertices=28, bevel=0.018)

    for index, spec in enumerate(recipe["frontProps"]["produceCrates"]):
        add_produce_crate(root, mats, index, float(spec["x"]), float(spec["y"]), spec["kind"])
    for index, spec in enumerate(recipe["frontProps"]["planters"]):
        add_planter(root, mats, index, float(spec["x"]), float(spec["y"]))

    arch.add_foundation_courses(box=box, root=root, materials=mats,
                                width=fw, depth=fd, height=fh, courses=2, trim_material="wall")
    root["architectureVocabulary"] = json.dumps(arch.vocabulary_metadata([
        arch.ModuleUse("windows", "commercial_storefront_glazing", "high"),
        arch.ModuleUse("entrances", "double_glass_retail_entry", "high"),
        arch.ModuleUse("architectural_trim", "flat_parapet_commercial", "medium"),
        arch.ModuleUse("emissive_lighting", "warm_storefront_and_wall_lamps", "medium"),
        arch.ModuleUse("small_arch_props", "roof_hvac_and_produce_crates", "medium"),
    ]))


def save_blend(path):
    if not path:
        return
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


def build_context(args):
    recipe_path = repo_path(args.recipe)
    recipe = load_recipe(recipe_path)
    reference_path = repo_path(recipe["referenceDescriptor"])
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    reference["descriptorSha256"] = sha256(reference_path)
    studio = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "reference_descriptor.json").write_text(json.dumps(reference, indent=2), encoding="utf-8")

    bs.clear_scene()
    source_resolution = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, source_resolution, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    root = empty("AssetRoot")
    for key, value in {
        "assetId": ASSET_ID,
        "assetType": "commercial_building",
        "cameraContract": "CH_CAMERA_V1",
        "studioPreset": "CH_TYCOON_STUDIO_V1",
        "styleContract": "CH_STYLIZED_PRERENDER_V1",
        "artDirectionContract": recipe["styleContract"],
        "groundIncludedInAsset": False,
        "publicSidewalkIncluded": False,
        "runtimeRepresentation": "2D_RGBA_pre_rendered_sprite",
        "footprint": "3x2",
        "referenceDescriptor": recipe["referenceDescriptor"],
        "referenceSourceSha256": reference["sourceSha256"],
        "directionPolicy": "rotate_asset_root_keep_camera_lights_fixed",
        "qualityGateContract": "CH_SCENE_PREFLIGHT_V1",
    }.items():
        root[key] = value

    mats = make_materials(recipe)
    build_market(root, mats, recipe)
    receiver = studio["shadowReceiver"]
    receiver_mat = bs.make_material("ShadowReceiver", receiver["materialColor"], float(receiver.get("roughness", 1.0)))
    ground = bs.add_box("ShadowReceiverPlane", receiver["location"], receiver["dimensions"], receiver_mat, 0.0)
    authored = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj != ground]
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    return recipe_path, recipe, reference, studio, out, scene, root, ground, authored


def render_final(context):
    recipe_path, recipe, reference, studio, out, scene, root, ground, authored = context
    directions = []
    for direction in bs.DIRECTIONS:
        bs.set_direction(root, direction)
        bpy.context.view_layer.update()
        color_name = f"{ASSET_ID}_{direction['id']}_color_source.png"
        shadow_name = f"{ASSET_ID}_{direction['id']}_shadow_source.png"
        bs.render_color_pass(scene, authored, ground, str(out / color_name))
        origin = bs.ground_origin_source_px(scene)
        bs.render_shadow_pass(scene, authored, ground, str(out / shadow_name))
        directions.append({
            "id": direction["id"],
            "quarterTurns": direction["quarterTurns"],
            "rotationDegrees": direction["rotationDegrees"],
            "colorSource": color_name,
            "shadowSource": shadow_name,
            "groundOriginSourcePx": origin,
        })

    metadata = {
        "sourceObject": ASSET_ID,
        "assetType": "commercial_building",
        "sourceContract": "DIRECT_CH_BLENDER_GUARDED_V1",
        "assetConfig": recipe_path.relative_to(ROOT).as_posix(),
        "builder": "tools/tycoon_photo_studio/build_commercial_mini_market_guarded.py",
        "reference": {"descriptor": recipe["referenceDescriptor"], "sourceSha256": reference["sourceSha256"], "usage": reference["usage"]},
        "studioPreset": studio["id"],
        "styleContract": "CH_STYLIZED_PRERENDER_V1",
        "artDirectionContract": recipe["styleContract"],
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
        "directionOrder": [d["id"] for d in bs.DIRECTIONS],
        "sourceSummary": {
            "groundIncludedInAsset": False,
            "publicSidewalkIncluded": False,
            "brandTextIncluded": False,
            "warmStorefrontRead": True,
            "rooftopMechanicalRead": True,
            "referenceUsedAsArtDirectionOnly": True,
        },
        "directions": directions,
    }
    (out / "studio_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    context = build_context(args)
    recipe_path, recipe, reference, studio, out, scene, root, ground, authored = context
    report = scene_gate.run_preflight(
        scene=scene, authored=authored, footprint=recipe["footprint"], profile=profile,
        asset_id=ASSET_ID, report_path=out / "preflight_report.json",
    )
    scene_gate.require_pass(report)

    if args.stage == "preflight":
        save_blend(args.save_blend)
        print("[CH_GATE] mini market preflight PASS")
        return
    if args.stage == "proxy":
        bs.set_direction(root, bs.DIRECTIONS[0])
        bpy.context.view_layer.update()
        proxy = scene_gate.render_proxy(
            scene=scene, authored=authored, output_path=out / "proxy_south.png",
            profile=profile, asset_id=ASSET_ID, direction="south",
        )
        (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        save_blend(args.save_blend)
        print(f"[CH_GATE] mini market SOUTH proxy ready: {proxy['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower().strip()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError("CH_FINAL_REQUIRES_APPROVED_PROXY: review proxy_south.png first")
    (out / "proxy_approval.json").write_text(
        json.dumps({"contract": "CH_PROXY_APPROVAL_V1", "assetId": ASSET_ID, "proxySha256": approval, "reviewed": True}, indent=2),
        encoding="utf-8",
    )
    render_final(context)
    save_blend(args.save_blend)
    print("[CH_GATE] mini market final four-direction source bake complete")


if __name__ == "__main__":
    main()
