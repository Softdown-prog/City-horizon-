"""Tycoon Material Library — procedural PBR recipes for the Blender bake pipeline.

Implements the 8 wall/roof material recipes defined in city_horizon_classic_tycoon.json
using only Blender built-in procedural textures (no external image files required).
All recipes are deterministic: the same ``seed`` always produces the same material.

Supported recipes
-----------------
plaster      Smooth painted stucco with subtle noise bump.
brick        Mortared brick grid via the built-in Brick Texture node.
concrete     Rough poured concrete — multi-octave noise, high roughness.
timber       Painted wood panels — Wave Texture grain with colour variation.
stone        Rough-cut stone — Voronoi cells for stone joints + noise surface.
metal_panel  Painted metal — slight metallic sheen with scratch roughness map.
glass        Window glass — Principled BSDF transmission with tinted base.
solid        Flat colour only, no procedural variation (legacy/default behaviour).

Usage
-----
    from tycoon_material_library import make as make_tycoon_material

    mat = make_tycoon_material(
        recipe_name="brick",
        mat_name="FrontWall_Brick",
        rgba=(0.42, 0.12, 0.07, 1.0),
        roughness=0.90,
        seed=17,
        strength=0.45,
    )

The asset source JSON can specify a recipe in two ways:

    # Classic (solid flat colour — backward compatible):
    "materials": {
        "wall": {"name": "Wall", "rgba": [0.72, 0.58, 0.37, 1.0], "roughness": 0.78}
    }

    # New (procedural recipe):
    "materials": {
        "wall": {"name": "Wall", "rgba": [0.72, 0.58, 0.37, 1.0], "recipe": "plaster",
                 "roughness": 0.78, "seed": 17, "strength": 0.45}
    }
"""

from __future__ import annotations

import math
from typing import Tuple

import bpy

RGBA = Tuple[float, float, float, float]

SUPPORTED_RECIPES = frozenset([
    "plaster", "brick", "concrete", "timber",
    "stone", "metal_panel", "glass", "solid",
])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def make(
    recipe_name: str,
    mat_name: str,
    rgba: RGBA,
    roughness: float = 0.72,
    metallic: float = 0.0,
    seed: int = 0,
    strength: float = 1.0,
) -> "bpy.types.Material":
    """Create a Blender material using the named Tycoon recipe.

    Parameters
    ----------
    recipe_name : str    One of SUPPORTED_RECIPES.
    mat_name    : str    Blender material data-block name.
    rgba        : tuple  (R, G, B, A) base/tint colour in [0, 1].
    roughness   : float  PBR roughness (some recipes add variation on top).
    metallic    : float  PBR metallic factor.
    seed        : int    Deterministic variation seed (affects noise phases etc.).
    strength    : float  Overall procedural variation strength in [0, 1].
    """
    key = recipe_name.lower().strip()
    if key not in SUPPORTED_RECIPES:
        raise ValueError(
            f"Unknown material recipe '{recipe_name}'. "
            f"Supported: {sorted(SUPPORTED_RECIPES)}"
        )
    _builders = {
        "plaster":     _plaster,
        "brick":       _brick,
        "concrete":    _concrete,
        "timber":      _timber,
        "stone":       _stone,
        "metal_panel": _metal_panel,
        "glass":       _glass,
        "solid":       _solid,
    }
    return _builders[key](mat_name, rgba, roughness, metallic, seed, strength)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _new_mat(name: str):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    return mat, mat.node_tree


def _n(tree, type_name: str, loc: tuple = (0, 0)):
    """Add a node and set its location."""
    node = tree.nodes.new(type_name)
    node.location = loc
    return node


def _l(tree, src, src_sock, dst, dst_sock):
    """Link two nodes."""
    tree.links.new(src.outputs[src_sock], dst.inputs[dst_sock])


def _darken(rgba: RGBA, factor: float) -> RGBA:
    return (rgba[0] * factor, rgba[1] * factor, rgba[2] * factor, rgba[3])


# ---------------------------------------------------------------------------
# Recipe builders
# ---------------------------------------------------------------------------


def _solid(name, rgba, roughness, metallic, seed, strength):
    """Flat colour — no procedural variation (backward-compatible legacy mode)."""
    mat, tree = _new_mat(name)
    output = _n(tree, "ShaderNodeOutputMaterial", (600, 0))
    bsdf = _n(tree, "ShaderNodeBsdfPrincipled", (0, 0))
    bsdf.inputs["Base Color"].default_value = tuple(rgba)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    _l(tree, bsdf, "BSDF", output, "Surface")
    return mat


