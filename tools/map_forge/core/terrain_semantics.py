"""CH_TERRAIN_SEMANTICS_V1: declarative terrain behavior, independent of pixels."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

CONTRACT = "CH_TERRAIN_SEMANTICS_V1"
REQUIRED_SEMANTIC_FIELDS = {"surface", "pedestrianWalkable", "vehicleDriveable", "buildable", "farmable"}
ALLOWED_SURFACES = {"sidewalk", "plaza", "industrial_floor", "grass", "soil", "road", "water", "restricted_area"}


class TerrainSemanticContractError(ValueError):
    """Raised instead of guessing when a terrain definition is invalid."""


def validate_definition(value: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(value, dict) or set(value) - {"contract", "id", "visualMaterial", "semantic"}:
        raise TerrainSemanticContractError("definition has unknown or malformed properties")
    if value.get("contract") != CONTRACT:
        raise TerrainSemanticContractError("unsupported terrain semantics contract")
    if not isinstance(value.get("id"), str) or not value["id"]:
        raise TerrainSemanticContractError("id must be a non-empty string")
    if not isinstance(value.get("visualMaterial"), str) or not value["visualMaterial"]:
        raise TerrainSemanticContractError("visualMaterial must be a non-empty string")
    semantic = value.get("semantic")
    if not isinstance(semantic, dict) or set(semantic) != REQUIRED_SEMANTIC_FIELDS:
        raise TerrainSemanticContractError("semantic must contain exactly the declared CH_TERRAIN_SEMANTICS_V1 fields")
    if semantic["surface"] not in ALLOWED_SURFACES:
        raise TerrainSemanticContractError("semantic.surface is unknown")
    if any(not isinstance(semantic[field], bool) for field in REQUIRED_SEMANTIC_FIELDS - {"surface"}):
        raise TerrainSemanticContractError("semantic boolean fields must be real booleans")
    return value


def load_terrain_semantic_catalog(asset_root: str) -> Dict[str, Dict[str, Any]]:
    root = Path(asset_root) / "assets" / "definitions" / "terrain"
    catalog: Dict[str, Dict[str, Any]] = {}
    if not root.is_dir():
        return catalog
    for path in sorted(root.glob("*.json")):
        try:
            definition = validate_definition(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TerrainSemanticContractError) as exc:
            raise TerrainSemanticContractError(f"{path.name}: {exc}") from exc
        if definition["id"] in catalog:
            raise TerrainSemanticContractError(f"duplicate terrain definition id: {definition['id']}")
        catalog[definition["id"]] = definition
    return catalog


def native_catalog_json(catalog: Dict[str, Dict[str, Any]]) -> str:
    """Stable envelope consumed by the C++ SemanticGrid resolver."""
    return json.dumps({"definitions": [catalog[key] for key in sorted(catalog)]}, separators=(",", ":"))
