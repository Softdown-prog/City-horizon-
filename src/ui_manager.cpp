#include "ui_manager.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <filesystem>
#include <utility>

namespace {

// Rendering receives commercial-demand text only from the gameplay model.
constexpr float kMargin = 12.0F;
constexpr float kTopBarHeight = 64.0F;
// The authored category buttons need enough vertical room to retain their
// bevel, icon and label instead of being compressed into debug-style strips.
constexpr float kToolbarHeight = 74.0F;
constexpr float kButtonHeight = 30.0F;

void draw_panel(SDL_Renderer* renderer, const UiRect& bounds) {
    SDL_SetRenderDrawColor(renderer, 16, 25, 30, 232);
    const SDL_FRect rect = {bounds.x, bounds.y, bounds.width, bounds.height};
    SDL_RenderFillRect(renderer, &rect);
    SDL_SetRenderDrawColor(renderer, 178, 217, 186, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &rect);
}

std::string ascii_debug_text(const std::string& text) {
    // SDL_RenderDebugText uses a compact ASCII glyph set.  Keep source data in
    // UTF-8 but present common Portuguese characters legibly in this UI.
    std::string result;
    for (std::size_t index = 0; index < text.size(); ++index) {
        const unsigned char first = static_cast<unsigned char>(text[index]);
        if (first < 0x80U) {
            result.push_back(static_cast<char>(first));
            continue;
        }
        if (first == 0xC3U && index + 1 < text.size()) {
            const unsigned char second = static_cast<unsigned char>(text[++index]);
            switch (second) {
                case 0x80: case 0x81: case 0x82: case 0x83: case 0x84: case 0x85: result.push_back('A'); break;
                case 0x87: result.push_back('C'); break;
                case 0x88: case 0x89: case 0x8A: case 0x8B: result.push_back('E'); break;
                case 0x8C: case 0x8D: case 0x8E: case 0x8F: result.push_back('I'); break;
                case 0x92: case 0x93: case 0x94: case 0x95: case 0x96: result.push_back('O'); break;
                case 0x99: case 0x9A: case 0x9B: case 0x9C: result.push_back('U'); break;
                case 0xA0: case 0xA1: case 0xA2: case 0xA3: case 0xA4: case 0xA5: result.push_back('a'); break;
                case 0xA7: result.push_back('c'); break;
                case 0xA8: case 0xA9: case 0xAA: case 0xAB: result.push_back('e'); break;
                case 0xAC: case 0xAD: case 0xAE: case 0xAF: result.push_back('i'); break;
                case 0xB2: case 0xB3: case 0xB4: case 0xB5: case 0xB6: result.push_back('o'); break;
                case 0xB9: case 0xBA: case 0xBB: case 0xBC: result.push_back('u'); break;
                default: result.push_back('?'); break;
            }
            continue;
        }
        // Consume the remainder of an unsupported UTF-8 sequence as one
        // placeholder rather than displaying mojibake byte-by-byte.
        result.push_back('?');
        while (index + 1 < text.size() && (static_cast<unsigned char>(text[index + 1]) & 0xC0U) == 0x80U) ++index;
    }
    return result;
}

void draw_text(SDL_Renderer* renderer, float x, float y, const std::string& text,
               Uint8 red = 238, Uint8 green = 244, Uint8 blue = 238) {
    SDL_SetRenderDrawColor(renderer, red, green, blue, SDL_ALPHA_OPAQUE);
    const std::string printable = ascii_debug_text(text);
    SDL_RenderDebugText(renderer, x, y, printable.c_str());
}

// SDL_RenderDebugText has no clipping or wrapping.  Keep every line inside
// its owning panel so long status and resource descriptions do not paint over
// nearby controls or the map.
void draw_text_fit(SDL_Renderer* renderer, float x, float y, float available_width, const std::string& text,
                   Uint8 red = 238, Uint8 green = 244, Uint8 blue = 238) {
    std::string printable = ascii_debug_text(text);
    const std::size_t maximum_characters = static_cast<std::size_t>(std::max(0.0F, available_width) / 8.0F);
    if (maximum_characters == 0) {
        return;
    }
    if (printable.size() > maximum_characters) {
        if (maximum_characters <= 3) {
            printable.resize(maximum_characters);
        } else {
            printable.resize(maximum_characters - 3);
            printable += "...";
        }
    }
    SDL_SetRenderDrawColor(renderer, red, green, blue, SDL_ALPHA_OPAQUE);
    SDL_RenderDebugText(renderer, x, y, printable.c_str());
}

// Contextual information must remain readable rather than being shortened
// with an ellipsis.  This small word wrapper is deliberately presentation
// only: gameplay continues to pass a normal, single string per field.
std::vector<std::string> wrap_debug_text(const std::string& text, const float available_width) {
    const std::size_t maximum_characters = static_cast<std::size_t>(std::max(0.0F, available_width) / 8.0F);
    if (maximum_characters == 0 || text.empty()) return {};

    std::string remaining = ascii_debug_text(text);
    std::vector<std::string> lines;
    while (!remaining.empty()) {
        while (!remaining.empty() && std::isspace(static_cast<unsigned char>(remaining.front())) != 0) {
            remaining.erase(remaining.begin());
        }
        if (remaining.size() <= maximum_characters) {
            lines.push_back(std::move(remaining));
            break;
        }
        std::size_t split = remaining.rfind(' ', maximum_characters);
        if (split == std::string::npos || split == 0) split = maximum_characters;
        lines.push_back(remaining.substr(0, split));
        remaining.erase(0, split);
    }
    return lines;
}

std::size_t draw_text_wrapped(SDL_Renderer* renderer, const float x, float y, const float available_width,
                              const std::string& text, const Uint8 red = 238, const Uint8 green = 244,
                              const Uint8 blue = 238) {
    const std::vector<std::string> lines = wrap_debug_text(text, available_width);
    SDL_SetRenderDrawColor(renderer, red, green, blue, SDL_ALPHA_OPAQUE);
    for (const std::string& line : lines) {
        SDL_RenderDebugText(renderer, x, y, line.c_str());
        y += 17.0F;
    }
    return lines.size();
}

void draw_hud_panel(SDL_Renderer* renderer, const UiRect& bounds) {
    const SDL_FRect rect = {bounds.x, bounds.y, bounds.width, bounds.height};
    SDL_SetRenderDrawColor(renderer, 16, 39, 56, 244);
    SDL_RenderFillRect(renderer, &rect);
    SDL_SetRenderDrawColor(renderer, 71, 111, 134, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &rect);
    SDL_SetRenderDrawColor(renderer, 35, 71, 92, SDL_ALPHA_OPAQUE);
    SDL_RenderLine(renderer, bounds.x + 1.0F, bounds.y + bounds.height - 2.0F,
                   bounds.x + bounds.width - 1.0F, bounds.y + bounds.height - 2.0F);
}

void draw_toolbar_panel(SDL_Renderer* renderer, const UiRect& bounds) {
    const SDL_FRect rect = {bounds.x, bounds.y, bounds.width, bounds.height};
    SDL_SetRenderDrawColor(renderer, 14, 35, 50, 246);
    SDL_RenderFillRect(renderer, &rect);
    SDL_SetRenderDrawColor(renderer, 66, 105, 127, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &rect);
    SDL_SetRenderDrawColor(renderer, 29, 62, 80, SDL_ALPHA_OPAQUE);
    SDL_RenderLine(renderer, bounds.x + 1.0F, bounds.y + 2.0F,
                   bounds.x + bounds.width - 1.0F, bounds.y + 2.0F);
}

enum class HudIcon { coins, calendar, people, energy };

bool is_primary_tool_action(UiAction action) {
    return action == UiAction::open_build_panel || action == UiAction::activate_roads ||
           action == UiAction::activate_sidewalks || action == UiAction::activate_land ||
           action == UiAction::activate_remove || action == UiAction::open_agriculture_panel ||
           action == UiAction::activate_decoration;
}

const char* icon_name_for(UiAction action) {
    switch (action) {
        case UiAction::open_build_panel: return "buildings";
        case UiAction::activate_roads: return "roads";
        case UiAction::activate_sidewalks: return "sidewalks";
        case UiAction::activate_land: return "land";
        case UiAction::activate_remove: return "demolish";
        case UiAction::open_agriculture_panel: return "agriculture";
        case UiAction::activate_decoration: return "decoration";
        case UiAction::toggle_pause: return "pause";
        case UiAction::open_settings: return "settings";
        case UiAction::close_selection: return "close";
        case UiAction::rotate_left:
        case UiAction::rotate_right: return "rotate";
        default: return nullptr;
    }
}

std::string ui_icon_path(const char* icon_name) {
    const char* base_path = SDL_GetBasePath();
    const std::filesystem::path root = base_path == nullptr ? std::filesystem::path(".") : std::filesystem::path(base_path);
    return (root / "assets" / "ui" / "icons" / (std::string(icon_name) + ".png")).string();
}

const char* chrome_name_for(const UiAction action) {
    switch (action) {
        case UiAction::open_build_panel: return "category_buildings";
        case UiAction::activate_roads: return "category_roads";
        case UiAction::open_agriculture_panel: return "category_agriculture";
        default: return nullptr;
    }
}

std::string ui_chrome_path(const char* chrome_name) {
    const char* base_path = SDL_GetBasePath();
    const std::filesystem::path root = base_path == nullptr ? std::filesystem::path(".") : std::filesystem::path(base_path);
    return (root / "assets" / "ui" / "chrome" / (std::string(chrome_name) + ".png")).string();
}

std::string ui_button_state_atlas_path() {
    const char* base_path = SDL_GetBasePath();
    const std::filesystem::path root = base_path == nullptr ? std::filesystem::path(".") : std::filesystem::path(base_path);
    return (root / "assets" / "ui" / "atlas" / "button_states_v1.png").string();
}

std::string ui_goals_controls_atlas_path() {
    const char* base_path = SDL_GetBasePath();
    const std::filesystem::path root = base_path == nullptr ? std::filesystem::path(".") : std::filesystem::path(base_path);
    return (root / "assets" / "ui" / "atlas" / "goals_controls_v1.png").string();
}

enum class UiAtlasButtonFamily : std::uint8_t {
    blue_wide,
    green_wide,
    red_wide,
    blue_compact,
    blue_circle,
};

[[nodiscard]] UiAtlasButtonFamily atlas_family_for(const UiButton& button) {
    const float aspect = button.bounds.height > 0.0F ? button.bounds.width / button.bounds.height : 1.0F;
    if (aspect < 1.35F) return UiAtlasButtonFamily::blue_circle;
    if (button.action == UiAction::settings_apply || button.action == UiAction::upgrade_building) {
        return UiAtlasButtonFamily::green_wide;
    }
    if (button.action == UiAction::settings_cancel || button.action == UiAction::activate_remove) {
        return UiAtlasButtonFamily::red_wide;
    }
    return aspect < 2.7F ? UiAtlasButtonFamily::blue_compact : UiAtlasButtonFamily::blue_wide;
}

// Coordinates are deliberately data-like and match button_states_v1.json.
// Each family uses four columns: normal, hover, pressed/selected, disabled.
[[nodiscard]] SDL_FRect atlas_source_for(const UiButton& button) {
    const UiButtonState state = !button.enabled ? UiButtonState::disabled
        : (button.active ? UiButtonState::pressed : button.state);
    const int column = state == UiButtonState::hover ? 1
        : state == UiButtonState::pressed ? 2
        : state == UiButtonState::disabled ? 3 : 0;

    switch (atlas_family_for(button)) {
        case UiAtlasButtonFamily::blue_wide:
            return {20.0F + 354.0F * static_cast<float>(column), 90.0F, 354.0F, 140.0F};
        case UiAtlasButtonFamily::green_wide:
            return {20.0F + 354.0F * static_cast<float>(column), 383.0F, 354.0F, 142.0F};
        case UiAtlasButtonFamily::red_wide:
            return {20.0F + 354.0F * static_cast<float>(column), 535.0F, 354.0F, 142.0F};
        case UiAtlasButtonFamily::blue_compact:
            return {35.0F + 350.0F * static_cast<float>(column), 688.0F, 330.0F, 114.0F};
        case UiAtlasButtonFamily::blue_circle:
            return {92.0F + 346.0F * static_cast<float>(column), 810.0F, 224.0F, 228.0F};
    }
    return {};
}

[[nodiscard]] SDL_FRect goals_close_source_for(const UiButtonState state) {
    const int column = state == UiButtonState::hover ? 1
        : state == UiButtonState::pressed ? 2
        : state == UiButtonState::disabled ? 3 : 0;
    static constexpr std::array<float, 4> kLeft = {704.0F, 837.0F, 985.0F, 1137.0F};
    return {kLeft[static_cast<std::size_t>(column)], 61.0F, 68.0F, 68.0F};
}

[[nodiscard]] SDL_FRect goals_back_source_for(const UiButtonState state) {
    const int column = state == UiButtonState::hover ? 1
        : state == UiButtonState::pressed ? 2
        : state == UiButtonState::disabled ? 3 : 0;
    return {666.0F + 150.0F * static_cast<float>(column), 197.0F, 146.0F, 59.0F};
}

std::string ui_overlay_path(const UiOverlay overlay) {
    const char* base_path = SDL_GetBasePath();
    const std::filesystem::path root = base_path == nullptr ? std::filesystem::path(".") : std::filesystem::path(base_path);
    switch (overlay) {
        case UiOverlay::pause: return (root / "assets" / "ui" / "screens" / "pause_menu.png").string();
        case UiOverlay::administration: return (root / "assets" / "ui" / "panels" / "administration_panel.png").string();
        case UiOverlay::reports: return (root / "assets" / "ui" / "panels" / "reports_panel.png").string();
        case UiOverlay::settings: return (root / "assets" / "ui" / "panels" / "settings_panel.png").string();
        case UiOverlay::none: break;
    }
    return {};
}

void draw_tool_icon(SDL_Renderer* renderer, float x, float y, UiAction action) {
    SDL_SetRenderDrawColor(renderer, 211, 229, 236, SDL_ALPHA_OPAQUE);
    if (action == UiAction::open_build_panel) {
        const SDL_FRect body = {x + 2.0F, y + 7.0F, 17.0F, 12.0F};
        SDL_RenderRect(renderer, &body);
        SDL_RenderLine(renderer, x, y + 8.0F, x + 10.0F, y + 1.0F);
        SDL_RenderLine(renderer, x + 10.0F, y + 1.0F, x + 21.0F, y + 8.0F);
    } else if (action == UiAction::activate_roads) {
        SDL_RenderLine(renderer, x + 4.0F, y + 1.0F, x + 16.0F, y + 20.0F);
        SDL_RenderLine(renderer, x + 12.0F, y + 1.0F, x, y + 20.0F);
    } else if (action == UiAction::activate_sidewalks) {
        for (int row = 0; row < 2; ++row) {
            for (int column = 0; column < 2; ++column) {
                const SDL_FRect tile = {x + static_cast<float>(column) * 10.0F, y + static_cast<float>(row) * 10.0F, 8.0F, 8.0F};
                SDL_RenderRect(renderer, &tile);
            }
        }
    } else if (action == UiAction::activate_land) {
        const SDL_FRect land = {x + 1.0F, y + 5.0F, 20.0F, 13.0F};
        SDL_RenderRect(renderer, &land);
        SDL_RenderLine(renderer, x + 4.0F, y + 14.0F, x + 10.0F, y + 8.0F);
        SDL_RenderLine(renderer, x + 10.0F, y + 8.0F, x + 18.0F, y + 8.0F);
    } else if (action == UiAction::activate_remove) {
        SDL_RenderLine(renderer, x + 2.0F, y + 2.0F, x + 20.0F, y + 20.0F);
        SDL_RenderLine(renderer, x + 20.0F, y + 2.0F, x + 2.0F, y + 20.0F);
    } else {
        const SDL_FRect trunk = {x + 9.0F, y + 12.0F, 4.0F, 9.0F};
        const SDL_FRect canopy = {x + 3.0F, y + 1.0F, 16.0F, 14.0F};
        SDL_RenderRect(renderer, &canopy);
        SDL_RenderFillRect(renderer, &trunk);
    }
}

void draw_hud_icon(SDL_Renderer* renderer, float x, float y, HudIcon icon) {
    SDL_SetRenderDrawColor(renderer, icon == HudIcon::energy ? 247 : 224,
                           icon == HudIcon::energy ? 197 : 225,
                           icon == HudIcon::energy ? 66 : 229, SDL_ALPHA_OPAQUE);
    if (icon == HudIcon::coins) {
        for (int row = 0; row < 3; ++row) {
            const SDL_FRect coin = {x + static_cast<float>(row % 2) * 2.0F, y + static_cast<float>(row) * 6.0F,
                                    16.0F, 4.0F};
            SDL_RenderFillRect(renderer, &coin);
        }
    } else if (icon == HudIcon::calendar) {
        const SDL_FRect calendar = {x, y + 3.0F, 18.0F, 16.0F};
        SDL_RenderRect(renderer, &calendar);
        SDL_RenderLine(renderer, x, y + 8.0F, x + 18.0F, y + 8.0F);
        SDL_RenderLine(renderer, x + 4.0F, y, x + 4.0F, y + 5.0F);
        SDL_RenderLine(renderer, x + 14.0F, y, x + 14.0F, y + 5.0F);
    } else if (icon == HudIcon::people) {
        const SDL_FRect head_a = {x + 2.0F, y, 5.0F, 5.0F};
        const SDL_FRect head_b = {x + 11.0F, y, 5.0F, 5.0F};
        const SDL_FRect body_a = {x, y + 7.0F, 9.0F, 11.0F};
        const SDL_FRect body_b = {x + 9.0F, y + 7.0F, 9.0F, 11.0F};
        SDL_RenderFillRect(renderer, &head_a);
        SDL_RenderFillRect(renderer, &head_b);
        SDL_RenderFillRect(renderer, &body_a);
        SDL_RenderFillRect(renderer, &body_b);
    } else {
        SDL_RenderLine(renderer, x + 11.0F, y, x + 4.0F, y + 10.0F);
        SDL_RenderLine(renderer, x + 4.0F, y + 10.0F, x + 10.0F, y + 10.0F);
        SDL_RenderLine(renderer, x + 10.0F, y + 10.0F, x + 6.0F, y + 20.0F);
    }
}

void draw_hud_stat(SDL_Renderer* renderer, float x, HudIcon icon, const std::string& label,
                   const std::string& value, const std::string& secondary = {}) {
    draw_hud_icon(renderer, x, 29.0F, icon);
    draw_text(renderer, x + 27.0F, 23.0F, label, 185, 204, 214);
    draw_text(renderer, x + 27.0F, 40.0F, value, 244, 248, 250);
    if (!secondary.empty()) {
        draw_text(renderer, x + 27.0F, 53.0F, secondary, 159, 180, 192);
    }
}

void draw_button_content(SDL_Renderer* renderer, const UiButton& button) {
    if (button.action == UiAction::open_settings) {
        const float center_x = button.bounds.x + button.bounds.width * 0.5F;
        const float center_y = button.bounds.y + button.bounds.height * 0.5F;
        SDL_SetRenderDrawColor(renderer, button.enabled ? 218 : 135, button.enabled ? 242 : 140,
                               button.enabled ? 251 : 145, SDL_ALPHA_OPAQUE);
        SDL_RenderLine(renderer, center_x - 8.0F, center_y, center_x + 8.0F, center_y);
        SDL_RenderLine(renderer, center_x, center_y - 8.0F, center_x, center_y + 8.0F);
        const SDL_FRect gear_center = {center_x - 4.0F, center_y - 4.0F, 8.0F, 8.0F};
        SDL_RenderRect(renderer, &gear_center);
        return;
    }
    const bool primary_tool = is_primary_tool_action(button.action);
    if (primary_tool) {
        draw_tool_icon(renderer, button.bounds.x + 10.0F, button.bounds.y + 7.0F, button.action);
    }
    const bool icon_text_control = button.action == UiAction::toggle_pause || button.action == UiAction::rotate_left ||
                                   button.action == UiAction::rotate_right;
    const float label_x = primary_tool ? 40.0F : (icon_text_control ? 36.0F : 8.0F);
    draw_text(renderer, button.bounds.x + label_x, button.bounds.y + 13.0F, button.label,
              button.enabled ? 238 : 135, button.enabled ? 244 : 140, button.enabled ? 238 : 145);
}

void draw_button(SDL_Renderer* renderer, const UiButton& button) {
    const bool hud_control = button.action == UiAction::toggle_pause || button.action == UiAction::open_administration ||
                             button.action == UiAction::open_settings;
    Uint8 red = hud_control ? 23 : 52;
    Uint8 green = hud_control ? 78 : 80;
    Uint8 blue = hud_control ? 109 : 66;
    if (!button.enabled) {
        red = 42;
        green = 47;
        blue = 48;
    } else if (button.state == UiButtonState::pressed) {
        red = hud_control ? 31 : 70;
        green = hud_control ? 108 : 126;
        blue = hud_control ? 142 : 91;
    } else if (button.state == UiButtonState::hover) {
        red = 73;
        green = 112;
        blue = 88;
    } else if (button.active) {
        red = hud_control ? 28 : 63;
        green = hud_control ? 113 : 137;
        blue = hud_control ? 145 : 95;
    }

    SDL_SetRenderDrawColor(renderer, red, green, blue, SDL_ALPHA_OPAQUE);
    const SDL_FRect rect = {button.bounds.x, button.bounds.y, button.bounds.width, button.bounds.height};
    SDL_RenderFillRect(renderer, &rect);
    SDL_SetRenderDrawColor(renderer, button.enabled ? (hud_control ? 108 : 197) : 94,
                           button.enabled ? (hud_control ? 171 : 229) : 100,
                           button.enabled ? (hud_control ? 205 : 205) : 104, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &rect);
    draw_button_content(renderer, button);
}

}  // namespace

