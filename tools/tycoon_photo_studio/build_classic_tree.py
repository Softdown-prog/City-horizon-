"""Bake a dense classic pre-rendered Tycoon tree from a compact procedural spec.

The goal is deliberately different from the low-poly canopy prototype: the crown is
built from hundreds of tiny leaf cards plus tapered branch geometry so that the
1024->256 downsample has real organic micro-contrast to preserve.  The script reuses
CH_TYCOON_STUDIO_V1 unchanged (camera, lighting, shadow receiver and four rotations).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Vector

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_scene as studio_base


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


def point_from(start, length, yaw_deg, elevation_deg):
    yaw = math.radians(yaw_deg)
    elevation = math.radians(elevation_deg)
    horizontal = math.cos(elevation) * length
    return Vector((
        start[0] + math.cos(yaw) * horizontal,
        start[1] + math.sin(yaw) * horizontal,
        start[2] + math.sin(elevation) * length,
    ))


def add_tapered_segment(name, start, end, radius1, radius2, material, vertices=10):
    start = Vector(start)
    end = Vector(end)
    direction = end - start
    length = direction.length
    if length <= 1e-6:
        raise RuntimeError(f"Degenerate tree segment: {name}")
    midpoint = (start + end) * 0.5
    bpy.ops.mesh.primitive_cone_add(
        vertices=int(vertices),
        radius1=float(radius1),
        radius2=float(radius2),
        depth=float(length),
        location=midpoint,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(material)
    return obj


def build_materials(asset):
    result = {}
    for key, spec in asset["materials"].items():
        result[key] = studio_base.make_material(
            spec.get("name", key),
            spec["rgba"],
            float(spec.get("roughness", 1.0)),
            float(spec.get("metallic", 0.0)),
        )
    return result


def generate_branch_geometry(asset, materials, authored):
    spec = asset["fractalTree"]
    rng = random.Random(int(spec.get("seed", 1)))
    levels = int(spec.get("levels", 4))
    primary_count = int(spec.get("primaryBranches", 4))
    branch_factor = int(spec.get("branchFactor", 2))
    if branch_factor != 2:
        raise RuntimeError("classic leaf-card tree currently requires branchFactor=2")

    material = materials[str(spec["material"])]
    origin = Vector(tuple(float(v) for v in spec.get("origin", [0.0, 0.0, 1.72])))
    base_length = float(spec.get("baseLength", 0.66))
    length_decay = float(spec.get("lengthDecay", 0.68))
    base_radius = float(spec.get("baseRadius", 0.075))
    radius_decay = float(spec.get("radiusDecay", 0.67))
    initial_elevation = float(spec.get("initialElevationDegrees", 47.0))
    elevation_gain = float(spec.get("elevationGainDegrees", 8.0))
    yaw_spread = float(spec.get("yawSpreadDegrees", 48.0))
    yaw_jitter = float(spec.get("yawJitterDegrees", 11.0))
    elevation_jitter = float(spec.get("elevationJitterDegrees", 6.0))
    base_yaw = float(spec.get("baseYawDegrees", -16.0))
    yaw_step = 360.0 / max(1, primary_count)

    terminals = []
    branch_count = 0

    def recurse(start, length, radius, yaw_deg, elevation_deg, level):
        nonlocal branch_count
        end = point_from(start, length, yaw_deg, elevation_deg)
        branch_count += 1
        authored.append(add_tapered_segment(
            f"ClassicBranch_{branch_count:03d}",
            start,
            end,
            radius,
            max(radius * 0.58, 0.006),
            material,
            vertices=8,
        ))
        if level >= levels:
            terminals.append(end)
            return

        next_length = length * length_decay
        next_radius = radius * radius_decay
        for side in (-1.0, 1.0):
            child_yaw = yaw_deg + side * yaw_spread + rng.uniform(-yaw_jitter, yaw_jitter)
            child_elev = elevation_deg + elevation_gain + rng.uniform(-elevation_jitter, elevation_jitter)
            recurse(end, next_length, next_radius, child_yaw, child_elev, level + 1)

    for index in range(primary_count):
        yaw = base_yaw + index * yaw_step + rng.uniform(-8.0, 8.0)
        elev = initial_elevation + rng.uniform(-5.0, 5.0)
        recurse(origin, base_length, base_radius, yaw, elev, 1)

    return terminals, branch_count


def build_leaf_mesh(asset, materials, terminals, authored):
    spec = asset["leafCards"]
    rng = random.Random(int(spec.get("seed", 2718)))
    count = int(spec.get("count", 560))
    material_keys = list(spec.get("materials", ["leafDark", "leafMid", "leafLight"]))
    if not material_keys:
        raise RuntimeError("leafCards.materials cannot be empty")

    width_range = tuple(float(v) for v in spec.get("widthRange", [0.11, 0.18]))
    height_range = tuple(float(v) for v in spec.get("heightRange", [0.18, 0.28]))
    size_bias_power = max(0.25, float(spec.get("sizeBiasPower", 1.0)))
    max_tilt = max(5.0, min(80.0, float(spec.get("maxTiltDegrees", 60.0))))
    cluster = tuple(float(v) for v in spec.get("clusterRadius", [0.34, 0.34, 0.26]))
    interior_fraction = float(spec.get("interiorFraction", 0.20))
    terminal_pull = float(spec.get("terminalPullToCenter", 0.18))
    crown_center = Vector(tuple(float(v) for v in spec.get("crownCenter", [0.0, 0.0, 3.0])))
    crown_radius = tuple(float(v) for v in spec.get("crownRadius", [1.10, 1.02, 0.86]))
    max_center_radius = float(spec.get("maxNormalizedCenterRadius", 0.97))

    vertices = []
    faces = []
    material_indices = []

    def random_ellipsoid_offset(radius):
        while True:
            x = rng.uniform(-1.0, 1.0)
            y = rng.uniform(-1.0, 1.0)
            z = rng.uniform(-1.0, 1.0)
            if x * x + y * y + z * z <= 1.0:
                return Vector((x * radius[0], y * radius[1], z * radius[2]))

    def clamp_to_crown(point):
        delta = point - crown_center
        nx = delta.x / max(crown_radius[0], 1e-6)
        ny = delta.y / max(crown_radius[1], 1e-6)
        nz = delta.z / max(crown_radius[2], 1e-6)
        normalized = math.sqrt(nx * nx + ny * ny + nz * nz)
        if normalized <= max_center_radius:
            return point
        scale = max_center_radius / max(normalized, 1e-6)
        return crown_center + Vector((delta.x * scale, delta.y * scale, delta.z * scale))

    for index in range(count):
        if terminals and rng.random() >= interior_fraction:
            terminal = Vector(terminals[rng.randrange(len(terminals))])
            terminal = terminal.lerp(crown_center, terminal_pull)
            center = terminal + random_ellipsoid_offset(cluster)
        else:
            center = crown_center + random_ellipsoid_offset(crown_radius)
        center = clamp_to_crown(center)

        size_t = rng.random() ** size_bias_power
        width = width_range[0] + (width_range[1] - width_range[0]) * size_t
        height_t = min(1.0, max(0.0, size_t * 0.72 + rng.random() * 0.28))
        height = height_range[0] + (height_range[1] - height_range[0]) * height_t
        local = (
            Vector((-0.48 * width, 0.0, 0.0)),
            Vector((-0.20 * width, 0.0, 0.38 * height)),
            Vector((0.0, 0.0, 0.52 * height)),
            Vector((0.20 * width, 0.0, 0.38 * height)),
            Vector((0.48 * width, 0.0, 0.0)),
            Vector((0.0, 0.0, -0.52 * height)),
        )
        rotation = Euler((
            math.radians(rng.uniform(-max_tilt, max_tilt)),
            math.radians(rng.uniform(-max_tilt * 0.72, max_tilt * 0.72)),
            math.radians(rng.uniform(0.0, 360.0)),
        ), "XYZ").to_matrix()
        start = len(vertices)
        vertices.extend([tuple(center + rotation @ point) for point in local])
        faces.append(tuple(start + i for i in range(6)))
        material_indices.append(rng.randrange(len(material_keys)))

    mesh = bpy.data.meshes.new("ClassicLeafCardsMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("ClassicLeafCards", mesh)
    bpy.context.collection.objects.link(obj)
    for key in material_keys:
        obj.data.materials.append(materials[key])
    for poly, material_index in zip(obj.data.polygons, material_indices):
        poly.material_index = material_index
    authored.append(obj)
    return count


def build_tree(asset):
    if asset.get("contract") != "TYCOON_FRACTAL_TREE_SOURCE_V1":
        raise RuntimeError("Classic tree source must use TYCOON_FRACTAL_TREE_SOURCE_V1")
    materials = build_materials(asset)
    authored = []

    trunk = asset.get("trunk", {})
    trunk_height = float(trunk.get("height", 1.90))
    base_radius = float(trunk.get("baseRadius", 0.29))
    top_radius = float(trunk.get("topRadius", 0.14))
    trunk_vertices = int(trunk.get("vertices", 12))
    lean = tuple(float(v) for v in trunk.get("lean", [0.0, 0.0]))
    kink = tuple(float(v) for v in trunk.get("midKink", [0.0, 0.0]))
    trunk_material = materials[str(trunk.get("material", "trunk"))]

    p0 = Vector((0.0, 0.0, 0.03))
    p1 = Vector((lean[0] * 0.24, lean[1] * 0.24, trunk_height * 0.37))
    p2 = Vector((lean[0] * 0.66 + kink[0], lean[1] * 0.66 + kink[1], trunk_height * 0.70))
    p3 = Vector((lean[0], lean[1], trunk_height))
    trunk_points = (p0, p1, p2, p3)
    trunk_radii = (
        base_radius,
        base_radius * 0.76,
        max(top_radius * 1.48, base_radius * 0.43),
        top_radius,
    )
    for index in range(3):
        authored.append(add_tapered_segment(
            f"ClassicTrunk_{index + 1:02d}",
            trunk_points[index],
            trunk_points[index + 1],
            trunk_radii[index],
            trunk_radii[index + 1],
            trunk_material,
            vertices=trunk_vertices,
        ))

    root_count = int(trunk.get("rootCount", 5))
    root_length = float(trunk.get("rootLength", 0.34))
    root_rng = random.Random(int(trunk.get("rootSeed", 919)))
    for index in range(root_count):
        yaw = 2.0 * math.pi * index / max(1, root_count) + root_rng.uniform(-0.18, 0.18)
        end = (math.cos(yaw) * root_length, math.sin(yaw) * root_length, 0.035)
        authored.append(add_tapered_segment(
            f"ClassicRoot_{index:02d}",
            (0.0, 0.0, 0.11),
            end,
            float(trunk.get("rootRadius", 0.105)),
            0.018,
            trunk_material,
            vertices=8,
        ))

    terminals, branch_count = generate_branch_geometry(asset, materials, authored)
    leaf_count = build_leaf_mesh(asset, materials, terminals, authored)
    return authored, branch_count, leaf_count


def main():
    args = parse_args()
    output_dir = os.path.abspath(args.output)
    asset = load_json(args.asset_config)
    studio = load_json(args.studio_preset)
    if asset.get("studioPreset") != studio.get("id"):
        raise RuntimeError("Tree source and studio preset do not match")

    studio_base.clear_scene()
    scene = studio_base.configure_scene(studio, output_dir)
    authored, branch_count, leaf_count = build_tree(asset)
    root = studio_base.create_asset_root(authored)

    receiver = studio["shadowReceiver"]
    ground_material = studio_base.make_material(
        "ClassicTreeShadowReceiver", receiver["materialColor"], float(receiver.get("roughness", 1.0))
    )
    ground = studio_base.add_box(
        "ShadowReceiverPlane", receiver["location"], receiver["dimensions"], ground_material, 0.0
    )

    asset_id = asset["assetId"]
    direction_metadata = []
    for direction in studio_base.DIRECTIONS:
        studio_base.set_direction(root, direction)
        direction_id = direction["id"]
        color_name = f"{asset_id}_{direction_id}_color_source.png"
        shadow_name = f"{asset_id}_{direction_id}_shadow_source.png"
        studio_base.render_color_pass(scene, authored, ground, os.path.join(output_dir, color_name))
        studio_base.render_shadow_pass(scene, authored, ground, os.path.join(output_dir, shadow_name))
        direction_metadata.append({
            **direction,
            "colorSource": color_name,
            "shadowSource": shadow_name,
            "groundOriginSourcePx": studio_base.ground_origin_source_px(scene),
        })

    metadata = {
        "contract": "TYCOON_ASSET_BAKE_V1",
        "sourceContract": asset["contract"],
        "sourceObject": asset_id,
        "assetType": asset.get("assetType", "static_decor"),
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
        "directionOrder": [direction["id"] for direction in studio_base.DIRECTIONS],
        "directions": direction_metadata,
        "rotationPolicy": {
            "cameraRotates": False,
            "assetRootRotates": True,
            "lightsRotate": False,
            "quarterTurnsMatchBuildingComposer": True,
        },
        "postProcess": studio["postProcess"],
        "shadowMode": "Cycles shadow catcher with object hidden from camera",
        "sourceSummary": {
            "materialCount": len(asset.get("materials", {})),
            "partCount": len(authored),
            "branchCount": branch_count,
            "leafCardCount": leaf_count,
            "sourceMode": "procedural_leaf_card_tree_v1",
        },
        "note": "Dense pre-rendered foliage candidate. Human gameplay-scale approval remains mandatory.",
    }
    Path(output_dir, "studio_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print("Classic leaf-card tree source generated:", asset_id)
    print("branches:", branch_count, "leafCards:", leaf_count)


if __name__ == "__main__":
    main()
