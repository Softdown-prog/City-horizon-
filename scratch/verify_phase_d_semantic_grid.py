import os
import sys

# Add ve root to sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from tools.map_forge.core.native_bridge import get_native_core


def run_phase_d_verification():
    print("==================================================")
    print(" PHASE D VERIFICATION GATE — SEMANTIC GRID & GOVERNANCE")
    print("==================================================")

    ch = get_native_core()
    print(f"1. Native Core Version: {ch.core_version}")
    print(f"   Anchor Contract: {ch.anchor_contract}")
    print(f"   Footprint Contract: {ch.footprint_contract}")
    print(f"   Connector Contract: {ch.connector_contract}")
    print(f"   Overlay Contract: {ch.semantic_overlay_contract}")
    print(f"   State Contract: {ch.semantic_state_contract}")

    scenario_path = os.path.join(repo_root, "build", "Debug", "assets", "scenarios", "initial_city.json")
    if not os.path.exists(scenario_path):
        scenario_path = os.path.join(repo_root, "build", "assets", "scenarios", "initial_city.json")

    print(f"\n2. Loading MapDocument from '{scenario_path}'...")
    doc = ch.MapDocument.load_from_file(scenario_path)
    assert doc is not None, "Failed to load MapDocument"
    print(f"   Buildings: {len(doc.buildings())}, Roads: {len(doc.roads())}")

    # 3. Test Tile Channel Inspection
    b0 = doc.buildings()[0]
    print(f"\n3. Inspecting Tile ({b0.tile_x}, {b0.tile_y}) occupied by '{b0.definition_id}'...")
    info = ch.inspect_tile_channels(doc, b0.tile_x, b0.tile_y)
    print(f"   Footprint State: {info.footprint_state.name}")
    print(f"   Occupancy State: {info.occupancy_state.name}")
    print(f"   Buildable State: {info.buildable_state.name}")
    print(f"   Pivot/Anchor State: {info.pivot_state.name}")
    print(f"   Occupied By: {info.occupied_by_asset}")
    assert info.footprint_state == ch.SemanticState.VALID
    assert info.occupancy_state == ch.SemanticState.VALID
    assert info.buildable_state == ch.SemanticState.INVALID

    # 4. Test Zero-Tolerance Divergence Output
    print("\n4. Testing Zero-Tolerance Divergence Output Formatting...")
    div = ch.SemanticDivergence()
    div.object_id = "city_hall_01"
    div.tile = ch.GridCoord(8, 12)
    div.contract = ch.anchor_contract
    div.field = "resolved_anchor_x"
    div.expected = "640"
    div.actual = "641"
    div.delta = "+1 px"
    div.status = ch.SemanticState.INVALID
    fmt = div.to_formatted_string()
    print(fmt)
    assert "CH_SEMANTIC_DIVERGENCE" in fmt
    assert "status: REJECTED" in fmt

    print("\n==================================================")
    print(" PHASE D VERIFICATION GATE: ALL CHECKS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    run_phase_d_verification()
