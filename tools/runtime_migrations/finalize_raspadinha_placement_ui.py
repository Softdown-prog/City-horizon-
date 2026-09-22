#!/usr/bin/env python3
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]


def replace_exact(path: Path, old: str, new: str, expected: int) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"CH_RASPADINHA_UI_PATCH_MISMATCH: {path}: expected {expected} matches, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


main = ROOT / "src/main.cpp"
replace_exact(
    main,
    '''        status = "DECORATION WILL BE AVAILABLE SOON";''',
    '''        status = "DECORATION: SELECT AN ITEM";''',
    2,
)
replace_exact(
    main,
    '''                                         catalog_footprint_label(definition), "LIVRE NO TERRENO"});''',
    '''                                         catalog_footprint_label(definition), catalog_requirements_label(definition)});''',
    1,
)

manifest_path = ROOT / "assets/props/raspadinha_vendor/raspadinha_vendor.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
manifest["placement"] = {
    "contract": "CH_PROP_PLACEMENT_V1",
    "footprint": {"widthTiles": 1, "depthTiles": 1},
    "baseTerrain": ["grass"],
    "requiredAdjacent": ["road", "path"],
    "adjacency": "cardinal_any",
    "blockedOwnTile": ["building", "object", "road", "path", "farm", "water", "non_grass_terrain"],
    "requiresOwnedLand": True
}
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("CH_RASPADINHA_UI_PATCH_OK")