bool UiRect::contains(float point_x, float point_y) const {
    return point_x >= x && point_y >= y && point_x <= x + width && point_y <= y + height;
}

void GameplayUi::update_layout(int viewport_width, int viewport_height, const GameplayUiModel& model) {
    model_ = model;
    viewport_width_ = std::max(viewport_width, 1);
    viewport_height_ = std::max(viewport_height, 1);
    buttons_.clear();
    panels_.clear();
    build_panel_bounds_.reset();
    overlay_bounds_.reset();

    const float width = static_cast<float>(viewport_width_);
    const float height = static_cast<float>(viewport_height_);
    add_panel({kMargin, kMargin, std::max(100.0F, width - kMargin * 2.0F), kTopBarHeight});

    const float settings_x = std::max(kMargin + 270.0F, width - 50.0F);
    const float administration_x = std::max(kMargin + 120.0F, settings_x - 112.0F);
    const float pause_x = std::max(kMargin, administration_x - 124.0F);
    add_button({pause_x, 28.0F, 114.0F, kButtonHeight}, model.paused ? "PLAY" : "PAUSE", UiAction::toggle_pause,
               true, model.paused);
    add_button({administration_x, 28.0F, 102.0F, kButtonHeight}, "ADMIN", UiAction::open_administration);
    add_button({settings_x, 28.0F, 30.0F, kButtonHeight}, "SET", UiAction::open_settings);

    const float toolbar_y = height - kToolbarHeight - kMargin;
    const float toolbar_width = std::max(100.0F, width - kMargin * 2.0F);
    const float context_width = std::clamp(toolbar_width * 0.25F, 190.0F, 330.0F);
    const float tools_width = std::max(1.0F, toolbar_width - context_width - 8.0F);
    const float tool_width = tools_width / 7.0F;
    add_panel({kMargin, toolbar_y, toolbar_width, kToolbarHeight});
    const float tool_y = toolbar_y + 11.0F;
    constexpr float tool_height = 52.0F;
    add_button({kMargin + 4.0F + tool_width * 0.0F, tool_y, tool_width - 6.0F, tool_height}, "CONSTRUCOES", UiAction::open_build_panel,
               true, model.active_tool == UiTool::buildings);
    add_button({kMargin + 4.0F + tool_width * 1.0F, tool_y, tool_width - 6.0F, tool_height}, "ESTRADAS", UiAction::activate_roads,
               true, model.active_tool == UiTool::roads);
    add_button({kMargin + 4.0F + tool_width * 2.0F, tool_y, tool_width - 6.0F, tool_height}, "PISO", UiAction::activate_sidewalks,
               true, model.active_tool == UiTool::sidewalks);
    add_button({kMargin + 4.0F + tool_width * 3.0F, tool_y, tool_width - 6.0F, tool_height}, "TERRENO", UiAction::activate_land,
               true, model.active_tool == UiTool::land);
    add_button({kMargin + 4.0F + tool_width * 4.0F, tool_y, tool_width - 6.0F, tool_height}, "DEMOLIR", UiAction::activate_remove,
               true, model.active_tool == UiTool::remove);
    add_button({kMargin + 4.0F + tool_width * 5.0F, tool_y, tool_width - 6.0F, tool_height}, "AGRICULTURA", UiAction::open_agriculture_panel,
               true, model.active_tool == UiTool::agriculture);
    add_button({kMargin + 4.0F + tool_width * 6.0F, tool_y, tool_width - 6.0F, tool_height}, "DECORACAO", UiAction::activate_decoration,
               true, model.active_tool == UiTool::decoration);


    if (model.build_panel_open || model.farming_panel_open || model.active_tool == UiTool::decoration) {
        constexpr float panel_width = 410.0F;
        const float header_height = model.farming_panel_open ? 60.0F : 42.0F;
        // Every catalog entry has a fixed-canvas thumbnail and the essential
        // placement facts. This avoids asking players to infer footprint or
        // infrastructure requirements from a world-sized sprite.
        constexpr float card_height = 96.0F;
        constexpr float card_gap = 6.0F;
        const float panel_y = 84.0F;
        const float panel_height = std::max(120.0F, toolbar_y - panel_y - 8.0F);
        const UiRect panel_bounds = {kMargin, panel_y, panel_width, panel_height};
        add_panel(panel_bounds);
        build_panel_bounds_ = panel_bounds;
        const float visible_height = panel_height - header_height - 8.0F;
        const std::vector<UiBuildItem>& panel_items =
            model.farming_panel_open ? model.farming_items
            : (model.active_tool == UiTool::decoration ? model.decor_items : model.build_items);
        const UiAction panel_action =
            model.farming_panel_open ? UiAction::select_farming_item : UiAction::select_building;
        const std::string& panel_selected_id =
            model.farming_panel_open ? model.selected_farming_id : model.selected_building_id;
        const float content_height = static_cast<float>(panel_items.size()) * (card_height + card_gap);
        build_scroll_max_ = std::max(0.0F, content_height - visible_height);
        build_scroll_offset_ = std::clamp(build_scroll_offset_, 0.0F, build_scroll_max_);
        float item_y = panel_y + header_height - build_scroll_offset_;
        for (const UiBuildItem& item : panel_items) {
            const UiRect card_bounds = {panel_bounds.x + 8.0F, item_y, panel_bounds.width - 16.0F, card_height};
            if (card_bounds.y >= panel_bounds.y + header_height &&
                card_bounds.y + card_bounds.height <= panel_bounds.y + panel_bounds.height - 6.0F) {
                add_build_card(card_bounds, item,
                               item.definition_id == panel_selected_id,
                               panel_action);
            }
            item_y += card_height + card_gap;
        }
    } else {
        build_scroll_offset_ = 0.0F;
        build_scroll_max_ = 0.0F;
    }


    if (model.land_details && model.active_tool == UiTool::land) {
        add_panel({kMargin, 84.0F, 300.0F, 62.0F});
    }

    if (model.selected_building) {
        const float panel_width = 330.0F;
        const UiSelectedBuilding& item = *model.selected_building;
        const std::vector<std::string> details = {
            "ACESSO A RUA: " + item.road_access_requirement + " / " + item.road_access,
            item.energy_consumption.empty() ? "" : "CONSUMO ENERGIA: " + item.energy_consumption,
            item.energy_production.empty() ? "" : "PRODUCAO ENERGIA: " + item.energy_production,
            item.residential_capacity.empty() ? "" : "CAPACIDADE RESIDENCIAL: " + item.residential_capacity,
            item.property_tax_per_year.empty() ? "" : "IPTU ANUAL: " + item.property_tax_per_year,
            item.commercial_demand.empty() ? "" : "RECEITA BASE: " + item.monthly_tax + "/MES",
            item.commercial_demand.empty() ? "" : "DEMANDA: " + item.commercial_demand,
            item.commercial_current_revenue.empty() ? "" : "RECEITA ESTIMADA: " + item.commercial_current_revenue + "/MES",
            item.commercial_demand.empty() ? "" : "MANUTENCAO: " + item.monthly_maintenance + "/MES",
            item.local_supply.empty() ? "" : "ABASTECIMENTO LOCAL: " + item.local_supply,
        };
        std::size_t detail_lines = 0;
        for (const std::string& detail : details) {
            if (!detail.empty()) detail_lines += wrap_debug_text(detail, 306.0F).size();
        }
        const float required_height = 126.0F + static_cast<float>(detail_lines) * 17.0F;
        const float maximum_height = std::max(120.0F, toolbar_y - 92.0F);
        const float panel_height = std::min(maximum_height, std::max(308.0F, required_height));
        add_panel({width - panel_width - kMargin, 84.0F, panel_width, panel_height});
        add_button({width - 38.0F, 92.0F, 18.0F, 18.0F}, "X", UiAction::close_selection);
    }

    if (!model.status.empty()) {
        // Reserve the central map strip between an open catalogue and an
        // inspection panel. This avoids a toast sitting on top of either UI.
        const float left_edge = (model.build_panel_open || model.farming_panel_open) ? 394.0F : kMargin;
        const float right_edge = model.selected_building ? width - 354.0F : width - kMargin;
        const float available_width = std::max(180.0F, right_edge - left_edge);
        const float toast_width = std::min(440.0F, available_width);
        add_panel({left_edge + (available_width - toast_width) * 0.5F, 84.0F, toast_width, 28.0F});
    }
    if (model.debug_visible) {
        const float debug_height = 18.0F + static_cast<float>(model.debug_lines.size()) * 18.0F;
        add_panel({kMargin, 120.0F, 460.0F, debug_height});
    }

    if (model.overlay != UiOverlay::none) {
        // The supplied panels are authored on a 1280x960 canvas.  Preserve
        // that aspect ratio at every game resolution; the image itself is the
        // visual chrome while these transparent hit regions expose logic.
        const float scale = std::min(width * 0.94F / 1280.0F, height * 0.90F / 960.0F);
        const UiRect panel = {(width - 1280.0F * scale) * 0.5F, (height - 960.0F * scale) * 0.5F,
                              1280.0F * scale, 960.0F * scale};
        overlay_bounds_ = panel;
        const auto source_rect = [&](const float x, const float y, const float w, const float h) {
            return UiRect{panel.x + x * scale, panel.y + y * scale, w * scale, h * scale};
        };
        if (model.overlay != UiOverlay::pause) {
            add_button(source_rect(1160.0F, 88.0F, 78.0F, 78.0F), "X", UiAction::close_modal);
        }
        if (model.overlay == UiOverlay::pause) {
            // Continue is operational. The other pause-menu commands remain
            // intentionally disabled until their underlying front-end/save
            // flows own the operation rather than a visual mock.
            add_button(source_rect(300.0F, 340.0F, 680.0F, 78.0F), "CONTINUAR", UiAction::resume_game);
            add_button(source_rect(300.0F, 432.0F, 680.0F, 78.0F), "SALVAR", UiAction::none, false);
            add_button(source_rect(300.0F, 522.0F, 680.0F, 78.0F), "CARREGAR", UiAction::none, false);
            add_button(source_rect(300.0F, 612.0F, 680.0F, 78.0F), "CONFIGURACOES", UiAction::none, false);
            add_button(source_rect(300.0F, 702.0F, 680.0F, 78.0F), "MENU PRINCIPAL", UiAction::none, false);
            add_button(source_rect(300.0F, 792.0F, 680.0F, 78.0F), "SAIR DO JOGO", UiAction::none, false);
        }
        if (model.overlay == UiOverlay::administration) {
            // Reports is a navigation target within the supplied Administration
            // composition.  The art remains a single panel; only the logical
            // region is interactive.
            add_button(source_rect(926.0F, 820.0F, 286.0F, 72.0F), "RELATORIOS", UiAction::open_reports);
        }
        if (model.overlay == UiOverlay::reports) {
            add_button(source_rect(1010.0F, 876.0F, 216.0F, 64.0F), "VOLTAR", UiAction::open_administration);
        }
        if (model.overlay == UiOverlay::settings) {
            add_button(source_rect(132.0F, 848.0F, 320.0F, 70.0F), "PADRAO", UiAction::settings_reset);
            add_button(source_rect(524.0F, 848.0F, 250.0F, 70.0F), "CANCELAR", UiAction::settings_cancel);
            add_button(source_rect(830.0F, 848.0F, 290.0F, 70.0F), "APLICAR", UiAction::settings_apply);
        }
    }

    handle_mouse_motion(mouse_x_, mouse_y_);
}

