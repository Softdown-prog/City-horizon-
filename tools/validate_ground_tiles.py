"""Reject ground-tile exports that cannot align to the City Horizon grid.

This is intentionally stricter than a visual preview: every profile has a
locked canvas and, where the renderer relies on it, locked opaque bounds.
There is no pixel tolerance. A one-pixel drift changes the render scale or
anchor and is therefore a rejected export, not a warning.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "assets" / "terrain" / "ground_tile_contract.json"


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def alpha_bounds(image: Image.Image) -> dict[str, int] | None:
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        return None
    left, top, right, bottom = bounds
    return {"left": left, "top": top, "right": right, "bottom": bottom}


def validate_tile(path: Path, profile_name: str, profile: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    with Image.open(path) as original:
        if original.mode != "RGBA":
            problems.append(f"format is {original.mode}; expected RGBA")
        expected_canvas = profile["canvas"]
        actual_canvas = {"width": original.width, "height": original.height}
        if actual_canvas != expected_canvas:
            problems.append(
                f"canvas is {original.width}x{original.height}; expected "
                f"{expected_canvas['width']}x{expected_canvas['height']} (tolerance 0 px)"
            )
        if original.mode != "RGBA":
            problems.append("opaque bounds and anchor cannot be validated until the source has a real alpha channel")
            return problems
        image = original.convert("RGBA")
        expected_bounds = profile.get("opaqueBounds")
        bounds = alpha_bounds(image)
        if expected_bounds is not None and bounds != expected_bounds:
            problems.append(f"opaque bounds are {bounds}; expected {expected_bounds} (tolerance 0 px)")
        max_content_y = profile.get("maxContentY")
        if max_content_y is not None:
            alpha = image.getchannel("A")
            below = alpha.crop((0, max_content_y + 1, image.width, image.height)).getbbox()
            if below is not None:
                problems.append(
                    f"has non-transparent content below row {max_content_y}: "
                    f"first offending bounds {below}"
                )
    return problems


def coast_paths(contract: dict[str, Any]) -> list[Path]:
    catalog_path = ROOT / contract["profiles"]["coast"]["catalog"]
    document = json.loads(catalog_path.read_text(encoding="utf-8"))
    paths: set[Path] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            texture = value.get("texture")
            if isinstance(texture, str):
                paths.add(ROOT / texture)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(document)
    return sorted(paths)


def report(path: Path, profile: str, problems: list[str], debug: bool) -> bool:
    relative = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
    if problems:
        print(f"[GROUND TILE REJECTED] {relative} [{profile}]")
        for problem in problems:
            print(f"  - {problem}")
        return False
    if debug:
        print(f"[GROUND TILE ACCEPTED] {relative} [{profile}]")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="validate every canonical ground-tile profile")
    parser.add_argument("--profile", help="profile for one or more explicit --file entries")
    parser.add_argument("--file", type=Path, action="append", default=[], help="candidate PNG to validate")
    parser.add_argument("--directory", type=Path, action="append", default=[],
                        help="validate every top-level PNG in a candidate directory")
    parser.add_argument("--debug", action="store_true", help="also print each accepted tile")
    args = parser.parse_args()
    if not args.all and (args.profile is None or not (args.file or args.directory)):
        parser.error("use --all, or provide --profile with --file and/or --directory")

    contract = load_contract()
    profiles = contract["profiles"]
    if args.profile is not None and args.profile not in profiles:
        parser.error("unknown profile '" + args.profile + "'; expected one of " + ", ".join(sorted(profiles)))
    targets: list[tuple[Path, str]] = []
    if args.all:
        targets.extend((ROOT / profiles[name]["reference"], name)
                       for name in ("grass", "prepared-soil", "plowed-soil"))
        targets.extend((path, "coast") for path in coast_paths(contract))
    else:
        targets.extend((path, args.profile) for path in args.file)
        for directory in args.directory:
            if not directory.is_dir():
                targets.append((directory, args.profile))
                continue
            targets.extend((path, args.profile) for path in sorted(directory.glob("*.png")))

    accepted = 0
    rejected = 0
    for path, profile_name in targets:
        if not path.is_file():
            report(path, profile_name, ["file is missing"], args.debug)
            rejected += 1
            continue
        if report(path, profile_name, validate_tile(path, profile_name, profiles[profile_name]), args.debug):
            accepted += 1
        else:
            rejected += 1
    print(f"ground-tile contract: {accepted} accepted, {rejected} rejected")
    if rejected:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
