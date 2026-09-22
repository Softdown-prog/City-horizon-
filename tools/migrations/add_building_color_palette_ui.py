from pathlib import Path
import re


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_once(path: str, pattern: str, replacement: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"{path}: regex expected exactly one match, found {count}")
    p.write_text(updated, encoding="utf-8")


# ---------------------------------------------------------------------------
# Building instance state: wall and roof are independently customizable.
# ---------------------------------------------------------------------------
replace_once(
    "src/building_system.h",
    '''    // Two instances of the same definition may carry different player colors.\n    // False means render the approved source PNG with no recolor pass.\n    bool color_customized = false;\n    BuildingColorTint wall_tint{};\n    BuildingColorTint roof_tint{};\n''',
    '''    // Wall and roof are intentionally independent: changing one channel\n    // must never brighten or recolor the other masked region.\n    bool wall_color_customized = false;\n    bool roof_color_customized = false;\n    BuildingColorTint wall_tint{};\n    BuildingColorTint roof_tint{};\n''',
)
replace_once(
    "src/building_system.h",
    '''    [[nodiscard]] bool set_color_customization(std::uint64_t instance_id, BuildingColorTint wall, BuildingColorTint roof);\n    [[nodiscard]] bool clear_color_customization(std::uint64_t instance_id);\n''',
    '''    [[nodiscard]] bool set_color_customization(std::uint64_t instance_id, BuildingColorTint wall, BuildingColorTint roof);\n    [[nodiscard]] bool set_wall_color_customization(std::uint64_t instance_id, BuildingColorTint wall);\n    [[nodiscard]] bool set_roof_color_customization(std::uint64_t instance_id, BuildingColorTint roof);\n    [[nodiscard]] bool clear_color_customization(std::uint64_t instance_id);\n''',
)
replace_once(
    "src/building_system.cpp",
    '''bool BuildingManager::set_color_customization(const std::uint64_t instance_id, const BuildingColorTint wall,\n                                              const BuildingColorTint roof) {\n    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {\n        return instance.instance_id == instance_id;\n    });\n    if (found == instances_.end()) return false;\n    found->wall_tint = wall;\n    found->roof_tint = roof;\n    found->color_customized = true;\n    return true;\n}\n\nbool BuildingManager::clear_color_customization(const std::uint64_t instance_id) {\n    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {\n        return instance.instance_id == instance_id;\n    });\n    if (found == instances_.end()) return false;\n    found->color_customized = false;\n    found->wall_tint = {};\n    found->roof_tint = {};\n    return true;\n}\n''',
    '''bool BuildingManager::set_color_customization(const std::uint64_t instance_id, const BuildingColorTint wall,\n                                              const BuildingColorTint roof) {\n    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {\n        return instance.instance_id == instance_id;\n    });\n    if (found == instances_.end()) return false;\n    found->wall_tint = wall;\n    found->roof_tint = roof;\n    found->wall_color_customized = true;\n    found->roof_color_customized = true;\n    return true;\n}\n\nbool BuildingManager::set_wall_color_customization(const std::uint64_t instance_id, const BuildingColorTint wall) {\n    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {\n        return instance.instance_id == instance_id;\n    });\n    if (found == instances_.end()) return false;\n    found->wall_tint = wall;\n    found->wall_color_customized = true;\n    return true;\n}\n\nbool BuildingManager::set_roof_color_customization(const std::uint64_t instance_id, const BuildingColorTint roof) {\n    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {\n        return instance.instance_id == instance_id;\n    });\n    if (found == instances_.end()) return false;\n    found->roof_tint = roof;\n    found->roof_color_customized = true;\n    return true;\n}\n\nbool BuildingManager::clear_color_customization(const std::uint64_t instance_id) {\n    const auto found = std::find_if(instances_.begin(), instances_.end(), [instance_id](BuildingInstance& instance) {\n        return instance.instance_id == instance_id;\n    });\n    if (found == instances_.end()) return false;\n    found->wall_color_customized = false;\n    found->roof_color_customized = false;\n    found->wall_tint = {};\n    found->roof_tint = {};\n    return true;\n}\n''',
)

