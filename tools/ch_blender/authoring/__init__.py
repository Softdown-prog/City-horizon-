"""High-level CH Blender authoring primitives for City Horizon assets.

The authoring package is deliberately higher level than raw bpy calls. Agents
should describe forms (soft volume, tapered limb, lofted shell, curve tube)
instead of rebuilding low-level Blender geometry for every asset.
"""

from .materials import stylized_material
from .shapes import (
    AuthoringObject,
    blob_cluster,
    create_root,
    soft_form,
    tapered_segment,
    loft_form,
    rounded_box,
    curve_tube,
    torus_form,
)
from .character import CharacterAuthoring
from .recipe import (
    CONTRACT as AUTHORING_RECIPE_CONTRACT,
    apply_proportion_profile,
    execute_recipe,
    load_recipe,
)

__all__ = [
    "AUTHORING_RECIPE_CONTRACT",
    "AuthoringObject",
    "CharacterAuthoring",
    "apply_proportion_profile",
    "blob_cluster",
    "create_root",
    "curve_tube",
    "execute_recipe",
    "load_recipe",
    "loft_form",
    "rounded_box",
    "soft_form",
    "stylized_material",
    "tapered_segment",
    "torus_form",
]
