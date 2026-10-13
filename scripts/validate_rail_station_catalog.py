#!/usr/bin/env python3
"""Validate reusable railway station catalog and all four authored rotations."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
definition = json.loads((root / "assets/definitions/rail_terminal_station_01.json").read_text())
manifest = json.loads((root / "assets/buildings/rail_terminal_station_b_5x3_01/station_runtime_manifest.json").read_text())
assert definition["id"] == "rail_terminal_station_01"
assert definition["playerBuildable"] is True and definition["rotatable"] is True
assert definition["buildCost"] > 0
assert definition["footprint"] == {"width": 5, "height": 3}
assert manifest["footprint"] == {"widthTiles": 5, "depthTiles": 3}
assert len(set(definition["sprites"].values())) == 4
for rotation, direction in enumerate(("south", "west", "north", "east")):
    sprite = Path(definition["sprites"][str(rotation)])
    assert (root / sprite).is_file(), f"Missing rotation {rotation}: {sprite}"
    assert str(sprite) == manifest["sprites"][direction]["path"]
    with (root / sprite).open("rb") as file:
        assert file.read(8) == bytes((137,80,78,71,13,10,26,10))
print("Station catalog, pricing, footprint and four PNG rotations: OK")