void GameplayUi::handle_mouse_motion(float mouse_x, float mouse_y) {
    mouse_x_ = mouse_x;
    mouse_y_ = mouse_y;
    for (UiButton& button : buttons_) {
        button.state = state_for(button, mouse_x_, mouse_y_, primary_pressed_);
    }
}

bool GameplayUi::handle_mouse_wheel(float mouse_x, float mouse_y, float wheel_y) {
    if (model_.overlay != UiOverlay::none) {
        return true;
    }
    if (!build_panel_bounds_ || !build_panel_bounds_->contains(mouse_x, mouse_y) || build_scroll_max_ <= 0.0F) {
        return false;
    }
    build_scroll_offset_ = std::clamp(build_scroll_offset_ - wheel_y * 48.0F, 0.0F, build_scroll_max_);
    update_layout(viewport_width_, viewport_height_, model_);
    return true;
}

void GameplayUi::release_renderer_resources() {
    for (const auto& [path, thumbnail] : thumbnails_) {
        (void)path;
        if (thumbnail.texture != nullptr) {
            SDL_DestroyTexture(thumbnail.texture);
        }
    }
    thumbnails_.clear();
}

UiInputResult GameplayUi::handle_mouse_button_down(float mouse_x, float mouse_y, bool primary_button) {
    handle_mouse_motion(mouse_x, mouse_y);
    UiInputResult result;
    result.consumed = consumes_point(mouse_x, mouse_y);
    if (!result.consumed || !primary_button) {
        return result;
    }

    primary_pressed_ = true;
    for (auto it = buttons_.rbegin(); it != buttons_.rend(); ++it) {
        UiButton& button = *it;
        button.state = state_for(button, mouse_x_, mouse_y_, true);
        if (!button.bounds.contains(mouse_x, mouse_y)) {
            continue;
        }
        if (button.enabled) {
            result.action = UiActionEvent{button.action, button.payload};
        }
        break;
    }
    return result;
}

