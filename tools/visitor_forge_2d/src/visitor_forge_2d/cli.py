from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from .character import (
    STYLE_CONTRACT,
    generate_v1_south_assets,
    validate_v1_character,
)
from .character.review import frame_measurements, gameplay_review, map_scale_review
from .character.concept_rig import build_concept_rig
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


def command_build_concept_rig(args: argparse.Namespace) -> int:
    result = build_concept_rig(args.master, args.asset_root, args.definition_output,
                               direction=args.direction)
    print(json.dumps({"status": "ok", **result}, indent=2))
    return 0


def _compose_and_export(
    definition_path: str,
    pose_paths: list[str],
    asset_root: str,
    output: str,
    art_root: str | None = None,
) -> tuple[list[Image.Image], list[Path], list[str]]:
    definition = load_character_definition(definition_path)
    poses = _load_poses(pose_paths)
    validate_v1_character(definition, poses)

    composer = LayerComposer(asset_root, art_root=art_root)
    output_dir = Path(output)
    working_frames: list[Image.Image] = []
    produced: list[Path] = []
    authored_layers: set[str] = set()

    for pose in poses:
        image = composer.compose(definition, pose)
        authored_layers.update(composer.authored_layers)
        working_frames.append(image)
        png_path, json_path = export_frame(
            image, definition, pose, output_dir,
            source_parts=composer.source_provenance.copy(),
        )
        produced.extend([png_path, json_path])

    return working_frames, produced, sorted(authored_layers)


def command_render(args: argparse.Namespace) -> int:
    _, produced, authored_layers = _compose_and_export(
        args.definition,
        args.pose,
        args.asset_root,
        args.output,
        getattr(args, "art_root", None),
    )
    print(json.dumps({"status": "ok", "outputs": [str(path) for path in produced],
                      "authoredLayers": authored_layers}, indent=2))
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
    working_frames, produced, authored_layers = _compose_and_export(
        args.definition,
        args.pose,
        args.asset_root,
        args.output,
        getattr(args, "art_root", None),
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

    concept_review = None
    concept_source = None
    if getattr(args, "concept", None):
        idle_id = f"{definition.direction}_idle"
        idle_index = next((index for index, path in enumerate(args.pose)
                           if load_pose(path).pose_id == idle_id), None)
        if idle_index is None:
            raise ValueError(f"Concept comparison requires a {idle_id} pose")
        concept_path = Path(args.concept)
        with Image.open(concept_path) as source:
            source.load()
            if source.mode != "RGBA" or source.size != definition.canvas.output_size:
                raise ValueError("Concept must be an RGBA PNG at the definition's output size")
            concept = source.copy()
        if concept.getchannel("A").getbbox() is None:
            raise ValueError("Concept must contain a visible character")
        concept_review = output_dir / f"{strip_name}_concept_comparison.png"
        gameplay_review([gameplay_frames[idle_index], concept], background).save(
            concept_review, format="PNG", optimize=False,
        )
        concept_source = {
            "path": str(concept_path),
            "sha256": hashlib.sha256(concept_path.read_bytes()).hexdigest(),
            "bounds": list(concept.getchannel("A").getbbox()),
        }

    measurements = frame_measurements(
        gameplay_frames,
        (definition.canvas.anchor.x, definition.canvas.anchor.y),
    )
    metrics_path = output_dir / f"{strip_name}_review_metrics.json"
    metrics_path.write_text(json.dumps(measurements, indent=2) + "\n", encoding="utf-8")

    summary = {
        "status": "ok",
        "styleContract": (STYLE_CONTRACT if definition.forge_contract_version == "CH_VISITOR_FORGE_2D_V1"
                          else definition.forge_contract_version),
        "generatedParts": [str(path) for path in generated],
        "partManifest": str(manifest_path),
        "preservedParts": manifest["preservedOverrides"],
        "authoredLayers": authored_layers,
        "artRoot": getattr(args, "art_root", None),
        "outputs": [str(path) for path in produced],
        "reviewStrip": str(review_path),
        "gameplayStrip": str(gameplay_path),
        "inWorldReview": str(in_world_path),
        "reviewMeasurements": str(metrics_path),
        "conceptComparison": str(concept_review) if concept_review else None,
        "conceptSource": concept_source,
        "runtimePromotion": False,
        "nextGate": "visual review at gameplay scale before EAST/WEST/NORTH",
    }
    print(json.dumps(summary, indent=2))
    return 0


def command_review_concept_directions(args: argparse.Namespace) -> int:
    """Build and review four views of one fixed character without runtime promotion."""
    tool_root = Path(args.tool_root)
    asset_root = Path(args.asset_root)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    background = None
    if args.background:
        with Image.open(args.background) as source:
            background = source.convert("RGBA")

    direction_order = ("south", "east", "north", "west")
    panels = []
    manifest = {"contract": "CH_VISITOR_2D_DIRECTIONAL_REVIEW_V1",
                "characterId": "visitor_male_01", "directions": {},
                "artApproved": False, "runtimePromotion": False}
    for direction in direction_order:
        master = tool_root / "art" / "concepts" / f"visitor_male_01_{direction}_master.png"
        folder = output / direction
        definition_path = folder / "definition.json"
        rig = build_concept_rig(master, asset_root, definition_path, direction)
        poses = [tool_root / "poses" / "concept" / f"{direction}_{name}.json"
                 for name in ("idle", "walk_a", "walk_b")]
        definition = load_character_definition(definition_path)
        validate_v1_character(definition, _load_poses([str(path) for path in poses]))
        _, produced, _ = _compose_and_export(
            str(definition_path), [str(path) for path in poses], str(asset_root), str(folder),
        )
        frames = []
        for name in ("idle", "walk_a", "walk_b"):
            with Image.open(folder / f"visitor_male_01_{direction}_{name}.png") as frame:
                frames.append(frame.convert("RGBA"))
        measurements = frame_measurements(frames, (64, 116))
        panel = gameplay_review(frames, background)
        panel_path = folder / f"visitor_male_01_{direction}_in_world_review.png"
        panel.save(panel_path, format="PNG", optimize=False)
        panels.append(panel)
        manifest["directions"][direction] = {
            "masterSha256": rig["masterSha256"],
            "definition": str(definition_path),
            "frames": [str(path) for path in produced],
            "reviewPanel": str(panel_path),
            "measurements": measurements,
        }

    board = Image.new("RGBA", (panels[0].width, sum(p.height for p in panels)))
    cursor = 0
    for panel in panels:
        board.alpha_composite(panel, (0, cursor))
        cursor += panel.height
    board_path = output / "visitor_male_01_four_directions_walk_review.png"
    board.save(board_path, format="PNG", optimize=False)
    manifest_path = output / "visitor_male_01_directional_review.json"
    manifest["board"] = str(board_path)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "board": str(board_path),
                      "manifest": str(manifest_path), "runtimePromotion": False}, indent=2))
    return 0


