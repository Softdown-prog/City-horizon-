"""Deterministic road-tile authoring for the SDL isometric renderer.

The renderer uses a 128x64 (2:1) diamond with its world point at the top
vertex. RoadManager's N/E/S/W neighbours share the four *sides* below, not the
four vertices. This tool is the single source of truth for that geometry.

By default it creates five visual-validation masks. The shipped runtime set is
generated with --all --runtime-names --output-dir assets/roads/premium_01.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
SCALE = 4
WIDTH = DISPLAY_WIDTH * SCALE
HEIGHT = DISPLAY_HEIGHT * SCALE
LANE_WIDTH = 2 * SCALE
EDGE_OVERLAP = SCALE  # one final pixel across adjoining diamonds
PADDING = 2 * SCALE  # render beyond each frame before the final crop
CANVAS_WIDTH = WIDTH + 2 * PADDING
CANVAS_HEIGHT = HEIGHT + 2 * PADDING

# RoadSystem: N=1, E=2, S=4, W=8. These are the exact shared-side centres
# derived from main.cpp's world_to_screen() and kTileWidth/kTileHeight.
NORTH, EAST, SOUTH, WEST = 1, 2, 4, 8
PORTS = {
    NORTH: (96 * SCALE, 16 * SCALE),  # midpoint: top -> right
    EAST: (96 * SCALE, 48 * SCALE),   # midpoint: right -> bottom
    SOUTH: (32 * SCALE, 48 * SCALE),  # midpoint: bottom -> left
    WEST: (32 * SCALE, 16 * SCALE),   # midpoint: left -> top
}
CENTER = (64 * SCALE, 32 * SCALE)

FILENAMES = (
    "road_00_isolated.png", "road_01_end_n.png", "road_02_end_e.png", "road_03_curve_ne.png",
    "road_04_end_s.png", "road_05_straight_ns.png", "road_06_curve_es.png", "road_07_tee_no_w.png",
    "road_08_end_w.png", "road_09_curve_nw.png", "road_10_straight_ew.png", "road_11_tee_no_s.png",
    "road_12_curve_sw.png", "road_13_tee_no_e.png", "road_14_tee_no_n.png", "road_15_cross.png",
)
TEST_MASKS = {3, 5, 7, 10, 15}


def lerp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def quadratic(start, control, end, segments: int = 48) -> list[tuple[float, float]]:
    points = []
    for index in range(segments + 1):
        t = index / segments
        a = lerp(start, control, t)
        b = lerp(control, end, t)
        points.append(lerp(a, b, t))
    return points


def connector_paths(mask: int) -> list[list[tuple[float, float]]]:
    """Centre paths for each mask, always beginning/ending at real ports."""
    active = [bit for bit in (NORTH, EAST, SOUTH, WEST) if mask & bit]
    if not active:
        return []
    if len(active) == 1:
        return [[PORTS[active[0]], CENTER]]
    if len(active) >= 3:
        return [[PORTS[bit], CENTER] for bit in active]

    first, second = active
    pair = frozenset(active)
    if pair in (frozenset((NORTH, SOUTH)), frozenset((EAST, WEST))):
        return [[PORTS[first], PORTS[second]]]

    # Rounded right-angle turns. The control points are on the inside of each
    # isometric corner and do not alter either connector endpoint.
    controls = {
        frozenset((NORTH, EAST)): (104 * SCALE, 32 * SCALE),
        frozenset((EAST, SOUTH)): (64 * SCALE, 56 * SCALE),
        frozenset((SOUTH, WEST)): (24 * SCALE, 32 * SCALE),
        frozenset((WEST, NORTH)): (64 * SCALE, 8 * SCALE),
    }
    return [quadratic(PORTS[first], controls[pair], PORTS[second])]


def diamond_mask() -> Image.Image:
    mask = Image.new("L", (CANVAS_WIDTH, CANVAS_HEIGHT), 0)
    ImageDraw.Draw(mask).polygon(
        ((PADDING + WIDTH // 2, PADDING - EDGE_OVERLAP),
         (PADDING + WIDTH + EDGE_OVERLAP, PADDING + HEIGHT // 2),
         (PADDING + WIDTH // 2, PADDING + HEIGHT + EDGE_OVERLAP),
         (PADDING - EDGE_OVERLAP, PADDING + HEIGHT // 2)),
        fill=255,
    )
    return mask


def road_mask(mask: int) -> Image.Image:
    # A road owns the entire logical diamond: adjacent road tiles therefore meet
    # on their shared side with no grass seam.  Alpha is transparent only
    # outside that diamond; ROAD_WIDTH describes the internal traffic corridor.
    del mask
    return diamond_mask()


def path_distances(path: list[tuple[float, float]]) -> list[float]:
    distances = [0.0]
    for start, end in zip(path, path[1:]):
        distances.append(distances[-1] + math.dist(start, end))
    return distances


def point_at_distance(path: list[tuple[float, float]], distances: list[float], distance: float) -> tuple[float, float]:
    for index in range(len(path) - 1):
        if distances[index + 1] >= distance:
            span = max(0.0001, distances[index + 1] - distances[index])
            return lerp(path[index], path[index + 1], (distance - distances[index]) / span)
    return path[-1]


def trim_path_tail(path: list[tuple[float, float]], trim: float) -> list[tuple[float, float]]:
    """Keep a path's port end while reserving visual space at its far end."""
    distances = path_distances(path)
    target_length = max(0.0, distances[-1] - trim)
    if target_length <= 0.0:
        return [path[0]]
    result = [point for point, distance in zip(path, distances) if distance < target_length]
    result.append(point_at_distance(path, distances, target_length))
    return result


