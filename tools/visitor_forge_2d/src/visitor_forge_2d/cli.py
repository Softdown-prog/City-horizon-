from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from .character import (
    STYLE_CONTRACT,
    generate_v1_south_assets,
    validate_v1_character,
)
from .character.review import frame_measurements, gameplay_review
from .core import LayerComposer, alpha_safe_resize, export_frame, load_character_definition, load_pose


def _load_poses(paths: list[str]) -> list:
    return [load_pose(path) for path in paths]


def _part_manifest(generated: list[Path]) -> tuple[Path, dict]:
    manifest_path = generated[0].parent / "generated_parts.json"
    return manifest_path, json.loads(manifest_path.read_text(encoding="utf-8"))


def command_validate(args: argparse.Namespace) -> int:
    definition = load_character_definition(args.definition)
    poses = _load_poses(args.pose)
    validate_v1_character(definition, poses)
    summary = {
        "status": "ok",
        "characterId": definition.character_id,
        "direction": definition.direction,
        "workingSize": list(definition.canvas.working_size),
        "outputSize": list(definition.canvas.output_size),
        "anchor": definition.canvas.anchor.as_list(),
        "parts": [part.part_id for part in definition.parts],
        "poses": [pose.pose_id for pose in poses],
        "forgeContractVersion": definition.forge_contract_version,
    }
    print(json.dumps(summary, indent=2))
    return 0


def command_build_assets(args: argparse.Namespace) -> int:
    written = generate_v1_south_assets(args.asset_root, overwrite=getattr(args, "overwrite_parts", False))
    manifest_path, manifest = _part_manifest(written)
    summary = {
        "status": "ok",
        "styleContract": STYLE_CONTRACT,
        "assetRoot": str(Path(args.asset_root)),
        "outputs": [str(path) for path in written],
        "partManifest": str(manifest_path),
        "preservedParts": manifest["preservedOverrides"],
    }
    print(json.dumps(summary, indent=2))
    return 0


def _compose_and_export(
    definition_path: str,
    pose_paths: list[str],
    asset_root: str,
    output: str,
) -> tuple[list[Image.Image], list[Path]]:
    definition = load_character_definition(definition_path)
    poses = _load_poses(pose_paths)
    validate_v1_character(definition, poses)

    composer = LayerComposer(asset_root)
    output_dir = Path(output)
    working_frames: list[Image.Image] = []
    produced: list[Path] = []

    for pose in poses:
        image = composer.compose(definition, pose)
        working_frames.append(image)
        png_path, json_path = export_frame(image, definition, pose, output_dir)
        produced.extend([png_path, json_path])

    return working_frames, produced


def command_render(args: argparse.Namespace) -> int:
    _, produced = _compose_and_export(
        args.definition,
        args.pose,
        args.asset_root,
        args.output,
    )
    print(json.dumps({"status": "ok", "outputs": [str(path) for path in produced]}, indent=2))
    return 0


def _horizontal_sheet(images: list[Image.Image], *, gap: int = 12) -> Image.Image:
    if not images:
        raise ValueError("At least one image is required for a contact sheet")
    width = sum(image.width for image in images) + gap * (len(images) - 1)
    height = max(image.height for image in images)
    sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    cursor = 0
    for image in images:
        rgba = image.convert("RGBA")
        sheet.alpha_composite(rgba, (cursor, (height - rgba.height) // 2))
        cursor += rgba.width + gap
    return sheet


def command_prototype(args: argparse.Namespace) -> int:
    generated = generate_v1_south_assets(args.asset_root, overwrite=getattr(args, "overwrite_parts", False))
    manifest_path, manifest = _part_manifest(generated)
    working_frames, produced = _compose_and_export(
        args.definition,
        args.pose,
        args.asset_root,
        args.output,
    )

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    review_frames = [alpha_safe_resize(frame, (256, 256)) for frame in working_frames]
    review_sheet = _horizontal_sheet(review_frames, gap=16)
    definition = load_character_definition(args.definition)
    strip_name = f"{definition.character_id}_{definition.direction}"
    review_path = output_dir / f"{strip_name}_review_strip.png"
    review_sheet.save(review_path, format="PNG", optimize=False)

    gameplay_frames: list[Image.Image] = []
    for pose_path in args.pose:
        pose = load_pose(pose_path)
        frame_path = output_dir / f"{definition.character_id}_{pose.pose_id}.png"
        with Image.open(frame_path) as frame:
            gameplay_frames.append(frame.convert("RGBA"))
    gameplay_sheet = _horizontal_sheet(gameplay_frames, gap=8)
    gameplay_path = output_dir / f"{strip_name}_gameplay_strip.png"
    gameplay_sheet.save(gameplay_path, format="PNG", optimize=False)

    background = None
    if getattr(args, "background", None):
        with Image.open(args.background) as terrain:
            background = terrain.convert("RGBA")
    in_world_path = output_dir / f"{strip_name}_in_world_review.png"
    gameplay_review(gameplay_frames, background).save(in_world_path, format="PNG", optimize=False)

    measurements = frame_measurements(
        gameplay_frames,
        (definition.canvas.anchor.x, definition.canvas.anchor.y),
    )
    metrics_path = output_dir / f"{strip_name}_review_metrics.json"
    metrics_path.write_text(json.dumps(measurements, indent=2) + "\n", encoding="utf-8")

    summary = {
        "status": "ok",
        "styleContract": STYLE_CONTRACT,
        "generatedParts": [str(path) for path in generated],
        "partManifest": str(manifest_path),
        "preservedParts": manifest["preservedOverrides"],
        "outputs": [str(path) for path in produced],
        "reviewStrip": str(review_path),
        "gameplayStrip": str(gameplay_path),
        "inWorldReview": str(in_world_path),
        "reviewMeasurements": str(metrics_path),
        "runtimePromotion": False,
        "nextGate": "visual review at gameplay scale before EAST/WEST/NORTH",
    }
    print(json.dumps(summary, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ch-visitor-forge-2d",
        description="City Horizon procedural 2D visitor composer",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate V1 character/pose contracts")
    validate.add_argument("--definition", required=True)
    validate.add_argument("--pose", action="append", required=True)
    validate.set_defaults(func=command_validate)

    build_assets = subparsers.add_parser(
        "build-assets",
        help="generate the deterministic V1 SOUTH 2D source-part library",
    )
    build_assets.add_argument("--asset-root", required=True)
    build_assets.add_argument("--overwrite-parts", action="store_true", help="Replace even manually edited source PNGs")
    build_assets.set_defaults(func=command_build_assets)

    render = subparsers.add_parser("render", help="compose and export one or more V1 poses")
    render.add_argument("--definition", required=True)
    render.add_argument("--pose", action="append", required=True)
    render.add_argument("--asset-root", required=True)
    render.add_argument("--output", required=True)
    render.set_defaults(func=command_render)

    prototype = subparsers.add_parser(
        "prototype",
        help="generate V1 parts, render poses and produce visual-gate strips",
    )
    prototype.add_argument("--definition", required=True)
    prototype.add_argument("--pose", action="append", required=True)
    prototype.add_argument("--asset-root", required=True)
    prototype.add_argument("--overwrite-parts", action="store_true", help="Replace even manually edited source PNGs")
    prototype.add_argument("--output", required=True)
    prototype.add_argument("--background", help="Optional terrain PNG for a native-size review strip")
    prototype.set_defaults(func=command_prototype)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
