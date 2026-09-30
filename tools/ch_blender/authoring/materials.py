"""Deterministic stylized material helpers for CH Blender authoring."""
from __future__ import annotations

import bpy


def _rgba(hex_value: str) -> tuple[float, float, float, float]:
    value = hex_value.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Expected #RRGGBB, got {hex_value!r}")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4)) + (1.0,)


def stylized_material(
    name: str,
    color: str,
    *,
    roughness: float = 0.82,
    specular: float = 0.16,
    metallic: float = 0.0,
) -> bpy.types.Material:
    """Create or reuse a matte pre-render material with stable settings.

    CH assets should read clearly after downsampling. High gloss is therefore
    intentionally avoided unless the recipe opts in explicitly.
    """
    existing = bpy.data.materials.get(name)
    if existing is not None:
        return existing

    mat = bpy.data.materials.new(name)
    mat.diffuse_color = _rgba(color)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = _rgba(color)
        bsdf.inputs["Roughness"].default_value = max(0.0, min(1.0, roughness))
        bsdf.inputs["Metallic"].default_value = max(0.0, min(1.0, metallic))
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = max(0.0, min(1.0, specular))
    return mat
