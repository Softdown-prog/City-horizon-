"""High-level CH Blender authoring primitives for City Horizon assets.

The authoring package is deliberately higher level than raw bpy calls. Agents
should describe forms (soft volume, tapered limb, rounded shell, curve tube)
instead of rebuilding low-level Blender geometry for every asset.
"""

from .materials import stylized_material
from .shapes import (
    AuthoringObject,
    create_root,
    soft_form,
    tapered_segment,
    rounded_box,
    curve_tube,
    torus_form,
)
from .character import CharacterAuthoring

__all__ = [
    "AuthoringObject",
    "CharacterAuthoring",
    "create_root",
    "curve_tube",
    "rounded_box",
    "soft_form",
    "stylized_material",
    "tapered_segment",
    "torus_form",
]
