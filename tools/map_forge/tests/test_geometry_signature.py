"""
Geometry Signature Verification Suite for City Horizon Map Forge (Phase C.3).
Asserts 100% equivalence between Game Runtime State and Map Forge Document signatures
and validates structured divergence reporting on mismatch.
"""

import unittest
import os
import sys

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from tools.map_forge.core.native_bridge import get_native_core


class TestGeometrySignature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ch = get_native_core()
        assert cls.ch is not None, "city_horizon_native module must be loaded"
        cls.asset_root = root_dir

    def test_01_signature_computation_and_hashing(self):
        sig = self.ch.RenderGeometrySignature()
        hash_val = sig.compute_hash()
        self.assertIsInstance(hash_val, str)
        self.assertGreater(len(hash_val), 0)

    def test_02_game_vs_forge_real_signature_equivalence(self):
        """
        Loads initial_city.json into both:
        1. Game side: BuildingCatalog + BuildingManager (C++ Runtime State)
        2. Map Forge side: MapDocument (Canonical Document Source)
        Asserts GAME HASH == FORGE HASH.
        """
        scenario_path = os.path.join(self.asset_root, "assets", "scenarios", "initial_city.json")
        definitions_dir = os.path.join(self.asset_root, "assets", "definitions")
        
        if not os.path.exists(scenario_path) or not os.path.exists(definitions_dir):
            self.skipTest("Required scenario or definitions path missing")

        # 1. Load BuildingCatalog
        catalog = self.ch.BuildingCatalog()
        ok = catalog.load_from_directory(definitions_dir)
        self.assertTrue(ok)

        # 2. Load MapDocument (Forge side)
        doc = self.ch.MapDocument.load_from_file(scenario_path)
        self.assertIsNotNone(doc)

        # 3. Reconstruct BuildingManager (Game Runtime side)
        mgr = self.ch.BuildingManager()
        for b in doc.buildings():
            restored = mgr.restore_instance(catalog, b.definition_id, b.tile_x, b.tile_y, b.rotation)
            self.assertTrue(restored, f"Failed to restore building {b.definition_id} at ({b.tile_x}, {b.tile_y})")

        # 4. Define identical camera state and view bounds
        camera = self.ch.CameraState()
        camera.pan_x = -2.0
        camera.pan_y = 12.0
        camera.zoom = 1.0
        camera.rotation = self.ch.CameraRotation.r0
        vw, vh = 1280.0, 720.0

        # 5. Compute Signatures
        game_sig = self.ch.compute_game_geometry_signature(mgr, catalog, camera, vw, vh)
        forge_sig = self.ch.compute_document_geometry_signature(doc, catalog, camera, vw, vh)

        game_hash = game_sig.compute_hash()
        forge_hash = forge_sig.compute_hash()

        # 6. Assert Signature Identity
        self.assertEqual(game_hash, forge_hash, f"Hash mismatch: Game={game_hash} vs Forge={forge_hash}")

        diff = self.ch.compare_signatures(game_sig, forge_sig)
        self.assertTrue(diff.match, f"Divergence detected: {diff.report}")
        self.assertIn("MATCH", diff.report)

        print(f"\n[GEOMETRY GATE] REAL SCENARIO HASH EQUIVALENCE CONFIRMED:\n  GAME HASH:  {game_hash}\n  FORGE HASH: {forge_hash}")

    def test_03_signature_divergence_reporting(self):
        sig1 = self.ch.RenderGeometrySignature()
        sig2 = self.ch.RenderGeometrySignature()

        # Modify sig2 to simulate rendering divergence
        rec = self.ch.RenderGeometryRecord()
        rec.asset_id = "test_building"
        rec.screen_x = 100.0
        recs = sig2.records
        recs.append(rec)
        sig2.records = recs

        diff = self.ch.compare_signatures(sig1, sig2)
        self.assertFalse(diff.match)
        self.assertIn("CH_RENDER_DIVERGENCE", diff.report)


if __name__ == "__main__":
    unittest.main()
