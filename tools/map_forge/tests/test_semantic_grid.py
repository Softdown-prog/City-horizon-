import unittest
import os
import sys

# Add ve root to sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from tools.map_forge.core.native_bridge import get_native_core


class TestSemanticGrid(unittest.TestCase):

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

    def test_semantic_contracts_declared(self):
        """Verify all 5 Phase D contract version strings are exported by native core."""
        self.assertEqual(self.core.anchor_contract, "CH_ANCHOR_V1")
        self.assertEqual(self.core.footprint_contract, "CH_FOOTPRINT_V1")
        self.assertEqual(self.core.connector_contract, "CH_CONNECTOR_V1")
        self.assertEqual(self.core.semantic_overlay_contract, "CH_SEMANTIC_OVERLAY_V1")
        self.assertEqual(self.core.semantic_state_contract, "CH_SEMANTIC_STATE_V1")

    def test_inspect_tile_channels_building(self):
        """Inspect a building tile and verify three-value semantic state response."""
        doc = self.core.MapDocument.load_from_file(self.scenario_path)
        buildings = doc.buildings()
        self.assertGreater(len(buildings), 0, "Initial scenario must contain buildings")

        b0 = buildings[0]
        info = self.core.inspect_tile_channels(doc, b0.tile_x, b0.tile_y)

        self.assertEqual(info.footprint_state, self.core.SemanticState.VALID)
        self.assertEqual(info.occupancy_state, self.core.SemanticState.VALID)
        self.assertEqual(info.buildable_state, self.core.SemanticState.INVALID)
        self.assertEqual(info.pivot_state, self.core.SemanticState.VALID)
        self.assertEqual(info.occupied_by_asset, b0.definition_id)

    def test_inspect_tile_channels_clear_tile(self):
        """Inspect a clear tile and verify valid buildable state."""
        doc = self.core.MapDocument.load_from_file(self.scenario_path)
        info = self.core.inspect_tile_channels(doc, -20, -20)

        self.assertEqual(info.footprint_state, self.core.SemanticState.NOT_APPLICABLE)
        self.assertEqual(info.buildable_state, self.core.SemanticState.VALID)
        self.assertEqual(info.water_state, self.core.SemanticState.NOT_APPLICABLE)

    def test_validate_map_semantics(self):
        """Validate scenario map semantics against building catalog."""
        doc = self.core.MapDocument.load_from_file(self.scenario_path)
        catalog = self.core.BuildingCatalog()
        if os.path.exists(self.catalog_dir):
            catalog.load_from_directory(self.catalog_dir)

        divergences = self.core.validate_map_semantics(doc, catalog)
        # Any reported divergence should format as CH_SEMANTIC_DIVERGENCE
        for div in divergences:
            formatted = div.to_formatted_string()
            self.assertTrue(formatted.startswith("CH_SEMANTIC_DIVERGENCE"))
            self.assertIn("contract:", formatted)

    def test_synthetic_divergence_report_formatting(self):
        """Verify zero-tolerance CH_SEMANTIC_DIVERGENCE report output format."""
        div = self.core.SemanticDivergence()
        div.object_id = "residence_01"
        div.tile = self.core.GridCoord(8, 12)
        div.contract = self.core.anchor_contract
        div.field = "resolved_anchor_x"
        div.expected = "640"
        div.actual = "641"
        div.delta = "+1 px"
        div.status = self.core.SemanticState.INVALID

        formatted = div.to_formatted_string()
        expected_output = (
            "CH_SEMANTIC_DIVERGENCE\n"
            "object: residence_01\n"
            "tile: 8,12\n"
            "contract: CH_ANCHOR_V1\n"
            "field: resolved_anchor_x\n"
            "expected: 640\n"
            "actual: 641\n"
            "delta: +1 px\n"
            "status: REJECTED"
        )
        self.assertEqual(formatted, expected_output)


if __name__ == "__main__":
    unittest.main()
