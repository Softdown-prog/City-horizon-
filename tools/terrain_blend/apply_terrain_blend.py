"""
CH_TERRAIN_BLEND_V1 — Autotile Bitmask Resolver & Blending Engine.
Evaluates 8-neighbor adjacency, material priority hierarchy, continuous world-space texture sampling,
composable primitive mask blending, and area-based core preservation.
"""

import os
import math
from typing import List, Dict, Tuple, Optional
from PIL import Image

from tools.terrain_blend.terrain_blend_contract import (
    TerrainMaterialsManifest, TerrainMaterialSpec, BlendSidecarMetadata, compute_file_sha256
)
from tools.terrain_blend.generate_transition_masks import (
    generate_primitive_mask, compose_primitive_masks
)

# Linear RGB <-> sRGB LUTs for high-precision blending
SRGB_TO_LIN_LUT = [math.pow(i / 255.0, 2.2) for i in range(256)]
LIN_TO_SRGB_LUT = [int(round(math.pow(i / 1023.0, 1.0 / 2.2) * 255.0)) for i in range(1024)]

def sample_material_texture(
    mat_spec: TerrainMaterialSpec,
    world_pixel_x: int,
    world_pixel_y: int,
    width: int,
    height: int,
    cache: dict
) -> Tuple[int, int, int]:
    """
    Samples a terrain material texture using continuous world coordinates (textureSpace: "world").
    """
    tex_path = mat_spec.texture
    if tex_path not in cache:
        cache[tex_path] = Image.open(tex_path).convert("RGB")
    tex_img = cache[tex_path]
    tw, th = tex_img.size

    tx = world_pixel_x % tw
    ty = world_pixel_y % th
    return tex_img.getpixel((tx, ty))


def resolve_tile_blend_primitives(
    grid: List[List[str]],
    grid_x: int,
    grid_y: int,
    manifest: TerrainMaterialsManifest
) -> Tuple[str, Optional[str], List[str]]:
    """
    Evaluates 8-neighbor bitmask and material priority hierarchy for grid cell (grid_x, grid_y).
    Returns (base_material_id, overlay_material_id, list_of_active_primitive_names).
    """
    rows = len(grid)
    cols = len(grid[0]) if rows > 0 else 0

    mat_self_id = grid[grid_y][grid_x]
    self_spec = manifest.materials.get(mat_self_id, TerrainMaterialSpec(id=mat_self_id, priority=10, texture=""))
    self_priority = self_spec.priority

    # Read 8 neighbors
    def get_mat(gy: int, gx: int) -> str:
        if 0 <= gy < rows and 0 <= gx < cols:
            return grid[gy][gx]
        return mat_self_id

    neighbors = {
        "N":  get_mat(grid_y - 1, grid_x),
        "NE": get_mat(grid_y - 1, grid_x + 1),
        "E":  get_mat(grid_y, grid_x + 1),
        "SE": get_mat(grid_y + 1, grid_x + 1),
        "S":  get_mat(grid_y + 1, grid_x),
        "SW": get_mat(grid_y + 1, grid_x - 1),
        "W":  get_mat(grid_y, grid_x - 1),
        "NW": get_mat(grid_y - 1, grid_x - 1),
    }

    # Find highest priority neighbor that exceeds self priority
    highest_overlay_mat = None
    highest_prio = self_priority

    for n_id in ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]:
        n_mat = neighbors[n_id]
        n_prio = manifest.materials.get(n_mat, TerrainMaterialSpec(id=n_mat, priority=0, texture="")).priority
        if n_prio > highest_prio:
            highest_prio = n_prio
            highest_overlay_mat = n_mat

    if not highest_overlay_mat:
        return (mat_self_id, None, [])

    # Identify higher priority directions matching highest_overlay_mat
    prio_dir = {}
    for d, n_mat in neighbors.items():
        n_prio = manifest.materials.get(n_mat, TerrainMaterialSpec(id=n_mat, priority=0, texture="")).priority
        prio_dir[d] = (n_prio >= highest_prio)

    primitives = []

    # Orthogonal edge primitives
    if prio_dir["N"]: primitives.append("edge_N")
    if prio_dir["E"]: primitives.append("edge_E")
    if prio_dir["S"]: primitives.append("edge_S")
    if prio_dir["W"]: primitives.append("edge_W")

    # Corner inner primitives (where both adjacent cardinal edges encroach)
    if prio_dir["N"] and prio_dir["E"]: primitives.append("corner_inner_NE")
    if prio_dir["S"] and prio_dir["E"]: primitives.append("corner_inner_SE")
    if prio_dir["S"] and prio_dir["W"]: primitives.append("corner_inner_SW")
    if prio_dir["N"] and prio_dir["W"]: primitives.append("corner_inner_NW")

    # Corner outer primitives (where diagonal encroaches but adjacent cardinals do NOT)
    if prio_dir["NE"] and not prio_dir["N"] and not prio_dir["E"]: primitives.append("corner_outer_NE")
    if prio_dir["SE"] and not prio_dir["S"] and not prio_dir["E"]: primitives.append("corner_outer_SE")
    if prio_dir["SW"] and not prio_dir["S"] and not prio_dir["W"]: primitives.append("corner_outer_SW")
    if prio_dir["NW"] and not prio_dir["N"] and not prio_dir["W"]: primitives.append("corner_outer_NW")

    return (mat_self_id, highest_overlay_mat, primitives)


