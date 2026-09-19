"""
Validation Engine for CH_MASK_V1 Asset Masks.
Enforces strict fail-closed validation for indexed 8-bit region masks, manifests, and material textures.
Pure PIL / Standard Python implementation.
"""

import os
from typing import List, Tuple, Dict, Any
from PIL import Image

from tools.asset_masks.mask_contract import MaskAssetManifest, kMaskContract


class MaskValidationError(Exception):
    """Raised when a mask asset violates CH_MASK_V1 contracts."""
    pass


def validate_mask_asset(manifest: MaskAssetManifest) -> List[str]:
    """
    Validates a MaskAssetManifest against all CH_MASK_V1 rules.
    Returns list of warning messages if valid, or raises MaskValidationError if invalid.
    """
    warnings: List[str] = []

    # 1. File existence
    if not os.path.exists(manifest.base):
        raise MaskValidationError(f"Base sprite missing: '{manifest.base}'")
    if not os.path.exists(manifest.semantic_mask):
        raise MaskValidationError(f"Semantic mask missing: '{manifest.semantic_mask}'")

    # 2. Check duplicate region IDs in manifest
    id_seen = set()
    for r_name, r_id in manifest.regions.items():
        if r_id in id_seen:
            raise MaskValidationError(f"Duplicate region ID {r_id} declared for region '{r_name}' in manifest.")
        id_seen.add(r_id)

    # 3. Open images and check modes/dimensions
    try:
        with Image.open(manifest.base) as base_img:
            base_mode = base_img.mode
            base_size = base_img.size
            base_bytes = base_img.tobytes()
    except Exception as e:
        raise MaskValidationError(f"Failed to open base sprite '{manifest.base}': {e}")

    try:
        with Image.open(manifest.semantic_mask) as mask_img:
            mask_size = mask_img.size
            mask_l_img = mask_img.convert("L")
            mask_bytes = mask_l_img.tobytes()
    except Exception as e:
        raise MaskValidationError(f"Failed to open semantic mask '{manifest.semantic_mask}': {e}")

    if base_mode != "RGBA":
        raise MaskValidationError(f"Base sprite mode is '{base_mode}', expected 'RGBA'")

    if base_size != mask_size:
        raise MaskValidationError(
            f"Dimension mismatch: base is {base_size}, semantic mask is {mask_size}"
        )

    num_pixels = base_size[0] * base_size[1]
    declared_ids = set(manifest.regions.values())

    first_trans_coord = None
    first_unmapped_coord = None
    unmapped_id = None
    trans_count = 0
    unmapped_count = 0

    # 4. Pixel validation loop
    for i in range(num_pixels):
        bA = base_bytes[i * 4 + 3]
        r_id = mask_bytes[i]

        # Strict Rule: if baseAlpha == 0: regionID MUST == 0
        if bA == 0 and r_id != 0:
            trans_count += 1
            if first_trans_coord is None:
                first_trans_coord = (i % base_size[0], i // base_size[0], r_id)

        # Strict Rule: any non-zero regionID used by mask MUST exist in manifest.regions
        if r_id != 0 and r_id not in declared_ids:
            unmapped_count += 1
            if first_unmapped_coord is None:
                first_unmapped_coord = (i % base_size[0], i // base_size[0])
                unmapped_id = r_id

    if trans_count > 0:
        x, y, rid = first_trans_coord
        raise MaskValidationError(
            f"Invalid active region ID {rid} over transparent base alpha (Alpha==0) at pixel ({x}, {y}). "
            f"CH_MASK_V1 strictly enforces: if baseAlpha == 0, regionID MUST == 0 ({trans_count} invalid pixels found)."
        )

    if unmapped_count > 0:
        x, y = first_unmapped_coord
        raise MaskValidationError(
            f"Undeclared region ID {unmapped_id} used at pixel ({x}, {y}) but missing from manifest.regions. "
            f"({unmapped_count} unmapped pixels found)."
        )

    # 5. Variants & Recipes Validation
    if not manifest.variants:
        raise MaskValidationError("Manifest contains 0 variants definitions.")

    for variant in manifest.variants:
        for r_name, recipe in variant.region_recipes.items():
            if r_name not in manifest.regions:
                raise MaskValidationError(
                    f"Variant '{variant.id}' recipe references region '{r_name}' which is missing from manifest.regions."
                )

            # Validate texture material file if mode is "texture"
            if recipe.mode == "texture":
                if not recipe.texture or not os.path.exists(recipe.texture):
                    raise MaskValidationError(
                        f"Variant '{variant.id}' recipe for region '{r_name}' references missing material texture: '{recipe.texture}'"
                    )
                try:
                    with Image.open(recipe.texture) as mat_img:
                        if mat_img.mode not in ("RGB", "RGBA"):
                            raise MaskValidationError(
                                f"Material texture '{recipe.texture}' has unsupported mode '{mat_img.mode}'. Expected 'RGB' or 'RGBA'."
                            )
                except Exception as e:
                    raise MaskValidationError(f"Failed to open material texture '{recipe.texture}': {e}")

    return warnings
