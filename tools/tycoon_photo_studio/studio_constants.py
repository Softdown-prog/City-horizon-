"""studio_constants.py — Shared constants for the CH Tycoon bake pipeline.

All three bake scripts (build_scene.py, build_classic_tree.py,
generate_shape_grammar_asset.py) import from here so that a change to the
tile scale or pixel dimensions propagates automatically.

Contract: these values are frozen alongside CH_CAMERA_V1. Do not alter them
without a corresponding camera contract version bump.
"""

# ---------------------------------------------------------------------------
# World scale
# ---------------------------------------------------------------------------

# Number of Blender world-units per isometric tile.
# One tile = TILE_PX_W × TILE_PX_H px at zoom 1.0.
BLENDER_UNITS_PER_TILE: float = 3.0

# Alias used by generate_shape_grammar_asset.py (legacy name).
TILE_WORLD: float = BLENDER_UNITS_PER_TILE

# ---------------------------------------------------------------------------
# Pixel dimensions
# ---------------------------------------------------------------------------

# Width and height of one isometric tile at the base game resolution.
TILE_PX_W: int = 128
TILE_PX_H: int = 64
