"""Create and validate a deterministic runtime-placement review board for a baked asset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

EXPECTED = ("south", "east", "west", "north")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def diamond(draw, cx, cy, fill, outline):
    points = [(cx, cy - 32), (cx + 64, cy), (cx, cy + 32), (cx - 64, cy)]
    draw.polygon(points, fill=fill, outline=outline)


def main():
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("contract") == "TYCOON_ASSET_BAKE_V1", "Unsupported manifest contract")
    require(tuple(manifest.get("directionOrder", [])) == EXPECTED, "Unexpected direction order")

    views = {view["direction"]: view for view in manifest.get("views", [])}
    require(set(views) == set(EXPECTED), "Manifest does not provide four runtime views")
    pivots = {(view["pivot"]["x"], view["pivot"]["y"]) for view in views.values()}
    require(len(pivots) == 1, f"Runtime placement requires one shared pivot, got {sorted(pivots)}")

    panel_w, panel_h = 448, 360
    sheet = Image.new("RGBA", (panel_w * 2, panel_h * 2), (126, 156, 99, 255))
    for index, direction in enumerate(EXPECTED):
        panel = Image.new("RGBA", (panel_w, panel_h), (126, 156, 99, 255))
        draw = ImageDraw.Draw(panel)
        draw.rectangle((0, 0, panel_w, 34), fill=(239, 234, 220, 255))
        draw.text((12, 10), f"Runtime placement gate: {direction}", fill=(34, 38, 33, 255))
        # Sidewalk and approach road provide the same ground context every rotation.
        draw.rectangle((0, 266, panel_w, panel_h), fill=(89, 94, 97, 255))
        draw.rectangle((0, 236, panel_w, 266), fill=(189, 183, 166, 255))
        anchor_x, anchor_y = panel_w // 2, 222
        diamond(draw, anchor_x, anchor_y, (116, 150, 84, 255), (76, 104, 58, 255))
        draw.line((anchor_x - 4, anchor_y, anchor_x + 4, anchor_y), fill=(226, 66, 60, 255), width=2)
        draw.line((anchor_x, anchor_y - 4, anchor_x, anchor_y + 4), fill=(226, 66, 60, 255), width=2)

        view = views[direction]
        source = manifest_path.parent / view["file"]
        require(source.is_file(), f"Missing runtime sprite: {source}")
        sprite = Image.open(source).convert("RGBA")
        require(sprite.getchannel("A").getbbox() is not None, f"Empty alpha: {source.name}")
        pivot = view["pivot"]
        panel.alpha_composite(sprite, (anchor_x - int(pivot["x"]), anchor_y - int(pivot["y"])))
        sheet.alpha_composite(panel, ((index % 2) * panel_w, (index // 2) * panel_h))

    board = output_dir / f"{manifest['assetId']}_runtime_placement_gate.png"
    sheet.save(board)
    report = {
        "contract": "CH_RUNTIME_PLACEMENT_GATE_V1",
        "status": "passed",
        "assetId": manifest["assetId"],
        "cameraContract": manifest["cameraContract"],
        "directionOrder": list(EXPECTED),
        "sharedPivot": {"x": next(iter(pivots))[0], "y": next(iter(pivots))[1]},
        "reviewImage": board.name,
        "checks": ["rgba_alpha", "four_directions", "shared_pivot", "road_sidewalk_terrain_context"],
    }
    (output_dir / f"{manifest['assetId']}_runtime_placement_gate.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print("CH_RUNTIME_PLACEMENT_GATE_V1: PASS")
    print(board)


if __name__ == "__main__":
    main()
