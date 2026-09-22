from pathlib import Path

path = Path('src/main.cpp')
text = path.read_text(encoding='utf-8')


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)

start = text.index('// The loading artwork is a single authored 1280x906 composition.')
end = text.index('void render_ui(', start)
new_loading = '''// Lightweight runtime loading UI. Progress advances only after real startup\n// milestones complete; no full-screen raster artwork or artificial delay is used.\nvoid render_loading_screen(SDL_Renderer* renderer, const int viewport_width, const int viewport_height,\n                           const float progress, const std::string& stage) {\n    const float width = static_cast<float>(viewport_width);\n    const float height = static_cast<float>(viewport_height);\n    const float clamped_progress = std::clamp(progress, 0.0F, 1.0F);\n\n    SDL_SetRenderDrawColor(renderer, 4, 14, 20, SDL_ALPHA_OPAQUE);\n    SDL_RenderClear(renderer);\n\n    const float panel_width = std::min(720.0F, std::max(340.0F, width - 80.0F));\n    const float panel_height = std::min(320.0F, std::max(250.0F, height - 120.0F));\n    const float panel_x = (width - panel_width) * 0.5F;\n    const float panel_y = (height - panel_height) * 0.5F;\n\n    const SDL_FRect shadow = {panel_x + 8.0F, panel_y + 10.0F, panel_width, panel_height};\n    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 90);\n    SDL_RenderFillRect(renderer, &shadow);\n\n    const SDL_FRect panel = {panel_x, panel_y, panel_width, panel_height};\n    SDL_SetRenderDrawColor(renderer, 15, 33, 45, 250);\n    SDL_RenderFillRect(renderer, &panel);\n    SDL_SetRenderDrawColor(renderer, 70, 119, 145, SDL_ALPHA_OPAQUE);\n    SDL_RenderRect(renderer, &panel);\n\n    const SDL_FRect accent = {panel_x, panel_y, panel_width, 4.0F};\n    SDL_SetRenderDrawColor(renderer, 91, 188, 211, SDL_ALPHA_OPAQUE);\n    SDL_RenderFillRect(renderer, &accent);\n\n    draw_text(renderer, panel_x + 32.0F, panel_y + 38.0F, "CITY HORIZON", 238, 246, 249);\n    draw_text(renderer, panel_x + 32.0F, panel_y + 64.0F, "PREPARANDO A CIDADE", 158, 186, 199);\n\n    const float track_x = panel_x + 32.0F;\n    const float track_y = panel_y + 132.0F;\n    const float track_width = panel_width - 64.0F;\n    const SDL_FRect track = {track_x, track_y, track_width, 22.0F};\n    SDL_SetRenderDrawColor(renderer, 25, 48, 61, SDL_ALPHA_OPAQUE);\n    SDL_RenderFillRect(renderer, &track);\n    SDL_SetRenderDrawColor(renderer, 64, 103, 123, SDL_ALPHA_OPAQUE);\n    SDL_RenderRect(renderer, &track);\n\n    if (clamped_progress > 0.0F) {\n        const SDL_FRect fill = {track_x + 2.0F, track_y + 2.0F,\n                                (track_width - 4.0F) * clamped_progress, 18.0F};\n        SDL_SetRenderDrawColor(renderer, 91, 188, 211, SDL_ALPHA_OPAQUE);\n        SDL_RenderFillRect(renderer, &fill);\n    }\n\n    const int percent = static_cast<int>(std::lround(clamped_progress * 100.0F));\n    draw_text(renderer, panel_x + 32.0F, panel_y + 170.0F, stage, 219, 232, 238);\n    draw_text(renderer, panel_x + panel_width - 86.0F, panel_y + 170.0F,\n              std::to_string(percent) + "%", 158, 186, 199);\n    draw_text(renderer, panel_x + 32.0F, panel_y + panel_height - 48.0F,\n              "DICA: CONECTE BAIRROS COM RUAS E CAMINHOS.", 118, 151, 166);\n}\n\n'''
text = text[:start] + new_loading + text[end:]

replace_once(
'''    TextureCache textures;\n    const TextureAsset* grass = textures.load(renderer, asset_root / "assets/terrain/grass_isometric_01_clean.png");\n    const TextureAsset* loading_ui_sheet = textures.load(renderer, asset_root / "assets/ui/loading/city_horizon_loading.png");\n    const Uint64 loading_screen_started = SDL_GetTicks();\n    if (loading_ui_sheet != nullptr) {\n        render_loading_screen(renderer, *loading_ui_sheet, 1280, 800, 0.12F);\n        SDL_RenderPresent(renderer);\n    }\n''',
'''    TextureCache textures;\n    const auto show_loading = [&](const float progress, const char* stage) {\n        int loading_width = 1280;\n        int loading_height = 800;\n        SDL_GetWindowSize(window, &loading_width, &loading_height);\n        render_loading_screen(renderer, loading_width, loading_height, progress, stage);\n        SDL_RenderPresent(renderer);\n    };\n    show_loading(0.08F, "INICIALIZANDO RENDER E AUDIO");\n    const TextureAsset* grass = textures.load(renderer, asset_root / "assets/terrain/grass_isometric_01_clean.png");\n''',
'startup loading block')

