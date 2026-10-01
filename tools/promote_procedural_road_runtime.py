#!/usr/bin/env python3
"""One-shot safe promotion of CH procedural 2D roads into the game runtime.

This script edits only RuntimeMapRenderer::render_roads. The permanent proof
workflow is updated separately through the GitHub connector so the Actions token
does not need workflow-write permission.

It is idempotent so a rerun is harmless. The temporary promotion workflow rebases
its generated commit onto the current main before pushing, avoiding force pushes
when unrelated City Horizon work lands concurrently.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "src/runtime_map_renderer.h"


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


def main() -> None:
    promote_runtime()
    print("Procedural 2D road runtime promotion patch applied.")


if __name__ == "__main__":
    main()