# Renderer: only draw the channel the player actually customized.
replace_once(
    "src/main.cpp",
    '''                if (draw.building->color_customized && definition->supports_color_mask(visual_rotation)) {\n                    constexpr Uint8 kTintOverlayAlpha = 184;\n                    const auto mask_path = root / definition->color_mask_path_for(visual_rotation);\n                    if (const TextureAsset* wall = textures.find_mask_channel(mask_path, 'R')) {\n                        render_building(renderer, *definition, *draw.building, visual_rotation, *wall, camera,\n                                        viewport_width, viewport_height, kTintOverlayAlpha,\n                                        draw.building->wall_tint.r, draw.building->wall_tint.g, draw.building->wall_tint.b);\n                    }\n                    if (const TextureAsset* roof = textures.find_mask_channel(mask_path, 'G')) {\n                        render_building(renderer, *definition, *draw.building, visual_rotation, *roof, camera,\n                                        viewport_width, viewport_height, kTintOverlayAlpha,\n                                        draw.building->roof_tint.r, draw.building->roof_tint.g, draw.building->roof_tint.b);\n                    }\n                }\n''',
    '''                if ((draw.building->wall_color_customized || draw.building->roof_color_customized) &&\n                    definition->supports_color_mask(visual_rotation)) {\n                    constexpr Uint8 kTintOverlayAlpha = 184;\n                    const auto mask_path = root / definition->color_mask_path_for(visual_rotation);\n                    if (draw.building->wall_color_customized) {\n                        if (const TextureAsset* wall = textures.find_mask_channel(mask_path, 'R')) {\n                            render_building(renderer, *definition, *draw.building, visual_rotation, *wall, camera,\n                                            viewport_width, viewport_height, kTintOverlayAlpha,\n                                            draw.building->wall_tint.r, draw.building->wall_tint.g, draw.building->wall_tint.b);\n                        }\n                    }\n                    if (draw.building->roof_color_customized) {\n                        if (const TextureAsset* roof = textures.find_mask_channel(mask_path, 'G')) {\n                            render_building(renderer, *definition, *draw.building, visual_rotation, *roof, camera,\n                                            viewport_width, viewport_height, kTintOverlayAlpha,\n                                            draw.building->roof_tint.r, draw.building->roof_tint.g, draw.building->roof_tint.b);\n                        }\n                    }\n                }\n''',
)