def command_review_map_scale(args: argparse.Namespace) -> int:
    frame_path, capture_path = Path(args.frame), Path(args.capture)
    with Image.open(frame_path) as source:
        if source.mode != "RGBA":
            raise ValueError("Visitor frame must be RGBA")
        frame = source.copy()
    with Image.open(capture_path) as source:
        capture = source.convert("RGBA")
    board, metrics = map_scale_review(
        frame, capture, tuple(args.crop), tuple(args.foot), args.display_height,
    )
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    board.save(destination, format="PNG", optimize=False)
    metrics["frameSha256"] = hashlib.sha256(frame_path.read_bytes()).hexdigest()
    metrics["captureSha256"] = hashlib.sha256(capture_path.read_bytes()).hexdigest()
    metadata = destination.with_suffix(".json")
    metadata.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "comparison": str(destination),
                      "metrics": str(metadata), "runtimePromotion": False}, indent=2))
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

    concept_rig = subparsers.add_parser(
        "build-concept-rig", help="derive one experimental directional cutout rig from a 512px concept master",
    )
    concept_rig.add_argument("--master", required=True)
    concept_rig.add_argument("--direction", choices=("south", "east", "north", "west"), default="south")
    concept_rig.add_argument("--asset-root", required=True)
    concept_rig.add_argument("--definition-output", required=True)
    concept_rig.set_defaults(func=command_build_concept_rig)

    render = subparsers.add_parser("render", help="compose and export one or more V1 poses")
    render.add_argument("--definition", required=True)
    render.add_argument("--pose", action="append", required=True)
    render.add_argument("--asset-root", required=True)
    render.add_argument("--art-root", help="Optional versioned RGBA part overrides")
    render.add_argument("--output", required=True)
    render.set_defaults(func=command_render)

    prototype = subparsers.add_parser(
        "prototype",
        help="generate V1 parts, render poses and produce visual-gate strips",
    )
    prototype.add_argument("--definition", required=True)
    prototype.add_argument("--pose", action="append", required=True)
    prototype.add_argument("--asset-root", required=True)
    prototype.add_argument("--art-root", help="Optional versioned RGBA part overrides")
    prototype.add_argument("--overwrite-parts", action="store_true", help="Replace even manually edited source PNGs")
    prototype.add_argument("--output", required=True)
    prototype.add_argument("--background", help="Optional terrain PNG for a native-size review strip")
    prototype.add_argument("--concept", help="Optional 128px RGBA SOUTH concept for idle comparison; never exported as an animated frame")
    prototype.set_defaults(func=command_prototype)

    directional_review = subparsers.add_parser(
        "review-concept-directions", help="build one character's 4 views and 12-frame gameplay board",
    )
    directional_review.add_argument("--tool-root", required=True)
    directional_review.add_argument("--asset-root", required=True)
    directional_review.add_argument("--output", required=True)
    directional_review.add_argument("--background", help="Optional terrain PNG for the review board")
    directional_review.set_defaults(func=command_review_concept_directions)

    map_scale = subparsers.add_parser(
        "review-map-scale", help="compare native and candidate visitor sizes on one real map crop",
    )
    map_scale.add_argument("--frame", required=True, help="128x128 visitor RGBA frame")
    map_scale.add_argument("--capture", required=True, help="MapForge or engine screenshot")
    map_scale.add_argument("--crop", type=int, nargs=4, required=True, metavar=("X0", "Y0", "X1", "Y1"))
    map_scale.add_argument("--foot", type=int, nargs=2, required=True, metavar=("X", "Y"))
    map_scale.add_argument("--display-height", type=int, required=True, help="Candidate body height in map pixels")
    map_scale.add_argument("--output", required=True, help="Review PNG path; JSON metadata saved alongside")
    map_scale.set_defaults(func=command_review_map_scale)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
