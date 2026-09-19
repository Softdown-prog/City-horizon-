"""One-way, deterministic legacy-map migration to CH_TERRAIN_SEMANTICS_V1."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def definition_for(texture: str) -> str:
    # This migration table is explicit compatibility data, not runtime inference.
    value = texture.lower()
    if "water_shallow" in value or "ocean_shallow" in value or "shallow_transition" in value:
        return "water_shallow"
    if "water_deep" in value or "ocean_deep" in value:
        return "water_deep"
    if "sand" in value:
        return "sand"
    return "grass"


def migrate(source: Path, target: Path) -> dict:
    data = json.loads(source.read_text(encoding="utf-8"))
    changed = 0
    for tile in data.get("terrain", []):
        definition = definition_for(str(tile.get("texture", "")))
        if tile.get("terrainDefinition") != definition:
            tile["terrainDefinition"] = definition
            changed += 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"terrain": len(data.get("terrain", [])), "changed": changed, "target": str(target)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--activate", action="store_true", help="write the runtime scenario marker beside target")
    args = parser.parse_args()
    result = migrate(args.source, args.target)
    if args.activate:
        (args.target.parent / "active_scenario.txt").write_text(args.target.name + "\n", encoding="utf-8")
        result["active"] = args.target.name
    print(json.dumps(result))