replace_once(
'''    (void)textures.load(renderer, asset_root / "assets/farming/prepared_soil/prepared_soil_01.png");\n\n    BuildingCatalog catalog;\n''',
'''    (void)textures.load(renderer, asset_root / "assets/farming/prepared_soil/prepared_soil_01.png");\n    show_loading(0.30F, "CARREGANDO TERRENO, RUAS E CAMINHOS");\n\n    BuildingCatalog catalog;\n''',
'road milestone')

replace_once(
'''    for (const BuildingDefinition& definition : catalog.definitions()) {\n        for (const auto& lvl : definition.levels) {\n            for (std::uint8_t rotation = 0; rotation < 4; ++rotation) {\n                const BuildingRotation logical_rotation = static_cast<BuildingRotation>(rotation);\n                if (definition.supports_rotation(logical_rotation)) {\n                    (void)textures.load(renderer, asset_root / definition.texture_path_for(logical_rotation, lvl.level));\n                }\n            }\n        }\n    }\n    ServiceVehicleCatalog service_vehicle_catalog;\n''',
'''    for (const BuildingDefinition& definition : catalog.definitions()) {\n        for (const auto& lvl : definition.levels) {\n            for (std::uint8_t rotation = 0; rotation < 4; ++rotation) {\n                const BuildingRotation logical_rotation = static_cast<BuildingRotation>(rotation);\n                if (definition.supports_rotation(logical_rotation)) {\n                    (void)textures.load(renderer, asset_root / definition.texture_path_for(logical_rotation, lvl.level));\n                }\n            }\n        }\n    }\n    show_loading(0.58F, "CARREGANDO CATALOGO E CONSTRUCOES");\n    ServiceVehicleCatalog service_vehicle_catalog;\n''',
'building milestone')

replace_once(
'''    for (const std::string& frame_asset : mobile_animations.frame_assets()) {\n        (void)textures.load(renderer, asset_root / frame_asset);\n    }\n\n    BuildingManager buildings(kMapMin, kMapMax);\n''',
'''    for (const std::string& frame_asset : mobile_animations.frame_assets()) {\n        (void)textures.load(renderer, asset_root / frame_asset);\n    }\n    show_loading(0.72F, "CARREGANDO VEICULOS E ENTIDADES");\n\n    BuildingManager buildings(kMapMin, kMapMax);\n''',
'entity milestone')

replace_once(
'''    population.rebuild_capacity(buildings, catalog);\n    power.rebuild(buildings, catalog);\n\n    std::unordered_map<std::uint64_t, const TextureAsset*> scenario_terrain_textures;\n''',
'''    population.rebuild_capacity(buildings, catalog);\n    power.rebuild(buildings, catalog);\n    show_loading(0.84F, "PREPARANDO ECONOMIA, POPULACAO E ENERGIA");\n\n    std::unordered_map<std::uint64_t, const TextureAsset*> scenario_terrain_textures;\n''',
'system milestone')

replace_once(
'''        if (const TextureAsset* overlay = textures.load(renderer, asset_root / "assets/terrain/coast_adjusted" / name)) {\n            shoreline_overlays.push_back({x, y, overlay});\n        }\n    }\n\n    Camera camera;\n''',
'''        if (const TextureAsset* overlay = textures.load(renderer, asset_root / "assets/terrain/coast_adjusted" / name)) {\n            shoreline_overlays.push_back({x, y, overlay});\n        }\n    }\n    show_loading(0.97F, "FINALIZANDO CENARIO E MAPA");\n\n    Camera camera;\n''',
'scenario milestone')

replace_once(
'''    GameplayUi gameplay_ui;\n    const auto vehicle_traversable = [&](const int x, const int y) {\n''',
'''    GameplayUi gameplay_ui;\n    show_loading(1.0F, "PRONTO");\n    const auto vehicle_traversable = [&](const int x, const int y) {\n''',
'final milestone')

replace_once(
'''        gameplay_ui.update_layout(viewport_width, viewport_height, make_ui_model(mouse_tile));\n        gameplay_ui.render(renderer);\n        if (loading_ui_sheet != nullptr) {\n            constexpr Uint64 kLoadingScreenMinimumMs = 1400;\n            const Uint64 loading_elapsed = SDL_GetTicks() - loading_screen_started;\n            if (loading_elapsed < kLoadingScreenMinimumMs) {\n                render_loading_screen(renderer, *loading_ui_sheet, viewport_width, viewport_height,\n                                      0.12F + 0.88F * static_cast<float>(loading_elapsed) /\n                                      static_cast<float>(kLoadingScreenMinimumMs));\n            }\n        }\n        SDL_RenderPresent(renderer);\n''',
'''        gameplay_ui.update_layout(viewport_width, viewport_height, make_ui_model(mouse_tile));\n        gameplay_ui.render(renderer);\n        SDL_RenderPresent(renderer);\n''',
'fake minimum loading overlay')

path.write_text(text, encoding='utf-8')
