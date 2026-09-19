"""
Recolor & Texture Processing Engine for CH_MASK_V1.
Applies data-driven region recoloring or seamless texture replacement with linear RGB shading options and deterministic wear.
Pure PIL / Python implementation.
"""

import os
import json
import statistics
from typing import Dict, Any, Tuple, Optional, List
from PIL import Image

from tools.asset_masks.mask_contract import (
    MaskAssetManifest, VariantConfig, RegionRecipe, SidecarMetadata,
    kMaskContract, kGeneratorVersion, kAlgorithmVersion, kColorSpace,
    compute_file_sha256
)
from tools.asset_masks.validate_mask_asset import validate_mask_asset

# Gamma 2.2 LUTs for fast conversion
SRGB_TO_LIN_LUT = [(i / 255.0) ** 2.2 for i in range(256)]


def lin_to_srgb_byte(v: float) -> int:
    """Converts Linear float [0..1] to sRGB byte [0..255]."""
    if v <= 0.0:
        return 0
    if v >= 1.0:
        return 255
    return int(round((v ** (1.0 / 2.2)) * 255.0))


def compute_linear_luminance(lin_r: float, lin_g: float, lin_b: float) -> float:
    """Computes relative linear luminance L = 0.2126R + 0.7152G + 0.0722B."""
    return 0.2126 * lin_r + 0.7152 * lin_g + 0.0722 * lin_b


def apply_variant_to_image(
    base_img: Image.Image,
    semantic_mask_img: Image.Image,
    manifest: MaskAssetManifest,
    variant: VariantConfig
) -> Image.Image:
    """
    Applies variant recoloring/texture replacement to base sprite in linear RGB space.
    Returns new RGBA Image with byte-identical alpha and unmasked pixel preservation.
    """
    w, h = base_img.size
    num_pixels = w * h

    base_bytes = base_img.tobytes()
    mask_l_img = semantic_mask_img.convert("L")
    mask_bytes = mask_l_img.tobytes()

    # Reverse mapping from region ID (int) -> region name (str)
    id_to_region = {r_id: r_name for r_name, r_id in manifest.regions.items()}

    # Pre-calculate linear luminance for all base pixels
    base_lin_lum = [0.0] * num_pixels
    for i in range(num_pixels):
        offset = i * 4
        bR = base_bytes[offset]
        bG = base_bytes[offset + 1]
        bB = base_bytes[offset + 2]
        base_lin_lum[i] = compute_linear_luminance(
            SRGB_TO_LIN_LUT[bR],
            SRGB_TO_LIN_LUT[bG],
            SRGB_TO_LIN_LUT[bB]
        )

    # Calculate region reference linear luminance (median) for each active region ID
    region_l_ref = {}
    for r_name, r_id in manifest.regions.items():
        region_lums = []
        for i in range(num_pixels):
            if mask_bytes[i] == r_id:
                region_lums.append(base_lin_lum[i])
        if region_lums:
            l_median = statistics.median(region_lums)
            region_l_ref[r_name] = max(0.001, l_median)

    # Pre-load material textures for "texture" mode recipes
    material_cache = {}
    for r_name, recipe in variant.region_recipes.items():
        if recipe.mode == "texture" and recipe.texture and os.path.exists(recipe.texture):
            mat_img = Image.open(recipe.texture).convert("RGBA")
            material_cache[r_name] = {
                "img": mat_img,
                "bytes": mat_img.tobytes(),
                "w": mat_img.width,
                "h": mat_img.height
            }

    output_bytes = bytearray(len(base_bytes))

    for i in range(num_pixels):
        offset = i * 4
        bR = base_bytes[offset]
        bG = base_bytes[offset + 1]
        bB = base_bytes[offset + 2]
        bA = base_bytes[offset + 3]

        r_id = mask_bytes[i]

        # Invariant 1: regionID == 0 or bA == 0 -> byte-identical copy of base RGBA
        if r_id == 0 or bA == 0:
            output_bytes[offset] = bR
            output_bytes[offset + 1] = bG
            output_bytes[offset + 2] = bB
            output_bytes[offset + 3] = bA
            continue

        r_name = id_to_region.get(r_id)
        recipe = variant.region_recipes.get(r_name) if r_name else None

        if not recipe:
            # Unmapped region recipe -> byte-identical copy
            output_bytes[offset] = bR
            output_bytes[offset + 1] = bG
            output_bytes[offset + 2] = bB
            output_bytes[offset + 3] = bA
            continue

        lin_r = SRGB_TO_LIN_LUT[bR]
        lin_g = SRGB_TO_LIN_LUT[bG]
        lin_b = SRGB_TO_LIN_LUT[bB]
        cur_lum = base_lin_lum[i]

        l_ref = region_l_ref.get(r_name, 0.5)
        shade = min(3.0, max(0.05, cur_lum / l_ref))

        out_lin_r = lin_r
        out_lin_g = lin_g
        out_lin_b = lin_b

        # MODE 1: RECOLOR
        if recipe.mode == "recolor":
            if recipe.target_rgb:
                t_lin_r = SRGB_TO_LIN_LUT[recipe.target_rgb[0]]
                t_lin_g = SRGB_TO_LIN_LUT[recipe.target_rgb[1]]
                t_lin_b = SRGB_TO_LIN_LUT[recipe.target_rgb[2]]

                if recipe.preserve_shading:
                    out_lin_r = t_lin_r * shade
                    out_lin_g = t_lin_g * shade
                    out_lin_b = t_lin_b * shade
                else:
                    out_lin_r = t_lin_r
                    out_lin_g = t_lin_g
                    out_lin_b = t_lin_b

        # MODE 2: TEXTURE
        elif recipe.mode == "texture" and r_name in material_cache:
            mat = material_cache[r_name]
            mat_w, mat_h = mat["w"], mat["h"]
            mat_bytes = mat["bytes"]

            x = i % w
            y = i // w

            # Deterministic UV sampling with scale and offset
            tx = int(round(x * recipe.scale + recipe.offset[0])) % mat_w
            ty = int(round(y * recipe.scale + recipe.offset[1])) % mat_h

            m_offset = (ty * mat_w + tx) * 4
            m_r = mat_bytes[m_offset]
            m_g = mat_bytes[m_offset + 1]
            m_b = mat_bytes[m_offset + 2]

            m_lin_r = SRGB_TO_LIN_LUT[m_r]
            m_lin_g = SRGB_TO_LIN_LUT[m_g]
            m_lin_b = SRGB_TO_LIN_LUT[m_b]

            if recipe.preserve_shading:
                out_lin_r = m_lin_r * shade
                out_lin_g = m_lin_g * shade
                out_lin_b = m_lin_b * shade
            else:
                out_lin_r = m_lin_r
                out_lin_g = m_lin_g
                out_lin_b = m_lin_b

        # WEAR MATH
        effective_wear = recipe.wear if recipe.wear > 0.0 else variant.wear
        final_wear = min(1.0, max(0.0, effective_wear))

        if final_wear > 0.0:
            darkening = 1.0 - 0.35 * final_wear
            out_lin_r *= darkening
            out_lin_g *= darkening
            out_lin_b *= darkening

            wear_lum = compute_linear_luminance(out_lin_r, out_lin_g, out_lin_b)
            desat = 0.40 * final_wear
            out_lin_r = (1.0 - desat) * out_lin_r + desat * wear_lum
            out_lin_g = (1.0 - desat) * out_lin_g + desat * wear_lum
            out_lin_b = (1.0 - desat) * out_lin_b + desat * wear_lum

        output_bytes[offset] = lin_to_srgb_byte(out_lin_r)
        output_bytes[offset + 1] = lin_to_srgb_byte(out_lin_g)
        output_bytes[offset + 2] = lin_to_srgb_byte(out_lin_b)
        output_bytes[offset + 3] = bA  # BYTE-IDENTICAL ALPHA PRESERVATION

    return Image.frombytes("RGBA", (w, h), bytes(output_bytes))


