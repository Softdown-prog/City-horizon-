"""Remove low-alpha red/magenta export guides from building PNGs.

Some source renders contained a horizontal anchor/bounds guide.  It is not
game art: its pixels are vivid red or magenta but almost fully transparent.
The deliberately narrow predicate below preserves opaque red building art.
Run with --check before writing, or with --write to sanitize in place.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BUILDINGS = ROOT / "assets" / "buildings"
CONTRACT_PATH = BUILDINGS / "export_contract.json"


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def is_export_guide(red: int, green: int, blue: int, alpha: int, contract: dict) -> bool:
    """Match only the faint red/magenta matte left by the exporter."""
    # At alpha <= 8 these high-saturation pixels cannot contribute useful
    # building detail. They are colour-matte residue from the export guides
    # (red, magenta, yellow or lime), so remove them wherever they appear.
    matte = contract["matteResidue"]
    return alpha <= matte["maxAlpha"] and max(red, green, blue) - min(red, green, blue) >= matte["minimumSaturation"]


def is_bottom_guide(red: int, green: int, blue: int, alpha: int, contract: dict) -> bool:
    """Match the opaque centre of a guide, but only near the canvas bottom."""
    # The outer antialiasing can retain the debug colour at alpha 1-8. It is
    # safe only as part of a long bottom-edge component, checked below.
    bottom_guide = contract["bottomGuide"]
    if alpha <= bottom_guide["faintMaxAlpha"]:
        return max(red, green, blue) - min(red, green, blue) >= bottom_guide["faintMinimumSaturation"]
    if alpha < bottom_guide["opaqueMinAlpha"]:
        return False
    vivid_red = red >= 170 and red >= green * 1.3 and red >= blue * 1.2
    muted_magenta = red >= green * 1.2 and blue >= green * 1.2 and max(red, green, blue) - min(red, green, blue) >= 25
    return vivid_red or muted_magenta


def largest_alpha_component(image: Image.Image, alpha_threshold: int = 20) -> list[set[tuple[int, int]]]:
    """Return all connected opaque components for an opt-in single-tile check."""
    pixels = image.load()
    width, height = image.size
    remaining = {
        (x, y)
        for y in range(height)
        for x in range(width)
        if pixels[x, y][3] >= alpha_threshold
    }
    components: list[set[tuple[int, int]]] = []
    while remaining:
        pending = [remaining.pop()]
        component = set(pending)
        while pending:
            x, y = pending.pop()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    pending.append(neighbor)
        components.append(component)
    return components


def retain_largest_alpha_component(image: Image.Image, alpha_threshold: int = 20) -> int:
    """Remove detached opaque presentation elements from a single-sprite export.

    This policy is deliberately opt-in.  A building can legitimately contain
    detached foliage or props, whereas a declared *single-tile* export must
    have exactly one dominant connected visual component.  Reference labels,
    compass captions and layout rulers are necessarily detached and fail this
    geometric contract.
    """
    pixels = image.load()
    components = largest_alpha_component(image, alpha_threshold)
    if len(components) <= 1:
        return 0
    largest = max(components, key=len)
    removed = 0
    for component in components:
        if component is largest:
            continue
        for x, y in component:
            if pixels[x, y][3] != 0:
                pixels[x, y] = (0, 0, 0, 0)
                removed += 1
    return removed


def clip_to_largest_component_bounds(image: Image.Image, padding: int = 12) -> int:
    """Erase every pixel outside the padded bounds of a declared single tile.

    Unlike component-only removal, this also removes sub-threshold antialias
    remnants of captions and rulers. It is safe only when explicitly enabled.
    """
    components = largest_alpha_component(image)
    if not components:
        return 0
    largest = max(components, key=len)
    xs = [x for x, _ in largest]
    ys = [y for _, y in largest]
    min_x, max_x = max(0, min(xs) - padding), min(image.width - 1, max(xs) + padding)
    min_y, max_y = max(0, min(ys) - padding), min(image.height - 1, max(ys) + padding)
    pixels = image.load()
    removed = 0
    for y in range(image.height):
        for x in range(image.width):
            if not (min_x <= x <= max_x and min_y <= y <= max_y) and pixels[x, y][3] != 0:
                pixels[x, y] = (0, 0, 0, 0)
                removed += 1
    return removed


def enforce_max_content_y(image: Image.Image, max_content_y: int) -> int:
    """Enforce the declared lower bound of a fixed-canvas sprite export."""
    if not 0 <= max_content_y < image.height:
        raise ValueError(f"max content row {max_content_y} is outside a {image.height}px canvas")
    pixels = image.load()
    removed = 0
    for y in range(max_content_y + 1, image.height):
        for x in range(image.width):
            if pixels[x, y][3] != 0:
                pixels[x, y] = (0, 0, 0, 0)
                removed += 1
    return removed


def clean(path: Path, write: bool, contract: dict, keep_largest_component: bool,
          clip_largest_component_bounds: bool, max_content_y: int | None) -> int:
    original = Image.open(path)
    if original.mode != contract["format"]["mode"]:
        raise ValueError(f"{path.name}: expected {contract['format']['mode']}, got {original.mode}")
    image = original.convert("RGBA")
    pixels = image.load()
    removed = 0
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if is_export_guide(red, green, blue, alpha, contract):
                pixels[x, y] = (0, 0, 0, 0)
                removed += 1

    # Some exporters store the centre of the guide with normal alpha. Limit
    # this second pass to long, thin red/magenta components touching the
    # bottom edge: real painted building details cannot match that geometry.
    bottom_guide = contract["bottomGuide"]
    bottom = max(0, image.height - bottom_guide["bandHeight"])
    candidates = {
        (x, y)
        for y in range(bottom, image.height)
        for x in range(image.width)
        if is_bottom_guide(*pixels[x, y], contract)
    }
    while candidates:
        pending = [candidates.pop()]
        component = set(pending)
        while pending:
            x, y = pending.pop()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1),
                             (x - 1, y - 1), (x + 1, y - 1), (x - 1, y + 1), (x + 1, y + 1)):
                if neighbor in candidates:
                    candidates.remove(neighbor)
                    component.add(neighbor)
                    pending.append(neighbor)
        xs = [point[0] for point in component]
        ys = [point[1] for point in component]
        touches_bottom = max(ys) == image.height - 1
        is_long_thin_guide = (max(xs) - min(xs) + 1 >= bottom_guide["minimumComponentWidth"] and
                              max(ys) - min(ys) + 1 <= bottom_guide["maximumComponentHeight"])
        if touches_bottom and is_long_thin_guide:
            # Erase the antialiased fringe around the detected centre as well.
            # This remains constrained to the final eight raster rows.
            min_x, max_x = max(0, min(xs) - 2), min(image.width - 1, max(xs) + 2)
            min_y = max(bottom, min(ys) - bottom_guide["fringeRows"])
            for y in range(min_y, image.height):
                for x in range(min_x, max_x + 1):
                    if pixels[x, y][3] != 0:
                        pixels[x, y] = (0, 0, 0, 0)
                        removed += 1
    if keep_largest_component:
        removed += retain_largest_alpha_component(image)
    if clip_largest_component_bounds:
        removed += clip_to_largest_component_bounds(image)
    if max_content_y is not None:
        removed += enforce_max_content_y(image, max_content_y)
    if removed and write:
        # Avoid partially rewriting a source asset if Pillow/Windows rejects
        # an in-place handle. The original survives until a complete PNG is
        # encoded successfully.
        temporary = path.with_suffix(".cleaning.png")
        image.save(temporary, "PNG", optimize=True)
        temporary.replace(path)
    return removed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="sanitize source PNGs in place")
    parser.add_argument("--validate", action="store_true", help="fail when an export violates the contract")
    parser.add_argument("--root", type=Path, default=BUILDINGS,
                        help="PNG directory to inspect; defaults to canonical building exports")
    parser.add_argument("--file", type=Path, action="append", default=[],
                        help="inspect one explicit PNG; may be supplied more than once")
    parser.add_argument("--keep-largest-component", action="store_true",
                        help="opt-in single-tile contract: retain only the dominant opaque component")
    parser.add_argument("--clip-largest-component-bounds", action="store_true",
                        help="opt-in single-tile contract: clear all pixels outside its dominant visual bounds")
    parser.add_argument("--max-content-y", type=int,
                        help="opt-in fixed-canvas contract: reject pixels below this raster row")
    args = parser.parse_args()
    contract = load_contract()

    changed = 0
    pixels = 0
    paths = args.file or sorted(args.root.rglob("*.png"))
    for path in paths:
        try:
            removed = clean(path, args.write, contract, args.keep_largest_component,
                            args.clip_largest_component_bounds, args.max_content_y)
        except ValueError as error:
            print(f"CONTRACT VIOLATION: {error}")
            changed += 1
            continue
        if removed:
            changed += 1
            pixels += removed
            print(f"{path.name}: {removed} guide pixels")
    verb = "removed" if args.write else "would remove"
    print(f"{verb} {pixels} invalid export pixels from {changed} PNG assets")
    if args.validate and (changed != 0 or pixels != 0):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
