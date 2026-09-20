"""Split a 3x6 reference sheet into transparent review samples.

These files are deliberately review-only: production terrain is authored by
the City Horizon pipeline, not copied from a visual reference sheet.
"""
from pathlib import Path
from PIL import Image

SOURCE = Path("upload/01-1000083853.png")
OUT = Path("out/reference_tile_samples")
NAMES = (
    "water_blue", "water_teal", "water_pale",
    "ground_mud", "ground_pale_sand", "ground_dark_grass",
    "water_green_shallow", "water_slate", "water_turquoise",
)

def make_transparent(image: Image.Image) -> Image.Image:
    source = image.convert("RGBA")
    px = source.load()
    for y in range(source.height):
        for x in range(source.width):
            r, g, b, _ = px[x, y]
            # Key only the true black sheet background; dark mud remains.
            alpha = 0 if max(r, g, b) <= 12 else 255
            px[x, y] = (r, g, b, alpha)
    return source

def main() -> None:
    sheet = Image.open(SOURCE)
    OUT.mkdir(parents=True, exist_ok=True)
    cell_w, cell_h = sheet.width // 3, sheet.height // 6
    for material_index, name in enumerate(NAMES):
        col = material_index % 3
        pair_row = (material_index // 3) * 2
        for variant in range(2):
            crop = sheet.crop((col * cell_w, (pair_row + variant) * cell_h,
                               (col + 1) * cell_w, (pair_row + variant + 1) * cell_h))
            make_transparent(crop).save(OUT / f"{name}_{variant + 1:02d}_reference.png")

if __name__ == "__main__":
    main()