def process_mask_manifest(
    manifest_path: str,
    output_dir: str
) -> Tuple[List[str], List[str]]:
    """
    Validates manifest, generates all variant PNGs and sidecar metadata JSONs.
    Returns (generated_png_paths, generated_json_paths).
    """
    json_dir = os.path.dirname(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    manifest = MaskAssetManifest.from_dict(data, json_dir)
    validate_mask_asset(manifest)

    base_img = Image.open(manifest.base).convert("RGBA")
    mask_img = Image.open(manifest.semantic_mask).convert("L")

    # Calculate input SHA-256 hashes
    sha256_base = compute_file_sha256(manifest.base)
    sha256_mask = compute_file_sha256(manifest.semantic_mask)
    sha256_manifest = compute_file_sha256(manifest_path)

    os.makedirs(output_dir, exist_ok=True)

    generated_pngs = []
    generated_jsons = []

    for variant in manifest.variants:
        variant_img = apply_variant_to_image(base_img, mask_img, manifest, variant)

        output_png_name = f"{manifest.asset_id}_{variant.id}.png"
        output_png_path = os.path.join(output_dir, output_png_name)

        # Deterministic PNG save without metadata chunks
        variant_img.save(output_png_path, format="PNG", pnginfo=None)
        generated_pngs.append(output_png_path)

        sha256_output = compute_file_sha256(output_png_path)

        # Find material texture sha256 if any recipe uses "texture" mode
        mat_sha256 = None
        for recipe in variant.region_recipes.values():
            if recipe.mode == "texture" and recipe.texture:
                mat_sha256 = compute_file_sha256(recipe.texture)
                break

        sidecar = SidecarMetadata(
            contract=kMaskContract,
            generator_version=kGeneratorVersion,
            algorithm_version=kAlgorithmVersion,
            color_space=kColorSpace,
            asset_id=manifest.asset_id,
            variant_id=variant.id,
            base_sha256=sha256_base,
            semantic_mask_sha256=sha256_mask,
            manifest_sha256=sha256_manifest,
            material_sha256=mat_sha256,
            output_sha256=sha256_output
        )

        output_json_name = f"{manifest.asset_id}_{variant.id}.json"
        output_json_path = os.path.join(output_dir, output_json_name)
        sidecar.save(output_json_path)
        generated_jsons.append(output_json_path)

    return generated_pngs, generated_jsons
