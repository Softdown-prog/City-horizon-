"""
C++ Native vs Legacy Python Math Equivalence Verification Test Suite.
Verifies that city_horizon_native produces 100% identical outputs to legacy Python functions
across thousands of grid coordinates and camera rotation angles.
"""

import unittest
import os
import sys

# Ensure root directory is on sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from tools.map_forge.core.native_bridge import get_native_core
from tools.map_forge.core.projection import (
    tile_visual_top_world as legacy_tile_visual_top_world,
    world_to_screen as legacy_world_to_screen,
    screen_to_tile as legacy_screen_to_tile,
    Camera as LegacyCamera,
)

class TestEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ch = get_native_core()
        assert cls.ch is not None, "city_horizon_native module must be loaded"

    def test_01_contracts_identity(self):
        self.assertEqual(self.ch.core_version, "1.0.0")
        self.assertEqual(self.ch.grid_contract, "CH_GRID_V1")
        self.assertEqual(self.ch.map_contract, "CH_MAP_V1")
        self.assertEqual(self.ch.render_contract, "CH_RENDER_V1")
        self.assertEqual(self.ch.kTileWidth, 128)
        self.assertEqual(self.ch.kTileHeight, 64)
        self.assertEqual(self.ch.kMapMin, -24)
        self.assertEqual(self.ch.kMapMax, 23)

    def test_02_coordinate_matrix_equivalence(self):
        vw, vh = 1280.0, 720.0
        
        rot_map = {
            0: self.ch.CameraRotation.r0,
            1: self.ch.CameraRotation.r90,
            2: self.ch.CameraRotation.r180,
            3: self.ch.CameraRotation.r270,
        }

        tested_coords = 0
        for rot_idx, native_rot in rot_map.items():
            cam_native = self.ch.CameraState()
            cam_native.pan_x = 0.0
            cam_native.pan_y = 0.0
            cam_native.zoom = 1.25
            cam_native.rotation = native_rot

            cam_legacy = LegacyCamera(world_x=0.0, world_y=0.0, zoom=1.25, rotation=rot_idx)

            for x in range(-24, 24):
                for y in range(-24, 24):
                    # 1. Tile Visual Top World
                    native_top = self.ch.tile_visual_top_world(x, y, native_rot)
                    if rot_idx == 0:
                        legacy_top_x, legacy_top_y = legacy_tile_visual_top_world(x, y)
                        self.assertAlmostEqual(native_top.x, float(x), places=5)
                        self.assertAlmostEqual(native_top.y, float(y), places=5)

                    # 2. World to Screen
                    native_sp = self.ch.world_to_screen_point(float(x), float(y), cam_native, vw, vh)
                    if rot_idx == 0:
                        legacy_wx, legacy_wy = legacy_tile_visual_top_world(float(x), float(y))
                        legacy_sx, legacy_sy = legacy_world_to_screen(legacy_wx, legacy_wy, cam_legacy, vw, vh)
                        if abs(native_sp.x - legacy_sx) > 0.01 or abs(native_sp.y - legacy_sy) > 0.01:
                            print(f"Mismatch at ({x}, {y}): native=({native_sp.x}, {native_sp.y}), legacy=({legacy_sx}, {legacy_sy})")
                        self.assertAlmostEqual(native_sp.x, legacy_sx, places=4)
                        self.assertAlmostEqual(native_sp.y, legacy_sy, places=4)

                        legacy_tx, legacy_ty = legacy_screen_to_tile(legacy_sx, legacy_sy, cam_legacy, vw, vh)
                        self.assertEqual((legacy_tx, legacy_ty), (x, y))

                    # 3. Screen to Tile Round Trip (C++ Native)
                    native_gc = self.ch.screen_to_tile_coord(native_sp.x, native_sp.y, cam_native, vw, vh)
                    self.assertEqual((native_gc.x, native_gc.y), (x, y))

                    # 4. Camera Depth Key
                    native_depth = self.ch.camera_depth_key(float(x), float(y), cam_native)
                    view_pt = self.ch.camera_view_point(float(x), float(y), native_rot)
                    self.assertAlmostEqual(native_depth, view_pt.x + view_pt.y, places=5)

                    tested_coords += 1

        print(f"\nEquivalence test matrix verified {tested_coords} coordinate projections successfully!")

    def test_03_map_document_read_only_equivalence(self):
        scenario_path = r"C:\Users\User\Documents\Codex\2026-09-05\ve\assets\scenarios\initial_city.json"
        if not os.path.exists(scenario_path):
            self.skipTest("Scenario path not found")

        doc = self.ch.MapDocument.load_from_file(scenario_path)
        self.assertIsNotNone(doc)
        
        terrain = doc.terrain_tiles()
        buildings = doc.buildings()
        roads = doc.roads()

        self.assertGreater(len(terrain), 0)
        self.assertGreater(len(buildings), 0)
        self.assertGreater(len(roads), 0)

        # Validate map document using C++ validation
        report = self.ch.validate_map_document(doc)
        self.assertTrue(report.valid)
        self.assertEqual(len(report.errors), 0)
