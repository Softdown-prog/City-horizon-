import unittest
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from tools.map_forge.core.native_bridge import get_native_core


class TestPlacementEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.core = get_native_core()
        candidates = [
            os.path.join(repo_root, "build", "Debug", "assets"),
            os.path.join(repo_root, "build", "assets"),
            os.path.join(repo_root, "assets")
        ]
        asset_base = next((c for c in candidates if os.path.exists(c)), candidates[-1])
        cls.scenario_path = os.path.join(asset_base, "scenarios", "initial_city.json")
        cls.catalog_dir = os.path.join(asset_base, "buildings")

    def test_placement_contract_declared(self):
        """Verify CH_PLACEMENT_V1 contract string exported by native core."""
        self.assertEqual(self.core.placement_contract, "CH_PLACEMENT_V1")

    def test_valid_placement(self):
        """Test valid building placement on clear terrain."""
        doc = self.core.MapDocument.load_from_file(self.scenario_path)
        catalog = self.core.BuildingCatalog()
        if os.path.exists(self.catalog_dir):
            catalog.load_from_directory(self.catalog_dir)

        req = self.core.PlacementRequest()
        req.object_id = "residence_01"
        req.category = self.core.PlacementCategory.BUILDING
        req.origin = self.core.GridCoord(-20, -20)
        req.rotation = 0

        res = self.core.can_place(doc, catalog, req)
        self.assertEqual(res.state, self.core.SemanticState.VALID)
        self.assertEqual(len(res.violations), 0)
        self.assertEqual(res.to_formatted_string(), "CH_PLACEMENT_VALID")

    def test_occupied_placement_rejection(self):
        """Test rejection when placed over an existing building (FOOTPRINT_OCCUPIED)."""
        doc = self.core.MapDocument.load_from_file(self.scenario_path)
        catalog = self.core.BuildingCatalog()
        if os.path.exists(self.catalog_dir):
            catalog.load_from_directory(self.catalog_dir)

        b0 = doc.buildings()[0]

        req = self.core.PlacementRequest()
        req.object_id = "residence_01"
        req.category = self.core.PlacementCategory.BUILDING
        req.origin = self.core.GridCoord(b0.tile_x, b0.tile_y)
        req.rotation = 0

        res = self.core.can_place(doc, catalog, req)
        self.assertEqual(res.state, self.core.SemanticState.INVALID)
        self.assertIn(self.core.PlacementViolation.CH_PLACE_OCCUPIED, res.violations)

        fmt = res.to_formatted_string()
        self.assertTrue(fmt.startswith("CH_PLACEMENT_REJECTED"))
        self.assertIn("CH_PLACE_OCCUPIED", fmt)

    def test_out_of_bounds_rejection(self):
        """Test rejection when footprint extends outside map boundary [-24, 24]."""
        doc = self.core.MapDocument.load_from_file(self.scenario_path)
        catalog = self.core.BuildingCatalog()

        req = self.core.PlacementRequest()
        req.object_id = "residence_01"
        req.category = self.core.PlacementCategory.BUILDING
        req.origin = self.core.GridCoord(30, 30)
        req.rotation = 0

        res = self.core.can_place(doc, catalog, req)
        self.assertEqual(res.state, self.core.SemanticState.INVALID)
        self.assertIn(self.core.PlacementViolation.CH_PLACE_BOUNDS, res.violations)

    def test_zero_mutation_guarantee(self):
        """Verify can_place performs zero state mutation on MapDocument."""
        doc = self.core.MapDocument.load_from_file(self.scenario_path)
        catalog = self.core.BuildingCatalog()
        
        initial_b_count = len(doc.buildings())
        initial_r_count = len(doc.roads())

        req = self.core.PlacementRequest()
        req.object_id = "residence_01"
        req.category = self.core.PlacementCategory.BUILDING
        req.origin = self.core.GridCoord(-20, -20)

        _ = self.core.can_place(doc, catalog, req)

        self.assertEqual(len(doc.buildings()), initial_b_count)
        self.assertEqual(len(doc.roads()), initial_r_count)


if __name__ == "__main__":
    unittest.main()
