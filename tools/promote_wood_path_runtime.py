#!/usr/bin/env python3
"""Register the generated wooden path family in the City Horizon runtime.

This is deliberately narrow: it only adds the `wood_path` style to the existing
sidewalk/floor flow, renderer lookup, and floor catalog.  It does not change the
rules for other tile recipes.
"""
from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"already promoted: {path}")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one promotion anchor in {path}; found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched: {path}")


def main() -> None:
    renderer = Path("src/runtime_map_renderer.h")
    renderer_anchor = '''    if (style_id == "sand_path") {
        std::string filename = dirt_path_sprite(connections).substr(std::string("assets/terrain/paths/dirt_01/").size());
        filename.replace(0, 4, "sand");
        return "assets/terrain/paths/sand_01/" + filename;
    }
'''
    renderer_replacement = renderer_anchor + '''    if (style_id == "wood_path") {
        std::string filename = dirt_path_sprite(connections).substr(std::string("assets/terrain/paths/dirt_01/").size());
        filename.replace(0, 4, "wood");
        return "assets/terrain/paths/wood_01/" + filename;
    }
'''
    replace_once(renderer, renderer_anchor, renderer_replacement)

    runtime = Path("src/main_runtime_impl.cpp")
    runtime_anchor = '''                if (action.payload == "dirt_path" || action.payload == "sand_path" || action.payload == "grass" ||
                    action.payload == "crosswalk_ns" || action.payload == "crosswalk_ew") {
'''
    runtime_replacement = '''                if (action.payload == "dirt_path" || action.payload == "sand_path" || action.payload == "wood_path" ||
                    action.payload == "grass" || action.payload == "crosswalk_ns" || action.payload == "crosswalk_ew") {
'''
    replace_once(runtime, runtime_anchor, runtime_replacement)

    ui = Path("src/ui_manager.cpp")
    array_anchor = '[[nodiscard]] std::array<UiBuildItem, 3> floor_catalog_items() {'
    array_replacement = '[[nodiscard]] std::array<UiBuildItem, 4> floor_catalog_items() {'
    replace_once(ui, array_anchor, array_replacement)

    card_anchor = '''        {"sand_path", "Tile de Areia", "PISO", "$0 / TILE", true,
         runtime_asset_path("assets/terrain/paths/sand_01/sand_path_00_isolated.png"),
         "1x1", "TERRENO PROPRIO | CLIQUE E ARRASTE", 1},
'''
    card_replacement = card_anchor + '''        {"wood_path", "Caminho de Madeira", "PISO", "$0 / TILE", true,
         runtime_asset_path("assets/terrain/paths/wood_01/wood_path_00_isolated.png"),
         "1x1", "TERRENO PROPRIO | CLIQUE E ARRASTE", 1},
'''
    replace_once(ui, card_anchor, card_replacement)

    print("PASS wood_path runtime registration")


if __name__ == "__main__":
    main()