def offset_path(path: list[tuple[float, float]], offset: float) -> list[tuple[float, float]]:
    """Offset a sampled centre path by a screen-space normal."""
    if len(path) < 2:
        return path
    result = []
    for index, point in enumerate(path):
        before = path[max(0, index - 1)]
        after = path[min(len(path) - 1, index + 1)]
        dx = after[0] - before[0]
        dy = after[1] - before[1]
        length = max(0.0001, math.hypot(dx, dy))
        result.append((point[0] - dy * offset / length, point[1] + dx * offset / length))
    return result


def path_dashes(path: list[tuple[float, float]], dash=7 * SCALE, gap=5 * SCALE, start=0.0):
    distances = path_distances(path)
    total = distances[-1]
    if total == 0:
        return []

    segments = []
    position = start
    while position < total:
        end = min(total, position + dash)
        segments.append((point_at_distance(path, distances, position), point_at_distance(path, distances, end)))
        position = end + gap
    return segments


def asphalt_texture() -> Image.Image:
    """Clean, stylized asphalt; details must not form a repeating tile pattern."""
    return Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (52, 57, 60, 255))


def render_tile(mask: int) -> Image.Image:
    alpha = road_mask(mask)
    # Keep straight RGB at the diamond edge. The padded render and one-pixel
    # overlap let antialiasing cover the shared side rather than reveal grass.
    image = asphalt_texture()
    image.putalpha(alpha)

    # Concrete curb/sidewalk lip belongs only to unconnected sides. A shared
    # side stays asphalt so adjacent road sprites join without a white seam.
    corners = ((PADDING + WIDTH // 2, PADDING - EDGE_OVERLAP),
               (PADDING + WIDTH + EDGE_OVERLAP, PADDING + HEIGHT // 2),
               (PADDING + WIDTH // 2, PADDING + HEIGHT + EDGE_OVERLAP),
               (PADDING - EDGE_OVERLAP, PADDING + HEIGHT // 2))
    sides = {NORTH: (corners[0], corners[1]),
             EAST: (corners[1], corners[2]),
             SOUTH: (corners[2], corners[3]),
             WEST: (corners[3], corners[0])}
    curbs = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    curb_draw = ImageDraw.Draw(curbs)
    for direction, edge in sides.items():
        if not mask & direction:
            curb_draw.line(edge, fill=(164, 157, 140, 255), width=11 * SCALE)
            curb_draw.line(edge, fill=(215, 207, 186, 255), width=4 * SCALE)
    # Two adjoining sprites meet at a diamond vertex. Their clipped line ends
    # otherwise leave a dark triangular notch at every tile boundary.
    incident = ((WEST, NORTH), (NORTH, EAST), (EAST, SOUTH), (SOUTH, WEST))
    for point, touching in zip(corners, incident):
        if all(mask & direction for direction in touching):
            continue
        for radius, color in ((5.5 * SCALE, (164, 157, 140, 255)),
                              (2.0 * SCALE, (215, 207, 186, 255))):
            x, y = point
            curb_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    curbs.putalpha(ImageChops.multiply(curbs.getchannel("A"), alpha))
    image = Image.alpha_composite(image, curbs)

    paths = connector_paths(mask)
    # Roads own the complete diamond.  Earlier versions drew a second, narrow
    # "corridor" plus white borders inside every tile.  At turns and junctions
    # those repeated borders read as disconnected black pieces of road.  A
    # clean asphalt surface gives adjacent tiles a continuous city-block road
    # first; markings are now only an aid on true straight stretches.
    markings = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(markings)
    active = [bit for bit in (NORTH, EAST, SOUTH, WEST) if mask & bit]
    opposite_straight = (
        len(active) == 2
        and frozenset(active) in (frozenset((NORTH, SOUTH)), frozenset((EAST, WEST)))
    )
    if opposite_straight:
        # The dashed centre line crosses the real shared-side centres, so the
        # next tile continues it exactly.  Curves, ends and intersections stay
        # unmarked deliberately: they are much clearer than a pile of tiny,
        # conflicting stripes on an isometric 128x64 diamond.
        # A whole number of periods fits between ports. Half a gap at either
        # end joins the next tile into one continuous dashed lane line.
        period = path_distances(paths[0])[-1] / 4.0
        gap = period * 0.45
        for start, end in path_dashes(paths[0], dash=period - gap, gap=gap, start=gap * 0.5):
            draw.line(((start[0] + PADDING, start[1] + PADDING),
                       (end[0] + PADDING, end[1] + PADDING)),
                      fill=(235, 185, 47, 230), width=LANE_WIDTH)
    # Paint is clipped by the same road geometry; no stripe can leak into grass.
    markings.putalpha(ImageChops.multiply(markings.getchannel("A"), alpha))
    image = Image.alpha_composite(image, markings)
    image.putalpha(alpha)
    full = image.resize((DISPLAY_WIDTH + 4, DISPLAY_HEIGHT + 4), Image.Resampling.LANCZOS)
    return full.crop((2, 2, 2 + DISPLAY_WIDTH, 2 + DISPLAY_HEIGHT))


def world_to_preview(tile_x: int, tile_y: int, origin: tuple[int, int]) -> tuple[int, int]:
    top_x = origin[0] + (tile_x - tile_y) * (DISPLAY_WIDTH // 2)
    top_y = origin[1] + (tile_x + tile_y) * (DISPLAY_HEIGHT // 2)
    return top_x - DISPLAY_WIDTH // 2, top_y


def build_preview(tiles: dict[int, Image.Image], output: Path) -> None:
    """An exact renderer-space straight continuity check, not an atlas mockup."""
    preview = Image.new("RGBA", (900, 420), (85, 126, 61, 255))
    origin = (300, 60)
    # Four contiguous N/S straight tiles and four E/W straight tiles. They use
    # the same position formula as main.cpp and expose any actual geometry gap.
    for coordinate in ((0, 0), (0, -1), (0, -2), (0, -3)):
        preview.alpha_composite(tiles[5], world_to_preview(*coordinate, origin))
    for coordinate in ((3, 0), (4, 0), (5, 0), (6, 0)):
        preview.alpha_composite(tiles[10], world_to_preview(*coordinate, origin))

    # Individual topology samples, intentionally separated from the continuity
    # test until the whole 16-tile set is approved.
    for mask, coordinate in ((3, (1, 4)), (7, (3, 4)), (15, (5, 4))):
        preview.alpha_composite(tiles[mask], world_to_preview(*coordinate, origin))
    preview.save(output)


def validate_ports(tiles: dict[int, Image.Image]) -> None:
    # Road alpha must reach the true connector centre for every active mask.
    for mask, image in tiles.items():
        alpha = image.getchannel("A")
        for bit, (x, y) in PORTS.items():
            if mask & bit:
                sample = alpha.getpixel((round(x / SCALE), round(y / SCALE)))
                if sample == 0:
                    raise RuntimeError(f"mask {mask} does not reach connector {bit}")


def validate_straight_seams(tiles: dict[int, Image.Image]) -> None:
    """Catch a grass-coloured stripe where two straight road diamonds meet."""
    background = (85, 126, 61, 255)
    asphalt = (52, 57, 60)
    cases = (
        (5, (128, 32), ((144, 72), (176, 88))),
        (10, (128, 96), ((176, 104), (144, 120))),
    )
    for mask, second_origin, samples in cases:
        composite = Image.new("RGBA", (300, 200), background)
        composite.alpha_composite(tiles[mask], (64, 64))
        composite.alpha_composite(tiles[mask], second_origin)
        for position in samples:
            pixel = composite.getpixel(position)
            if max(abs(pixel[channel] - asphalt[channel]) for channel in range(3)) > 3:
                raise RuntimeError(f"road mask {mask} has a visible seam at {position}: {pixel}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="generate all sixteen masks")
    parser.add_argument("--output-dir", type=Path, default=Path("assets/roads"))
    parser.add_argument("--preview", type=Path, default=Path("work/road_geometry_preview.png"))
    parser.add_argument("--runtime-names", action="store_true", help="write road_00.png ... road_15.png for RoadVisualCatalog")
    args = parser.parse_args()

    masks = range(16) if args.all else sorted(TEST_MASKS)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.preview.parent.mkdir(parents=True, exist_ok=True)
    tiles: dict[int, Image.Image] = {}
    for mask in masks:
        tile = render_tile(mask)
        filename = f"road_{mask:02}.png" if args.runtime_names else FILENAMES[mask]
        tile.save(args.output_dir / filename)
        tiles[mask] = tile
        print(f"wrote {args.output_dir / filename}")

    validate_ports(tiles)
    if TEST_MASKS.issubset(tiles):
        validate_straight_seams(tiles)
        build_preview(tiles, args.preview)
        print(f"wrote {args.preview}")


if __name__ == "__main__":
    main()
