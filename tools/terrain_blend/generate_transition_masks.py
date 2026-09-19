"""
CH_TERRAIN_BLEND_V1 — Projection-Aware Composable Primitive Transition Mask Generator.
Generates 8-bit single-channel grayscale (mode: "L") primitive transition masks for 2:1 isometric diamond tiles.
Implements edge-locked world seed functions to guarantee 100% seam-compatible organic noise boundaries.
"""

import os
import math
import hashlib
from PIL import Image

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def compute_edge_noise_1d(u: float, world_edge_x: int, world_edge_y: int, edge_id: str, style: str = "organic") -> float:
    """
    Computes a deterministic 1D organic noise displacement in range [-1.0, 1.0] along a shared world edge segment u in [0, 1].
    Uses 1D Sine Fourier / Hash harmonics so u=0 and u=1 match at vertices.
    """
    if style == "soft":
        return 0.0

    # Create deterministic seed from world edge coordinates and orientation
    seed_str = f"edge_{world_edge_x}_{world_edge_y}_{edge_id}_{style}"
    h = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest(), 16)
    
    # Extract phase offsets for 3 octave harmonics
    p1 = ((h & 0xFF) / 255.0) * 2.0 * math.pi
    p2 = (((h >> 8) & 0xFF) / 255.0) * 2.0 * math.pi
    p3 = (((h >> 16) & 0xFF) / 255.0) * 2.0 * math.pi

    # Harmonic frequencies (periodic on 0..1 boundary, vanishing at endpoints u=0, u=1)
    n1 = math.sin(1.0 * math.pi * u + p1) * 0.50
    n2 = math.sin(3.0 * math.pi * u + p2) * 0.30
    n3 = math.sin(5.0 * math.pi * u + p3) * 0.20

    # Envelope to taper noise smoothly to 0 at the diamond corner vertices
    envelope = math.sin(math.pi * u)
    return (n1 + n2 + n3) * envelope


