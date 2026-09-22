"""Post-process the approved Ferris wheel animation into runtime-ready 2D PNGs.

Input is a directory containing one source subdirectory per animation frame. Each
frame source directory follows the normal Tycoon Asset Baker metadata contract,
so the existing canonical postprocess.py remains the authority for downsample,
alpha, shadow and edge handling.

The output adds animation packaging only:
- 12 processed frames per direction (S/E/W/N)
- one transparent horizontal sheet per direction
- one transparent 4-row animation sheet
- a runtime manifest with frame order, fps, pivots and source approval hash
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

DIRECTION_ORDER = ("south", "east", "west", "north")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Root containing frame_### source directories")
    p.add_argument("--output", required=True)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--asset-id", required=True)
    p.add_argument("--frame-start", type=int, required=True)
    p.add_argument("--frame-end", type=int, required=True)
    p.add_argument("--fps", type=int, required=True)
    p.add_argument("--approved-proxy-sha", required=True)
    return p.parse_args()


def run_postprocess(source_dir: Path, output_dir: Path, studio_preset: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(Path(__file__).with_name("postprocess.py")),
        "--input", str(source_dir),
        "--output", str(output_dir),
        "--studio-preset", str(studio_preset),
    ]
    subprocess.run(cmd, check=True)


def alpha_bounds(image: Image.Image):
    bbox = image.convert("RGBA").getchannel("A").getbbox()
    return [0, 0, image.width, image.height] if bbox is None else list(map(int, bbox))


def main():
    args = parse_args()
    input_root = Path(args.input).resolve()
    output_root = Path(args.output).resolve()
    studio_preset = Path(args.studio_preset).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    frames = list(range(args.frame_start, args.frame_end + 1))
    if not frames:
        raise RuntimeError("Ferris wheel animation has no frames")

    processed = {}
    pivot_reference = None
    frame_size = None

    for frame in frames:
        source_dir = input_root / f"frame_{frame:03d}"
        if not (source_dir / "studio_metadata.json").exists():
            raise RuntimeError(f"Missing Ferris source metadata for frame {frame}: {source_dir}")
        frame_out = output_root / "frames" / f"frame_{frame:03d}"
        run_postprocess(source_dir, frame_out, studio_preset)

        manifest_path = frame_out / f"{args.asset_id}_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        views = {view["direction"]: view for view in manifest["views"]}
        frame_pivots = {direction: views[direction]["pivot"] for direction in DIRECTION_ORDER}
        unique = {(p["x"], p["y"]) for p in frame_pivots.values()}
        if len(unique) != 1:
            raise RuntimeError(f"Frame {frame} has non-uniform direction pivots: {sorted(unique)}")
        pivot = next(iter(frame_pivots.values()))
        if pivot_reference is None:
            pivot_reference = dict(pivot)
        elif pivot != pivot_reference:
            raise RuntimeError(
                f"Animation pivot drift at frame {frame}: expected {pivot_reference}, got {pivot}"
            )

        processed[frame] = {}
        for direction in DIRECTION_ORDER:
            png = frame_out / f"{args.asset_id}_{direction}.png"
            image = Image.open(png).convert("RGBA")
            if frame_size is None:
                frame_size = image.size
            elif image.size != frame_size:
                raise RuntimeError(f"Frame size drift: {png} is {image.size}, expected {frame_size}")
            alpha = image.getchannel("A")
            if alpha.getextrema()[0] != 0:
                raise RuntimeError(f"Runtime PNG is not transparent at frame {frame} {direction}")
            processed[frame][direction] = png

    assert frame_size is not None
    fw, fh = frame_size

    direction_sheets = {}
    for direction in DIRECTION_ORDER:
        sheet = Image.new("RGBA", (fw * len(frames), fh), (0, 0, 0, 0))
        for column, frame in enumerate(frames):
            image = Image.open(processed[frame][direction]).convert("RGBA")
            sheet.alpha_composite(image, (column * fw, 0))
        name = f"{args.asset_id}_{direction}_animation.png"
        sheet.save(output_root / name)
        direction_sheets[direction] = name

    all_sheet = Image.new(
        "RGBA",
        (fw * len(frames), fh * len(DIRECTION_ORDER)),
        (0, 0, 0, 0),
    )
    for row, direction in enumerate(DIRECTION_ORDER):
        for column, frame in enumerate(frames):
            image = Image.open(processed[frame][direction]).convert("RGBA")
            all_sheet.alpha_composite(image, (column * fw, row * fh))
    all_sheet_name = f"{args.asset_id}_4dir_animation.png"
    all_sheet.save(output_root / all_sheet_name)

    first_images = {
        direction: Image.open(processed[frames[0]][direction]).convert("RGBA")
        for direction in DIRECTION_ORDER
    }
    bounds = {direction: alpha_bounds(image) for direction, image in first_images.items()}

    runtime_manifest = {
        "contract": "CH_ANIMATED_SPRITE_BAKE_V1",
        "assetId": args.asset_id,
        "assetType": "animated_attraction",
        "runtimeRepresentation": "2D_RGBA_pre_rendered_sprite",
        "transparentCanvas": True,
        "backgroundIncluded": False,
        "directionOrder": list(DIRECTION_ORDER),
        "frameStart": args.frame_start,
        "frameEnd": args.frame_end,
        "frameCount": len(frames),
        "fps": args.fps,
        "looping": True,
        "frameResolution": [fw, fh],
        "pivot": pivot_reference,
        "approvedProxySha256": args.approved_proxy_sha,
        "postprocess": "tools/tycoon_photo_studio/postprocess.py",
        "directions": {
            direction: {
                "sheet": direction_sheets[direction],
                "rows": 1,
                "columns": len(frames),
                "frameOrder": frames,
                "firstFrameAlphaBounds": bounds[direction],
            }
            for direction in DIRECTION_ORDER
        },
        "combinedSheet": {
            "file": all_sheet_name,
            "rows": len(DIRECTION_ORDER),
            "columns": len(frames),
            "rowOrder": list(DIRECTION_ORDER),
            "frameOrder": frames,
        },
    }
    (output_root / f"{args.asset_id}_runtime_manifest.json").write_text(
        json.dumps(runtime_manifest, indent=2), encoding="utf-8"
    )

    print(
        f"[ferris_postprocess] runtime package ready: {len(frames)} frames x "
        f"{len(DIRECTION_ORDER)} directions at {fw}x{fh}, transparent RGBA"
    )


if __name__ == "__main__":
    main()