# ---------------------------------------------------------------------------
# Save v10 persists independent wall/roof toggles and remains compatible with
# the brief v9 all-or-nothing tint foundation.
# ---------------------------------------------------------------------------
replace_once("src/save_manager.h", "static constexpr int kSaveVersion = 9;", "static constexpr int kSaveVersion = 10;")
replace_once(
    "src/save_manager.cpp",
    '''        const auto service_price = json_number<std::int64_t>(building, "servicePrice");\n        const auto wall_tint_r = json_number<int>(building, "wallTintR");\n''',
    '''        const auto service_price = json_number<std::int64_t>(building, "servicePrice");\n        const auto wall_color_customized = json_bool(building, "wallColorCustomized");\n        const auto roof_color_customized = json_bool(building, "roofColorCustomized");\n        const auto wall_tint_r = json_number<int>(building, "wallTintR");\n''',
)
replace_once(
    "src/save_manager.cpp",
    '''        const bool has_any_tint = wall_tint_r || wall_tint_g || wall_tint_b || roof_tint_r || roof_tint_g || roof_tint_b;\n        if (has_any_tint) {\n            if (!wall_tint_r || !wall_tint_g || !wall_tint_b || !roof_tint_r || !roof_tint_g || !roof_tint_b ||\n                *wall_tint_r < 0 || *wall_tint_r > 255 || *wall_tint_g < 0 || *wall_tint_g > 255 ||\n                *wall_tint_b < 0 || *wall_tint_b > 255 || *roof_tint_r < 0 || *roof_tint_r > 255 ||\n                *roof_tint_g < 0 || *roof_tint_g > 255 || *roof_tint_b < 0 || *roof_tint_b > 255) {\n                error = "building color customization is invalid";\n                return false;\n            }\n            saved.color_customized = true;\n            saved.wall_tint = {static_cast<std::uint8_t>(*wall_tint_r), static_cast<std::uint8_t>(*wall_tint_g),\n                               static_cast<std::uint8_t>(*wall_tint_b)};\n            saved.roof_tint = {static_cast<std::uint8_t>(*roof_tint_r), static_cast<std::uint8_t>(*roof_tint_g),\n                               static_cast<std::uint8_t>(*roof_tint_b)};\n        }\n''',
    '''        const auto valid_channel = [](const std::optional<int>& r, const std::optional<int>& g, const std::optional<int>& b) {\n            return r && g && b && *r >= 0 && *r <= 255 && *g >= 0 && *g <= 255 && *b >= 0 && *b <= 255;\n        };\n        if (*version >= 10) {\n            saved.wall_color_customized = wall_color_customized.value_or(false);\n            saved.roof_color_customized = roof_color_customized.value_or(false);\n            if ((saved.wall_color_customized && !valid_channel(wall_tint_r, wall_tint_g, wall_tint_b)) ||\n                (saved.roof_color_customized && !valid_channel(roof_tint_r, roof_tint_g, roof_tint_b))) {\n                error = "building color customization is invalid";\n                return false;\n            }\n            if (saved.wall_color_customized) {\n                saved.wall_tint = {static_cast<std::uint8_t>(*wall_tint_r), static_cast<std::uint8_t>(*wall_tint_g),\n                                   static_cast<std::uint8_t>(*wall_tint_b)};\n            }\n            if (saved.roof_color_customized) {\n                saved.roof_tint = {static_cast<std::uint8_t>(*roof_tint_r), static_cast<std::uint8_t>(*roof_tint_g),\n                                   static_cast<std::uint8_t>(*roof_tint_b)};\n            }\n        } else {\n            const bool has_legacy_tint = wall_tint_r || wall_tint_g || wall_tint_b || roof_tint_r || roof_tint_g || roof_tint_b;\n            if (has_legacy_tint) {\n                if (!valid_channel(wall_tint_r, wall_tint_g, wall_tint_b) || !valid_channel(roof_tint_r, roof_tint_g, roof_tint_b)) {\n                    error = "building color customization is invalid";\n                    return false;\n                }\n                saved.wall_color_customized = true;\n                saved.roof_color_customized = true;\n                saved.wall_tint = {static_cast<std::uint8_t>(*wall_tint_r), static_cast<std::uint8_t>(*wall_tint_g),\n                                   static_cast<std::uint8_t>(*wall_tint_b)};\n                saved.roof_tint = {static_cast<std::uint8_t>(*roof_tint_r), static_cast<std::uint8_t>(*roof_tint_g),\n                                   static_cast<std::uint8_t>(*roof_tint_b)};\n            }\n        }\n''',
)
replace_once(
    "src/save_manager.cpp",
    '''               << ", \\"level\\": " << building.current_level\n               << ", \\"servicePrice\\": " << building.service_price;\n        if (building.color_customized) {\n            output << ", \\"wallTintR\\": " << static_cast<int>(building.wall_tint.r)\n                   << ", \\"wallTintG\\": " << static_cast<int>(building.wall_tint.g)\n                   << ", \\"wallTintB\\": " << static_cast<int>(building.wall_tint.b)\n                   << ", \\"roofTintR\\": " << static_cast<int>(building.roof_tint.r)\n                   << ", \\"roofTintG\\": " << static_cast<int>(building.roof_tint.g)\n                   << ", \\"roofTintB\\": " << static_cast<int>(building.roof_tint.b);\n        }\n'''.replace('\\\\"', '\\"'),
    '''               << ", \\"level\\": " << building.current_level\n               << ", \\"servicePrice\\": " << building.service_price\n               << ", \\"wallColorCustomized\\": " << (building.wall_color_customized ? "true" : "false")\n               << ", \\"roofColorCustomized\\": " << (building.roof_color_customized ? "true" : "false");\n        if (building.wall_color_customized) {\n            output << ", \\"wallTintR\\": " << static_cast<int>(building.wall_tint.r)\n                   << ", \\"wallTintG\\": " << static_cast<int>(building.wall_tint.g)\n                   << ", \\"wallTintB\\": " << static_cast<int>(building.wall_tint.b);\n        }\n        if (building.roof_color_customized) {\n            output << ", \\"roofTintR\\": " << static_cast<int>(building.roof_tint.r)\n                   << ", \\"roofTintG\\": " << static_cast<int>(building.roof_tint.g)\n                   << ", \\"roofTintB\\": " << static_cast<int>(building.roof_tint.b);\n        }\n'''.replace('\\\\"', '\\"'),
)

