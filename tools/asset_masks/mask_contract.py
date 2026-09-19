"""
CH_MASK_V1 Contract & Metadata Definitions.
Defines canonical constants, schemas, and SHA-256 hashing utilities for the 8-bit indexed mask system.
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

kMaskContract = "CH_MASK_V1"
kGeneratorVersion = "1.0.0"
kAlgorithmVersion = "1.0.0"
kColorSpace = "linear_rgb_srgb"


@dataclass
class RegionRecipe:
    mode: str = "recolor"  # "recolor" or "texture"
    target_rgb: Optional[List[int]] = None  # e.g. [220, 190, 140]
    texture: Optional[str] = None  # Path to seamless material texture
    texture_space: str = "world"  # "world" or "tile"
    scale: float = 1.0
    offset: List[float] = field(default_factory=lambda: [0.0, 0.0])
    preserve_shading: bool = True
    hue_shift: float = 0.0
    saturation: float = 1.0
    brightness: float = 1.0
    wear: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any], json_dir: str) -> "RegionRecipe":
        mode = data.get("mode", "recolor")
        target_rgb = data.get("targetRGB")
        tex_path = data.get("texture")
        if tex_path and not os.path.isabs(tex_path):
            tex_path = os.path.normpath(os.path.join(json_dir, tex_path))

        return cls(
            mode=mode,
            target_rgb=list(target_rgb) if target_rgb else None,
            texture=tex_path,
            texture_space=data.get("textureSpace", "world"),
            scale=float(data.get("scale", 1.0)),
            offset=list(data.get("offset", [0.0, 0.0])),
            preserve_shading=bool(data.get("preserveShading", True)),
            hue_shift=float(data.get("hueShift", 0.0)),
            saturation=float(data.get("saturation", 1.0)),
            brightness=float(data.get("brightness", 1.0)),
            wear=float(data.get("wear", 0.0))
        )


@dataclass
class VariantConfig:
    id: str
    region_recipes: Dict[str, RegionRecipe]
    wear: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any], json_dir: str, regions_map: Dict[str, int]) -> "VariantConfig":
        vid = data["id"]
        wear_val = float(data.get("wear", 0.0))
        recipes = {}

        # Parse region recipes defined under "region_recipes" or root region keys
        recipe_source = data.get("region_recipes", data)
        for r_name in regions_map.keys():
            if r_name in recipe_source and isinstance(recipe_source[r_name], dict):
                recipes[r_name] = RegionRecipe.from_dict(recipe_source[r_name], json_dir)
            elif r_name in data and isinstance(data[r_name], list):
                # Legacy simple RGB array shorthand
                recipes[r_name] = RegionRecipe(mode="recolor", target_rgb=list(data[r_name]))

        return cls(id=vid, region_recipes=recipes, wear=wear_val)


@dataclass
class MaskAssetManifest:
    contract: str
    asset_id: str
    base: str  # Path to canonical base sprite
    semantic_mask: str  # Path to 8-bit grayscale region mask (mode: "L")
    regions: Dict[str, int]  # Mapping: {"wall": 1, "roof": 2, "trim": 3, ...}
    variants: List[VariantConfig]

    @classmethod
    def from_dict(cls, data: Dict[str, Any], json_dir: str) -> "MaskAssetManifest":
        if data.get("contract") != kMaskContract:
            raise ValueError(f"Invalid contract '{data.get('contract')}'. Expected '{kMaskContract}'")

        asset_id = data["assetId"]
        base_path = data["base"]
        mask_path = data.get("semanticMask", data.get("colorMask"))

        if not os.path.isabs(base_path):
            base_path = os.path.normpath(os.path.join(json_dir, base_path))
        if mask_path and not os.path.isabs(mask_path):
            mask_path = os.path.normpath(os.path.join(json_dir, mask_path))

        regions_map = data.get("regions", {})
        if not regions_map and "channels" in data:
            # Legacy R, G, B channel string mapping
            channel_letters = {"R": 1, "G": 2, "B": 3}
            for ch_letter, r_name in data["channels"].items():
                if ch_letter in channel_letters:
                    regions_map[r_name] = channel_letters[ch_letter]

        variants = []
        for vdata in data.get("variants", []):
            variants.append(VariantConfig.from_dict(vdata, json_dir, regions_map))

        return cls(
            contract=data["contract"],
            asset_id=asset_id,
            base=base_path,
            semantic_mask=mask_path,
            regions=regions_map,
            variants=variants,
        )


def compute_file_sha256(filepath: str) -> str:
    """Computes SHA-256 hash of a file on disk."""
    if not filepath or not os.path.exists(filepath):
        return ""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclass
class SidecarMetadata:
    contract: str
    generator_version: str
    algorithm_version: str
    color_space: str
    asset_id: str
    variant_id: str
    base_sha256: str
    semantic_mask_sha256: str
    manifest_sha256: str
    material_sha256: Optional[str]
    output_sha256: str

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "contract": self.contract,
            "generatorVersion": self.generator_version,
            "algorithmVersion": self.algorithm_version,
            "colorSpace": self.color_space,
            "assetId": self.asset_id,
            "variantId": self.variant_id,
            "base_sha256": self.base_sha256,
            "semantic_mask_sha256": self.semantic_mask_sha256,
            "manifest_sha256": self.manifest_sha256,
            "output_sha256": self.output_sha256,
        }
        if self.material_sha256:
            d["material_sha256"] = self.material_sha256
        return d

    def save(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