void GameplayUi::handle_mouse_button_up(float mouse_x, float mouse_y) {
    primary_pressed_ = false;
    handle_mouse_motion(mouse_x, mouse_y);
}

bool GameplayUi::consumes_point(float mouse_x, float mouse_y) const {
    if (model_.overlay != UiOverlay::none) {
        // A modal pauses map interaction everywhere, including the translucent
        // area outside its artwork.
        return true;
    }
    return std::any_of(panels_.begin(), panels_.end(), [mouse_x, mouse_y](const UiRect& panel) {
        return panel.contains(mouse_x, mouse_y);
    });
}

void GameplayUi::render(SDL_Renderer* renderer) const {
    if (renderer == nullptr) {
        return;
    }
    const auto draw_ui_icon = [&](const char* name, const SDL_FRect& bounds) {
        if (const UiThumbnail* icon = thumbnail_for(renderer, ui_icon_path(name))) {
            const float scale = std::min(bounds.w / icon->width, bounds.h / icon->height);
            const SDL_FRect destination = {bounds.x + (bounds.w - icon->width * scale) * 0.5F,
                                           bounds.y + (bounds.h - icon->height * scale) * 0.5F,
                                           icon->width * scale, icon->height * scale};
            SDL_RenderTexture(renderer, icon->texture, nullptr, &destination);
        }
    };
    const auto draw_chrome_button = [&](const UiButton& button) -> bool {
        const char* chrome_name = chrome_name_for(button.action);
        if (chrome_name == nullptr) {
            return false;
        }
        const UiThumbnail* chrome = thumbnail_for(renderer, ui_chrome_path(chrome_name));
        if (chrome == nullptr) {
            return false;
        }
        const SDL_FRect destination = {button.bounds.x, button.bounds.y, button.bounds.width, button.bounds.height};
        SDL_RenderTexture(renderer, chrome->texture, nullptr, &destination);
        if (!button.enabled) {
            SDL_SetRenderDrawColor(renderer, 7, 13, 18, 150);
            SDL_RenderFillRect(renderer, &destination);
        } else if (button.active || button.state == UiButtonState::pressed) {
            SDL_SetRenderDrawColor(renderer, 60, 222, 255, 58);
            SDL_RenderFillRect(renderer, &destination);
        } else if (button.state == UiButtonState::hover) {
            SDL_SetRenderDrawColor(renderer, 176, 244, 255, 36);
            SDL_RenderFillRect(renderer, &destination);
        }
        return true;
    };
    const auto draw_state_atlas_button = [&](const UiButton& button) -> bool {
        // Build cards carry a different information-dense layout. Everything
        // else uses the shared four-state atlas, including modal controls.
        if (button.build_card) return false;
        const UiButtonState state = !button.enabled ? UiButtonState::disabled
            : (button.active ? UiButtonState::pressed : button.state);
        const bool is_close = button.action == UiAction::close_modal || button.action == UiAction::close_selection;
        const bool is_back = button.action == UiAction::open_administration && model_.overlay == UiOverlay::reports;
        const UiThumbnail* atlas = thumbnail_for(renderer, is_close || is_back
            ? ui_goals_controls_atlas_path() : ui_button_state_atlas_path());
        if (atlas == nullptr) return false;
        const SDL_FRect source = is_close ? goals_close_source_for(state)
            : is_back ? goals_back_source_for(state) : atlas_source_for(button);
        const SDL_FRect destination = {button.bounds.x, button.bounds.y, button.bounds.width, button.bounds.height};
        SDL_RenderTexture(renderer, atlas->texture, &source, &destination);
        return true;
    };
    for (std::size_t index = 0; index < panels_.size(); ++index) {
        if (index == 0) {
            draw_hud_panel(renderer, panels_[index]);
        } else if (index == 1) {
            draw_toolbar_panel(renderer, panels_[index]);
        } else {
            draw_panel(renderer, panels_[index]);
        }
    }
    if (panels_.size() > 1) {
        const UiRect& toolbar = panels_[1];
        const float context_width = std::clamp(toolbar.width * 0.25F, 190.0F, 330.0F);
        const float context_x = toolbar.x + toolbar.width - context_width;
        SDL_SetRenderDrawColor(renderer, 55, 91, 111, SDL_ALPHA_OPAQUE);
        SDL_RenderLine(renderer, context_x - 8.0F, toolbar.y + 7.0F, context_x - 8.0F,
                       toolbar.y + toolbar.height - 7.0F);

        std::string title = "SELECIONE UMA FERRAMENTA";
        std::string description = "ESCOLHA UMA CATEGORIA ABAIXO";
        switch (model_.active_tool) {
            case UiTool::buildings:
                title = "MODO CONSTRUCOES";
                description = model_.build_panel_open ? "SELECIONE UM ITEM PARA POSICIONAR" : "ESCOLHA UMA CONSTRUCAO";
                break;
            case UiTool::roads: title = "MODO ESTRADAS"; description = "CLIQUE E ARRASTE PARA CONSTRUIR"; break;
            case UiTool::sidewalks: title = "MODO CALCADAS"; description = "CLIQUE OU ARRASTE EM TERRENO PROPRIO"; break;
            case UiTool::land: title = "MODO TERRENO"; description = "SELECIONE UM TERRENO VIZINHO"; break;
            case UiTool::remove: title = "MODO DEMOLIR"; description = "CLIQUE EM PREDIO, CALCADA OU ESTRADA"; break;
            case UiTool::agriculture: title = "MODO AGRICULTURA"; description = "PREPARE O SOLO OU PLANTE UMA CULTURA"; break;
            case UiTool::decoration: title = "MODO DECORACAO"; description = "EM BREVE"; break;
            case UiTool::none: break;
        }
        draw_text_fit(renderer, context_x + 6.0F, toolbar.y + 11.0F, context_width - 12.0F, title, 219, 232, 238);
        draw_text_fit(renderer, context_x + 6.0F, toolbar.y + 27.0F, context_width - 12.0F, description, 162, 187, 199);
    }
    if (!panels_.empty()) {
        const UiRect& hud = panels_.front();
        const float controls_width = 154.0F;
        const float available_width = std::max(360.0F, hud.width - controls_width - 24.0F);
        const float block_width = available_width / 4.0F;
        const float block_x = hud.x + 16.0F;
        draw_hud_stat(renderer, block_x, HudIcon::coins, "FUNDOS", model_.funds);
        draw_hud_stat(renderer, block_x + block_width, HudIcon::calendar, "DATA",
                      model_.day_month.empty() ? model_.date : model_.day_month, model_.year);
        draw_hud_stat(renderer, block_x + block_width * 2.0F, HudIcon::people, "POPULACAO",
                      model_.population + " / " + model_.residential_capacity);
        draw_hud_stat(renderer, block_x + block_width * 3.0F, HudIcon::energy, "ENERGIA",
                      model_.power_demand + " / " + model_.power_capacity);
        draw_ui_icon("funds", {block_x - 1.0F, 28.0F, 22.0F, 24.0F});
        draw_ui_icon("calendar", {block_x + block_width - 1.0F, 28.0F, 22.0F, 24.0F});
        draw_ui_icon("population", {block_x + block_width * 2.0F - 1.0F, 28.0F, 22.0F, 24.0F});
        draw_ui_icon("energy", {block_x + block_width * 3.0F - 1.0F, 28.0F, 22.0F, 24.0F});
        SDL_SetRenderDrawColor(renderer, 55, 91, 111, SDL_ALPHA_OPAQUE);
        for (int separator = 1; separator < 4; ++separator) {
            const float separator_x = block_x + block_width * static_cast<float>(separator) - 12.0F;
            SDL_RenderLine(renderer, separator_x, hud.y + 12.0F, separator_x, hud.y + hud.height - 12.0F);
        }
    }

    if (build_panel_bounds_) {
        const UiRect& panel = *build_panel_bounds_;
        draw_text(renderer, panel.x + 12.0F, panel.y + 12.0F, model_.farming_panel_open ? "AGRICULTURA" : "CONSTRUCOES", 232, 240, 244);
        if (model_.farming_panel_open) {
            draw_text_fit(renderer, panel.x + 12.0F, panel.y + 27.0F, panel.width - 24.0F,
                          model_.farming_infrastructure, 151, 178, 192);
            draw_text_fit(renderer, panel.x + 12.0F, panel.y + 42.0F, panel.width - 24.0F,
                          model_.farming_stock + " | " + model_.farming_tile_status, 151, 178, 192);
        } else {
            draw_text(renderer, panel.x + 12.0F, panel.y + 27.0F,
                      std::to_string(model_.build_items.size()) + " ITENS", 151, 178, 192);
        }
        SDL_SetRenderDrawColor(renderer, 55, 91, 111, SDL_ALPHA_OPAQUE);
        const float separator_y = panel.y + (model_.farming_panel_open ? 55.0F : 38.0F);
        SDL_RenderLine(renderer, panel.x + 8.0F, separator_y, panel.x + panel.width - 8.0F, separator_y);
        if (build_scroll_max_ > 0.0F) {
            const float track_y = panel.y + (model_.farming_panel_open ? 63.0F : 45.0F);
            const float track_height = panel.height - (model_.farming_panel_open ? 70.0F : 52.0F);
            const float visible_height = panel.height - (model_.farming_panel_open ? 68.0F : 50.0F);
            const float content_height = visible_height + build_scroll_max_;
            const float thumb_height = std::max(20.0F, track_height * visible_height / content_height);
            const float thumb_y = track_y + (track_height - thumb_height) * (build_scroll_offset_ / build_scroll_max_);
            const SDL_FRect track = {panel.x + panel.width - 7.0F, track_y, 3.0F, track_height};
            const SDL_FRect thumb = {panel.x + panel.width - 8.0F, thumb_y, 5.0F, thumb_height};
            SDL_SetRenderDrawColor(renderer, 35, 68, 85, SDL_ALPHA_OPAQUE);
            SDL_RenderFillRect(renderer, &track);
            SDL_SetRenderDrawColor(renderer, 113, 163, 185, SDL_ALPHA_OPAQUE);
            SDL_RenderFillRect(renderer, &thumb);
        }
    }
    if (model_.land_details && model_.active_tool == UiTool::land) {
        draw_text(renderer, 22.0F, 94.0F, "PARCEL " + model_.land_details->parcel_id + " | " + model_.land_details->state);
        draw_text(renderer, 22.0F, 112.0F, "PRICE " + model_.land_details->price);
    }
    if (model_.selected_building) {
        const UiSelectedBuilding& item = *model_.selected_building;
        float panel_x = 0.0F;
        for (const UiRect& panel : panels_) {
            if (panel.width == 330.0F && panel.y == 84.0F) {
                panel_x = panel.x;
                break;
            }
        }
        const SDL_FRect preview = {panel_x + 12.0F, 116.0F, 78.0F, 68.0F};
        SDL_SetRenderDrawColor(renderer, 13, 34, 47, SDL_ALPHA_OPAQUE);
        SDL_RenderFillRect(renderer, &preview);
        if (const UiThumbnail* thumbnail = thumbnail_for(renderer, item.thumbnail_path)) {
            const float scale = std::min(preview.w / thumbnail->width, preview.h / thumbnail->height);
            const SDL_FRect destination = {preview.x + (preview.w - thumbnail->width * scale) * 0.5F,
                                           preview.y + (preview.h - thumbnail->height * scale) * 0.5F,
                                           thumbnail->width * scale, thumbnail->height * scale};
            SDL_RenderTexture(renderer, thumbnail->texture, nullptr, &destination);
        } else {
            SDL_SetRenderDrawColor(renderer, 74, 112, 127, SDL_ALPHA_OPAQUE);
            SDL_RenderRect(renderer, &preview);
        }
        draw_text_fit(renderer, panel_x + 102.0F, 96.0F, 212.0F, item.name, 236, 244, 248);
        draw_text_fit(renderer, panel_x + 102.0F, 113.0F, 212.0F, item.category, 164, 193, 205);
        draw_text_fit(renderer, panel_x + 102.0F, 133.0F, 212.0F, "CUSTO: " + item.cost, 214, 230, 236);
        draw_text_fit(renderer, panel_x + 102.0F, 151.0F, 212.0F, "ROTACAO: " + item.rotation, 164, 193, 205);

        float detail_y = 198.0F;
        const auto detail = [&](const std::string& label, const std::string& value) {
            if (value.empty()) {
                return;
            }
            detail_y += 17.0F * static_cast<float>(draw_text_wrapped(renderer, panel_x + 12.0F, detail_y, 306.0F,
                                                                       label + ": " + value, 202, 219, 227));
        };
        detail("ACESSO A RUA", item.road_access_requirement + " / " + item.road_access);
        detail("CONSUMO ENERGIA", item.energy_consumption);
        detail("PRODUCAO ENERGIA", item.energy_production);
        if (!item.residential_capacity.empty()) {
            detail("CAPACIDADE RESIDENCIAL", item.residential_capacity);
            detail("IPTU ANUAL", item.property_tax_per_year);
        }
        if (!item.commercial_demand.empty()) {
            detail("RECEITA BASE", item.monthly_tax + "/MES");
            detail("DEMANDA", item.commercial_demand);
            detail("RECEITA ESTIMADA", item.commercial_current_revenue + "/MES");
            detail("MANUTENCAO", item.monthly_maintenance + "/MES");
        }
        detail("ABASTECIMENTO LOCAL", item.local_supply);
    }
    if (!model_.status.empty()) {
        const UiRect* toast = nullptr;
        for (const UiRect& panel : panels_) {
            if (panel.y == 84.0F && panel.height == 28.0F) {
                toast = &panel;
            }
        }
        if (toast != nullptr) {
            draw_text_fit(renderer, toast->x + 10.0F, 94.0F, toast->width - 20.0F, model_.status);
        }
    }
    if (model_.debug_visible) {
        float line_y = 130.0F;
        for (const std::string& line : model_.debug_lines) {
            draw_text(renderer, 22.0F, line_y, line);
            line_y += 18.0F;
        }
    }
    for (const UiButton& button : buttons_) {
        if (button.build_card) {
            render_build_card(renderer, button);
        } else {
            if (!draw_chrome_button(button)) {
                if (draw_state_atlas_button(button)) {
                    draw_button_content(renderer, button);
                } else {
                    draw_button(renderer, button);
                }
            }
        }
    }
    for (const UiButton& button : buttons_) {
        if (button.build_card) {
            continue;
        }
        if (chrome_name_for(button.action) != nullptr) {
            continue;
        }
        if (button.action == UiAction::close_selection || button.action == UiAction::close_modal) {
            // The atlas cell already contains the X glyph.
            continue;
        }
        if (const char* icon_name = icon_name_for(button.action)) {
            const bool primary_tool = is_primary_tool_action(button.action);
            const SDL_FRect icon_bounds = primary_tool
                ? SDL_FRect{button.bounds.x + 9.0F, button.bounds.y + 5.0F, 26.0F, 25.0F}
                : (button.action == UiAction::close_selection
                    ? SDL_FRect{button.bounds.x + 2.0F, button.bounds.y + 2.0F, 14.0F, 14.0F}
                    : SDL_FRect{button.bounds.x + 5.0F, button.bounds.y + 5.0F, 22.0F, 22.0F});
            draw_ui_icon(icon_name, icon_bounds);
        }
    }

    if (model_.overlay != UiOverlay::none && overlay_bounds_) {
        const SDL_FRect screen = {0.0F, 0.0F, static_cast<float>(viewport_width_), static_cast<float>(viewport_height_)};
        SDL_SetRenderDrawColor(renderer, 1, 9, 14, 178);
        SDL_RenderFillRect(renderer, &screen);

        const UiRect& panel = *overlay_bounds_;
        const SDL_FRect destination = {panel.x, panel.y, panel.width, panel.height};
        if (const UiThumbnail* artwork = thumbnail_for(renderer, ui_overlay_path(model_.overlay))) {
            SDL_RenderTexture(renderer, artwork->texture, nullptr, &destination);
        } else {
            // Keep the game usable if an asset is missing in a development
            // build; the state and controls still exist rather than failing
            // silently behind a black screen.
            draw_panel(renderer, panel);
            draw_text(renderer, panel.x + 24.0F, panel.y + 24.0F, "UI ARTWORK NOT FOUND", 255, 160, 130);
        }

        const float scale = panel.width / 1280.0F;
        const auto text_at = [&](const float x, const float y, const std::string& value, const Uint8 r = 232,
                                 const Uint8 g = 244, const Uint8 b = 248) {
            draw_text_fit(renderer, panel.x + x * scale, panel.y + y * scale, 210.0F * scale, value, r, g, b);
        };
        if (model_.overlay == UiOverlay::administration || model_.overlay == UiOverlay::reports) {
            text_at(520.0F, 338.0F, model_.monthly_revenue, 112, 238, 135);
            text_at(520.0F, 405.0F, model_.monthly_expenses, 255, 139, 139);
            text_at(520.0F, 470.0F, model_.monthly_balance, 122, 225, 250);
            text_at(900.0F, 340.0F, model_.population + " / " + model_.residential_capacity);
            text_at(92.0F, 650.0F, model_.power_demand + " / " + model_.power_capacity);
            text_at(330.0F, 852.0F, model_.administration_alerts, 188, 215, 228);
        } else {
            text_at(1080.0F, 316.0F, std::to_string(model_.master_volume_percent) + "%");
            text_at(1080.0F, 351.0F, std::to_string(model_.effects_volume_percent) + "%");
        }
    }
}