# ---------------------------------------------------------------------------
# UI data and actions.
# ---------------------------------------------------------------------------
replace_once(
    "src/ui_manager.h",
    '''    decrease_service_price,\n    increase_service_price,\n    close_selection,\n''',
    '''    decrease_service_price,\n    increase_service_price,\n    set_wall_color,\n    set_roof_color,\n    reset_building_colors,\n    close_selection,\n''',
)
replace_once(
    "src/ui_manager.h",
    '''    bool can_decrease_service_price = false;\n    bool can_increase_service_price = false;\n};\n''',
    '''    bool can_decrease_service_price = false;\n    bool can_increase_service_price = false;\n    bool has_color_customization = false;\n    bool wall_color_customized = false;\n    bool roof_color_customized = false;\n    int wall_tint_r = 255;\n    int wall_tint_g = 255;\n    int wall_tint_b = 255;\n    int roof_tint_r = 255;\n    int roof_tint_g = 255;\n    int roof_tint_b = 255;\n};\n''',
)
replace_once(
    "src/ui_manager.h",
    '''    std::string thumbnail_path;\n    bool build_card = false;\n};\n''',
    '''    std::string thumbnail_path;\n    bool build_card = false;\n    bool color_swatch = false;\n    Uint8 swatch_r = 255;\n    Uint8 swatch_g = 255;\n    Uint8 swatch_b = 255;\n};\n''',
)

# Palette + visual renderer.
replace_once(
    "src/ui_manager.cpp",
    '''constexpr float kButtonHeight = 30.0F;\n\nvoid draw_panel''',
    '''constexpr float kButtonHeight = 30.0F;\n\nstruct BuildingColorSwatch {\n    Uint8 r;\n    Uint8 g;\n    Uint8 b;\n};\n\nconstexpr std::array<BuildingColorSwatch, 7> kBuildingColorPalette = {{\n    {226, 202, 160},  // warm cream\n    {190, 112, 81},   // brick\n    {203, 163, 91},   // ochre\n    {119, 151, 116},  // sage\n    {105, 143, 172},  // blue\n    {172, 119, 131},  // rose\n    {122, 132, 139},  // slate\n}};\n\nstd::string color_payload(const BuildingColorSwatch swatch) {\n    return std::to_string(static_cast<int>(swatch.r)) + ":" +\n           std::to_string(static_cast<int>(swatch.g)) + ":" +\n           std::to_string(static_cast<int>(swatch.b));\n}\n\nvoid draw_panel''',
)
replace_once(
    "src/ui_manager.cpp",
    '''void draw_pause_button(SDL_Renderer* renderer, const UiButton& button) {\n''',
    '''void draw_color_swatch_button(SDL_Renderer* renderer, const UiButton& button) {\n    const SDL_FRect shadow = {button.bounds.x + 2.0F, button.bounds.y + 2.0F, button.bounds.width, button.bounds.height};\n    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 70);\n    SDL_RenderFillRect(renderer, &shadow);\n    const SDL_FRect rect = {button.bounds.x, button.bounds.y, button.bounds.width, button.bounds.height};\n    SDL_SetRenderDrawColor(renderer, button.swatch_r, button.swatch_g, button.swatch_b, SDL_ALPHA_OPAQUE);\n    SDL_RenderFillRect(renderer, &rect);\n    if (button.active) SDL_SetRenderDrawColor(renderer, 238, 246, 249, SDL_ALPHA_OPAQUE);\n    else if (button.state == UiButtonState::hover || button.state == UiButtonState::pressed)\n        SDL_SetRenderDrawColor(renderer, 91, 188, 211, SDL_ALPHA_OPAQUE);\n    else SDL_SetRenderDrawColor(renderer, 54, 78, 90, SDL_ALPHA_OPAQUE);\n    SDL_RenderRect(renderer, &rect);\n    if (button.active) {\n        const SDL_FRect inner = {rect.x + 2.0F, rect.y + 2.0F, rect.w - 4.0F, rect.h - 4.0F};\n        SDL_RenderRect(renderer, &inner);\n    }\n}\n\nvoid draw_pause_button(SDL_Renderer* renderer, const UiButton& button) {\n''',
)

