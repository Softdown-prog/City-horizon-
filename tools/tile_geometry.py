"""One raster footprint for all 128x64 ground/path tile stages."""

from PIL import Image, ImageDraw

TILE_WIDTH = 128
TILE_HEIGHT = 64


def diamond_mask() -> Image.Image:
    mask = Image.new("L", (TILE_WIDTH, TILE_HEIGHT), 0)
    ImageDraw.Draw(mask).polygon(
        ((TILE_WIDTH // 2, 0), (TILE_WIDTH - 1, TILE_HEIGHT // 2),
         (TILE_WIDTH // 2, TILE_HEIGHT - 1), (0, TILE_HEIGHT // 2)),
        fill=255,
    )
    return mask
