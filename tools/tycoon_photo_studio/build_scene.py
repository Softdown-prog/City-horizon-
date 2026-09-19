"""Generic City Horizon Tycoon Asset Baker source render stage.

Loads one asset source JSON and one frozen studio preset JSON, builds the scene,
then bakes four rotations with a fixed camera and fixed world lighting.
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


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--asset-config", required=True)
    parser.add_argument("--studio-preset", required=True)
    return parser.parse_args(argv)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


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


def build_asset(asset):
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
        material_key = part.get("material")
        if material_key not in materials:
            raise RuntimeError(f"Unknown material {material_key!r} for part {part.get('name')!r}")
        material = materials[material_key]
        kind = part.get("type")
        if kind == "box":
            obj = add_box(
                part["name"], part["location"], part["dimensions"], material,
                float(part.get("bevel", 0.035)),
            )
        elif kind == "pyramid_roof":
            obj = add_pyramid_roof(part, material)
        elif kind == "uv_sphere":
            obj = add_uv_sphere(part, material)
        else:
            raise RuntimeError(f"Unsupported declarative part type: {kind!r}")
        authored.append(obj)

    if not authored:
        raise RuntimeError("Asset source did not create any renderable parts")
    return authored


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


def configure_scene(studio, output_dir):
    if studio.get("id") != "CH_TYCOON_STUDIO_V1":
        raise RuntimeError("This baker expects frozen studio preset CH_TYCOON_STUDIO_V1")
    scene = bpy.context.scene
    render = studio["render"]
    scene.render.engine = render["engine"]
    scene.cycles.device = render["device"]
    scene.cycles.samples = int(render["samples"])
    scene.cycles.use_denoising = bool(render["denoising"])
    scene.render.resolution_x = int(render["sourceResolution"][0])
    scene.render.resolution_y = int(render["sourceResolution"][1])
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


def _shadow_render_overrides():
    """Return optional CI-only shadow quality overrides without changing the frozen studio."""
    samples_raw = os.environ.get("CH_TYCOON_SHADOW_SAMPLES", "").strip()
    denoising_raw = os.environ.get("CH_TYCOON_SHADOW_DENOISING", "").strip().lower()

    samples = None
    if samples_raw:
        samples = int(samples_raw)
        if samples < 1:
            raise RuntimeError("CH_TYCOON_SHADOW_SAMPLES must be >= 1")

    denoising = None
    if denoising_raw:
        if denoising_raw not in {"0", "1", "false", "true", "no", "yes"}:
            raise RuntimeError(
                "CH_TYCOON_SHADOW_DENOISING must be one of 0/1/false/true/no/yes"
            )
        denoising = denoising_raw in {"1", "true", "yes"}

    return samples, denoising


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

    original_samples = scene.cycles.samples
    original_denoising = scene.cycles.use_denoising
    shadow_samples, shadow_denoising = _shadow_render_overrides()
    if shadow_samples is not None:
        scene.cycles.samples = shadow_samples
    if shadow_denoising is not None:
        scene.cycles.use_denoising = shadow_denoising

    try:
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
    finally:
        # The next color pass must always return to the frozen studio quality.
        scene.cycles.samples = original_samples
        scene.cycles.use_denoising = original_denoising


def main():
    args = parse_args()
    output_dir = os.path.abspath(args.output)
    asset = load_json(args.asset_config)
    studio = load_json(args.studio_preset)
    if asset.get("studioPreset") != studio.get("id"):
        raise RuntimeError(
            f"Asset requests studio {asset.get('studioPreset')!r}, but loaded {studio.get('id')!r}"
        )

    clear_scene()
    scene = configure_scene(studio, output_dir)
    authored = build_asset(asset)
    root = create_asset_root(authored)

    receiver = studio["shadowReceiver"]
    ground_material = make_material(
        "ShadowReceiver", receiver["materialColor"], float(receiver.get("roughness", 1.0))
    )
    ground = add_box(
        "ShadowReceiverPlane", receiver["location"], receiver["dimensions"], ground_material, 0.0
    )

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
        "tileWidth": 128,
        "tileHeight": 64,
        "renderResolution": [scene.render.resolution_x, scene.render.resolution_y],
        "finalResolution": studio["render"]["finalResolution"],
        "orthoScale": scene.camera.data.ortho_scale,
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
    print("studio:", studio["id"])
    for direction in DIRECTIONS:
        print(" -", direction["id"], direction["rotationDegrees"], "degrees")


if __name__ == "__main__":
    main()
