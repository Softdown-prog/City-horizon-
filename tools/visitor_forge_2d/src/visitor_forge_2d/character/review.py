"""Gameplay-sized, non-approval visual review of the SOUTH candidate."""

from __future__ import annotations

from PIL import Image, ImageChops, ImageOps


def frame_measurements(frames: list[Image.Image], anchor: tuple[float, float]) -> dict:
    """Measure opaque body geometry, ignoring the separate translucent shadow."""
    if not frames:
        raise ValueError("At least one frame is required")
    size = frames[0].size
    if any(frame.size != size for frame in frames):
        raise ValueError("Every frame must use the same gameplay canvas")

    silhouettes = [frame.convert("RGBA").getchannel("A").point(
        lambda value: 255 if value >= 180 else 0
    ) for frame in frames]
    boxes = [mask.getbbox() for mask in silhouettes]
    if any(box is None for box in boxes):
        raise ValueError("A frame has no opaque character body")
    foot_rows = [box[3] - 1 for box in boxes if box is not None]
    changed = []
    for mask in silhouettes[1:]:
        diff = ImageChops.difference(silhouettes[0], mask)
        changed.append(round(sum(value != 0 for value in diff.tobytes()) /
                             max(1, sum(value != 0 for value in silhouettes[0].tobytes())), 4))

    return {
        "contract": "CH_VISITOR_2D_REVIEW_MEASUREMENTS_V1",
        "canvasSize": list(size),
        "bodyBounds": [list(box) for box in boxes if box is not None],
        "footRows": foot_rows,
        "footRowRangePx": max(foot_rows) - min(foot_rows),
        "anchor": [anchor[0], anchor[1]],
        "footOffsetFromAnchorPx": [round(row - anchor[1], 2) for row in foot_rows],
        "changedSilhouetteFractionFromIdle": changed,
        "artApproved": False,
    }


def gameplay_review(frames: list[Image.Image], background: Image.Image | None = None) -> Image.Image:
    """Display real 128px sprites over a terrain sample, without enlarging them."""
    if not frames:
        raise ValueError("At least one frame is required")
    width, height = frames[0].size
    panel_size = (width + 48, height + 48)
    if background is not None:
        source = background.convert("RGBA")
        # Transparent terrain diamonds are reference textures, not a full
        # screenshot. Sample their opaque center to avoid green panel corners.
        if (source.getchannel("A").getextrema()[0] < 255 and
                source.width >= width * 2 and source.height >= height * 2):
            box = source.getchannel("A").getbbox()
            if box is not None:
                center_x = (box[0] + box[2]) // 2
                center_y = (box[1] + box[3]) // 2
                side = min(source.width // 4, source.height // 3, 256)
                source = source.crop((center_x - side // 2, center_y - side // 2,
                                      center_x + side // 2, center_y + side // 2))
        sample = ImageOps.fit(source, panel_size, method=Image.Resampling.LANCZOS)
        backdrop = Image.alpha_composite(Image.new("RGBA", panel_size, (76, 116, 48, 255)), sample)
    else:
        backdrop = Image.new("RGBA", panel_size, (76, 116, 48, 255))

    result = Image.new("RGBA", (panel_size[0] * len(frames), panel_size[1]), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        if frame.size != (width, height):
            raise ValueError("Every frame must use the same gameplay canvas")
        panel = backdrop.copy()
        panel.alpha_composite(frame.convert("RGBA"), ((panel_size[0] - width) // 2, 16))
        result.alpha_composite(panel, (index * panel_size[0], 0))
    return result