def generate_primitive_mask(
    primitive_type: str,
    width: int = 128,
    height: int = 64,
    world_tile_x: int = 0,
    world_tile_y: int = 0,
    style: str = "organic",
    depth_ratio: float = 0.40
) -> Image.Image:
    """
    Generates an 8-bit single-channel ('L') primitive transition mask for a 2:1 isometric diamond tile.
    
    Primitives supported:
    - 'edge_N', 'edge_E', 'edge_S', 'edge_W'
    - 'corner_outer_NE', 'corner_outer_SE', 'corner_outer_SW', 'corner_outer_NW'
    - 'corner_inner_NE', 'corner_inner_SE', 'corner_inner_SW', 'corner_inner_NW'
    """
    img = Image.new("L", (width, height), 0)
    pixels = img.load()

    cx, cy = width / 2.0, height / 2.0
    hw, hh = width / 2.0, height / 2.0

    for y in range(height):
        for x in range(width):
            # Check if pixel is inside the 2:1 isometric diamond: |x-cx|/hw + |y-cy|/hh <= 1.0
            iso_dist = abs(x - cx) / hw + abs(y - cy) / hh
            if iso_dist > 1.0:
                continue # Outside diamond remains 0

            # Normalized diamond coordinates: rx in [-1, 1], ry in [-1, 1]
            rx = (x - cx) / hw
            ry = (y - cy) / hh

            val = 0.0

            if primitive_type == "edge_N":
                # Encroaches from Top apex (ry = -1) down toward center (ry = 0)
                u = (rx + 1.0) * 0.5  # 0..1 along N edge
                noise = compute_edge_noise_1d(u, world_tile_x, world_tile_y, "N", style) * 0.15
                dist = (-ry) - abs(rx)  # Peak at top apex
                thresh = depth_ratio + noise
                if dist > (1.0 - thresh):
                    val = min(1.0, (dist - (1.0 - thresh)) / 0.25)

            elif primitive_type == "edge_S":
                # Encroaches from Bottom apex (ry = +1) up toward center (ry = 0)
                u = (rx + 1.0) * 0.5
                noise = compute_edge_noise_1d(u, world_tile_x, world_tile_y + 1, "N", style) * 0.15
                dist = (ry) - abs(rx)
                thresh = depth_ratio + noise
                if dist > (1.0 - thresh):
                    val = min(1.0, (dist - (1.0 - thresh)) / 0.25)

            elif primitive_type == "edge_E":
                # Encroaches from Right apex (rx = +1) left toward center (rx = 0)
                u = (ry + 1.0) * 0.5
                noise = compute_edge_noise_1d(u, world_tile_x + 1, world_tile_y, "E", style) * 0.15
                dist = (rx) - abs(ry)
                thresh = depth_ratio + noise
                if dist > (1.0 - thresh):
                    val = min(1.0, (dist - (1.0 - thresh)) / 0.25)

            elif primitive_type == "edge_W":
                # Encroaches from Left apex (rx = -1) right toward center (rx = 0)
                u = (ry + 1.0) * 0.5
                noise = compute_edge_noise_1d(u, world_tile_x, world_tile_y, "E", style) * 0.15
                dist = (-rx) - abs(ry)
                thresh = depth_ratio + noise
                if dist > (1.0 - thresh):
                    val = min(1.0, (dist - (1.0 - thresh)) / 0.25)

            elif primitive_type == "corner_outer_NE":
                # Outer corner at Top-Right quadrant
                u = (rx + ry + 1.0) * 0.5
                noise = compute_edge_noise_1d(u, world_tile_x + 1, world_tile_y, "NE_corner", style) * 0.12
                dist = (rx - ry) / 2.0
                if dist > (0.6 - noise):
                    val = min(1.0, (dist - (0.6 - noise)) / 0.3)

            elif primitive_type == "corner_outer_SE":
                dist = (rx + ry) / 2.0
                u = (rx - ry + 1.0) * 0.5
                noise = compute_edge_noise_1d(u, world_tile_x + 1, world_tile_y + 1, "SE_corner", style) * 0.12
                if dist > (0.6 - noise):
                    val = min(1.0, (dist - (0.6 - noise)) / 0.3)

            elif primitive_type == "corner_outer_SW":
                dist = (-rx + ry) / 2.0
                u = (-rx - ry + 1.0) * 0.5
                noise = compute_edge_noise_1d(u, world_tile_x, world_tile_y + 1, "SW_corner", style) * 0.12
                if dist > (0.6 - noise):
                    val = min(1.0, (dist - (0.6 - noise)) / 0.3)

            elif primitive_type == "corner_outer_NW":
                dist = (-rx - ry) / 2.0
                u = (-rx + ry + 1.0) * 0.5
                noise = compute_edge_noise_1d(u, world_tile_x, world_tile_y, "NW_corner", style) * 0.12
                if dist > (0.6 - noise):
                    val = min(1.0, (dist - (0.6 - noise)) / 0.3)

            elif primitive_type == "corner_inner_NE":
                # Notch/inner corner encroachment near NE
                dist = max(0.0, rx) + max(0.0, -ry)
                if dist > 0.7:
                    val = min(1.0, (dist - 0.7) / 0.3)

            elif primitive_type == "corner_inner_SE":
                dist = max(0.0, rx) + max(0.0, ry)
                if dist > 0.7:
                    val = min(1.0, (dist - 0.7) / 0.3)

            elif primitive_type == "corner_inner_SW":
                dist = max(0.0, -rx) + max(0.0, ry)
                if dist > 0.7:
                    val = min(1.0, (dist - 0.7) / 0.3)

            elif primitive_type == "corner_inner_NW":
                dist = max(0.0, -rx) + max(0.0, -ry)
                if dist > 0.7:
                    val = min(1.0, (dist - 0.7) / 0.3)

            pixels[x, y] = int(val * 255.0)

    return img


def compose_primitive_masks(primitive_images: list, width: int = 128, height: int = 64) -> Image.Image:
    """
    Composes multiple active primitive transition masks via max-layer blending:
    Mask_combined = max(mask_1, mask_2, ...)
    """
    if not primitive_images:
        return Image.new("L", (width, height), 0)

    combined = Image.new("L", (width, height), 0)
    comb_pixels = combined.load()

    for p_img in primitive_images:
        p_pix = p_img.load()
        for y in range(height):
            for x in range(width):
                v1 = comb_pixels[x, y]
                v2 = p_pix[x, y]
                if v2 > v1:
                    comb_pixels[x, y] = v2

    return combined