const std::vector<UiButton>& GameplayUi::buttons() const {
    return buttons_;
}

const std::vector<UiRect>& GameplayUi::panels() const {
    return panels_;
}

void GameplayUi::add_button(UiRect bounds, std::string label, UiAction action, bool enabled, bool active, std::string payload) {
    UiButton button;
    button.bounds = bounds;
    button.label = std::move(label);
    button.action = action;
    button.payload = std::move(payload);
    button.enabled = enabled;
    button.active = active;
    buttons_.push_back(std::move(button));
}

void GameplayUi::add_build_card(UiRect bounds, const UiBuildItem& item, bool active, UiAction action) {
    UiButton card;
    card.bounds = bounds;
    card.label = item.name;
    card.action = action;
    card.payload = item.definition_id;
    card.enabled = item.enabled;
    card.active = active;
    card.detail = item.category + "  |  " + item.build_cost + "  |  " + item.footprint;
    card.requirements = item.requirements;
    card.thumbnail_path = item.thumbnail_path;
    card.build_card = true;
    buttons_.push_back(std::move(card));
}

void GameplayUi::add_panel(UiRect bounds) {
    panels_.push_back(bounds);
}

const GameplayUi::UiThumbnail* GameplayUi::thumbnail_for(SDL_Renderer* renderer, const std::string& path) const {
    if (path.empty()) {
        return nullptr;
    }
    if (const auto found = thumbnails_.find(path); found != thumbnails_.end()) {
        return found->second.texture == nullptr ? nullptr : &found->second;
    }

    UiThumbnail thumbnail;
    SDL_Surface* surface = SDL_LoadPNG(path.c_str());
    if (surface != nullptr) {
        thumbnail.width = static_cast<float>(surface->w);
        thumbnail.height = static_cast<float>(surface->h);
        thumbnail.texture = SDL_CreateTextureFromSurface(renderer, surface);
        SDL_DestroySurface(surface);
        if (thumbnail.texture != nullptr) {
            SDL_SetTextureBlendMode(thumbnail.texture, SDL_BLENDMODE_BLEND);
            SDL_SetTextureScaleMode(thumbnail.texture, SDL_SCALEMODE_LINEAR);
        }
    }
    return thumbnails_.emplace(path, thumbnail).first->second.texture == nullptr ? nullptr :
           &thumbnails_.find(path)->second;
}

