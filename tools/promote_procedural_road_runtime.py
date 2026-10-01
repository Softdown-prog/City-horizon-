#!/usr/bin/env python3
"""One-shot safe promotion of CH procedural 2D roads into the game runtime.

This script intentionally edits only the two promotion seams:
- RuntimeMapRenderer::render_roads gets a procedural-first call with legacy fallback.
- The existing road proof workflow also compiles the real city_builder executable.

It is idempotent so a rerun is harmless.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "src/runtime_map_renderer.h"
WORKFLOW = ROOT / ".github/workflows/ch-procedural-road-proof.yml"


def promote_runtime() -> None:
    text = RUNTIME.read_text(encoding="utf-8")

    include = '#include "src/runtime_procedural_road_renderer.h"\n'
    if include not in text:
        anchor = '#include "src/ch_render/map_renderer.h"\n'
        if anchor not in text:
            raise SystemExit("runtime_map_renderer.h include anchor not found")
        text = text.replace(anchor, anchor + include, 1)

    call = (
        "        if (try_render_procedural_roads_runtime(\n"
        "                renderer, roads, camera, viewport_width, viewport_height)) {\n"
        "            return;\n"
        "        }\n\n"
    )
    if "try_render_procedural_roads_runtime(" not in text:
        anchor = "        if (!visible.valid || roads.tiles().empty()) return;\n\n"
        if anchor not in text:
            raise SystemExit("RuntimeMapRenderer::render_roads admission anchor not found")
        text = text.replace(anchor, anchor + call, 1)

    RUNTIME.write_text(text, encoding="utf-8")


def promote_gate() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    runtime_asserts = (
        '          grep -q "CH_PROCEDURAL_ROAD_2D_RUNTIME_V1" src/runtime_procedural_road_renderer.h\n'
        '          grep -q "try_render_procedural_roads_runtime" src/runtime_map_renderer.h\n'
    )
    if "CH_PROCEDURAL_ROAD_2D_RUNTIME_V1" not in text:
        anchor = '          grep -q "ProceduralRoad2DMesh" src/ch_render/procedural_road_network_renderer.h\n'
        if anchor not in text:
            raise SystemExit("road proof assertion anchor not found")
        text = text.replace(anchor, anchor + runtime_asserts, 1)

    runtime_build = (
        "      - name: Configure City Horizon runtime\n"
        "        run: >-\n"
        "          cmake -S . -B build/ch-runtime-road -G Ninja\n"
        "          -DCMAKE_BUILD_TYPE=Release\n"
        "          -DBUILD_TESTING=OFF\n\n"
        "      - name: Build City Horizon runtime with procedural 2D roads\n"
        "        run: cmake --build build/ch-runtime-road --target city_builder --parallel 2\n\n"
    )
    if "Build City Horizon runtime with procedural 2D roads" not in text:
        anchor = "      - name: Configure focused MapForge build\n"
        if anchor not in text:
            raise SystemExit("road proof MapForge configure anchor not found")
        text = text.replace(anchor, runtime_build + anchor, 1)

    WORKFLOW.write_text(text, encoding="utf-8")


def main() -> None:
    promote_runtime()
    promote_gate()
    print("Procedural 2D road runtime promotion patch applied.")


if __name__ == "__main__":
    main()