def enforce_core_preservation(
    mask_img: Image.Image,
    min_core_ratio: float = 0.08,
    width: int = 128,
    height: int = 64
) -> Image.Image:
    """
    Enforces minimumCoreAreaRatio (default 8% of isometric diamond area) for the tile's base material.
    Clamps maximum transition mask values if overlay threatens to erase the tile's logical core.
    """
    mask = mask_img.copy()
    pixels = mask.load()

    cx, cy = width / 2.0, height / 2.0
    hw, hh = width / 2.0, height / 2.0

    total_diamond_px = 0
    preserved_base_sum = 0.0

    for y in range(height):
        for x in range(width):
            if abs(x - cx) / hw + abs(y - cy) / hh <= 1.0:
                total_diamond_px += 1
                val = pixels[x, y] / 255.0
                preserved_base_sum += (1.0 - val)

    current_core_ratio = preserved_base_sum / total_diamond_px if total_diamond_px > 0 else 1.0

    if current_core_ratio < min_core_ratio:
        # Scale down mask intensity to guarantee min_core_ratio area preservation
        scale_factor = (1.0 - min_core_ratio) / (1.0 - current_core_ratio)
        scale_factor = max(0.0, min(1.0, scale_factor))

        for y in range(height):
            for x in range(width):
                if abs(x - cx) / hw + abs(y - cy) / hh <= 1.0:
                    val = int(pixels[x, y] * scale_factor)
                    pixels[x, y] = val

    return mask


def render_blended_tile(
    grid: List[List[str]],
    grid_x: int,
    grid_y: int,
    manifest: TerrainMaterialsManifest,
    width: int = 128,
    height: int = 64,
    tex_cache: dict = None
) -> Tuple[Image.Image, BlendSidecarMetadata]:
    """
    Renders a single blended 2:1 isometric tile cell for position (grid_x, grid_y).
    """
    if tex_cache is None:
        tex_cache = {}

    base_mat_id, overlay_mat_id, primitive_names = resolve_tile_blend_primitives(grid, grid_x, grid_y, manifest)

    base_spec = manifest.materials[base_mat_id]
    
    # Base tile canvas with isometric diamond alpha mask
    tile_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    tile_pixels = tile_img.load()

    cx, cy = width / 2.0, height / 2.0
    hw, hh = width / 2.0, height / 2.0

    world_origin_x = grid_x * width
    world_origin_y = grid_y * height

    # 1. If no overlay, render base material tile directly
    if not overlay_mat_id or not primitive_names:
        for y in range(height):
            for x in range(width):
                if abs(x - cx) / hw + abs(y - cy) / hh <= 1.0:
                    r, g, b = sample_material_texture(base_spec, world_origin_x + x, world_origin_y + y, width, height, tex_cache)
                    tile_pixels[x, y] = (r, g, b, 255)

        metadata = BlendSidecarMetadata(
            contract=manifest.contract,
            generator_version="1.0.0",
            tile_coord=[grid_x, grid_y],
            base_material=base_mat_id,
            overlay_material=base_mat_id,
            active_primitives=[],
            output_sha256=""
        )
        return (tile_img, metadata)

    # 2. Build composed primitive transition mask
    overlay_spec = manifest.materials[overlay_mat_id]
    primitive_imgs = []
    for p_name in primitive_names:
        p_img = generate_primitive_mask(p_name, width, height, grid_x, grid_y, manifest.default_style)
        primitive_imgs.append(p_img)

    combined_mask = compose_primitive_masks(primitive_imgs, width, height)
    final_mask = enforce_core_preservation(combined_mask, manifest.minimum_core_area_ratio, width, height)
    mask_pixels = final_mask.load()

    # 3. Blend Base and Overlay in Linear RGB space
    for y in range(height):
        for x in range(width):
            if abs(x - cx) / hw + abs(y - cy) / hh <= 1.0:
                wx = world_origin_x + x
                wy = world_origin_y + y

                rA, gA, bA = sample_material_texture(base_spec, wx, wy, width, height, tex_cache)
                rB, gB, bB = sample_material_texture(overlay_spec, wx, wy, width, height, tex_cache)

                alpha = mask_pixels[x, y] / 255.0

                lin_r = SRGB_TO_LIN_LUT[rA] * (1.0 - alpha) + SRGB_TO_LIN_LUT[rB] * alpha
                lin_g = SRGB_TO_LIN_LUT[gA] * (1.0 - alpha) + SRGB_TO_LIN_LUT[gB] * alpha
                lin_b = SRGB_TO_LIN_LUT[bA] * (1.0 - alpha) + SRGB_TO_LIN_LUT[bB] * alpha

                out_r = LIN_TO_SRGB_LUT[max(0, min(1023, int(lin_r * 1023)))]
                out_g = LIN_TO_SRGB_LUT[max(0, min(1023, int(lin_g * 1023)))]
                out_b = LIN_TO_SRGB_LUT[max(0, min(1023, int(lin_b * 1023)))]

                tile_pixels[x, y] = (out_r, out_g, out_b, 255)

    metadata = BlendSidecarMetadata(
        contract=manifest.contract,
        generator_version="1.0.0",
        tile_coord=[grid_x, grid_y],
        base_material=base_mat_id,
        overlay_material=overlay_mat_id,
        active_primitives=primitive_names,
        output_sha256=""
    )
    return (tile_img, metadata)
