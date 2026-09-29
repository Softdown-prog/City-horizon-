"""Validate the generated CH Clown V4 costume package before promotion.

This is intentionally a strict production gate. It verifies that the generated
costume package still matches the approved CH Actor contract instead of merely
checking that PNG files exist.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

DEFAULT_ROOT = Path("assets/characters/ch_actor_green_01/costumes/clown_01")
EXPECTED_CONTRACT = "CH_ACTOR_COSTUME_V4"
EXPECTED_ACTOR = "ch_actor_green_01"
EXPECTED_COSTUME = "clown_01"
EXPECTED_FRAME = (48, 64)
EXPECTED_ANCHOR = [24, 60]
EXPECTED_SUPERSAMPLE = 4
DIRECTIONS = "senw"


def expected_names() -> list[str]:
    names: list[str] = []
    for key in DIRECTIONS:
        names.append(f"{key}_idle.png")
        names.extend(f"{key}_walk_{index:02d}.png" for index in range(8))
    return names


def validate_png(path: Path, *, label: str) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing {label}: {path}"]

    try:
        with Image.open(path) as image:
            image.load()
            if image.format != "PNG":
                errors.append(f"{label} is not PNG: {path} ({image.format})")
            if image.size != EXPECTED_FRAME:
                errors.append(
                    f"{label} has wrong size: {path} {image.size}, expected {EXPECTED_FRAME}"
                )
            if image.mode != "RGBA":
                errors.append(f"{label} is not RGBA: {path} ({image.mode})")
            elif image.getbbox() is None:
                errors.append(f"{label} is fully transparent: {path}")
    except (OSError, ValueError) as exc:
        errors.append(f"cannot read {label}: {path}: {exc}")

    return errors


def validate_mask_channels(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return errors

    try:
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
            extrema = rgba.getextrema()
            # R/G/B are the three supported customization channels. Requiring
            # all of them prevents a visually valid-looking export from losing
            # one customization region silently.
            for channel, index in (("R", 0), ("G", 1), ("B", 2)):
                if extrema[index][1] == 0:
                    errors.append(f"mask has no {channel} customization data: {path}")
            if extrema[3][1] == 0:
                errors.append(f"mask has no alpha coverage: {path}")
    except (OSError, ValueError):
        # The main PNG validation reports the detailed read error.
        pass

    return errors


def validate_manifest(root: Path, expected: list[str]) -> list[str]:
    errors: list[str] = []
    path = root / "manifest.json"
    if not path.is_file():
        return [f"missing manifest: {path}"]

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read manifest: {path}: {exc}"]

    checks = (
        ("contract", manifest.get("contract"), EXPECTED_CONTRACT),
        ("actor", manifest.get("actor"), EXPECTED_ACTOR),
        ("costume", manifest.get("costume"), EXPECTED_COSTUME),
        ("motionPolicy", manifest.get("motionPolicy"), "reuse_approved_actor_frames_without_pose_changes"),
    )
    for field, actual, wanted in checks:
        if actual != wanted:
            errors.append(f"manifest {field}={actual!r}, expected {wanted!r}")

    frame = manifest.get("frame") or {}
    if (frame.get("width"), frame.get("height")) != EXPECTED_FRAME:
        errors.append(
            "manifest frame size "
            f"{(frame.get('width'), frame.get('height'))!r}, expected {EXPECTED_FRAME!r}"
        )
    if frame.get("groundAnchor") != EXPECTED_ANCHOR:
        errors.append(
            f"manifest groundAnchor={frame.get('groundAnchor')!r}, expected {EXPECTED_ANCHOR!r}"
        )
    if frame.get("authoringSupersample") != EXPECTED_SUPERSAMPLE:
        errors.append(
            "manifest authoringSupersample="
            f"{frame.get('authoringSupersample')!r}, expected {EXPECTED_SUPERSAMPLE}"
        )

    manifest_frames = manifest.get("frames")
    if manifest_frames != expected:
        errors.append("manifest frame list does not exactly match the approved 36-frame ordering")

    mask_channels = manifest.get("maskChannels") or {}
    expected_channels = {
        "R": "primary_costume",
        "G": "secondary_costume",
        "B": "wig",
        "A": "overlay_alpha",
    }
    if mask_channels != expected_channels:
        errors.append(
            f"manifest maskChannels={mask_channels!r}, expected {expected_channels!r}"
        )

    return errors


def validate(root: Path) -> list[str]:
    expected = expected_names()
    errors = validate_manifest(root, expected)
    frame_dir = root / "frames"
    mask_dir = root / "masks"

    for filename in expected:
        frame_path = frame_dir / filename
        mask_path = mask_dir / filename
        errors.extend(validate_png(frame_path, label="overlay"))
        errors.extend(validate_png(mask_path, label="mask"))
        errors.extend(validate_mask_channels(mask_path))

    if frame_dir.is_dir():
        actual = sorted(path.name for path in frame_dir.glob("*.png"))
        unexpected = sorted(set(actual) - set(expected))
        if unexpected:
            errors.append(f"unexpected overlay PNGs: {', '.join(unexpected)}")
    if mask_dir.is_dir():
        actual = sorted(path.name for path in mask_dir.glob("*.png"))
        unexpected = sorted(set(actual) - set(expected))
        if unexpected:
            errors.append(f"unexpected mask PNGs: {', '.join(unexpected)}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()

    errors = validate(args.root)
    if errors:
        print(f"CH Clown V4 validation FAILED ({len(errors)} error(s))")
        for error in errors:
            print(f" - {error}")
        return 1

    print("CH Clown V4 validation OK")
    print(" - 36 overlays: 48x64 RGBA PNG")
    print(" - 36 masks: 48x64 RGBA PNG with R/G/B customization data")
    print(" - ground anchor: [24, 60]")
    print(" - approved motion policy preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