def _plaster(name, rgba, roughness, metallic, seed, strength):
    """Smooth painted stucco with subtle micro-surface noise bump."""
    mat, tree = _new_mat(name)
    output = _n(tree, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = _n(tree, "ShaderNodeBsdfPrincipled", (500, 0))
    bsdf.inputs["Base Color"].default_value = tuple(rgba)
    bsdf.inputs["Roughness"].default_value = max(0.60, roughness)
    bsdf.inputs["Metallic"].default_value = 0.0

    noise = _n(tree, "ShaderNodeTexNoise", (-300, -200))
    noise.inputs["Scale"].default_value = 30.0 + (seed % 7) * 0.8
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Roughness"].default_value = 0.60
    noise.inputs["Distortion"].default_value = 0.08

    bump = _n(tree, "ShaderNodeBump", (100, -200))
    bump.inputs["Strength"].default_value = 0.10 * strength
    bump.inputs["Distance"].default_value = 0.006

    _l(tree, noise, "Fac", bump, "Height")
    _l(tree, bump, "Normal", bsdf, "Normal")
    _l(tree, bsdf, "BSDF", output, "Surface")
    return mat


def _brick(name, rgba, roughness, metallic, seed, strength):
    """Mortared brick via the built-in Brick Texture node with noise colour variation."""
    mat, tree = _new_mat(name)
    output = _n(tree, "ShaderNodeOutputMaterial", (1200, 0))
    bsdf = _n(tree, "ShaderNodeBsdfPrincipled", (700, 0))
    bsdf.inputs["Roughness"].default_value = max(0.78, roughness)
    bsdf.inputs["Metallic"].default_value = 0.0

    tex_coord = _n(tree, "ShaderNodeTexCoord", (-900, 0))
    mapping = _n(tree, "ShaderNodeMapping", (-700, 0))
    mapping.inputs["Scale"].default_value = (4.0 + seed % 3, 3.5, 1.0)

    brick_tex = _n(tree, "ShaderNodeTexBrick", (-400, 100))
    brick_tex.inputs["Color1"].default_value = tuple(rgba)
    brick_tex.inputs["Color2"].default_value = _darken(rgba, 0.85)
    brick_tex.inputs["Mortar"].default_value = (0.28, 0.26, 0.24, 1.0)
    brick_tex.inputs["Scale"].default_value = 1.0
    brick_tex.inputs["Mortar Size"].default_value = 0.038
    brick_tex.inputs["Bias"].default_value = seed * 0.01
    brick_tex.inputs["Brick Width"].default_value = 0.50
    brick_tex.inputs["Row Height"].default_value = 0.25

    noise = _n(tree, "ShaderNodeTexNoise", (-650, -200))
    noise.inputs["Scale"].default_value = 15.0
    noise.inputs["Detail"].default_value = 4.0
    noise.inputs["Roughness"].default_value = 0.55

    col_mix = _n(tree, "ShaderNodeMixRGB", (-100, -50))
    col_mix.blend_type = "MULTIPLY"
    col_mix.inputs["Fac"].default_value = 0.22 * strength

    bump = _n(tree, "ShaderNodeBump", (300, -250))
    bump.inputs["Strength"].default_value = 0.38 * strength
    bump.inputs["Distance"].default_value = 0.018

    _l(tree, tex_coord, "UV", mapping, "Vector")
    _l(tree, mapping, "Vector", brick_tex, "Vector")
    _l(tree, mapping, "Vector", noise, "Vector")
    _l(tree, brick_tex, "Color", col_mix, "Color1")
    _l(tree, noise, "Fac", col_mix, "Color2")
    _l(tree, col_mix, "Color", bsdf, "Base Color")
    _l(tree, brick_tex, "Fac", bump, "Height")
    _l(tree, bump, "Normal", bsdf, "Normal")
    _l(tree, bsdf, "BSDF", output, "Surface")
    return mat


def _concrete(name, rgba, roughness, metallic, seed, strength):
    """Poured concrete — dual-layer noise, high roughness."""
    mat, tree = _new_mat(name)
    output = _n(tree, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = _n(tree, "ShaderNodeBsdfPrincipled", (500, 0))
    bsdf.inputs["Roughness"].default_value = max(0.82, roughness)
    bsdf.inputs["Metallic"].default_value = 0.0

    tex_coord = _n(tree, "ShaderNodeTexCoord", (-800, 0))
    mapping = _n(tree, "ShaderNodeMapping", (-600, 0))
    mapping.inputs["Scale"].default_value = (5.0, 5.0, 1.0)

    # Large-scale form noise
    noise1 = _n(tree, "ShaderNodeTexNoise", (-350, 120))
    noise1.inputs["Scale"].default_value = 6.0 + seed % 4
    noise1.inputs["Detail"].default_value = 12.0
    noise1.inputs["Roughness"].default_value = 0.72
    noise1.inputs["Distortion"].default_value = 0.20

    # Fine speckle noise
    noise2 = _n(tree, "ShaderNodeTexNoise", (-350, -120))
    noise2.inputs["Scale"].default_value = 80.0
    noise2.inputs["Detail"].default_value = 4.0
    noise2.inputs["Roughness"].default_value = 0.55

    col_mix = _n(tree, "ShaderNodeMixRGB", (50, 0))
    col_mix.blend_type = "MULTIPLY"
    col_mix.inputs["Fac"].default_value = 0.18 * strength
    col_mix.inputs["Color1"].default_value = tuple(rgba)

    bump = _n(tree, "ShaderNodeBump", (200, -250))
    bump.inputs["Strength"].default_value = 0.30 * strength
    bump.inputs["Distance"].default_value = 0.014

    _l(tree, tex_coord, "UV", mapping, "Vector")
    _l(tree, mapping, "Vector", noise1, "Vector")
    _l(tree, mapping, "Vector", noise2, "Vector")
    _l(tree, noise1, "Fac", col_mix, "Color2")
    _l(tree, col_mix, "Color", bsdf, "Base Color")
    _l(tree, noise2, "Fac", bump, "Height")
    _l(tree, bump, "Normal", bsdf, "Normal")
    _l(tree, bsdf, "BSDF", output, "Surface")
    return mat


def _timber(name, rgba, roughness, metallic, seed, strength):
    """Painted timber — Wave Texture grain with subtle colour variation."""
    mat, tree = _new_mat(name)
    output = _n(tree, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = _n(tree, "ShaderNodeBsdfPrincipled", (500, 0))
    bsdf.inputs["Roughness"].default_value = max(0.70, roughness)
    bsdf.inputs["Metallic"].default_value = 0.0

    tex_coord = _n(tree, "ShaderNodeTexCoord", (-800, 0))
    mapping = _n(tree, "ShaderNodeMapping", (-600, 0))
    mapping.inputs["Scale"].default_value = (8.0, 2.0, 1.0)

    wave = _n(tree, "ShaderNodeTexWave", (-350, 120))
    wave.wave_type = "BANDS"
    wave.inputs["Scale"].default_value = 6.0 + seed % 3
    wave.inputs["Distortion"].default_value = 1.2
    wave.inputs["Detail"].default_value = 8.0
    wave.inputs["Detail Scale"].default_value = 1.5

    noise = _n(tree, "ShaderNodeTexNoise", (-350, -120))
    noise.inputs["Scale"].default_value = 20.0
    noise.inputs["Detail"].default_value = 4.0

    grain_mix = _n(tree, "ShaderNodeMixRGB", (-50, 0))
    grain_mix.blend_type = "MULTIPLY"
    grain_mix.inputs["Fac"].default_value = 0.14 * strength
    grain_mix.inputs["Color1"].default_value = tuple(rgba)

    bump = _n(tree, "ShaderNodeBump", (200, -250))
    bump.inputs["Strength"].default_value = 0.20 * strength
    bump.inputs["Distance"].default_value = 0.008

    _l(tree, tex_coord, "UV", mapping, "Vector")
    _l(tree, mapping, "Vector", wave, "Vector")
    _l(tree, mapping, "Vector", noise, "Vector")
    _l(tree, wave, "Fac", grain_mix, "Color2")
    _l(tree, grain_mix, "Color", bsdf, "Base Color")
    _l(tree, noise, "Fac", bump, "Height")
    _l(tree, bump, "Normal", bsdf, "Normal")
    _l(tree, bsdf, "BSDF", output, "Surface")
    return mat


def _stone(name, rgba, roughness, metallic, seed, strength):
    """Rough-cut ashlar stone — Voronoi cells for stone joints + noise surface."""
    mat, tree = _new_mat(name)
    output = _n(tree, "ShaderNodeOutputMaterial", (1000, 0))
    bsdf = _n(tree, "ShaderNodeBsdfPrincipled", (600, 0))
    bsdf.inputs["Roughness"].default_value = max(0.88, roughness)
    bsdf.inputs["Metallic"].default_value = 0.0

    tex_coord = _n(tree, "ShaderNodeTexCoord", (-800, 0))
    mapping = _n(tree, "ShaderNodeMapping", (-600, 0))
    mapping.inputs["Scale"].default_value = (3.5 + seed * 0.15, 3.5, 1.0)

    voronoi = _n(tree, "ShaderNodeTexVoronoi", (-350, 120))
    voronoi.voronoi_dimensions = "3D"
    voronoi.distance = "EUCLIDEAN"
    voronoi.inputs["Scale"].default_value = 4.0
    voronoi.inputs["Randomness"].default_value = 0.85

    noise = _n(tree, "ShaderNodeTexNoise", (-350, -120))
    noise.inputs["Scale"].default_value = 12.0
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.65

    # Colour ramp maps voronoi distance to light/dark stone face
    ramp = _n(tree, "ShaderNodeValToRGB", (-50, 120))
    ramp.color_ramp.elements[0].color = _darken(rgba, 0.80)
    ramp.color_ramp.elements[1].color = tuple(rgba)

    bump = _n(tree, "ShaderNodeBump", (200, -250))
    bump.inputs["Strength"].default_value = 0.45 * strength
    bump.inputs["Distance"].default_value = 0.022

    _l(tree, tex_coord, "UV", mapping, "Vector")
    _l(tree, mapping, "Vector", voronoi, "Vector")
    _l(tree, mapping, "Vector", noise, "Vector")
    _l(tree, voronoi, "Distance", ramp, "Fac")
    _l(tree, ramp, "Color", bsdf, "Base Color")
    _l(tree, voronoi, "Distance", bump, "Height")
    _l(tree, bump, "Normal", bsdf, "Normal")
    _l(tree, bsdf, "BSDF", output, "Surface")
    return mat


def _metal_panel(name, rgba, roughness, metallic, seed, strength):
    """Painted metal panel — slight metallic sheen with noise-driven scratch roughness."""
    mat, tree = _new_mat(name)
    output = _n(tree, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = _n(tree, "ShaderNodeBsdfPrincipled", (500, 0))
    bsdf.inputs["Base Color"].default_value = tuple(rgba)
    bsdf.inputs["Metallic"].default_value = max(0.25, metallic)

    # Fine noise for scratch/wear roughness variation
    noise = _n(tree, "ShaderNodeTexNoise", (-350, -120))
    noise.inputs["Scale"].default_value = 40.0
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Roughness"].default_value = 0.70

    ramp = _n(tree, "ShaderNodeValToRGB", (-50, -120))
    ramp.color_ramp.elements[0].position = 0.42
    ramp.color_ramp.elements[1].position = 0.55
    low = max(0.0, min(1.0, roughness))
    high = max(0.0, min(1.0, roughness + 0.20))
    ramp.color_ramp.elements[0].color = (low, low, low, 1.0)
    ramp.color_ramp.elements[1].color = (high, high, high, 1.0)

    bump = _n(tree, "ShaderNodeBump", (200, -300))
    bump.inputs["Strength"].default_value = 0.06 * strength
    bump.inputs["Distance"].default_value = 0.004

    _l(tree, noise, "Fac", ramp, "Fac")
    _l(tree, ramp, "Color", bsdf, "Roughness")
    _l(tree, noise, "Fac", bump, "Height")
    _l(tree, bump, "Normal", bsdf, "Normal")
    _l(tree, bsdf, "BSDF", output, "Surface")
    return mat


def _glass(name, rgba, roughness, metallic, seed, strength):
    """Window glass — Principled BSDF transmission with tinted base colour."""
    mat, tree = _new_mat(name)
    mat.use_backface_culling = False
    output = _n(tree, "ShaderNodeOutputMaterial", (700, 0))
    bsdf = _n(tree, "ShaderNodeBsdfPrincipled", (200, 0))

    # Tint: blues/greens come from the rgba but kept mostly transparent
    tint = (rgba[0] * 0.40, rgba[1] * 0.52, rgba[2] * 0.65, 1.0)
    bsdf.inputs["Base Color"].default_value = tint
    bsdf.inputs["Roughness"].default_value = min(0.18, roughness)
    bsdf.inputs["Metallic"].default_value = 0.0

    # Blender 4.x uses "Transmission Weight"; older uses "Transmission"
    for key in ("Transmission Weight", "Transmission"):
        try:
            bsdf.inputs[key].default_value = 0.82
            break
        except KeyError:
            continue

    try:
        bsdf.inputs["IOR"].default_value = 1.45
    except KeyError:
        pass

    _l(tree, bsdf, "BSDF", output, "Surface")
    return mat
