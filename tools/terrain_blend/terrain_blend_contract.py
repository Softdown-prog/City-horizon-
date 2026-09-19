"""
CH_TERRAIN_BLEND_V1 Contract & Metadata Definitions.
Defines schemas, material priorities, core preservation bounds, and hashing utilities for terrain autotiling.
"""

import os
import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

kTerrainBlendContract = "CH_TERRAIN_BLEND_V1"
kGeneratorVersion = "1.0.0"


@dataclass
class TerrainMaterialSpec:
    id: str
    priority: int
    texture: str
    texture_space: str = "world"

    @classmethod
    def from_dict(cls, mat_id: str, data: Dict[str, Any], base_dir: str) -> "TerrainMaterialSpec":
        tex_path = data["texture"]
        if not os.path.isabs(tex_path):
            p1 = os.path.normpath(os.path.join(base_dir, tex_path))
            if os.path.exists(p1):
                tex_path = p1
            else:
                repo_root = os.path.abspath(os.path.join(base_dir, "..", ".."))
                tex_path = os.path.normpath(os.path.join(repo_root, tex_path))
        return cls(
            id=mat_id,
            priority=int(data.get("priority", 100)),
            texture=tex_path,
            texture_space=data.get("textureSpace", "world")
        )


@dataclass
class TerrainMaterialsManifest:
    contract: str
    default_style: str
    minimum_core_area_ratio: float
    materials: Dict[str, TerrainMaterialSpec]

    @classmethod
    def from_dict(cls, data: Dict[str, Any], json_dir: str) -> "TerrainMaterialsManifest":
        if data.get("contract") != kTerrainBlendContract:
            raise ValueError(f"Invalid contract '{data.get('contract')}'. Expected '{kTerrainBlendContract}'")

        style = data.get("defaultStyle", "organic")
        core_cfg = data.get("corePreservation", {})
        min_core_ratio = float(core_cfg.get("minimumCoreAreaRatio", 0.08))

        mats = {}
        for m_id, m_data in data.get("materials", {}).items():
            mats[m_id] = TerrainMaterialSpec.from_dict(m_id, m_data, json_dir)

        return cls(
            contract=data["contract"],
            default_style=style,
            minimum_core_area_ratio=min_core_ratio,
            materials=mats
        )

    @classmethod
    def load_from_file(cls, filepath: str) -> "TerrainMaterialsManifest":
        json_dir = os.path.dirname(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data, json_dir)


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
class BlendSidecarMetadata:
    contract: str
    generator_version: str
    tile_coord: List[int]  # [x, y]
    base_material: str
    overlay_material: str
    active_primitives: List[str]
    output_sha256: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "generatorVersion": self.generator_version,
            "tileCoord": self.tile_coord,
            "baseMaterial": self.base_material,
            "overlayMaterial": self.overlay_material,
            "activePrimitives": self.active_primitives,
            "output_sha256": self.output_sha256,
        }

    def save(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