# Reserve panel space and add two palette rows + reset.
replace_once(
    "src/ui_manager.cpp",
    '''        const float service_height = item.has_service_pricing ? 82.0F : 0.0F;\n        const float required_height = 126.0F + service_height + static_cast<float>(detail_lines) * 17.0F;\n''',
    '''        const float service_height = item.has_service_pricing ? 82.0F : 0.0F;\n        const float color_height = item.has_color_customization ? 122.0F : 0.0F;\n        const float required_height = 126.0F + service_height + color_height + static_cast<float>(detail_lines) * 17.0F;\n''',
)
replace_once(
    "src/ui_manager.cpp",
    '''        if (item.has_service_pricing) {\n            add_button({panel_x + 194.0F, panel_y + 143.0F, 34.0F, 30.0F}, "-",\n                       UiAction::decrease_service_price, item.can_decrease_service_price);\n            add_button({panel_x + 282.0F, panel_y + 143.0F, 34.0F, 30.0F}, "+",\n                       UiAction::increase_service_price, item.can_increase_service_price);\n        }\n''',
    '''        if (item.has_service_pricing) {\n            add_button({panel_x + 194.0F, panel_y + 143.0F, 34.0F, 30.0F}, "-",\n                       UiAction::decrease_service_price, item.can_decrease_service_price);\n            add_button({panel_x + 282.0F, panel_y + 143.0F, 34.0F, 30.0F}, "+",\n                       UiAction::increase_service_price, item.can_increase_service_price);\n        }\n        if (item.has_color_customization) {\n            const float color_top = panel_y + panel_height - 116.0F;\n            constexpr float swatch_size = 26.0F;\n            constexpr float swatch_gap = 5.0F;\n            const auto add_palette_row = [&](const float y, const UiAction action, const bool customized,\n                                             const int current_r, const int current_g, const int current_b) {\n                for (std::size_t index = 0; index < kBuildingColorPalette.size(); ++index) {\n                    const BuildingColorSwatch swatch = kBuildingColorPalette[index];\n                    const bool active = customized && current_r == swatch.r && current_g == swatch.g && current_b == swatch.b;\n                    add_button({panel_x + 96.0F + static_cast<float>(index) * (swatch_size + swatch_gap), y, swatch_size, swatch_size},\n                               "", action, true, active, color_payload(swatch));\n                    UiButton& button = buttons_.back();\n                    button.color_swatch = true;\n                    button.swatch_r = swatch.r; button.swatch_g = swatch.g; button.swatch_b = swatch.b;\n                }\n            };\n            add_palette_row(color_top + 21.0F, UiAction::set_wall_color, item.wall_color_customized,\n                            item.wall_tint_r, item.wall_tint_g, item.wall_tint_b);\n            add_palette_row(color_top + 53.0F, UiAction::set_roof_color, item.roof_color_customized,\n                            item.roof_tint_r, item.roof_tint_g, item.roof_tint_b);\n            add_button({panel_x + 216.0F, color_top + 84.0F, 100.0F, 24.0F}, "ORIGINAL",\n                       UiAction::reset_building_colors, item.wall_color_customized || item.roof_color_customized);\n        }\n''',
)

