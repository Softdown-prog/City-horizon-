"""Deterministic catalog discovery shared by the Map Forge UI and workers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    label: str
    relative_path: str
    category: str


def resolve_asset_path(asset_root: str, relative_path: str) -> Path:
    """Resolve an assets/... reference only under the selected runtime root."""
    root = Path(asset_root).resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError(f"Asset path escapes configured root: {relative_path}") from error
    return candidate


def terrain_catalog(asset_root: str) -> list[CatalogEntry]:
    root = Path(asset_root)
    terrain_root = root / "assets" / "terrain"
    entries: list[CatalogEntry] = []
    
    # Exclude overlay sub-pieces, wave animations, autotile edge/corner pieces, and caustics
    excluded_keywords = {"anim", "foam", "corner_", "border_", "caustics", "piece_"}
    
    for path in sorted(terrain_root.rglob("*.png")) if terrain_root.is_dir() else []:
        stem_lower = path.stem.lower()
        if any(kw in stem_lower for kw in excluded_keywords):
            continue

        relative = path.relative_to(root).as_posix()
        labels = {
            "grass_to_concrete_path_01_concrete_path": "Caminho de Cimento (CH_MASK_V1)",
            "grass_isometric_01": "Grama Padrão (Base Canônica)",
            "coast_sand_center_01": "Areia Seca Limpa",
            "coast_sand_wet_01": "Areia Molhada (Orla)",
            "coast_grass_sand_transition": "Transição Grama-Areia",
            "coast_shallow_transition": "Margem Rasa / Transição",
            "coast_water_shallow": "Água Rasa Base",
            "coast_water_deep": "Água Profunda Base",
        }
        stem = labels.get(path.stem, path.stem.replace("_", " ").title())
        entries.append(CatalogEntry(relative, stem, relative, "terrain"))
    return entries


def building_catalog_entries(catalog: dict[str, dict[str, Any]]) -> list[CatalogEntry]:
    entries: list[CatalogEntry] = []
    for asset_id, definition in sorted(catalog.items()):
        texture = str(definition.get("texture", ""))
        if not texture:
            continue
        entries.append(CatalogEntry(
            asset_id,
            str(definition.get("name", asset_id)),
            texture,
            str(definition.get("category", "building")),
        ))
    return entries


def scenario_catalog(asset_root: str) -> Iterable[Path]:
    scenario_root = Path(asset_root) / "assets" / "scenarios"
    return sorted(scenario_root.glob("*.json")) if scenario_root.is_dir() else []
