"""Deterministic silhouette-first authoring helpers for CH Blender.

The goal is not to replace Blender modelling. It is to give agent-authored assets a
small set of predictable geometry primitives plus objective shape diagnostics so a
bad silhouette is caught as data instead of discovered only after a beauty render.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Sequence

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

CONTRACT_ID = "CH_SHAPE_AUTHORING_V1"
REPORT_CONTRACT = "CH_SHAPE_REPORT_V1"
CONTRACT_PATH = Path(__file__).resolve().parent / "contracts" / "ch_shape_authoring_v1.json"


def load_contract() -> dict:
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if data.get("contract") != CONTRACT_ID:
        raise RuntimeError(f"Expected {CONTRACT_ID} at {CONTRACT_PATH}")
    return data


def _tag(obj: bpy.types.Object, role: str) -> None:
    if not role:
        raise ValueError("shape primitives require a semantic role")
    obj["ch.semanticRole"] = role
    obj["chShapeContract"] = CONTRACT_ID


def add_rounded_box(
    name: str,
    *,
    location: Sequence[float],
    dimensions: Sequence[float],
    material,
    role: str,
    bevel: float = 0.0,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=tuple(location))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = tuple(float(v) for v in dimensions)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel > 0.0:
        mod = obj.modifiers.new("CHShapeBevel", "BEVEL")
        mod.width = float(bevel)
        mod.segments = 2
    _tag(obj, role)
    obj["chShapePrimitive"] = "rounded_box"
    return obj


def _validate_sections(sections: Sequence[dict]) -> None:
    if len(sections) < 2:
        raise ValueError("symmetric loft requires at least two sections")
    previous_y = None
    for index, section in enumerate(sections):
        for key in ("y", "halfWidth", "bottomZ", "topZ"):
            if key not in section:
                raise ValueError(f"section {index} missing {key}")
        y = float(section["y"])
        half_width = float(section["halfWidth"])
        bottom_z = float(section["bottomZ"])
        top_z = float(section["topZ"])
        if previous_y is not None and y <= previous_y:
            raise ValueError("loft sections must be strictly increasing in Y")
        if half_width <= 0.0:
            raise ValueError("halfWidth must be > 0")
        if top_z <= bottom_z:
            raise ValueError("topZ must be > bottomZ")
        previous_y = y


def _section_ring(section: dict) -> list[tuple[float, float, float]]:
    """Eight-point symmetric section with softened lower and upper shoulders."""
    y = float(section["y"])
    w = float(section["halfWidth"])
    bottom = float(section["bottomZ"])
    top = float(section["topZ"])
    h = top - bottom
    return [
        (-w * 0.72, y, bottom),
        (-w, y, bottom + h * 0.20),
        (-w, y, top - h * 0.14),
        (-w * 0.78, y, top),
        (w * 0.78, y, top),
        (w, y, top - h * 0.14),
        (w, y, bottom + h * 0.20),
        (w * 0.72, y, bottom),
    ]


def add_symmetric_section_loft(
    name: str,
    *,
    sections: Sequence[dict],
    material,
    role: str,
    bevel: float = 0.0,
    cap_ends: bool = True,
) -> bpy.types.Object:
    """Create one integrated symmetric body from ordered longitudinal sections."""
    _validate_sections(sections)
    rings = [_section_ring(section) for section in sections]
    verts = [vertex for ring in rings for vertex in ring]
    ring_size = len(rings[0])
    faces: list[tuple[int, ...]] = []

    for section_index in range(len(rings) - 1):
        a = section_index * ring_size
        b = (section_index + 1) * ring_size
        for i in range(ring_size):
            j = (i + 1) % ring_size
            faces.append((a + i, a + j, b + j, b + i))

    if cap_ends:
        faces.append(tuple(range(ring_size - 1, -1, -1)))
        last = (len(rings) - 1) * ring_size
        faces.append(tuple(last + i for i in range(ring_size)))

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    if bevel > 0.0:
        mod = obj.modifiers.new("CHShapeBevel", "BEVEL")
        mod.width = float(bevel)
        mod.segments = 2
    _tag(obj, role)
    obj["chShapePrimitive"] = "symmetric_section_loft"
    obj["chShapeSections"] = json.dumps(sections, sort_keys=True, separators=(",", ":"))
    return obj


def _validate_open_tub_sections(sections: Sequence[dict]) -> None:
    if len(sections) < 2:
        raise ValueError("open tub loft requires at least two sections")
    previous_y = None
    required = ("y", "outerHalfWidth", "innerHalfWidth", "outerBottomZ", "innerFloorZ", "rimZ")
    for index, section in enumerate(sections):
        for key in required:
            if key not in section:
                raise ValueError(f"open tub section {index} missing {key}")
        y = float(section["y"])
        outer = float(section["outerHalfWidth"])
        inner = float(section["innerHalfWidth"])
        outer_bottom = float(section["outerBottomZ"])
        inner_floor = float(section["innerFloorZ"])
        rim = float(section["rimZ"])
        if previous_y is not None and y <= previous_y:
            raise ValueError("open tub sections must be strictly increasing in Y")
        if outer <= 0.0 or inner <= 0.0:
            raise ValueError("open tub widths must be > 0")
        if inner >= outer:
            raise ValueError("open tub innerHalfWidth must be smaller than outerHalfWidth")
        if inner_floor <= outer_bottom:
            raise ValueError("open tub innerFloorZ must be above outerBottomZ")
        if rim <= inner_floor:
            raise ValueError("open tub rimZ must be above innerFloorZ")
        previous_y = y


def _open_tub_section_ring(section: dict) -> list[tuple[float, float, float]]:
    """Closed U-shaped material section whose upper middle remains an open cavity."""
    y = float(section["y"])
    outer = float(section["outerHalfWidth"])
    inner = float(section["innerHalfWidth"])
    bottom = float(section["outerBottomZ"])
    floor = float(section["innerFloorZ"])
    rim = float(section["rimZ"])
    outer_h = rim - bottom
    inner_rim_z = float(section.get("innerRimZ", rim))
    if inner_rim_z <= floor or inner_rim_z > rim:
        raise ValueError("open tub innerRimZ must be above innerFloorZ and <= rimZ")
    return [
        (-outer * 0.72, y, bottom),
        (-outer, y, bottom + outer_h * 0.20),
        (-outer, y, rim - outer_h * 0.12),
        (-outer * 0.94, y, rim),
        (-inner, y, inner_rim_z),
        (-inner * 0.90, y, floor),
        (inner * 0.90, y, floor),
        (inner, y, inner_rim_z),
        (outer * 0.94, y, rim),
        (outer, y, rim - outer_h * 0.12),
        (outer, y, bottom + outer_h * 0.20),
        (outer * 0.72, y, bottom),
    ]


def add_open_tub_loft(
    name: str,
    *,
    sections: Sequence[dict],
    material,
    role: str,
    bevel: float = 0.0,
    cap_ends: bool = True,
) -> bpy.types.Object:
    """Create one deterministic hollow, open-top body from longitudinal U sections.

    The cavity, floor and side walls are a single mesh. This avoids the detached-panel
    look produced when open vehicles are assembled from unrelated boxes or wall slabs.
    """
    _validate_open_tub_sections(sections)
    rings = [_open_tub_section_ring(section) for section in sections]
    verts = [vertex for ring in rings for vertex in ring]
    ring_size = len(rings[0])
    faces: list[tuple[int, ...]] = []

    for section_index in range(len(rings) - 1):
        a = section_index * ring_size
        b = (section_index + 1) * ring_size
        for i in range(ring_size):
            j = (i + 1) % ring_size
            faces.append((a + i, a + j, b + j, b + i))

    if cap_ends:
        faces.append(tuple(range(ring_size - 1, -1, -1)))
        last = (len(rings) - 1) * ring_size
        faces.append(tuple(last + i for i in range(ring_size)))

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    if bevel > 0.0:
        mod = obj.modifiers.new("CHShapeBevel", "BEVEL")
        mod.width = float(bevel)
        mod.segments = 2
    _tag(obj, role)
    obj["chShapePrimitive"] = "open_tub_loft"
    obj["chShapeOpenTop"] = True
    obj["chShapeSections"] = json.dumps(sections, sort_keys=True, separators=(",", ":"))
    return obj


def add_profile_prism(
    name: str,
    *,
    x_center: float,
    thickness: float,
    y_center: float,
    profile_yz: Sequence[Sequence[float]],
    material,
    role: str,
    bevel: float = 0.0,
) -> bpy.types.Object:
    if len(profile_yz) < 3:
        raise ValueError("profile prism requires at least three profile points")
    if thickness <= 0.0:
        raise ValueError("profile prism thickness must be > 0")
    x0 = float(x_center) - float(thickness) * 0.5
    x1 = float(x_center) + float(thickness) * 0.5
    verts = []
    for x in (x0, x1):
        verts.extend((x, float(y_center) + float(y), float(z)) for y, z in profile_yz)
    n = len(profile_yz)
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    if bevel > 0.0:
        mod = obj.modifiers.new("CHShapeBevel", "BEVEL")
        mod.width = float(bevel)
        mod.segments = 2
    _tag(obj, role)
    obj["chShapePrimitive"] = "profile_prism"
    return obj


def add_mirrored_profile_pair(
    name_prefix: str,
    *,
    x_center: float,
    thickness: float,
    y_center: float,
    profile_yz: Sequence[Sequence[float]],
    material,
    role: str,
    bevel: float = 0.0,
) -> tuple[bpy.types.Object, bpy.types.Object]:
    left = add_profile_prism(
        f"{name_prefix}_L",
        x_center=-abs(float(x_center)),
        thickness=thickness,
        y_center=y_center,
        profile_yz=profile_yz,
        material=material,
        role=role,
        bevel=bevel,
    )
    right = add_profile_prism(
        f"{name_prefix}_R",
        x_center=abs(float(x_center)),
        thickness=thickness,
        y_center=y_center,
        profile_yz=profile_yz,
        material=material,
        role=role,
        bevel=bevel,
    )
    left["chShapeMirrorPeer"] = right.name
    right["chShapeMirrorPeer"] = left.name
    return left, right


def _mesh_objects(objects: Iterable[bpy.types.Object]) -> list[bpy.types.Object]:
    return [obj for obj in objects if obj.type == "MESH"]


def _world_points(obj: bpy.types.Object) -> list[Vector]:
    return [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]


def _bounds(objects: Iterable[bpy.types.Object]) -> dict | None:
    points = [point for obj in _mesh_objects(objects) for point in _world_points(obj)]
    if not points:
        return None
    mins = [min(p[i] for p in points) for i in range(3)]
    maxs = [max(p[i] for p in points) for i in range(3)]
    return {"min": mins, "max": maxs}


def _semantic_bounds(objects: Iterable[bpy.types.Object]) -> dict:
    groups: dict[str, list[bpy.types.Object]] = {}
    for obj in _mesh_objects(objects):
        role = obj.get("ch.semanticRole")
        if role:
            groups.setdefault(str(role), []).append(obj)
    return {role: _bounds(group) for role, group in sorted(groups.items())}


def _primitive_counts(objects: Iterable[bpy.types.Object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for obj in _mesh_objects(objects):
        primitive = obj.get("chShapePrimitive")
        if primitive:
            key = str(primitive)
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def build_shape_report(
    *,
    scene,
    objects: Iterable[bpy.types.Object],
    asset_id: str,
    constraints: dict | None = None,
) -> dict:
    objects = _mesh_objects(objects)
    bounds = _bounds(objects)
    violations = []
    dimensions = None
    center_offset_x = None
    symmetry_error = None
    if bounds:
        dimensions = [bounds["max"][i] - bounds["min"][i] for i in range(3)]
        width = max(dimensions[0], 1e-9)
        center_offset_x = (bounds["min"][0] + bounds["max"][0]) * 0.5
        symmetry_error = abs(bounds["min"][0] + bounds["max"][0]) / width

    projected_bounds = None
    occupancy = None
    if scene.camera is not None and objects:
        projected = [world_to_camera_view(scene, scene.camera, p) for obj in objects for p in _world_points(obj)]
        min_x = min(p.x for p in projected)
        max_x = max(p.x for p in projected)
        min_y = min(p.y for p in projected)
        max_y = max(p.y for p in projected)
        projected_bounds = {"minX": min_x, "maxX": max_x, "minY": min_y, "maxY": max_y}
        occupancy = max(0.0, max_x - min_x) * max(0.0, max_y - min_y)

    primitive_counts = _primitive_counts(objects)
    constraints = constraints or {}
    if symmetry_error is not None:
        maximum = float(constraints.get("maxXSymmetryError", 1.0))
        if symmetry_error > maximum:
            violations.append({
                "code": "CH_SHAPE_X_SYMMETRY",
                "message": "Authored shape is too far from the expected X symmetry.",
                "actual": symmetry_error,
                "allowed": maximum,
            })
    if center_offset_x is not None:
        maximum = float(constraints.get("maxAbsCenterOffsetX", 1e9))
        if abs(center_offset_x) > maximum:
            violations.append({
                "code": "CH_SHAPE_CENTER_OFFSET_X",
                "message": "Authored shape is not centered closely enough on X=0.",
                "actual": center_offset_x,
                "allowedAbs": maximum,
            })
    if occupancy is not None:
        minimum = float(constraints.get("minProjectedSouthOccupancy", 0.0))
        maximum = float(constraints.get("maxProjectedSouthOccupancy", 1e9))
        if occupancy < minimum:
            violations.append({
                "code": "CH_SHAPE_SCREEN_OCCUPANCY_LOW",
                "message": "Projected SOUTH silhouette uses too little of the proxy frame.",
                "actual": occupancy,
                "minimum": minimum,
            })
        if occupancy > maximum:
            violations.append({
                "code": "CH_SHAPE_SCREEN_OCCUPANCY_HIGH",
                "message": "Projected SOUTH silhouette uses too much of the proxy frame.",
                "actual": occupancy,
                "maximum": maximum,
            })

    required_minimums = constraints.get("requiredPrimitiveMinimums", {})
    if not isinstance(required_minimums, dict):
        raise ValueError("requiredPrimitiveMinimums must be an object mapping primitive name to minimum count")
    for primitive, minimum_value in sorted(required_minimums.items()):
        minimum = int(minimum_value)
        actual = int(primitive_counts.get(str(primitive), 0))
        if actual < minimum:
            violations.append({
                "code": "CH_SHAPE_REQUIRED_PRIMITIVE",
                "message": "Authored asset is missing a required deterministic shape primitive.",
                "primitive": str(primitive),
                "actual": actual,
                "minimum": minimum,
            })

    return {
        "contract": REPORT_CONTRACT,
        "status": "pass" if not violations else "fail",
        "assetId": asset_id,
        "meshCount": len(objects),
        "bounds": bounds,
        "dimensions": dimensions,
        "centerOffsetX": center_offset_x,
        "xSymmetryError": symmetry_error,
        "projectedSouthBounds": projected_bounds,
        "projectedSouthOccupancy": occupancy,
        "semanticRoleBounds": _semantic_bounds(objects),
        "shapePrimitiveCounts": primitive_counts,
        "constraints": constraints,
        "violations": violations,
    }


def write_shape_report(path: str | Path, report: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")


def require_shape_pass(report: dict) -> None:
    if report.get("status") != "pass":
        codes = ",".join(v.get("code", "CH_SHAPE_UNKNOWN") for v in report.get("violations", []))
        raise RuntimeError(f"CH_SHAPE_REJECTED:{codes}")