# Render color section labels at the reserved bottom of the selected panel.
replace_once(
    "src/ui_manager.cpp",
    '''        float panel_x = 0.0F;\n        for (const UiRect& panel : panels_) if (panel.width == 330.0F && panel.y == 84.0F) { panel_x = panel.x; break; }\n''',
    '''        float panel_x = 0.0F;\n        float panel_height = 0.0F;\n        for (const UiRect& panel : panels_) if (panel.width == 330.0F && panel.y == 84.0F) {\n            panel_x = panel.x; panel_height = panel.height; break;\n        }\n''',
)
replace_once(
    "src/ui_manager.cpp",
    '''        detail("ABASTECIMENTO LOCAL", item.local_supply);\n    }\n\n    if (!model_.status.empty()) {\n''',
    '''        detail("ABASTECIMENTO LOCAL", item.local_supply);\n        if (item.has_color_customization) {\n            const float color_top = 84.0F + panel_height - 116.0F;\n            SDL_SetRenderDrawColor(renderer, 55, 91, 111, SDL_ALPHA_OPAQUE);\n            SDL_RenderLine(renderer, panel_x + 12.0F, color_top + 5.0F, panel_x + 316.0F, color_top + 5.0F);\n            draw_text(renderer, panel_x + 12.0F, color_top + 28.0F, "PAREDE", 164, 193, 205);\n            draw_text(renderer, panel_x + 12.0F, color_top + 60.0F, "TELHADO", 164, 193, 205);\n            draw_text(renderer, panel_x + 12.0F, color_top + 91.0F,\n                      item.wall_color_customized || item.roof_color_customized ? "CORES PERSONALIZADAS" : "CORES ORIGINAIS",\n                      118, 151, 166);\n        }\n    }\n\n    if (!model_.status.empty()) {\n''',
)
replace_once(
    "src/ui_manager.cpp",
    '''    for (const UiButton& button : buttons_) {\n        if (button.build_card) render_build_card(renderer, button);\n        else if (!draw_chrome_button(button)) {\n            if (draw_state_atlas_button(button)) draw_button_content(renderer, button);\n            else draw_button(renderer, button);\n        }\n    }\n''',
    '''    for (const UiButton& button : buttons_) {\n        if (button.build_card) render_build_card(renderer, button);\n        else if (button.color_swatch) draw_color_swatch_button(renderer, button);\n        else if (!draw_chrome_button(button)) {\n            if (draw_state_atlas_button(button)) draw_button_content(renderer, button);\n            else draw_button(renderer, button);\n        }\n    }\n''',
)

