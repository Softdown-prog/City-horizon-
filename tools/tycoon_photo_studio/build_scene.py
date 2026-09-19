"""Generic City Horizon Tycoon Asset Baker source render stage.

Loads one asset source JSON and one frozen studio preset JSON, builds the scene,
then bakes four rotations with a fixed camera and fixed world lighting.

New in this revision
--------------------
GAP 1 — blend_import part type:
    A part with ``"type": "blend_import"`` appends a Collection from an
    external .blend file (FBX/GLB also supported via ``"type": "fbx_import"``
    or ``"type": "glb_import"``).  The AssetRoot remains the rotation pivot.

GAP 2 — Dynamic render resolution:
    ``sourceResolution`` and ``finalResolution`` are now computed automatically
    from the asset footprint and building height.  Values in the studio preset
    act as *minimum* limits.  Pass ``--source-resolution WxH`` or
    ``--final-resolution WxH`` to override explicitly.

GAP 3 — Auto-fit orthoScale:
    After the scene is built, the camera's ortho_scale is calibrated so that
    all geometry fits inside the frame with a configurable safety margin
    (default 12 %).  This prevents large multi-tile assets from being cropped.
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

DIRECTIONS = (
    {"id": "south", "quarterTurns": 0, "rotationDegrees": 0.0},
    {"id": "east", "quarterTurns": 1, "rotationDegrees": 90.0},
    {"id": "west", "quarterTurns": 3, "rotationDegrees": 270.0},
    {"id": "north", "quarterTurns": 2, "rotationDegrees": 180.0},
)

# Canonical scale: number of Blender world-units per isometric tile.
# One tile = 128 × 64 px at 1.0 zoom.  Calibrate new assets against this.
BLENDER_UNITS_PER_TILE = 3.0

# Pixel dimensions of one isometric tile at the base game resolution.
TILE_PX_W = 128
TILE_PX_H = 64


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--asset-config", required=True)
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument(
        "--source-resolution",
        default=None,
        metavar="WxH",
        help="Override source resolution, e.g. 2048x2048",
    )
    parser.add_argument(
        "--final-resolution",
        default=None,
        metavar="WxH",
        help="Override final (gameplay) resolution, e.g. 512x384",
    )
    parser.add_argument(
        "--ortho-safety",
        type=float,
        default=0.12,
        metavar="F",
        help="Safety margin for auto-fit orthoScale (fraction, default 0.12 = 12%%)",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_resolution(spec):
    """Parse 'WxH' string into (int, int) tuple."""
    w, h = spec.lower().split("x")
    return int(w), int(h)


# ---------------------------------------------------------------------------
# Scene setup helpers
# ---------------------------------------------------------------------------


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def make_material(name, rgba, roughness=0.72, metallic=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = tuple(rgba)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def add_box(name, location, dimensions, material, bevel=0.035):
    bpy.ops.mesh.primitive_cube_add(location=tuple(location))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = tuple(dimensions)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel > 0:
        modifier = obj.modifiers.new(name="ProductionBevel", type="BEVEL")
        modifier.width = bevel
        modifier.segments = 2
    return obj


def add_pyramid_roof(part, material):
    bpy.ops.mesh.primitive_cone_add(
        vertices=4,
        radius1=float(part["radius"]),
        radius2=0.0,
        depth=float(part["depth"]),
        location=tuple(part["location"]),
        rotation=(0.0, 0.0, math.radians(float(part.get("rotationDegrees", 45.0)))),
    )
    obj = bpy.context.object
    obj.name = part["name"]
    obj.data.materials.append(material)
    bevel_width = float(part.get("bevel", 0.025))
    if bevel_width > 0:
        bevel = obj.modifiers.new(name="RoofEdgeSoftening", type="BEVEL")
        bevel.width = bevel_width
        bevel.segments = 2
    return obj


def add_uv_sphere(part, material):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=int(part.get("segments", 24)),
        ring_count=int(part.get("rings", 12)),
        radius=float(part["radius"]),
        location=tuple(part["location"]),
    )
    obj = bpy.context.object
    obj.name = part["name"]
    obj.data.materials.append(material)
    return obj


# ---------------------------------------------------------------------------
# GAP 1 — blend_import / fbx_import / glb_import part types
# ---------------------------------------------------------------------------


def _resolve_asset_path(path_spec, asset_config_path):
    """Resolve a path that may be relative to the asset config file."""
    p = Path(path_spec)
    if p.is_absolute():
        return p
    # Try relative to the asset config directory first
    candidate = Path(asset_config_path).parent / p
    if candidate.is_file():
        return candidate
    # Try relative to the repo root (two levels up from tools/tycoon_photo_studio/)
    repo_root = Path(asset_config_path).parents[3]
    candidate2 = repo_root / p
    if candidate2.is_file():
        return candidate2
    raise FileNotFoundError(
        f"Asset file not found: '{path_spec}'. "
        f"Searched relative to '{Path(asset_config_path).parent}' and '{repo_root}'."
    )


def import_blend_collection(part, asset_config_path):
    """Append a Collection from an external .blend file.

    Part spec keys
    --------------
    blendFile   : path to the .blend file (relative to asset config or absolute)
    collection  : name of the Collection to append (optional; appends all if omitted)
    location    : [x, y, z] offset applied to every imported object (default [0,0,0])
    scale       : uniform scale multiplier (default 1.0)
    materialMap : dict mapping original material names → asset material keys (optional)
    """
    blend_path = _resolve_asset_path(part["blendFile"], asset_config_path)
    collection_name = part.get("collection")
    offset = part.get("location", [0.0, 0.0, 0.0])
    scale_factor = float(part.get("scale", 1.0))

    print(f"[blend_import] Loading '{blend_path}' collection='{collection_name}'")

    with bpy.data.libraries.load(str(blend_path), link=False) as (data_from, data_to):
        if collection_name:
            if collection_name not in data_from.collections:
                raise RuntimeError(
                    f"Collection '{collection_name}' not in '{blend_path.name}'. "
                    f"Available: {list(data_from.collections)}"
                )
            data_to.collections = [collection_name]
        else:
            data_to.collections = list(data_from.collections)

    imported_objects = []
    for col in data_to.collections:
        if col is None:
            continue
        # Link the collection into the active scene collection
        if col.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(col)
        for obj in col.all_objects:
            if obj.type == "MESH":
                # Apply offset and scale
                obj.location.x += offset[0]
                obj.location.y += offset[1]
                obj.location.z += offset[2]
                if scale_factor != 1.0:
                    obj.scale = (
                        obj.scale.x * scale_factor,
                        obj.scale.y * scale_factor,
                        obj.scale.z * scale_factor,
                    )
                    bpy.ops.object.select_all(action="DESELECT")
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.transform_apply(
                        location=False, rotation=False, scale=True
                    )
                imported_objects.append(obj)

    if not imported_objects:
        raise RuntimeError(
            f"No MESH objects found in collection from '{blend_path.name}'."
        )

    print(
        f"[blend_import] Imported {len(imported_objects)} mesh object(s) "
        f"from '{blend_path.name}'"
    )
    return imported_objects


def import_fbx(part, asset_config_path):
    """Import an FBX file and return its mesh objects."""
    fbx_path = _resolve_asset_path(part["fbxFile"], asset_config_path)
    offset = part.get("location", [0.0, 0.0, 0.0])
    scale_factor = float(part.get("scale", 1.0))

    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(
        filepath=str(fbx_path),
        global_scale=scale_factor,
    )
    new_names = set(bpy.data.objects.keys()) - before
    imported = [bpy.data.objects[n] for n in new_names if bpy.data.objects[n].type == "MESH"]

    for obj in imported:
        obj.location.x += offset[0]
        obj.location.y += offset[1]
        obj.location.z += offset[2]

    print(f"[fbx_import] Imported {len(imported)} mesh object(s) from '{fbx_path.name}'")
    return imported


def import_glb(part, asset_config_path):
    """Import a GLB/GLTF file and return its mesh objects."""
    glb_path = _resolve_asset_path(part["glbFile"], asset_config_path)
    offset = part.get("location", [0.0, 0.0, 0.0])

    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.gltf(filepath=str(glb_path))
    new_names = set(bpy.data.objects.keys()) - before
    imported = [bpy.data.objects[n] for n in new_names if bpy.data.objects[n].type == "MESH"]

    for obj in imported:
        obj.location.x += offset[0]
        obj.location.y += offset[1]
        obj.location.z += offset[2]

    scale_factor = float(part.get("scale", 1.0))
    if scale_factor != 1.0:
        for obj in imported:
            obj.scale = (scale_factor, scale_factor, scale_factor)
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    print(f"[glb_import] Imported {len(imported)} mesh object(s) from '{glb_path.name}'")
    return imported


# ---------------------------------------------------------------------------
# Scene builder
# ---------------------------------------------------------------------------


def build_asset(asset, asset_config_path=""):
    if asset.get("contract") != "TYCOON_ASSET_SOURCE_V1":
        raise RuntimeError("Asset source must use TYCOON_ASSET_SOURCE_V1")

    materials = {}
    for key, spec in asset.get("materials", {}).items():
        materials[key] = make_material(
            spec.get("name", key),
            spec["rgba"],
            float(spec.get("roughness", 0.72)),
            float(spec.get("metallic", 0.0)),
        )

    authored = []
    for part in asset.get("parts", []):
        kind = part.get("type")

        # ── Declarative geometry ──────────────────────────────────────
        if kind in ("box", "pyramid_roof", "uv_sphere"):
            material_key = part.get("material")
            if material_key not in materials:
                raise RuntimeError(
                    f"Unknown material '{material_key}' for part '{part.get('name')}'"
                )
            material = materials[material_key]
            if kind == "box":
                obj = add_box(
                    part["name"], part["location"], part["dimensions"], material,
                    float(part.get("bevel", 0.035)),
                )
            elif kind == "pyramid_roof":
                obj = add_pyramid_roof(part, material)
            elif kind == "uv_sphere":
                obj = add_uv_sphere(part, material)
            authored.append(obj)

        # ── GAP 1: External mesh import ───────────────────────────────
        elif kind == "blend_import":
            objs = import_blend_collection(part, asset_config_path)
            authored.extend(objs)

        elif kind == "fbx_import":
            objs = import_fbx(part, asset_config_path)
            authored.extend(objs)

        elif kind == "glb_import":
            objs = import_glb(part, asset_config_path)
            authored.extend(objs)

        else:
            raise RuntimeError(
                f"Unsupported part type: '{kind}'. "
                f"Supported: box, pyramid_roof, uv_sphere, blend_import, fbx_import, glb_import"
            )

    if not authored:
        raise RuntimeError("Asset source did not create any renderable parts")
    return authored


# ---------------------------------------------------------------------------
# GAP 3 — Auto-fit orthoScale
# ---------------------------------------------------------------------------


def calibrate_ortho_scale(scene, authored, safety_margin=0.12):
    """Fit the orthographic camera scale so all authored geometry is visible.

    Samples every bounding-box corner of every MESH object, projects into
    camera local space, and sets ortho_scale = max_extent × (1 + safety_margin).

    This must be called *after* build_asset() and before rendering.
    The camera's ``target`` (pan) is not changed — the pivot remains at
    the world origin so the ground-origin source pixel stays correct.

    Returns the new ortho_scale value.
    """
    cam = scene.camera
    if cam is None:
        return None

    cam_mat_inv = cam.matrix_world.inverted()
    max_half_x = 0.0
    max_half_y = 0.0

    # Sample all 4 rotations to find the worst-case envelope
    root_obj = bpy.data.objects.get("AssetRoot")
    original_z = root_obj.rotation_euler[2] if root_obj else 0.0

    for direction in DIRECTIONS:
        if root_obj:
            root_obj.rotation_euler[2] = math.radians(direction["rotationDegrees"])
            bpy.context.view_layer.update()

        for obj in authored:
            if obj.type != "MESH":
                continue
            for corner in obj.bound_box:
                world_pt = obj.matrix_world @ Vector(corner)
                cam_pt = cam_mat_inv @ world_pt
                max_half_x = max(max_half_x, abs(cam_pt.x))
                max_half_y = max(max_half_y, abs(cam_pt.y))

    # Restore original rotation
    if root_obj:
        root_obj.rotation_euler[2] = original_z
        bpy.context.view_layer.update()

    if max_half_x == 0.0 and max_half_y == 0.0:
        return cam.data.ortho_scale

    aspect = scene.render.resolution_x / max(1, scene.render.resolution_y)
    needed_from_x = (max_half_x * 2.0) / aspect
    needed_from_y = max_half_y * 2.0
    needed = max(needed_from_x, needed_from_y)
    new_scale = needed * (1.0 + safety_margin)

    old_scale = cam.data.ortho_scale
    cam.data.ortho_scale = new_scale
    bpy.context.view_layer.update()

    print(
        f"[ortho_calibration] ortho_scale: {old_scale:.3f} → {new_scale:.3f} "
        f"(max_half_x={max_half_x:.3f}, max_half_y={max_half_y:.3f}, "
        f"safety={safety_margin:.0%})"
    )
    return new_scale


# ---------------------------------------------------------------------------
# GAP 2 — Dynamic render resolution
# ---------------------------------------------------------------------------


def compute_dynamic_resolution(asset, studio, min_src=(1024, 1024), min_final=(256, 256)):
    """Compute source and final render resolutions from footprint and height.

    Formula
    -------
    The isometric 2:1 projection maps a footprint of (W × D) tiles to a
    screen-space diamond of width (W+D)×TILE_PX_W/2 pixels at base scale.
    We add vertical space for floors + roof, then supersample 4× for Cycles.

    The studio preset minimums act as hard lower bounds.
    Values are rounded to multiples of 32 (required by automatic_export_contract).
    """
    footprint = asset.get("footprint", {})
    w_tiles = int(footprint.get("widthTiles", 1))
    d_tiles = int(footprint.get("depthTiles", 1))
    floors = int(asset.get("floors", 1))

    # Isometric diamond width in px: each tile adds TILE_PX_W/2 in each direction
    iso_diamond_w = (w_tiles + d_tiles) * (TILE_PX_W // 2)
    # Height: half the diamond base + floors × floor height + roof estimate
    FLOOR_HEIGHT_PX = 64
    ROOF_MARGIN_PX = 48
    BASE_MARGIN_PX = 32
    iso_height = (
        (w_tiles + d_tiles) * (TILE_PX_H // 2)
        + floors * FLOOR_HEIGHT_PX
        + ROOF_MARGIN_PX
        + BASE_MARGIN_PX
    )

    # Final resolution — must be ≥ contract minimums and rounded to 32
    preset_min_final = studio.get("render", {}).get("finalResolution", list(min_final))
    final_w = max(min_final[0], preset_min_final[0], iso_diamond_w + 64)
    final_h = max(min_final[1], preset_min_final[1], iso_height)
    final_w = _round_to(final_w, 32)
    final_h = _round_to(final_h, 32)

    # Source resolution — 4× final for Cycles supersampling, rounded to next power of 2
    preset_min_src = studio.get("render", {}).get("sourceResolution", list(min_src))
    src_w = _next_pow2(max(min_src[0], preset_min_src[0], final_w * 4))
    src_h = _next_pow2(max(min_src[1], preset_min_src[1], final_h * 4))
    # Cap at 4096 for reasonable render times
    src_w = min(4096, src_w)
    src_h = min(4096, src_h)

    print(
        f"[resolution] footprint={w_tiles}×{d_tiles} floors={floors} → "
        f"final={final_w}×{final_h}  source={src_w}×{src_h}"
    )
    return (src_w, src_h), (final_w, final_h)


def _round_to(value, multiple):
    return ((value + multiple - 1) // multiple) * multiple


def _next_pow2(value):
    if value <= 0:
        return 1
    p = 1
    while p < value:
        p <<= 1
    return p


# ---------------------------------------------------------------------------
# Lighting and camera
# ---------------------------------------------------------------------------


def add_area_light(spec):
    if spec.get("type", "AREA") != "AREA":
        raise RuntimeError("CH_TYCOON_STUDIO_V1 currently supports AREA lights only")
    data = bpy.data.lights.new(name=spec["name"], type="AREA")
    data.energy = float(spec["energy"])
    data.color = tuple(spec["color"])
    data.shape = "DISK"
    data.size = float(spec["size"])
    if hasattr(data, "use_shadow"):
        data.use_shadow = bool(spec.get("useShadow", True))
    obj = bpy.data.objects.new(name=spec["name"], object_data=data)
    bpy.context.collection.objects.link(obj)
    obj.location = tuple(spec["location"])
    target = Vector(tuple(spec.get("target", [0.0, 0.0, 1.15])))
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def add_camera(camera):
    target = Vector(tuple(camera["target"]))
    horizontal_distance = float(camera["horizontalDistance"])
    yaw = math.radians(float(camera["yawDegrees"]))
    elevation = math.radians(float(camera["elevationDegrees"]))
    location = Vector((
        math.cos(yaw) * horizontal_distance,
        -math.sin(yaw) * horizontal_distance,
        target.z + math.tan(elevation) * horizontal_distance,
    ))
    data = bpy.data.cameras.new(camera["contract"])
    data.type = "ORTHO"
    data.ortho_scale = float(camera["orthoScale"])
    obj = bpy.data.objects.new(camera["contract"], data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (target - location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = obj
    return obj


def configure_scene(studio, src_resolution, output_dir):
    if studio.get("id") != "CH_TYCOON_STUDIO_V1":
        raise RuntimeError("This baker expects frozen studio preset CH_TYCOON_STUDIO_V1")
    scene = bpy.context.scene
    render = studio["render"]
    scene.render.engine = render["engine"]
    scene.cycles.device = render["device"]
    scene.cycles.samples = int(render["samples"])
    scene.cycles.use_denoising = bool(render["denoising"])
    scene.render.resolution_x = src_resolution[0]
    scene.render.resolution_y = src_resolution[1]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = bool(render["transparent"])

    try:
        scene.view_settings.view_transform = render["viewTransform"]
    except Exception:
        pass
    try:
        scene.view_settings.look = render["look"]
    except Exception:
        pass
    scene.view_settings.exposure = float(render["exposure"])
    scene.view_settings.gamma = float(render["gamma"])

    world = scene.world or bpy.data.worlds.new("PhotoStudioWorld")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = tuple(studio["world"]["color"])
    background.inputs["Strength"].default_value = float(studio["world"]["strength"])

    add_camera(studio["camera"])
    for light in studio["lights"]:
        add_area_light(light)
    os.makedirs(output_dir, exist_ok=True)
    return scene


# ---------------------------------------------------------------------------
# AssetRoot and rotation helpers
# ---------------------------------------------------------------------------


def create_asset_root(authored):
    root = bpy.data.objects.new("AssetRoot", None)
    bpy.context.collection.objects.link(root)
    root.location = (0.0, 0.0, 0.0)
    root.rotation_mode = "XYZ"
    for obj in authored:
        obj.parent = root
    return root


def set_direction(root, direction):
    root.rotation_euler[2] = math.radians(direction["rotationDegrees"])
    bpy.context.view_layer.update()


def ground_origin_source_px(scene):
    coord = world_to_camera_view(scene, scene.camera, Vector((0.0, 0.0, 0.0)))
    scale = scene.render.resolution_percentage / 100.0
    width = scene.render.resolution_x * scale
    height = scene.render.resolution_y * scale
    return {"x": round(coord.x * width, 4), "y": round((1.0 - coord.y) * height, 4)}


# ---------------------------------------------------------------------------
# Render passes
# ---------------------------------------------------------------------------


def render_color_pass(scene, authored, ground, path):
    ground.hide_render = True
    if hasattr(ground, "is_shadow_catcher"):
        ground.is_shadow_catcher = False
    for obj in authored:
        obj.hide_render = False
        if hasattr(obj, "visible_camera"):
            obj.visible_camera = True
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def render_shadow_pass(scene, authored, ground, path):
    ground.hide_render = False
    if hasattr(ground, "is_shadow_catcher"):
        ground.is_shadow_catcher = True
    for obj in authored:
        obj.hide_render = False
        if hasattr(obj, "visible_camera"):
            obj.visible_camera = False
        if hasattr(obj, "visible_shadow"):
            obj.visible_shadow = True
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ---------------------------------------------------------------------------
# Footprint scale validator (GAP 6 — partial: warning only)
# ---------------------------------------------------------------------------


def validate_footprint_scale(asset, authored):
    """Warn if the authored geometry does not match the declared footprint scale.

    One tile = BLENDER_UNITS_PER_TILE world units in each axis.
    A widthTiles=2, depthTiles=1 building should be ≈ 6.0 × 3.0 units wide.
    """
    footprint = asset.get("footprint", {})
    w_tiles = float(footprint.get("widthTiles", 1))
    d_tiles = float(footprint.get("depthTiles", 1))
    expected_x = w_tiles * BLENDER_UNITS_PER_TILE
    expected_y = d_tiles * BLENDER_UNITS_PER_TILE

    xs, ys = [], []
    for obj in authored:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            pt = obj.matrix_world @ Vector(corner)
            xs.append(pt.x)
            ys.append(pt.y)

    if not xs:
        return

    actual_x = max(xs) - min(xs)
    actual_y = max(ys) - min(ys)
    tolerance = 0.40  # 40 % tolerance — geometry rarely fills the whole footprint

    if actual_x > expected_x * (1.0 + tolerance):
        print(
            f"[WARN][scale] Asset X extent {actual_x:.2f} BU exceeds "
            f"footprint {w_tiles}×tile = {expected_x:.2f} BU by >{tolerance:.0%}. "
            f"Check BLENDER_UNITS_PER_TILE={BLENDER_UNITS_PER_TILE}."
        )
    if actual_y > expected_y * (1.0 + tolerance):
        print(
            f"[WARN][scale] Asset Y extent {actual_y:.2f} BU exceeds "
            f"footprint {d_tiles}×tile = {expected_y:.2f} BU by >{tolerance:.0%}. "
            f"Check BLENDER_UNITS_PER_TILE={BLENDER_UNITS_PER_TILE}."
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    args = parse_args()
    output_dir = os.path.abspath(args.output)
    asset = load_json(args.asset_config)
    studio = load_json(args.studio_preset)

    if asset.get("studioPreset") != studio.get("id"):
        raise RuntimeError(
            f"Asset requests studio {asset.get('studioPreset')!r}, "
            f"but loaded {studio.get('id')!r}"
        )

    # ── GAP 2: compute dynamic resolutions ────────────────────────────────
    if args.source_resolution:
        src_res = parse_resolution(args.source_resolution)
    else:
        src_res = None  # will be computed after studio is parsed

    if args.final_resolution:
        final_res = parse_resolution(args.final_resolution)
    else:
        final_res = None

    auto_src, auto_final = compute_dynamic_resolution(asset, studio)
    src_res = src_res or auto_src
    final_res = final_res or auto_final

    # ── Build scene with the computed source resolution ───────────────────
    clear_scene()
    scene = configure_scene(studio, src_res, output_dir)
    authored = build_asset(asset, asset_config_path=args.asset_config)
    root = create_asset_root(authored)

    # Footprint scale sanity check
    validate_footprint_scale(asset, authored)

    # Shadow receiver plane
    receiver = studio["shadowReceiver"]
    ground_material = make_material(
        "ShadowReceiver", receiver["materialColor"], float(receiver.get("roughness", 1.0))
    )
    ground = add_box(
        "ShadowReceiverPlane",
        receiver["location"],
        receiver["dimensions"],
        ground_material,
        0.0,
    )

    # ── GAP 3: auto-fit orthoScale across all four rotations ──────────────
    calibrated_scale = calibrate_ortho_scale(
        scene, authored, safety_margin=args.ortho_safety
    )

    # ── Render four directions ─────────────────────────────────────────────
    asset_id = asset["assetId"]
    direction_metadata = []
    for direction in DIRECTIONS:
        set_direction(root, direction)
        direction_id = direction["id"]
        color_name = f"{asset_id}_{direction_id}_color_source.png"
        shadow_name = f"{asset_id}_{direction_id}_shadow_source.png"
        render_color_pass(scene, authored, ground, os.path.join(output_dir, color_name))
        render_shadow_pass(scene, authored, ground, os.path.join(output_dir, shadow_name))
        direction_metadata.append({
            **direction,
            "colorSource": color_name,
            "shadowSource": shadow_name,
            "groundOriginSourcePx": ground_origin_source_px(scene),
        })

    root.rotation_euler[2] = 0.0
    bpy.context.view_layer.update()

    # ── Write studio_metadata.json ────────────────────────────────────────
    metadata = {
        "contract": "TYCOON_ASSET_BAKE_V1",
        "sourceContract": asset["contract"],
        "sourceObject": asset_id,
        "assetType": asset.get("assetType", "static_prop"),
        "footprint": asset["footprint"],
        "assetConfig": os.path.basename(args.asset_config),
        "studioPreset": studio["id"],
        "blenderVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "renderDevice": studio["render"]["device"],
        "samples": scene.cycles.samples,
        "cameraContract": studio["camera"]["contract"],
        "gridContract": "CH_GRID_V1",
        "projection": studio["camera"]["projection"],
        "yawDegrees": studio["camera"]["yawDegrees"],
        "elevationDegrees": studio["camera"]["elevationDegrees"],
        "tileWidth": TILE_PX_W,
        "tileHeight": TILE_PX_H,
        "blenderUnitsPerTile": BLENDER_UNITS_PER_TILE,
        "renderResolution": list(src_res),
        "finalResolution": list(final_res),
        "orthoScaleCalibrated": calibrated_scale,
        "orthoScaleOriginal": studio["camera"]["orthoScale"],
        "directionOrder": [direction["id"] for direction in DIRECTIONS],
        "directions": direction_metadata,
        "rotationPolicy": {
            "cameraRotates": False,
            "assetRootRotates": True,
            "lightsRotate": False,
            "quarterTurnsMatchBuildingComposer": True,
        },
        "lighting": {
            "preset": studio["id"],
            "fixedAcrossDirections": True,
            "lightNames": [light["name"] for light in studio["lights"]],
            "worldStrength": studio["world"]["strength"],
        },
        "postProcess": studio["postProcess"],
        "shadowMode": "Cycles shadow catcher with object hidden from camera",
        "sourceSummary": {
            "materialCount": len(asset.get("materials", {})),
            "partCount": len(asset.get("parts", [])),
            "sourceMode": "declarative_scene_v1",
        },
        "note": "Generic Tycoon Asset Baker V1 output. Golden visual approval remains human-gated.",
    }
    with open(os.path.join(output_dir, "studio_metadata.json"), "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)

    print("Tycoon Asset Baker V1 source passes generated:", asset_id)
    print(f"  source_resolution : {src_res[0]}×{src_res[1]}")
    print(f"  final_resolution  : {final_res[0]}×{final_res[1]}")
    print(f"  ortho_scale       : {calibrated_scale:.3f} (was {studio['camera']['orthoScale']})")
    print(f"  studio            : {studio['id']}")
    for direction in DIRECTIONS:
        print(f"  - {direction['id']} {direction['rotationDegrees']}°")


if __name__ == "__main__":
    main()
