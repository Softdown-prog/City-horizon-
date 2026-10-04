#!/usr/bin/env python3
"""Promote the approved stone path and wire priced premium floors into runtime."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

WOOD_COST = 25
STONE_COST = 40


def replace_once(path: Path, old: str, new: str, already: str | None = None) -> None:
    text = path.read_text(encoding="utf-8")
    if old in text:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        return
    if already is not None and already in text:
        return
    raise RuntimeError(f"expected patch anchor not found in {path}: {old[:120]!r}")


def promote_assets(output_root: Path) -> None:
    source = output_root / "stone_01"
    target = Path("assets/terrain/paths/stone_01")
    target.mkdir(parents=True, exist_ok=True)
    pngs = sorted(source.glob("stone_path_*.png"))
    if len(pngs) != 16:
        raise RuntimeError(f"expected 16 stone path PNGs, found {len(pngs)}")
    for png in pngs:
        shutil.copy2(png, target / png.name)

    manifest = json.loads((output_root / "stone_path_01.json").read_text(encoding="utf-8"))
    manifest["styleId"] = "stone_path"
    manifest["promotionState"] = "runtime"
    manifest["buildCostPerTile"] = STONE_COST
    (target / "stone_path_01.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def patch_ui() -> None:
    path = Path("src/ui_manager.cpp")
    replace_once(
        path,
        "[[nodiscard]] std::array<UiBuildItem, 4> floor_catalog_items() {",
        "[[nodiscard]] std::array<UiBuildItem, 5> floor_catalog_items() {",
        "[[nodiscard]] std::array<UiBuildItem, 5> floor_catalog_items() {",
    )
    replace_once(
        path,
        '{"wood_path", "Caminho de Madeira", "PISO", "$0 / TILE", true,',
        f'{{"wood_path", "Caminho de Madeira", "PISO", "${WOOD_COST} / TILE", true,',
        f'{{"wood_path", "Caminho de Madeira", "PISO", "${WOOD_COST} / TILE", true,',
    )

    text = path.read_text(encoding="utf-8")
    stone_marker = '{"stone_path", "Caminho de Pedras", "PISO",'
    if stone_marker in text:
        return
    wood_block = f'''        {{"wood_path", "Caminho de Madeira", "PISO", "${WOOD_COST} / TILE", true,
         runtime_asset_path("assets/terrain/paths/wood_01/wood_path_00_isolated.png"),
         "1x1", "TERRENO PROPRIO | CLIQUE E ARRASTE", 1}},
'''
    stone_block = f'''        {{"stone_path", "Caminho de Pedras", "PISO", "${STONE_COST} / TILE", true,
         runtime_asset_path("assets/terrain/paths/stone_01/stone_path_00_isolated.png"),
         "1x1", "TERRENO PROPRIO | CLIQUE E ARRASTE", 1}},
'''
    if wood_block not in text:
        raise RuntimeError("wood UI block not found while adding stone")
    path.write_text(text.replace(wood_block, wood_block + stone_block, 1), encoding="utf-8")


def patch_renderer() -> None:
    path = Path("src/runtime_map_renderer.h")
    text = path.read_text(encoding="utf-8")
    if 'style_id == "stone_path"' in text:
        return
    wood_block = '''    if (style_id == "wood_path") {
        std::string filename = dirt_path_sprite(connections).substr(std::string("assets/terrain/paths/dirt_01/").size());
        filename.replace(0, 4, "wood");
        return "assets/terrain/paths/wood_01/" + filename;
    }
'''
    stone_block = '''    if (style_id == "stone_path") {
        std::string filename = dirt_path_sprite(connections).substr(std::string("assets/terrain/paths/dirt_01/").size());
        filename.replace(0, 4, "stone");
        return "assets/terrain/paths/stone_01/" + filename;
    }
'''
    if wood_block not in text:
        raise RuntimeError("wood renderer block not found while adding stone")
    path.write_text(text.replace(wood_block, wood_block + stone_block, 1), encoding="utf-8")


def patch_runtime() -> None:
    path = Path("src/main_runtime_impl.cpp")
    text = path.read_text(encoding="utf-8")

    if 'action.payload == "stone_path"' not in text:
        old = '''if (action.payload == "dirt_path" || action.payload == "sand_path" || action.payload == "wood_path" ||
                    action.payload == "grass" || action.payload == "crosswalk_ns" || action.payload == "crosswalk_ew") {'''
        new = '''if (action.payload == "dirt_path" || action.payload == "sand_path" || action.payload == "wood_path" ||
                    action.payload == "stone_path" || action.payload == "grass" || action.payload == "crosswalk_ns" || action.payload == "crosswalk_ew") {'''
        if old not in text:
            raise RuntimeError("floor action whitelist anchor not found")
        text = text.replace(old, new, 1)

    if "const auto floor_style_cost = " not in text:
        anchor = '''    const auto begin_sidewalk_mode = [&]() {
        clear_map_modes(); build_panel_open = false; sidewalk_mode = true; selected_instance_id.reset();
        status = "FLOOR MODE: DRAG ON OWNED LAND"; (void)play_sound(SoundEvent::ui_select);
    };
'''
        addition = f'''    const auto floor_style_cost = [](const std::string& style) -> std::int64_t {{
        if (style == "wood_path") return {WOOD_COST};
        if (style == "stone_path") return {STONE_COST};
        return 0;
    }};
'''
        if anchor not in text:
            raise RuntimeError("sidewalk mode anchor not found")
        text = text.replace(anchor, anchor + addition, 1)

    if "const std::int64_t tile_cost = floor_style_cost(sidewalk_style);" not in text:
        old = '''                        bool changed_tile = false;
                        if (sidewalk_style == "grass") {
                            changed_tile = sidewalks.remove_tile(tile.x, tile.y);
                        } else {
                            changed_tile = sidewalks.paint_tile(tile.x, tile.y, sidewalk_style);
                        }
                        if (restore_grass(tile.x, tile.y)) changed_tile = true;
                        if (changed_tile) ++changed;
'''
        new = '''                        const SidewalkTile* existing_floor = sidewalks.tile_at(tile.x, tile.y);
                        const bool style_would_change = sidewalk_style == "grass"
                            ? existing_floor != nullptr
                            : existing_floor == nullptr || existing_floor->style_id != sidewalk_style;
                        if (!style_would_change) continue;
                        const std::int64_t tile_cost = floor_style_cost(sidewalk_style);
                        if (tile_cost > 0 && !economy.can_afford(tile_cost)) {
                            ++blocked;
                            continue;
                        }
                        bool changed_tile = false;
                        if (sidewalk_style == "grass") {
                            changed_tile = sidewalks.remove_tile(tile.x, tile.y);
                        } else {
                            changed_tile = sidewalks.paint_tile(tile.x, tile.y, sidewalk_style);
                        }
                        if (restore_grass(tile.x, tile.y)) changed_tile = true;
                        if (changed_tile) {
                            if (tile_cost > 0) (void)economy.try_spend(tile_cost);
                            ++changed;
                        }
'''
        if old not in text:
            raise RuntimeError("floor placement economy anchor not found")
        text = text.replace(old, new, 1)

    path.write_text(text, encoding="utf-8")


def verify() -> None:
    checks = {
        Path("src/ui_manager.cpp"): [
            f'{{"wood_path", "Caminho de Madeira", "PISO", "${WOOD_COST} / TILE"',
            f'{{"stone_path", "Caminho de Pedras", "PISO", "${STONE_COST} / TILE"',
        ],
        Path("src/runtime_map_renderer.h"): ['style_id == "stone_path"'],
        Path("src/main_runtime_impl.cpp"): [
            'action.payload == "stone_path"',
            f'if (style == "wood_path") return {WOOD_COST};',
            f'if (style == "stone_path") return {STONE_COST};',
            "const std::int64_t tile_cost = floor_style_cost(sidewalk_style);",
        ],
    }
    for path, needles in checks.items():
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                raise RuntimeError(f"verification failed: {needle!r} missing from {path}")
    for name in ("stone_path_00_isolated.png", "stone_path_15_cross.png", "stone_path_01.json"):
        if not (Path("assets/terrain/paths/stone_01") / name).is_file():
            raise RuntimeError(f"missing runtime stone asset: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("out/stone_path_01"))
    args = parser.parse_args()
    promote_assets(args.output_root)
    patch_ui()
    patch_renderer()
    patch_runtime()
    verify()
    print(f"PASS premium floors: wood=${WOOD_COST}/tile stone=${STONE_COST}/tile")


if __name__ == "__main__":
    main()