# ---------------------------------------------------------------------------
# Main action binding + model data.
# ---------------------------------------------------------------------------
replace_once(
    "src/main.cpp",
    '''            case UiAction::close_selection:\n                selected_instance_id.reset();\n''',
    '''            case UiAction::set_wall_color:\n            case UiAction::set_roof_color: {\n                if (!selected_instance_id) {\n                    status = "NO BUILDING SELECTED";\n                    (void)audio.play(SoundEvent::ui_error);\n                    break;\n                }\n                const BuildingInstance* instance = buildings.find_by_id(*selected_instance_id);\n                const BuildingDefinition* definition = instance == nullptr ? nullptr : catalog.find(instance->definition_id);\n                if (instance == nullptr || definition == nullptr || !definition->supports_color_mask(instance->rotation)) {\n                    status = "BUILDING HAS NO COLOR MASK";\n                    (void)audio.play(SoundEvent::ui_error);\n                    break;\n                }\n                const std::size_t first = action.payload.find(':');\n                const std::size_t second = first == std::string::npos ? std::string::npos : action.payload.find(':', first + 1);\n                if (first == std::string::npos || second == std::string::npos) {\n                    status = "INVALID COLOR";\n                    (void)audio.play(SoundEvent::ui_error);\n                    break;\n                }\n                try {\n                    const int r = std::clamp(std::stoi(action.payload.substr(0, first)), 0, 255);\n                    const int g = std::clamp(std::stoi(action.payload.substr(first + 1, second - first - 1)), 0, 255);\n                    const int b = std::clamp(std::stoi(action.payload.substr(second + 1)), 0, 255);\n                    const BuildingColorTint tint{static_cast<std::uint8_t>(r), static_cast<std::uint8_t>(g), static_cast<std::uint8_t>(b)};\n                    const bool changed = action.action == UiAction::set_wall_color\n                        ? buildings.set_wall_color_customization(instance->instance_id, tint)\n                        : buildings.set_roof_color_customization(instance->instance_id, tint);\n                    status = changed ? definition->name + (action.action == UiAction::set_wall_color ? ": WALL COLOR" : ": ROOF COLOR")\n                                     : "COLOR CHANGE FAILED";\n                    (void)audio.play(changed ? SoundEvent::ui_click : SoundEvent::ui_error);\n                } catch (...) {\n                    status = "INVALID COLOR";\n                    (void)audio.play(SoundEvent::ui_error);\n                }\n                break;\n            }\n            case UiAction::reset_building_colors:\n                if (selected_instance_id && buildings.clear_color_customization(*selected_instance_id)) {\n                    status = "ORIGINAL BUILDING COLORS RESTORED";\n                    (void)audio.play(SoundEvent::ui_click);\n                } else {\n                    status = "COLOR RESET FAILED";\n                    (void)audio.play(SoundEvent::ui_error);\n                }\n                break;\n            case UiAction::close_selection:\n                selected_instance_id.reset();\n''',
)
replace_once(
    "src/main.cpp",
    '''                        definition->default_service_price > 0 && instance->service_price > definition->minimum_service_price,\n                        definition->default_service_price > 0 && instance->service_price < definition->maximum_service_price,\n                    };\n''',
    '''                        definition->default_service_price > 0 && instance->service_price > definition->minimum_service_price,\n                        definition->default_service_price > 0 && instance->service_price < definition->maximum_service_price,\n                        definition->color_mask.has_value() && definition->color_mask->enabled,\n                        instance->wall_color_customized,\n                        instance->roof_color_customized,\n                        static_cast<int>(instance->wall_tint.r),\n                        static_cast<int>(instance->wall_tint.g),\n                        static_cast<int>(instance->wall_tint.b),\n                        static_cast<int>(instance->roof_tint.r),\n                        static_cast<int>(instance->roof_tint.g),\n                        static_cast<int>(instance->roof_tint.b),\n                    };\n''',
)

# Lightweight source-level assertions: fail before committing if a partial patch
# would leave the runtime in a mixed contract state.
checks = {
    "src/building_system.h": ["wall_color_customized", "set_wall_color_customization", "set_roof_color_customization"],
    "src/main.cpp": ["UiAction::set_wall_color", "wall_color_customized", "ROOF COLOR"],
    "src/ui_manager.cpp": ["kBuildingColorPalette", "draw_color_swatch_button", "CORES PERSONALIZADAS"],
    "src/save_manager.cpp": ["wallColorCustomized", "roofColorCustomized"],
    "src/save_manager.h": ["kSaveVersion = 10"],
}
for file_name, needles in checks.items():
    text = Path(file_name).read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"{file_name}: missing expected token {needle!r}")

print("CH_COLOR_MASK_V1 palette UI migration applied")
