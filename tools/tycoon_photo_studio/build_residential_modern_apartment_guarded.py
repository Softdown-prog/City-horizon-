"""Guarded CH Blender authoring for residential_modern_apartment_4x4_01.

The SOUTH view follows the user supplied modern apartment reference closely while
respecting City Horizon runtime separation: public sidewalk, curb, bench and large
street trees are deliberately excluded from the authored building asset.

Quality path: preflight -> SOUTH proxy -> explicit human approval -> final 4 views.
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
for p in (HERE, CH_BLENDER):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402

ASSET_ID = "residential_modern_apartment_4x4_01"
DEFAULT_RECIPE = "tools/tycoon_photo_studio/assets/residential_modern_apartment_4x4_01.apartment.json"


def args_parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", default=DEFAULT_RECIPE)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    p.add_argument("--preflight-profile", default=None)
    p.add_argument("--approval-proxy-sha", default=None)
    p.add_argument("--save-blend", default=None)
    return p.parse_args(argv)


def repo_path(value):
    p = (ROOT / value).resolve()
    p.relative_to(ROOT)
    return p


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def empty(name, parent=None):
    o = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(o)
    o.rotation_mode = "XYZ"
    o.parent = parent
    return o


def box(name, loc, dims, mat, parent, bevel=0.035):
    o = bs.add_box(name, loc, dims, mat, bevel)
    o.parent = parent
    return o


def sphere(name, loc, radius, mat, parent, scale=(1, 1, 1), seg=16, rings=8):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=radius, location=loc)
    o = bpy.context.object
    o.name = name
    o.parent = parent
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    return o


def cylinder(name, loc, radius, depth, mat, parent, vertices=24, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rotation)
    o = bpy.context.object
    o.name = name
    o.parent = parent
    o.data.materials.append(mat)
    bevel = o.modifiers.new("EdgeSoftening", "BEVEL")
    bevel.width = min(0.025, radius * 0.08)
    bevel.segments = 2
    return o


def make_materials(recipe):
    out = {}
    for key, spec in recipe["materials"].items():
        out[key] = bs.make_material(
            spec["name"],
            spec["rgba"],
            float(spec.get("roughness", 0.78)),
            float(spec.get("metallic", 0.0)),
            recipe=spec.get("recipe", "solid"),
            seed=int(spec.get("seed", 0)),
            strength=float(spec.get("strength", 0.04)),
        )
        mat = out[key]
        if key == "glass" and mat.use_nodes:
            node = mat.node_tree.nodes.get("Principled BSDF")
            if node:
                emission_key = "Emission Color" if "Emission Color" in node.inputs else "Emission"
                if emission_key in node.inputs:
                    node.inputs[emission_key].default_value = tuple(spec["rgba"])
                if "Emission Strength" in node.inputs:
                    node.inputs["Emission Strength"].default_value = float(spec.get("emission", 0.72))
        if key == "railGlass":
            mat.diffuse_color = tuple(spec["rgba"])
            if mat.use_nodes:
                node = mat.node_tree.nodes.get("Principled BSDF")
                if node:
                    if "Alpha" in node.inputs:
                        node.inputs["Alpha"].default_value = float(spec["rgba"][3])
                    if "Transmission Weight" in node.inputs:
                        node.inputs["Transmission Weight"].default_value = 0.22
    return out


def window_front(root, mats, name, x, y, z, width=0.92, height=1.18, mullion=True):
    box(name + "Frame", (x, y, z), (width + 0.16, 0.13, height + 0.16), mats["frame"], root, 0.018)
    box(name + "Glass", (x, y - 0.078, z), (width, 0.035, height), mats["glass"], root, 0.008)
    if mullion:
        box(name + "V", (x, y - 0.100, z), (0.052, 0.035, height), mats["frame"], root, 0.006)
        box(name + "H", (x, y - 0.100, z), (width, 0.035, 0.048), mats["frame"], root, 0.006)


def window_east(root, mats, name, x, y, z, width=0.90, height=1.18, mullion=True):
    box(name + "Frame", (x, y, z), (0.13, width + 0.16, height + 0.16), mats["frame"], root, 0.018)
    box(name + "Glass", (x + 0.078, y, z), (0.035, width, height), mats["glass"], root, 0.008)
    if mullion:
        box(name + "V", (x + 0.100, y, z), (0.035, 0.052, height), mats["frame"], root, 0.006)
        box(name + "H", (x + 0.100, y, z), (0.035, width, 0.048), mats["frame"], root, 0.006)


def plant(root, mats, name, x, y, z, scale=1.0):
    cylinder(name + "Pot", (x, y, z + 0.16 * scale), 0.18 * scale, 0.32 * scale, mats["pot"], root, 16)
    for i, (dx, dy, dz, s) in enumerate((
        (-0.10, 0.00, 0.39, 0.20),
        (0.09, 0.03, 0.43, 0.22),
        (0.00, -0.08, 0.51, 0.21),
        (0.04, 0.08, 0.58, 0.18),
    )):
        sphere(name + f"Leaf{i}", (x + dx * scale, y + dy * scale, z + dz * scale), s * scale,
               mats["greenLight" if i % 2 else "green"], root, (0.75, 0.55, 1.25), 12, 6)


def add_front_balcony(root, mats, name, center_x, front_y, slab_z, width, depth=1.05):
    slab_y = front_y - depth * 0.48
    box(name + "Slab", (center_x, slab_y, slab_z), (width, depth, 0.16), mats["charcoalMid"], root, 0.035)
    rail_z = slab_z + 0.61
    front_edge = slab_y - depth / 2 + 0.03
    box(name + "RailTop", (center_x, front_edge, rail_z + 0.48), (width, 0.07, 0.07), mats["darkMetal"], root, 0.010)
    box(name + "RailBottom", (center_x, front_edge, rail_z - 0.45), (width, 0.06, 0.06), mats["darkMetal"], root, 0.008)
    glass_w = width - 0.20
    box(name + "RailGlass", (center_x, front_edge + 0.018, rail_z), (glass_w, 0.030, 0.86), mats["railGlass"], root, 0.006)
    for px in (center_x - width / 2 + 0.08, center_x, center_x + width / 2 - 0.08):
        box(name + f"Post{px:.2f}", (px, front_edge - 0.010, rail_z), (0.055, 0.055, 0.98), mats["darkMetal"], root, 0.008)
    side_y = slab_y
    for side, sx in (("L", center_x - width / 2 + 0.03), ("R", center_x + width / 2 - 0.03)):
        box(name + side + "SideGlass", (sx, side_y, rail_z), (0.030, depth - 0.12, 0.86), mats["railGlass"], root, 0.006)
        box(name + side + "SideTop", (sx, side_y, rail_z + 0.48), (0.055, depth, 0.055), mats["darkMetal"], root, 0.008)
    return slab_y


def add_east_balcony(root, mats, name, east_x, center_y, slab_z, width=1.0, depth=2.0):
    slab_x = east_x + width * 0.46
    box(name + "Slab", (slab_x, center_y, slab_z), (width, depth, 0.15), mats["charcoalMid"], root, 0.030)
    rail_z = slab_z + 0.60
    edge_x = slab_x + width / 2 - 0.03
    box(name + "RailGlass", (edge_x, center_y, rail_z), (0.030, depth - 0.16, 0.84), mats["railGlass"], root, 0.006)
    box(name + "RailTop", (edge_x, center_y, rail_z + 0.47), (0.055, depth, 0.055), mats["darkMetal"], root, 0.008)
    for py in (center_y - depth / 2 + 0.08, center_y, center_y + depth / 2 - 0.08):
        box(name + f"Post{py:.2f}", (edge_x, py, rail_z), (0.055, 0.055, 0.95), mats["darkMetal"], root, 0.008)


def add_rooftop_hvac(root, mats, z):
    # Access / elevator headhouse.
    box("RoofHeadHouse", (0.75, 0.80, z + 0.82), (2.20, 2.10, 1.64), mats["cream"], root, 0.035)
    box("RoofHeadHouseCap", (0.75, 0.80, z + 1.68), (2.38, 2.28, 0.16), mats["charcoal"], root, 0.025)
    box("RoofDoor", (0.75, -0.285, z + 0.72), (0.62, 0.055, 1.15), mats["charcoal"], root, 0.012)

    # Main condenser with top fan and side grille.
    hx, hy = (2.55, -0.15)
    box("HVACMainBody", (hx, hy, z + 0.48), (1.30, 1.15, 0.82), mats["metal"], root, 0.045)
    box("HVACMainTop", (hx, hy, z + 0.92), (1.36, 1.20, 0.08), mats["darkMetal"], root, 0.020)
    cylinder("HVACFanRing", (hx, hy, z + 0.975), 0.40, 0.055, mats["darkMetal"], root, 28)
    cylinder("HVACFanHub", (hx, hy, z + 1.015), 0.10, 0.045, mats["metal"], root, 20)
    for i in range(8):
        a = i * math.pi / 4
        box(f"HVACFanBlade{i}", (hx + math.cos(a) * 0.19, hy + math.sin(a) * 0.19, z + 1.02),
            (0.26, 0.055, 0.025), mats["metal"], root, 0.004).rotation_euler[2] = a
    for i in range(6):
        box(f"HVACGrille{i}", (hx + 0.665, hy - 0.42 + i * 0.16, z + 0.49),
            (0.035, 0.09, 0.60), mats["darkMetal"], root, 0.004)

    # Secondary duct/utility box beside the condenser.
    box("HVACSecondary", (1.62, -0.05, z + 0.35), (0.55, 0.80, 0.58), mats["metal"], root, 0.025)
    box("HVACDuct", (1.35, 0.28, z + 0.35), (0.60, 0.30, 0.34), mats["metal"], root, 0.020)

    # Roof vents visible in reference.
    for i, (x, y, h) in enumerate(((-2.1, 0.6, 0.42), (-0.9, -0.8, 0.26), (3.05, 0.95, 0.24), (-2.9, -0.45, 0.22))):
        box(f"RoofVentBase{i}", (x, y, z + h * 0.40), (0.38, 0.38, h * 0.70), mats["metal"], root, 0.015)
        box(f"RoofVentCap{i}", (x, y, z + h * 0.82), (0.48, 0.48, 0.09), mats["creamLight"], root, 0.012)


def build_apartment(root, mats, recipe):
    d = recipe["dimensions"]
    bw = float(d["bodyWidth"])
    bd = float(d["bodyDepth"])
    fh = float(d["foundationHeight"])
    floor_h = float(d["floorHeight"])
    floors = int(d["floors"])
    body_h = floor_h * floors
    front = -bd / 2
    east = bw / 2

    foundation = box("BuildingFoundation", (0, 0, fh / 2), (bw + 0.30, bd + 0.30, fh), mats["concrete"], root, 0.055)
    scene_gate.tag(foundation, "building.foundation", ground_contact=True)
    box("ApartmentMainMass", (0, 0, fh + body_h / 2), (bw, bd, body_h), mats["cream"], root, 0.055)

    # Strong facade composition from reference: charcoal center spine + cream side piers + timber accent on east face.
    box("FrontCharcoalSpine", (-0.55, front - 0.058, fh + body_h / 2), (2.05, 0.11, body_h - 0.22), mats["charcoalMid"], root, 0.016)
    box("FrontLeftCreamPier", (-3.02, front - 0.070, fh + body_h / 2), (1.25, 0.13, body_h - 0.18), mats["creamLight"], root, 0.016)
    box("FrontRightCreamPier", (2.86, front - 0.070, fh + body_h / 2), (1.35, 0.13, body_h - 0.18), mats["creamLight"], root, 0.016)
    box("EastTimberPanel", (east + 0.065, 0.65, fh + body_h / 2), (0.12, 2.20, body_h - 0.30), mats["wood"], root, 0.014)

    # Horizontal facade joints/bands to make floor rhythm legible.
    for level in range(1, floors):
        z = fh + level * floor_h
        box(f"FrontFloorBand{level}", (0, front - 0.095, z), (bw - 0.20, 0.08, 0.12), mats["charcoalMid"], root, 0.010)
        box(f"EastFloorBand{level}", (east + 0.095, 0, z), (0.08, bd - 0.20, 0.12), mats["charcoalMid"], root, 0.010)

    # Windows, balcony doors and repeated stacked rhythm across five storeys.
    for floor in range(floors):
        z = fh + floor * floor_h + 1.08
        # Central charcoal bay: two warm windows.
        window_front(root, mats, f"CenterWindowL{floor}", -0.98, front - 0.095, z, 0.68, 1.16)
        window_front(root, mats, f"CenterWindowR{floor}", -0.15, front - 0.095, z, 0.68, 1.16)
        # Left apartment glazing.
        window_front(root, mats, f"LeftWindow{floor}", -2.72, front - 0.095, z, 0.88, 1.22)
        # Right apartment glazing and balcony door pairing.
        window_front(root, mats, f"RightDoor{floor}", 1.70, front - 0.095, z, 0.84, 1.28)
        window_front(root, mats, f"RightWindow{floor}", 2.63, front - 0.095, z, 0.70, 1.20)
        # East facade windows behind side balconies.
        window_east(root, mats, f"EastFrontWindow{floor}", east + 0.095, -1.80, z, 0.78, 1.22)
        window_east(root, mats, f"EastRearWindow{floor}", east + 0.095, 2.05, z, 0.82, 1.18)

    # Ground-floor main entrance/canopy, with only private stoop/steps (no public pavement).
    entry_x = 0.50
    door_z = fh + 1.08
    box("EntryTimberSurround", (entry_x, front - 0.115, door_z), (1.72, 0.16, 1.95), mats["wood"], root, 0.022)
    box("EntryFrame", (entry_x, front - 0.205, door_z), (1.18, 0.09, 1.62), mats["frame"], root, 0.014)
    box("EntryGlassL", (entry_x - 0.30, front - 0.258, door_z), (0.49, 0.030, 1.48), mats["glass"], root, 0.005)
    box("EntryGlassR", (entry_x + 0.30, front - 0.258, door_z), (0.49, 0.030, 1.48), mats["glass"], root, 0.005)
    box("EntryDivider", (entry_x, front - 0.275, door_z), (0.055, 0.035, 1.54), mats["frame"], root, 0.005)
    door = box("MainEntranceDoor", (entry_x, front - 0.260, door_z), (1.08, 0.035, 1.52), mats["glass"], root, 0.005)
    scene_gate.tag(door, "building.entrance")
    box("EntranceCanopy", (entry_x, front - 0.58, fh + 2.13), (2.12, 1.06, 0.20), mats["charcoal"], root, 0.035)
    step1 = box("PrivateEntryStep1", (entry_x, front - 0.53, 0.11), (1.65, 0.78, 0.20), mats["concrete"], root, 0.025)
    scene_gate.tag(step1, "building.entry_step", ground_contact=True)
    box("PrivateEntryStep2", (entry_x, front - 0.83, 0.055), (1.92, 0.42, 0.11), mats["concrete"], root, 0.020)

    # Four upper levels of front balconies, matching the reference's paired stacks.
    for level in range(1, floors):
        slab_z = fh + level * floor_h + 0.08
        left_y = add_front_balcony(root, mats, f"LeftBalcony{level}", -2.64, front, slab_z, 2.35, 1.06)
        right_y = add_front_balcony(root, mats, f"RightBalcony{level}", 2.03, front, slab_z, 2.60, 1.10)
        plant(root, mats, f"LBPlant{level}A", -3.34, left_y - 0.05, slab_z + 0.10, 0.72)
        plant(root, mats, f"LBPlant{level}B", -2.10, left_y + 0.02, slab_z + 0.10, 0.66)
        plant(root, mats, f"RBPlant{level}A", 1.28, right_y + 0.03, slab_z + 0.10, 0.72)
        plant(root, mats, f"RBPlant{level}B", 2.78, right_y + 0.02, slab_z + 0.10, 0.68)
        # One simple lounge-chair silhouette on the upper-right balcony, visible but subordinate.
        if level == 3:
            box("BalconyChairSeat", (2.12, right_y - 0.04, slab_z + 0.33), (0.58, 0.52, 0.12), mats["wood"], root, 0.025)
            chair_back = box("BalconyChairBack", (2.32, right_y + 0.18, slab_z + 0.68), (0.12, 0.52, 0.70), mats["wood"], root, 0.020)
            chair_back.rotation_euler[1] = math.radians(-12)

    # Side balconies on east facade as visible in the reference rotation.
    for level in range(1, floors):
        slab_z = fh + level * floor_h + 0.08
        add_east_balcony(root, mats, f"EastBalcony{level}", east, -0.95, slab_z, 0.98, 1.72)
        plant(root, mats, f"EastPlant{level}", east + 0.40, -0.95, slab_z + 0.10, 0.58)

    # Compact private foundation landscaping only; no street trees, benches or sidewalks.
    for i, (x, y, s) in enumerate(((-3.50, front - 0.22, 0.62), (-1.75, front - 0.20, 0.55), (3.45, front - 0.18, 0.60))):
        sphere(f"FoundationShrub{i}", (x, y, 0.38 * s + 0.10), 0.44 * s, mats["greenLight" if i == 1 else "green"], root, (1.35, 0.80, 0.90), 14, 7)

    # Flat roof membrane and continuous raised parapet.
    roof_z = fh + body_h
    box("RoofMembrane", (0, 0, roof_z + 0.055), (bw - 0.22, bd - 0.22, 0.11), mats["roof"], root, 0.018)
    ph = float(d["parapetHeight"])
    pz = roof_z + ph / 2
    box("ParapetSouth", (0, front + 0.08, pz), (bw, 0.24, ph), mats["charcoal"], root, 0.020)
    box("ParapetNorth", (0, bd / 2 - 0.08, pz), (bw, 0.24, ph), mats["charcoal"], root, 0.020)
    box("ParapetEast", (east - 0.08, 0, pz), (0.24, bd, ph), mats["charcoal"], root, 0.020)
    box("ParapetWest", (-east + 0.08, 0, pz), (0.24, bd, ph), mats["charcoal"], root, 0.020)
    add_rooftop_hvac(root, mats, roof_z + 0.10)


def load_recipe(path):
    recipe = json.loads(Path(path).read_text(encoding="utf-8"))
    if recipe.get("contract") != "CITY_HORIZON_APARTMENT_V1" or recipe.get("assetId") != ASSET_ID:
        raise RuntimeError("CH_APARTMENT_RECIPE_CONTRACT")
    if recipe.get("footprint") != {"widthTiles": 4, "depthTiles": 4}:
        raise RuntimeError("CH_APARTMENT_FOOTPRINT: asset must remain 4x4")
    return recipe


def save_blend(path):
    if path:
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(p))


def build_context(a):
    recipe_path = repo_path(a.recipe)
    recipe = load_recipe(recipe_path)
    studio = bs.load_json(a.studio_preset)
    out = Path(a.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    src = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, src, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    root = empty("AssetRoot")
    metadata = {
        "assetId": ASSET_ID,
        "assetType": "building",
        "cameraContract": "CH_CAMERA_V1",
        "studioPreset": "CH_TYCOON_STUDIO_V1",
        "styleContract": "CH_STYLIZED_PRERENDER_V1",
        "artDirectionContract": recipe["styleContract"],
        "groundIncludedInAsset": False,
        "publicSidewalkIncluded": False,
        "publicCurbIncluded": False,
        "streetFurnitureIncluded": False,
        "largeStreetTreeIncluded": False,
        "runtimeRepresentation": "2D_RGBA_pre_rendered_sprite",
        "footprint": "4x4",
        "directionPolicy": "rotate_asset_root_keep_camera_lights_fixed",
        "qualityGateContract": "CH_SCENE_PREFLIGHT_V1",
    }
    for key, value in metadata.items():
        root[key] = value

    mats = make_materials(recipe)
    build_apartment(root, mats, recipe)

    rec = studio["shadowReceiver"]
    ground_mat = bs.make_material("ShadowReceiver", rec["materialColor"], float(rec.get("roughness", 1.0)))
    ground = bs.add_box("ShadowReceiverPlane", rec["location"], rec["dimensions"], ground_mat, 0)
    authored = [o for o in bpy.context.scene.objects if o.type == "MESH" and o != ground]
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.12)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    return recipe_path, recipe, studio, out, scene, root, ground, authored


def render_final(ctx):
    recipe_path, recipe, studio, out, scene, root, ground, authored = ctx
    directions = []
    for direction in bs.DIRECTIONS:
        bs.set_direction(root, direction)
        bpy.context.view_layer.update()
        color = f"{ASSET_ID}_{direction['id']}_color_source.png"
        shadow = f"{ASSET_ID}_{direction['id']}_shadow_source.png"
        bs.render_color_pass(scene, authored, ground, str(out / color))
        origin = bs.ground_origin_source_px(scene)
        bs.render_shadow_pass(scene, authored, ground, str(out / shadow))
        directions.append({
            "id": direction["id"],
            "quarterTurns": direction["quarterTurns"],
            "rotationDegrees": direction["rotationDegrees"],
            "colorSource": color,
            "shadowSource": shadow,
            "groundOriginSourcePx": origin,
        })
    meta = {
        "sourceObject": ASSET_ID,
        "assetType": "building",
        "sourceContract": "DIRECT_CH_BLENDER_GUARDED_V1",
        "assetConfig": recipe_path.relative_to(ROOT).as_posix(),
        "builder": "tools/tycoon_photo_studio/build_residential_modern_apartment_guarded.py",
        "studioPreset": studio["id"],
        "styleContract": "CH_STYLIZED_PRERENDER_V1",
        "artDirectionContract": recipe["styleContract"],
        "cameraContract": "CH_CAMERA_V1",
        "gridContract": "CH_GRID_V1",
        "projection": "orthographic_dimetric_2_to_1",
        "yawDegrees": 45,
        "elevationDegrees": 30,
        "tileWidth": 128,
        "tileHeight": 64,
        "footprint": recipe["footprint"],
        "blenderVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "directionOrder": [d["id"] for d in bs.DIRECTIONS],
        "sourceSummary": {
            "groundIncludedInAsset": False,
            "publicSidewalkIncluded": False,
            "publicCurbIncluded": False,
            "streetBenchIncluded": False,
            "largeStreetTreeIncluded": False,
            "privateEntryStepsIncluded": True,
            "compactPrivatePlantersIncluded": True,
            "stackedGlassBalconies": True,
            "warmWindowRead": True,
            "rooftopHVAC": True,
        },
        "directions": directions,
    }
    (out / "studio_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main():
    a = args_parse()
    profile = scene_gate.load_profile(a.preflight_profile)
    ctx = build_context(a)
    recipe_path, recipe, studio, out, scene, root, ground, authored = ctx
    report = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=recipe["footprint"],
        profile=profile,
        asset_id=ASSET_ID,
        report_path=out / "preflight_report.json",
    )
    scene_gate.require_pass(report)

    if a.stage == "preflight":
        save_blend(a.save_blend)
        print("[CH_GATE] modern apartment preflight PASS")
        return

    if a.stage == "proxy":
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
        save_blend(a.save_blend)
        print(f"[CH_GATE] SOUTH proxy ready: {proxy['sha256']}")
        return

    approval = (a.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError("CH_FINAL_REQUIRES_APPROVED_PROXY: review proxy_south.png first")
    (out / "proxy_approval.json").write_text(json.dumps({
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": ASSET_ID,
        "proxySha256": approval,
        "reviewed": True,
    }, indent=2), encoding="utf-8")
    render_final(ctx)
    save_blend(a.save_blend)
    print("[CH_GATE] final four-direction source bake complete")


if __name__ == "__main__":
    main()
