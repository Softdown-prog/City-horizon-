#!/usr/bin/env python3
"""Guard the actual game's world-depth draw path against a fused-consist regression.

C++ integration tests cover locomotiva / 7 coaches world poses; this source
check ensures the SDL main runtime consumes those poses, not the locomotive
lead pose re-expanded to a permanently attached train.
"""
from pathlib import Path
import re

source=Path("src/main_runtime_impl.cpp").read_text(encoding="utf-8")
start=source.find("void render_world_entities(")
end=source.find("\nvoid ",start+5)
assert start>=0,"Missing world entity renderer"
render=source[start:end if end!=-1 else None]
assert len(render)>2000,"Renderer extraction invalid"
assert "rail_controller->articulated_poses()" in render, "production draw path bypasses train controller"
assert "build_articulated_consist_poses(" not in render, "production draw path rebuilds a fused train"
assert re.search(r"for\s*\(const auto& unit\s*:\s*rail_units\)",render), "not rendering each independent unit"
assert "camera_depth_key(static_cast<float>(unit.pose.x)" in render, "missing actual independent world-space depth"
assert "std::stable_sort(draws.begin(), draws.end()" in render, "world-depth sorting regressed"
print("CH_RAIL_WORLD_DEPTH_CONSIST_V1: PASS independent actual production rail units in SDL draw queue")
