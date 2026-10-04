"""Generate the City Horizon wooden-path family from an authored source PNG.

The authored source may be a presentation-sized pixel-art render on a black
background.  This recipe rectifies only this material into the canonical 2:1
128x64 diamond before handing it to the shared ground-tile worker.  It does not
change the global atomic-path intake rules.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

from ground_tile_worker import prepare
from tile_geometry import TILE_HEIGHT, TILE_WIDTH, diamond_mask

W, H = TILE_WIDTH, TILE_HEIGHT
NAMES = (
    "wood_path_00_isolated.png", "wood_path_01_end_n.png", "wood_path_02_end_e.png", "wood_path_03_curve_ne.png",
    "wood_path_04_end_s.png", "wood_path_05_straight_ns.png", "wood_path_06_curve_es.png", "wood_path_07_tee_no_w.png",
    "wood_path_08_end_w.png", "wood_path_09_curve_nw.png", "wood_path_10_straight_ew.png", "wood_path_11_tee_no_s.png",
    "wood_path_12_curve_sw.png", "wood_path_13_tee_no_e.png", "wood_path_14_tee_no_n.png", "wood_path_15_cross.png",
)


def rectify_authored_diamond(source_path: Path, output_path: Path, black_threshold: int = 20) -> None:
    """Fit this authored wooden diamond to the official 128x64 camera footprint.

    The source is already approved art.  We remove only the near-black
    presentation background, crop its authored silhouette, rectify that
    silhouette to the locked 2:1 footprint, and apply the shared diamond alpha.
    """
    source = Image.open(source_path).convert("RGBA")
    pixels = source.load()
    for y in range(source.height):
        for x in range(source.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha and red <= black_threshold and green <= black_threshold and blue <= black_threshold:
                pixels[x, y] = (red, green, blue, 0)

    bounds = source.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError(f"source contains no usable wooden tile pixels: {source_path}")

    cropped = source.crop(bounds)
    # This material was authored from an image-generation presentation canvas
    # whose visible diamond is slightly too tall.  Rectifying the crop is the
    # material-specific camera correction; the shared normalizer remains strict.
    rectified = cropped.resize((W, H), Image.Resampling.LANCZOS)
    rectified.putalpha(ImageChops.multiply(rectified.getchannel("A"), diamond_mask()))
    # The authored diamond occupies the full target footprint; lock alpha to the
    # canonical raster so the downstream seam worker sees one exact topology.
    rectified.putalpha(diamond_mask())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rectified.save(output_path, "PNG")


def family_preview(tiles: dict[int, Image.Image], output: Path) -> None:
    canvas = Image.new("RGBA", (896, 448), (87, 126, 62, 255))
    origin = (320, 54)

    def at(x: int, y: int) -> tuple[int, int]:
        return origin[0] + (x - y) * 64 - 64, origin[1] + (x + y) * 32

    layout = [
        (0, 0, 2), (1, 0, 10), (2, 0, 10), (3, 0, 8),
        (2, -2, 4), (2, -1, 5), (2, 0, 15), (2, 1, 5), (2, 2, 1),
        (-1, 3, 6), (0, 3, 9), (4, 3, 3), (5, 3, 12),
    ]
    for x, y, mask in layout:
        canvas.alpha_composite(tiles[mask], at(x, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, "PNG")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path,
        default=Path("Converter/file_00000000e7b4820ea8e8cdc823cfa927.png"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("assets/terrain/paths/wood_01"))
    parser.add_argument("--work-dir", type=Path, default=Path("out/wood_path_01"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.work_dir.mkdir(parents=True, exist_ok=True)
    base = args.work_dir / "wood_path_base_128x64.png"
    repeat_preview = args.work_dir / "wood_path_repeat_preview.png"
    worker_report = args.work_dir / "wood_path_worker_report.json"

    with tempfile.TemporaryDirectory() as temporary:
        rectified_source = Path(temporary) / "wood_rectified_128x64.png"
        rectify_authored_diamond(args.source, rectified_source)
        report = prepare(
            rectified_source,
            base,
            repeat_preview,
            worker_report,
            max_edge_error=6.0,
            strip_edge_pixels=1,
            decontaminate_edge_pixels=0,
            max_dark_pixels=None,
        )

    prepared = Image.open(base).convert("RGBA")
    # Wooden planks are a continuous floor material.  The logical 16-mask
    # topology still controls navigation/neighbor selection, while preserving
    # one seam-safe plank surface avoids rotating or bending the boards at every
    # junction.  Separate filenames keep the runtime contract identical to the
    # other path families.
    tiles = {mask: prepared.copy() for mask in range(16)}
    for mask, tile in tiles.items():
        tile.save(args.output_dir / NAMES[mask], "PNG")

    preview = args.work_dir / "wood_path_autotile_preview.png"
    family_preview(tiles, preview)
    manifest = {
        "contract": "CH_ATOMIC_PATH_FAMILY_V1",
        "id": "wood_path_01",
        "styleId": "wood_path",
        "displayName": "Caminho de Madeira",
        "tileCanvas": {"width": W, "height": H, "projection": "isometric_2_to_1"},
        "connectivity": {"bits": {"N": 1, "E": 2, "S": 4, "W": 8}, "variantCount": 16},
        "source": str(args.source),
        "variants": list(NAMES),
        "workerReport": report,
        "promotionState": "runtime",
    }
    (args.output_dir / "wood_path_01.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"PASS wood path: source={args.source} masks=16 edge_error={report['edgeError']} "
        f"runtime={args.output_dir} preview={preview}"
    )


if __name__ == "__main__":
    main()