void GameplayUi::render_build_card(SDL_Renderer* renderer, const UiButton& button) const {
    Uint8 red = 25;
    Uint8 green = 56;
    Uint8 blue = 73;
    if (!button.enabled) {
        red = 32; green = 40; blue = 46;
    } else if (button.state == UiButtonState::pressed || button.active) {
        red = 28; green = 104; blue = 131;
    } else if (button.state == UiButtonState::hover) {
        red = 37; green = 78; blue = 99;
    }
    const SDL_FRect card = {button.bounds.x, button.bounds.y, button.bounds.width, button.bounds.height};
    SDL_SetRenderDrawColor(renderer, red, green, blue, SDL_ALPHA_OPAQUE);
    SDL_RenderFillRect(renderer, &card);
    SDL_SetRenderDrawColor(renderer, button.active ? 112 : 74, button.active ? 192 : 125,
                           button.active ? 218 : 148, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &card);

    const SDL_FRect preview = {button.bounds.x + 7.0F, button.bounds.y + 7.0F, 82.0F, 82.0F};
    SDL_SetRenderDrawColor(renderer, 13, 34, 47, SDL_ALPHA_OPAQUE);
    SDL_RenderFillRect(renderer, &preview);
        if (const UiThumbnail* thumbnail = thumbnail_for(renderer, button.thumbnail_path)) {
        const float scale = std::min(preview.w / thumbnail->width, preview.h / thumbnail->height);
        const SDL_FRect destination = {preview.x + (preview.w - thumbnail->width * scale) * 0.5F,
                                       preview.y + (preview.h - thumbnail->height * scale) * 0.5F,
                                       thumbnail->width * scale, thumbnail->height * scale};
        SDL_RenderTexture(renderer, thumbnail->texture, nullptr, &destination);
        } else {
            SDL_SetRenderDrawColor(renderer, 74, 112, 127, SDL_ALPHA_OPAQUE);
            SDL_RenderRect(renderer, &preview);
            if (button.thumbnail_path.empty()) {
                draw_text(renderer, preview.x + 25.0F, preview.y + 22.0F, "$", 182, 210, 111);
            }
        }
    const float text_x = button.bounds.x + 101.0F;
    const float text_width = button.bounds.width - 109.0F;
    draw_text_fit(renderer, text_x, button.bounds.y + 10.0F, text_width, button.label,
                  button.enabled ? 236 : 142, button.enabled ? 244 : 149, button.enabled ? 246 : 154);
    draw_text_fit(renderer, text_x, button.bounds.y + 28.0F, text_width, button.detail,
                  button.enabled ? 165 : 113, button.enabled ? 193 : 126, button.enabled ? 204 : 135);
    draw_text_fit(renderer, text_x, button.bounds.y + 46.0F, text_width, button.requirements,
                  button.enabled ? 177 : 122, button.enabled ? 207 : 135, button.enabled ? 215 : 143);
    if (button.active) {
        draw_text(renderer, text_x, button.bounds.y + 66.0F, "SELECIONADO", 173, 231, 245);
    } else if (!button.enabled) {
        draw_text(renderer, text_x, button.bounds.y + 66.0F, "INDISPONIVEL", 205, 144, 135);
    }
}

UiButtonState GameplayUi::state_for(const UiButton& button, float mouse_x, float mouse_y, bool pressed) {
    if (!button.enabled) {
        return UiButtonState::disabled;
    }
    if (!button.bounds.contains(mouse_x, mouse_y)) {
        return UiButtonState::normal;
    }
    return pressed ? UiButtonState::pressed : UiButtonState::hover;
}
