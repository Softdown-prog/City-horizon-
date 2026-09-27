"""Reusable roof-form primitives for CH_ARCHITECTURE_VOCABULARY_V1.

These helpers are deliberately camera-agnostic. They create deterministic roof
massing under the caller's AssetRoot; the frozen CH Blender studio continues to
own camera, lights and projection.
"""
from __future__ import annotations

from typing import Callable


MeshFn = Callable[..., object]


def gable_x(
    *, mesh: MeshFn, root, material, name: str,
    center_x: float, center_y: float, width: float, depth: float,
    eave_z: float, ridge_z: float, bevel: float = 0.03,
):
    """Two-slope gable whose ridge runs along world X."""
    half_w = width / 2.0
    half_d = depth / 2.0
    vertices = [
        (center_x-half_w, center_y-half_d, eave_z),
        (center_x-half_w, center_y, ridge_z),
        (center_x+half_w, center_y, ridge_z),
        (center_x+half_w, center_y-half_d, eave_z),
        (center_x-half_w, center_y+half_d, eave_z),
        (center_x+half_w, center_y+half_d, eave_z),
    ]
    return mesh(name, vertices, [(0,1,2,3),(1,4,5,2)], material, root, bevel)


def gable_y(
    *, mesh: MeshFn, root, material, name: str,
    center_x: float, center_y: float, width: float, depth: float,
    eave_z: float, ridge_z: float, bevel: float = 0.03,
):
    """Two-slope gable whose ridge runs along world Y."""
    half_w = width / 2.0
    half_d = depth / 2.0
    vertices = [
        (center_x-half_w, center_y-half_d, eave_z),
        (center_x, center_y-half_d, ridge_z),
        (center_x, center_y+half_d, ridge_z),
        (center_x-half_w, center_y+half_d, eave_z),
        (center_x+half_w, center_y-half_d, eave_z),
        (center_x+half_w, center_y+half_d, eave_z),
    ]
    return mesh(name, vertices, [(0,1,2,3),(1,4,5,2)], material, root, bevel)


def hip(
    *, mesh: MeshFn, root, material, name: str,
    center_x: float, center_y: float, width: float, depth: float,
    eave_z: float, ridge_z: float, ridge_fraction: float = 0.42,
    bevel: float = 0.03,
):
    """Compact four-slope hip roof with an X-aligned short ridge."""
    half_w = width / 2.0
    half_d = depth / 2.0
    ridge_half = max(0.0, min(half_w * 0.9, half_w * ridge_fraction))
    vertices = [
        (center_x-half_w, center_y-half_d, eave_z),
        (center_x+half_w, center_y-half_d, eave_z),
        (center_x+half_w, center_y+half_d, eave_z),
        (center_x-half_w, center_y+half_d, eave_z),
        (center_x-ridge_half, center_y, ridge_z),
        (center_x+ridge_half, center_y, ridge_z),
    ]
    faces = [
        (0,1,5,4),
        (1,2,5),
        (2,3,4,5),
        (3,0,4),
    ]
    return mesh(name, vertices, faces, material, root, bevel)


def dormer_gable(
    *, mesh: MeshFn, root, material, name: str,
    center_x: float, center_y: float, width: float, depth: float,
    eave_z: float, ridge_z: float, facing: str = "south",
    bevel: float = 0.025,
):
    """Readable dormer roof. South/north use a Y ridge; east/west use X."""
    facing = facing.lower()
    if facing in {"south", "north"}:
        return gable_y(
            mesh=mesh, root=root, material=material, name=name,
            center_x=center_x, center_y=center_y, width=width, depth=depth,
            eave_z=eave_z, ridge_z=ridge_z, bevel=bevel,
        )
    if facing in {"east", "west"}:
        return gable_x(
            mesh=mesh, root=root, material=material, name=name,
            center_x=center_x, center_y=center_y, width=width, depth=depth,
            eave_z=eave_z, ridge_z=ridge_z, bevel=bevel,
        )
    raise ValueError(f"Unsupported dormer facing: {facing}")
