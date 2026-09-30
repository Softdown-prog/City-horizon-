"""High-level deterministic shape primitives for CH Blender.

These helpers intentionally hide repetitive bpy mesh setup from asset recipes.
They are designed for small stylized assets that will be pre-rendered to 2D.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import bpy
from mathutils import Vector


@dataclass(frozen=True)
class AuthoringObject:
    name: str
    object: bpy.types.Object


def _vec(value: Sequence[float] | Vector) -> Vector:
    return value.copy() if isinstance(value, Vector) else Vector(value)


def _assign_material(obj: bpy.types.Object, material: bpy.types.Material | None) -> None:
    if material is not None:
        obj.data.materials.append(material)


def _smooth(obj: bpy.types.Object) -> None:
    if getattr(obj, "data", None) is None or not hasattr(obj.data, "polygons"):
        return
    for poly in obj.data.polygons:
        poly.use_smooth = True


def _parent(obj: bpy.types.Object, root: bpy.types.Object | None) -> None:
    if root is not None:
        obj.parent = root


def create_root(name: str, *, location=(0.0, 0.0, 0.0)) -> bpy.types.Object:
    root = bpy.data.objects.new(name, None)
    root.location = _vec(location)
    bpy.context.collection.objects.link(root)
    return root


def soft_form(
    name: str,
    location,
    scale,
    material: bpy.types.Material | None,
    *,
    root: bpy.types.Object | None = None,
    rotation=(0.0, 0.0, 0.0),
    segments: int = 28,
    rings: int = 18,
) -> AuthoringObject:
    """Create a smooth ellipsoidal volume for heads, cheeks, hair masses, etc."""
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=max(12, int(segments)),
        ring_count=max(8, int(rings)),
        location=_vec(location),
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = _vec(scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    _assign_material(obj, material)
    _smooth(obj)
    _parent(obj, root)
    return AuthoringObject(name, obj)


def tapered_segment(
    name: str,
    start,
    end,
    radius_start: float,
    radius_end: float,
    material: bpy.types.Material | None,
    *,
    root: bpy.types.Object | None = None,
    vertices: int = 24,
    cap_ends: bool = True,
) -> AuthoringObject:
    """Create a tapered limb/garment segment aligned between two points.

    Unlike a constant-radius capsule, this can describe sleeves, trousers,
    forearms and shins without making every limb read as a tube.
    """
    a = _vec(start)
    b = _vec(end)
    delta = b - a
    length = delta.length
    if length <= 1e-6:
        raise ValueError(f"{name}: tapered segment requires distinct endpoints")

    bpy.ops.mesh.primitive_cone_add(
        vertices=max(8, int(vertices)),
        radius1=max(1e-4, float(radius_start)),
        radius2=max(1e-4, float(radius_end)),
        depth=length,
        end_fill_type="NGON" if cap_ends else "NOTHING",
        location=(a + b) * 0.5,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(delta.normalized())
    _assign_material(obj, material)
    _smooth(obj)
    _parent(obj, root)
    return AuthoringObject(name, obj)


def rounded_box(
    name: str,
    location,
    size,
    material: bpy.types.Material | None,
    *,
    root: bpy.types.Object | None = None,
    rotation=(0.0, 0.0, 0.0),
    bevel: float = 0.04,
    bevel_segments: int = 3,
) -> AuthoringObject:
    """Create a rounded box useful for torso shells, bags and blocky props."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=_vec(location), rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = _vec(size)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0.0:
        modifier = obj.modifiers.new("CH_Rounded", "BEVEL")
        modifier.width = float(bevel)
        modifier.segments = max(1, int(bevel_segments))
        modifier.limit_method = "ANGLE"
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    _assign_material(obj, material)
    _smooth(obj)
    _parent(obj, root)
    return AuthoringObject(name, obj)


def curve_tube(
    name: str,
    points: Iterable[Sequence[float] | Vector],
    radius: float,
    material: bpy.types.Material | None,
    *,
    root: bpy.types.Object | None = None,
    resolution: int = 2,
    bevel_resolution: int = 3,
    cyclic: bool = False,
) -> AuthoringObject:
    """Create a smooth tube following control points.

    This is useful for locks of hair, piping, straps and decorative curves where
    straight capsule segments are visually too mechanical.
    """
    pts = [_vec(point) for point in points]
    if len(pts) < 2:
        raise ValueError(f"{name}: curve tube requires at least two points")

    curve = bpy.data.curves.new(name + "_Curve", type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = max(1, int(resolution))
    curve.bevel_depth = max(1e-4, float(radius))
    curve.bevel_resolution = max(0, int(bevel_resolution))
    curve.resolution_u = max(1, int(resolution))
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(pts) - 1)
    for bp, point in zip(spline.bezier_points, pts):
        bp.co = point
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"
    spline.use_cyclic_u = bool(cyclic)

    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    _assign_material(obj, material)
    _parent(obj, root)
    return AuthoringObject(name, obj)


def torus_form(
    name: str,
    location,
    major_radius: float,
    minor_radius: float,
    material: bpy.types.Material | None,
    *,
    root: bpy.types.Object | None = None,
    rotation=(0.0, 0.0, 0.0),
    major_segments: int = 32,
    minor_segments: int = 12,
) -> AuthoringObject:
    """Create a toroidal form for collars, cuffs, rings and round trims."""
    bpy.ops.mesh.primitive_torus_add(
        major_radius=max(1e-4, float(major_radius)),
        minor_radius=max(1e-4, float(minor_radius)),
        major_segments=max(12, int(major_segments)),
        minor_segments=max(6, int(minor_segments)),
        location=_vec(location),
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    _assign_material(obj, material)
    _smooth(obj)
    _parent(obj, root)
    return AuthoringObject(name, obj)
