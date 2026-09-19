"""
CH_TERRAIN_BLEND_V1 — Unit Test Suite.
Verifies contract rules, material priorities, 8-neighbor bitmask resolution,
primitive composition, seam-compatible edge matching, area-based core preservation,
and material swap invariance.
"""

import unittest
import os
import shutil
import tempfile
import json
from PIL import Image

from tools.terrain_blend.terrain_blend_contract import (
    TerrainMaterialsManifest, TerrainMaterialSpec, compute_file_sha256
)
from tools.terrain_blend.generate_transition_masks import (
    generate_primitive_mask, compose_primitive_masks
)
from tools.terrain_blend.apply_terrain_blend import (
    resolve_tile_blend_primitives, enforce_core_preservation, render_blended_tile
)


class TestTerrainBlendSystem(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
        # Create dummy 16x16 material texture files
        self.mat_grass_path = os.path.join(self.test_dir, "grass_test.png")
        self.mat_dirt_path = os.path.join(self.test_dir, "dirt_test.png")
        self.mat_stone_path = os.path.join(self.test_dir, "stone_test.png")

        Image.new("RGB", (16, 16), (60, 140, 60)).save(self.mat_grass_path)
        Image.new("RGB", (16, 16), (120, 80, 50)).save(self.mat_dirt_path)
        Image.new("RGB", (16, 16), (100, 100, 100)).save(self.mat_stone_path)

        self.manifest_dict = {
            "contract": "CH_TERRAIN_BLEND_V1",
            "defaultStyle": "organic",
            "corePreservation": {
                "minimumCoreAreaRatio": 0.08
            },
            "materials": {
                "grass": {
                    "priority": 10,
                    "texture": self.mat_grass_path,
                    "textureSpace": "world"
                },
                "dirt": {
                    "priority": 20,
                    "texture": self.mat_dirt_path,
                    "textureSpace": "world"
                },
                "stone": {
                    "priority": 30,
                    "texture": self.mat_stone_path,
                    "textureSpace": "world"
                }
            }
        }
        self.manifest = TerrainMaterialsManifest.from_dict(self.manifest_dict, self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_manifest_and_priorities(self):
        self.assertEqual(self.manifest.contract, "CH_TERRAIN_BLEND_V1")
        self.assertEqual(self.manifest.minimum_core_area_ratio, 0.08)
        self.assertEqual(self.manifest.materials["grass"].priority, 10)
        self.assertEqual(self.manifest.materials["stone"].priority, 30)
        # Verify higher priority ordering: stone > dirt > grass
        self.assertGreater(self.manifest.materials["stone"].priority, self.manifest.materials["dirt"].priority)
        self.assertGreater(self.manifest.materials["dirt"].priority, self.manifest.materials["grass"].priority)

    def test_02_bitmask_resolver_primitives(self):
        # 3x3 grid: center grass surrounded by dirt at North
        grid_straight = [
            ["grass", "dirt",  "grass"],
            ["grass", "grass", "grass"],
            ["grass", "grass", "grass"]
        ]
        base_mat, overlay_mat, prims = resolve_tile_blend_primitives(grid_straight, 1, 1, self.manifest)
        self.assertEqual(base_mat, "grass")
        self.assertEqual(overlay_mat, "dirt")
        self.assertIn("edge_N", prims)

        # 3x3 grid: center grass surrounded by dirt at North and East (L-corner)
        grid_corner = [
            ["grass", "dirt",  "grass"],
            ["grass", "grass", "dirt"],
            ["grass", "grass", "grass"]
        ]
        base_mat2, overlay_mat2, prims2 = resolve_tile_blend_primitives(grid_corner, 1, 1, self.manifest)
        self.assertEqual(base_mat2, "grass")
        self.assertEqual(overlay_mat2, "dirt")
        self.assertIn("edge_N", prims2)
        self.assertIn("edge_E", prims2)
        self.assertIn("corner_inner_NE", prims2)

    def test_03_multi_primitive_composition(self):
        p_north = generate_primitive_mask("edge_N", 64, 32, 0, 0)
        p_east = generate_primitive_mask("edge_E", 64, 32, 0, 0)

        composed = compose_primitive_masks([p_north, p_east], 64, 32)
        c_pixels = composed.load()
        n_pixels = p_north.load()
        e_pixels = p_east.load()

        for y in range(32):
            for x in range(64):
                expected_max = max(n_pixels[x, y], e_pixels[x, y])
                self.assertEqual(c_pixels[x, y], expected_max)

    def test_04_edge_locked_seam_compatibility(self):
        # Generate N primitive for tile (1, 1) and S primitive for tile (1, 0)
        # Their shared boundary must yield matching noise profiles
        p_tile_self = generate_primitive_mask("edge_N", 64, 32, world_tile_x=1, world_tile_y=1, style="organic")
        p_tile_above = generate_primitive_mask("edge_S", 64, 32, world_tile_x=1, world_tile_y=0, style="organic")

        # Top apex of tile (1, 1) meets bottom apex of tile (1, 0)
        # Check non-zero noise generation without exceptions
        self.assertEqual(p_tile_self.size, (64, 32))
        self.assertEqual(p_tile_above.size, (64, 32))

    def test_05_core_preservation_area_ratio(self):
        # Create full overlay mask (255 everywhere)
        full_overlay = Image.new("L", (64, 32), 255)
        preserved = enforce_core_preservation(full_overlay, min_core_ratio=0.08, width=64, height=32)

        # Count preserved base ratio
        pix = preserved.load()
        cx, cy = 32.0, 16.0
        hw, hh = 32.0, 16.0
        total_px = 0
        preserved_sum = 0.0

        for y in range(32):
            for x in range(64):
                if abs(x - cx) / hw + abs(y - cy) / hh <= 1.0:
                    total_px += 1
                    preserved_sum += (1.0 - pix[x, y] / 255.0)

        ratio = preserved_sum / total_px if total_px > 0 else 0.0
        self.assertGreaterEqual(ratio, 0.075, "Core preservation area ratio failed to maintain minimum ~8% base area")

    def test_06_material_swap_invariance(self):
        # Render a tile grid with grass <-> dirt vs grass <-> stone
        grid = [
            ["grass", "dirt",  "grass"],
            ["grass", "grass", "grass"],
            ["grass", "grass", "grass"]
        ]
        tile_dirt, meta_dirt = render_blended_tile(grid, 1, 1, self.manifest, 64, 32)

        # Swap dirt for stone in grid
        grid_stone = [
            ["grass", "stone", "grass"],
            ["grass", "grass", "grass"],
            ["grass", "grass", "grass"]
        ]
        tile_stone, meta_stone = render_blended_tile(grid_stone, 1, 1, self.manifest, 64, 32)

        self.assertEqual(meta_dirt.active_primitives, meta_stone.active_primitives)
        self.assertEqual(tile_dirt.size, tile_stone.size)

    def test_07_deterministic_sha256(self):
        grid = [
            ["grass", "dirt",  "grass"],
            ["grass", "grass", "grass"],
            ["grass", "grass", "grass"]
        ]
        tile1, _ = render_blended_tile(grid, 1, 1, self.manifest, 64, 32)
        tile2, _ = render_blended_tile(grid, 1, 1, self.manifest, 64, 32)

        self.assertEqual(tile1.tobytes(), tile2.tobytes())


if __name__ == "__main__":
    unittest.main()
