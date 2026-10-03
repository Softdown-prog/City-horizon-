"""Review real proxy pixels on dark/light backgrounds and a calibrated gameplay grid."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tycoon_photo_studio"))
from postprocess import make_context_panel


def write_proxy_review(output_root: Path, proxy: dict, preflight: dict) -> dict:
    path = output_root / "proxy_south.png"
    with Image.open(path) as source:
        if source.mode != "RGBA":
            raise ValueError("Proxy must contain RGBA pixels")
        sprite = source.copy()
    alpha = sprite.getchannel("A")
    bounds = alpha.point(lambda value: 255 if value >= 16 else 0).getbbox()
    if bounds is None:
        raise ValueError("Proxy has no visible asset; an empty render cannot pass")
    if list(sprite.size) != proxy.get("resolution"):
        raise ValueError("Proxy PNG dimensions differ from its report")
    tile_width = proxy.get("projectedTileWidthPx")
    pivot = proxy.get("groundOriginPx")
    calibrated = isinstance(tile_width, (int, float)) and tile_width > 0 and isinstance(pivot, dict)
    context = make_context_panel(sprite, pivot or {"x": sprite.width // 2, "y": sprite.height},
                                 "SOUTH", preflight.get("footprint"), tile_width if calibrated else None)
    # Background comparisons are thumbnails only; gameplay panel carries its
    # own explicitly calibrated scale, never the proxy's arbitrary canvas scale.
    thumbnail = sprite.copy()
    thumbnail.thumbnail((640, 640), Image.Resampling.LANCZOS)
    width = max(context.width, 2 * (thumbnail.width + 24))
    height = 64 + thumbnail.height + 48 + context.height
    board = Image.new("RGBA", (width, height), (242, 240, 233, 255))
    draw = ImageDraw.Draw(board)
    draw.text((16, 12), "CH Blender proxy review - synthetic grid, not runtime capture", fill=(35, 35, 35, 255))
    draw.text((16, 30), f"{proxy.get('assetId')} / {sprite.width}x{sprite.height}", fill=(35, 35, 35, 255))
    for index, background in enumerate(((239, 237, 228, 255), (35, 40, 48, 255))):
        panel = Image.new("RGBA", thumbnail.size, background)
        panel.alpha_composite(thumbnail)
        x = 12 + index * (thumbnail.width + 24)
        board.alpha_composite(panel, (x, 64))
        draw.text((x, 68 + thumbnail.height), "light background" if index == 0 else "dark background", fill=(35, 35, 35, 255))
    board.alpha_composite(context, (0, 64 + thumbnail.height + 48))
    review_path = output_root / "proxy_review.png"
    board.save(review_path)
    border_contact = bounds[0] == 0 or bounds[1] == 0 or bounds[2] == sprite.width or bounds[3] == sprite.height
    report = {"contract": "CH_PROXY_PIXEL_REVIEW_V1", "assetId": proxy.get("assetId"),
              "proxySha256": proxy["sha256"], "sourceFingerprint": proxy.get("sourceFingerprint"),
              "studioFingerprint": proxy.get("studioFingerprint"), "alphaBounds": list(bounds),
              "gameplayScaleCalibrated": calibrated, "projectedTileWidthPx": tile_width,
              "reviewFile": review_path.name,
              "warnings": ["VISIBLE_ALPHA_TOUCHES_FRAME"] if border_contact else [],
              "humanVisualApprovalRequired": True}
    (output_root / "proxy_review_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
