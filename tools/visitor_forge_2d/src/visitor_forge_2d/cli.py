from __future__ import annotations

import argparse
import json
from pathlib import Path

from .character import validate_v1_character
from .core import LayerComposer, export_frame, load_character_definition, load_pose


def _load_poses(paths: list[str]) -> list:
    return [load_pose(path) for path in paths]


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


def command_render(args: argparse.Namespace) -> int:
    definition = load_character_definition(args.definition)
    poses = _load_poses(args.pose)
    validate_v1_character(definition, poses)

    composer = LayerComposer(args.asset_root)
    output_dir = Path(args.output)
    produced: list[str] = []
    for pose in poses:
        image = composer.compose(definition, pose)
        png_path, json_path = export_frame(image, definition, pose, output_dir)
        produced.extend([str(png_path), str(json_path)])

    print(json.dumps({"status": "ok", "outputs": produced}, indent=2))
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

    render = subparsers.add_parser("render", help="compose and export one or more V1 poses")
    render.add_argument("--definition", required=True)
    render.add_argument("--pose", action="append", required=True)
    render.add_argument("--asset-root", required=True)
    render.add_argument("--output", required=True)
    render.set_defaults(func=command_render)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
