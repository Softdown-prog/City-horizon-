from pathlib import Path

path = Path("src/main_runtime_impl.cpp")
text = path.read_text(encoding="utf-8")

include_anchor = '#include "sidewalk_system.h"\n#include "ui_manager.h"'
include_replacement = '#include "sidewalk_system.h"\n#include "tool_cursor.h"\n#include "ui_manager.h"'
if '#include "tool_cursor.h"' not in text:
    if include_anchor not in text:
        raise SystemExit("tool cursor include anchor not found")
    text = text.replace(include_anchor, include_replacement, 1)

manager_anchor = '    SidewalkManager sidewalks(kMapMin, kMapMax);\n    FarmingSystem farming(kMapMin, kMapMax);'
manager_replacement = '    SidewalkManager sidewalks(kMapMin, kMapMax);\n    ToolCursorManager tool_cursors;\n    FarmingSystem farming(kMapMin, kMapMax);'
if '    ToolCursorManager tool_cursors;' not in text:
    if manager_anchor not in text:
        raise SystemExit("tool cursor manager anchor not found")
    text = text.replace(manager_anchor, manager_replacement, 1)

loop_anchor = '''        gameplay_ui.update_layout(viewport_width, viewport_height, make_ui_model(event_mouse_tile));

        SDL_Event event;
        while (SDL_PollEvent(&event)) {'''
loop_replacement = '''        gameplay_ui.update_layout(viewport_width, viewport_height, make_ui_model(event_mouse_tile));

        // CH_TOOL_CURSOR_V1: active editing modes replace the generic pointer
        // with a precise contextual cursor. This is presentation only; the
        // existing screen_to_tile picking contract remains authoritative.
        ToolCursorKind desired_cursor = ToolCursorKind::pointer;
        if (!placement_definition_id.empty()) {
            desired_cursor = ToolCursorKind::build;
        } else if (terrain_relief_mode) {
            desired_cursor = *terrain_relief_mode == ch::TerrainBrushMode::raise ? ToolCursorKind::raise_terrain :
                (*terrain_relief_mode == ch::TerrainBrushMode::lower ? ToolCursorKind::lower_terrain : ToolCursorKind::smooth_terrain);
        } else if (!water_terrain_id.empty()) {
            desired_cursor = ToolCursorKind::water;
        } else if (land_mode) {
            desired_cursor = ToolCursorKind::land;
        } else if (road_mode && road_removal_mode) {
            desired_cursor = ToolCursorKind::demolish;
        } else if (sidewalk_mode) {
            desired_cursor = ToolCursorKind::floor;
        } else if (road_mode) {
            desired_cursor = ToolCursorKind::road;
        }
        tool_cursors.set(desired_cursor);

        SDL_Event event;
        while (SDL_PollEvent(&event)) {'''
if 'ToolCursorKind desired_cursor' not in text:
    if loop_anchor not in text:
        raise SystemExit("tool cursor loop anchor not found")
    text = text.replace(loop_anchor, loop_replacement, 1)

path.write_text(text, encoding="utf-8")
print("PASS CH_TOOL_CURSOR_V1 integrated into src/main_runtime_impl.cpp")
