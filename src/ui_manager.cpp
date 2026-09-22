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

struct BuildingColorSwatch {
    Uint8 r;
    Uint8 g;
    Uint8 b;
};

constexpr std::array<BuildingColorSwatch, 7> kBuildingColorPalette = {{
    {226, 202, 160},  // warm cream
    {190, 112, 81},   // brick
    {203, 163, 91},   // ochre
    {119, 151, 116},  // sage
    {105, 143, 172},  // blue
    {172, 119, 131},  // rose
    {122, 132, 139},  // slate
}};

std::string color_payload(const BuildingColorSwatch swatch) {
    return std::to_string(static_cast<int>(swatch.r)) + ":" +
           std::to_string(static_cast<int>(swatch.g)) + ":" +
           std::to_string(static_cast<int>(swatch.b));
}

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

void draw_text_fit(SDL_Renderer* renderer, float x, float y, float available_width, const std::string& text,
                   Uint8 red = 238, Uint8 green = 244, Uint8 blue = 238) {
    std::string printable = ascii_debug_text(text);
    const std::size_t maximum_characters = static_cast<std::size_t>(std::max(0.0F, available_width) / 8.0F);
    if (maximum_characters == 0) return;
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

void draw_text_centered(SDL_Renderer* renderer, const UiRect& bounds, float y, const std::string& text,
                        Uint8 red = 238, Uint8 green = 244, Uint8 blue = 238) {
    const std::string printable = ascii_debug_text(text);
    const float text_width = static_cast<float>(printable.size()) * 8.0F;
    draw_text(renderer, bounds.x + std::max(0.0F, (bounds.width - text_width) * 0.5F), y,
              printable, red, green, blue);
}

void draw_text_centered_fit(SDL_Renderer* renderer, const UiRect& bounds, float y, const std::string& text,
                            Uint8 red = 238, Uint8 green = 244, Uint8 blue = 238) {
    std::string printable = ascii_debug_text(text);
    const float usable_width = std::max(0.0F, bounds.width - 10.0F);
    const std::size_t maximum_characters = static_cast<std::size_t>(usable_width / 8.0F);
    if (maximum_characters == 0) return;
    if (printable.size() > maximum_characters) {
        if (maximum_characters <= 3) printable.resize(maximum_characters);
        else {
            printable.resize(maximum_characters - 3);
            printable += "...";
        }
    }
    const float text_width = static_cast<float>(printable.size()) * 8.0F;
    draw_text(renderer, bounds.x + std::max(5.0F, (bounds.width - text_width) * 0.5F), y,
              printable, red, green, blue);
}

std::vector<std::string> wrap_debug_text(const std::string& text, const float available_width) {
    const std::size_t maximum_characters = static_cast<std::size_t>(std::max(0.0F, available_width) / 8.0F);
    if (maximum_characters == 0 || text.empty()) return {};
    std::string remaining = ascii_debug_text(text);
    std::vector<std::string> lines;
    while (!remaining.empty()) {
        while (!remaining.empty() && std::isspace(static_cast<unsigned char>(remaining.front())) != 0) remaining.erase(remaining.begin());
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
    const SDL_FRect shadow = {bounds.x + 3.0F, bounds.y + 4.0F, bounds.width, bounds.height};
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 74);
    SDL_RenderFillRect(renderer, &shadow);
    const SDL_FRect rect = {bounds.x, bounds.y, bounds.width, bounds.height};
    SDL_SetRenderDrawColor(renderer, 12, 32, 46, 248);
    SDL_RenderFillRect(renderer, &rect);
    SDL_SetRenderDrawColor(renderer, 63, 105, 128, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &rect);
    SDL_SetRenderDrawColor(renderer, 78, 174, 199, SDL_ALPHA_OPAQUE);
    SDL_RenderLine(renderer, bounds.x + 2.0F, bounds.y + 2.0F,
                   bounds.x + bounds.width - 2.0F, bounds.y + 2.0F);
}

void draw_pause_panel(SDL_Renderer* renderer, const UiRect& bounds) {
    const SDL_FRect shadow = {bounds.x + 8.0F, bounds.y + 10.0F, bounds.width, bounds.height};
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 92);
    SDL_RenderFillRect(renderer, &shadow);

    const SDL_FRect rect = {bounds.x, bounds.y, bounds.width, bounds.height};
    SDL_SetRenderDrawColor(renderer, 15, 33, 45, 248);
    SDL_RenderFillRect(renderer, &rect);
    SDL_SetRenderDrawColor(renderer, 70, 119, 145, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &rect);

    SDL_SetRenderDrawColor(renderer, 91, 188, 211, SDL_ALPHA_OPAQUE);
    SDL_RenderLine(renderer, bounds.x + 2.0F, bounds.y + 3.0F,
                   bounds.x + bounds.width - 2.0F, bounds.y + 3.0F);
}

void draw_color_swatch_button(SDL_Renderer* renderer, const UiButton& button) {
    const SDL_FRect shadow = {button.bounds.x + 2.0F, button.bounds.y + 2.0F, button.bounds.width, button.bounds.height};
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 70);
    SDL_RenderFillRect(renderer, &shadow);
    const SDL_FRect rect = {button.bounds.x, button.bounds.y, button.bounds.width, button.bounds.height};
    SDL_SetRenderDrawColor(renderer, button.swatch_r, button.swatch_g, button.swatch_b, SDL_ALPHA_OPAQUE);
    SDL_RenderFillRect(renderer, &rect);
    if (button.active) SDL_SetRenderDrawColor(renderer, 238, 246, 249, SDL_ALPHA_OPAQUE);
    else if (button.state == UiButtonState::hover || button.state == UiButtonState::pressed)
        SDL_SetRenderDrawColor(renderer, 91, 188, 211, SDL_ALPHA_OPAQUE);
    else SDL_SetRenderDrawColor(renderer, 54, 78, 90, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &rect);
    if (button.active) {
        const SDL_FRect inner = {rect.x + 2.0F, rect.y + 2.0F, rect.w - 4.0F, rect.h - 4.0F};
        SDL_RenderRect(renderer, &inner);
    }
}

void draw_pause_button(SDL_Renderer* renderer, const UiButton& button) {
    Uint8 red = 31;
    Uint8 green = 43;
    Uint8 blue = 50;
    Uint8 border_red = 52;
    Uint8 border_green = 66;
    Uint8 border_blue = 74;
    Uint8 text_red = 105;
    Uint8 text_green = 121;
    Uint8 text_blue = 129;

    if (button.enabled) {
        red = 27;
        green = 83;
        blue = 105;
        border_red = 77;
        border_green = 154;
        border_blue = 178;
        text_red = 238;
        text_green = 246;
        text_blue = 249;
        if (button.state == UiButtonState::hover) {
            red = 33;
            green = 101;
            blue = 125;
            border_red = 91;
            border_green = 188;
            border_blue = 211;
        } else if (button.state == UiButtonState::pressed) {
            red = 22;
            green = 68;
            blue = 87;
        }
    }

    const SDL_FRect rect = {button.bounds.x, button.bounds.y, button.bounds.width, button.bounds.height};
    SDL_SetRenderDrawColor(renderer, red, green, blue, SDL_ALPHA_OPAQUE);
    SDL_RenderFillRect(renderer, &rect);
    SDL_SetRenderDrawColor(renderer, border_red, border_green, border_blue, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &rect);
    if (button.enabled) {
        SDL_SetRenderDrawColor(renderer, 151, 229, 240, 92);
        SDL_RenderLine(renderer, button.bounds.x + 2.0F, button.bounds.y + 2.0F,
                       button.bounds.x + button.bounds.width - 2.0F, button.bounds.y + 2.0F);
    }
    draw_text_centered(renderer, button.bounds, button.bounds.y + std::max(8.0F, (button.bounds.height - 8.0F) * 0.5F),
                       button.label, text_red, text_green, text_blue);
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

std::string ui_service_icon_path(const char* icon_name) {
    const char* base_path = SDL_GetBasePath();
    const std::filesystem::path root = base_path == nullptr ? std::filesystem::path(".") : std::filesystem::path(base_path);
    return (root / "assets" / "ui" / "icons" / "service" / (std::string(icon_name) + ".png")).string();
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

enum class UiAtlasButtonFamily : std::uint8_t { blue_wide, green_wide, red_wide, blue_compact, blue_circle };

[[nodiscard]] UiAtlasButtonFamily atlas_family_for(const UiButton& button) {
    const float aspect = button.bounds.height > 0.0F ? button.bounds.width / button.bounds.height : 1.0F;
    if (aspect < 1.35F) return UiAtlasButtonFamily::blue_circle;
    if (button.action == UiAction::settings_apply || button.action == UiAction::upgrade_building) return UiAtlasButtonFamily::green_wide;
    if (button.action == UiAction::settings_cancel || button.action == UiAction::activate_remove) return UiAtlasButtonFamily::red_wide;
    return aspect < 2.7F ? UiAtlasButtonFamily::blue_compact : UiAtlasButtonFamily::blue_wide;
}

[[nodiscard]] SDL_FRect atlas_source_for(const UiButton& button) {
    const UiButtonState state = !button.enabled ? UiButtonState::disabled : (button.active ? UiButtonState::pressed : button.state);
    const int column = state == UiButtonState::hover ? 1 : state == UiButtonState::pressed ? 2 : state == UiButtonState::disabled ? 3 : 0;
    switch (atlas_family_for(button)) {
        case UiAtlasButtonFamily::blue_wide: return {20.0F + 354.0F * static_cast<float>(column), 90.0F, 354.0F, 140.0F};
        case UiAtlasButtonFamily::green_wide: return {20.0F + 354.0F * static_cast<float>(column), 383.0F, 354.0F, 142.0F};
        case UiAtlasButtonFamily::red_wide: return {20.0F + 354.0F * static_cast<float>(column), 535.0F, 354.0F, 142.0F};
        case UiAtlasButtonFamily::blue_compact: return {35.0F + 350.0F * static_cast<float>(column), 688.0F, 330.0F, 114.0F};
        case UiAtlasButtonFamily::blue_circle: return {92.0F + 346.0F * static_cast<float>(column), 810.0F, 224.0F, 228.0F};
    }
    return {};
}

[[nodiscard]] SDL_FRect goals_close_source_for(const UiButtonState state) {
    const int column = state == UiButtonState::hover ? 1 : state == UiButtonState::pressed ? 2 : state == UiButtonState::disabled ? 3 : 0;
    static constexpr std::array<float, 4> kLeft = {704.0F, 837.0F, 985.0F, 1137.0F};
    return {kLeft[static_cast<std::size_t>(column)], 61.0F, 68.0F, 68.0F};
}

[[nodiscard]] SDL_FRect goals_back_source_for(const UiButtonState state) {
    const int column = state == UiButtonState::hover ? 1 : state == UiButtonState::pressed ? 2 : state == UiButtonState::disabled ? 3 : 0;
    return {666.0F + 150.0F * static_cast<float>(column), 197.0F, 146.0F, 59.0F};
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
        for (int row = 0; row < 2; ++row) for (int column = 0; column < 2; ++column) {
            const SDL_FRect tile = {x + static_cast<float>(column) * 10.0F, y + static_cast<float>(row) * 10.0F, 8.0F, 8.0F};
            SDL_RenderRect(renderer, &tile);
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
    SDL_SetRenderDrawColor(renderer, icon == HudIcon::energy ? 247 : 224, icon == HudIcon::energy ? 197 : 225,
                           icon == HudIcon::energy ? 66 : 229, SDL_ALPHA_OPAQUE);
    if (icon == HudIcon::coins) {
        for (int row = 0; row < 3; ++row) {
            const SDL_FRect coin = {x + static_cast<float>(row % 2) * 2.0F, y + static_cast<float>(row) * 6.0F, 16.0F, 4.0F};
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
        SDL_RenderFillRect(renderer, &head_a); SDL_RenderFillRect(renderer, &head_b);
        SDL_RenderFillRect(renderer, &body_a); SDL_RenderFillRect(renderer, &body_b);
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
    if (!secondary.empty()) draw_text(renderer, x + 27.0F, 53.0F, secondary, 159, 180, 192);
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
    if (is_primary_tool_action(button.action)) {
        const float icon_x = button.bounds.x + std::max(4.0F, (button.bounds.width - 22.0F) * 0.5F);
        draw_tool_icon(renderer, icon_x, button.bounds.y + 5.0F, button.action);
        draw_text_centered_fit(renderer, button.bounds, button.bounds.y + button.bounds.height - 15.0F,
                               button.label, button.enabled ? 236 : 128, button.enabled ? 244 : 137,
                               button.enabled ? 248 : 144);
        return;
    }
    if (button.action == UiAction::none && button.payload.rfind("build_category:", 0) == 0) {
        draw_text_centered_fit(renderer, button.bounds, button.bounds.y + 11.0F, button.label,
                               button.enabled ? 225 : 128, button.enabled ? 238 : 137,
                               button.enabled ? 244 : 144);
        return;
    }
    const bool icon_text_control = button.action == UiAction::toggle_pause || button.action == UiAction::rotate_left || button.action == UiAction::rotate_right;
    const float label_x = icon_text_control ? 36.0F : 8.0F;
    draw_text(renderer, button.bounds.x + label_x, button.bounds.y + 13.0F, button.label,
              button.enabled ? 238 : 135, button.enabled ? 244 : 140, button.enabled ? 238 : 145);
}

void draw_button(SDL_Renderer* renderer, const UiButton& button) {
    const bool primary_tool = is_primary_tool_action(button.action);
    const bool category_tab = button.action == UiAction::none && button.payload.rfind("build_category:", 0) == 0;
    if (primary_tool || category_tab) {
        Uint8 red = category_tab ? 19 : 16;
        Uint8 green = category_tab ? 48 : 45;
        Uint8 blue = category_tab ? 64 : 62;
        Uint8 border_red = 55, border_green = 98, border_blue = 120;
        if (!button.enabled) {
            red = 31; green = 39; blue = 44;
            border_red = 55; border_green = 63; border_blue = 68;
        } else if (button.state == UiButtonState::pressed || button.active) {
            red = 22; green = 78; blue = 99;
            border_red = 91; border_green = 188; border_blue = 211;
        } else if (button.state == UiButtonState::hover) {
            red = 22; green = 61; blue = 78;
            border_red = 77; border_green = 143; border_blue = 168;
        }
        const SDL_FRect rect = {button.bounds.x, button.bounds.y, button.bounds.width, button.bounds.height};
        SDL_SetRenderDrawColor(renderer, red, green, blue, SDL_ALPHA_OPAQUE);
        SDL_RenderFillRect(renderer, &rect);
        SDL_SetRenderDrawColor(renderer, border_red, border_green, border_blue, SDL_ALPHA_OPAQUE);
        SDL_RenderRect(renderer, &rect);
        if (button.active && button.enabled) {
            SDL_SetRenderDrawColor(renderer, 104, 211, 231, SDL_ALPHA_OPAQUE);
            SDL_RenderLine(renderer, button.bounds.x + 3.0F, button.bounds.y + button.bounds.height - 3.0F,
                           button.bounds.x + button.bounds.width - 3.0F, button.bounds.y + button.bounds.height - 3.0F);
        }
        draw_button_content(renderer, button);
        return;
    }

    const bool hud_control = button.action == UiAction::toggle_pause || button.action == UiAction::open_administration || button.action == UiAction::open_settings;
    Uint8 red = hud_control ? 23 : 52, green = hud_control ? 78 : 80, blue = hud_control ? 109 : 66;
    if (!button.enabled) { red = 42; green = 47; blue = 48; }
    else if (button.state == UiButtonState::pressed) { red = hud_control ? 31 : 70; green = hud_control ? 108 : 126; blue = hud_control ? 142 : 91; }
    else if (button.state == UiButtonState::hover) { red = 73; green = 112; blue = 88; }
    else if (button.active) { red = hud_control ? 28 : 63; green = hud_control ? 113 : 137; blue = hud_control ? 145 : 95; }
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
    const UiOverlay previous_overlay = model_.overlay;
    const bool entering_settings = model.overlay == UiOverlay::settings && previous_overlay != UiOverlay::settings;
    const bool entering_build_panel = model.build_panel_open && !model_.build_panel_open;
    model_ = model;
    if (entering_build_panel) {
        build_category_filter_ = "TODOS";
        build_scroll_offset_ = 0.0F;
    }
    viewport_width_ = std::max(viewport_width, 1);
    viewport_height_ = std::max(viewport_height, 1);
    buttons_.clear(); panels_.clear(); build_panel_bounds_.reset(); overlay_bounds_.reset();
    settings_master_slider_bounds_.reset();
    settings_effects_slider_bounds_.reset();
    if (entering_settings) {
        settings_draft_master_percent_ = std::clamp(model.master_volume_percent, 0, 100);
        settings_draft_effects_percent_ = std::clamp(model.effects_volume_percent, 0, 100);
        settings_drag_target_ = SettingsDragTarget::none;
    } else if (model.overlay != UiOverlay::settings) {
        settings_drag_target_ = SettingsDragTarget::none;
    }

    const float width = static_cast<float>(viewport_width_);
    const float height = static_cast<float>(viewport_height_);
    add_panel({kMargin, kMargin, std::max(100.0F, width - kMargin * 2.0F), kTopBarHeight});

    const float settings_x = std::max(kMargin + 270.0F, width - 50.0F);
    const float administration_x = std::max(kMargin + 120.0F, settings_x - 112.0F);
    const float pause_x = std::max(kMargin, administration_x - 124.0F);
    add_button({pause_x, 28.0F, 114.0F, kButtonHeight}, model.paused ? "PLAY" : "PAUSE", UiAction::toggle_pause, true, model.paused);
    add_button({administration_x, 28.0F, 102.0F, kButtonHeight}, "ADMIN", UiAction::open_administration);
    add_button({settings_x, 28.0F, 30.0F, kButtonHeight}, "SET", UiAction::open_settings);

    const float toolbar_y = height - kToolbarHeight - kMargin;
    const float toolbar_width = std::max(100.0F, width - kMargin * 2.0F);
    const float context_width = std::clamp(toolbar_width * 0.25F, 190.0F, 330.0F);
    const float context_x = kMargin + toolbar_width - context_width;
    const float tools_width = std::max(1.0F, toolbar_width - context_width - 8.0F);
    const float tool_width = tools_width / 7.0F;
    add_panel({kMargin, toolbar_y, toolbar_width, kToolbarHeight});
    const float tool_y = toolbar_y + 11.0F;
    constexpr float tool_height = 52.0F;
    add_button({kMargin + 4.0F + tool_width * 0.0F, tool_y, tool_width - 6.0F, tool_height}, "CONSTRUCOES", UiAction::open_build_panel, true, model.active_tool == UiTool::buildings);
    add_button({kMargin + 4.0F + tool_width * 1.0F, tool_y, tool_width - 6.0F, tool_height}, "ESTRADAS", UiAction::activate_roads, true, model.active_tool == UiTool::roads);
    add_button({kMargin + 4.0F + tool_width * 2.0F, tool_y, tool_width - 6.0F, tool_height}, "PISO", UiAction::activate_sidewalks, true, model.active_tool == UiTool::sidewalks);
    add_button({kMargin + 4.0F + tool_width * 3.0F, tool_y, tool_width - 6.0F, tool_height}, "TERRENO", UiAction::activate_land, true, model.active_tool == UiTool::land);
    add_button({kMargin + 4.0F + tool_width * 4.0F, tool_y, tool_width - 6.0F, tool_height}, "DEMOLIR", UiAction::activate_remove, true, model.active_tool == UiTool::remove);
    add_button({kMargin + 4.0F + tool_width * 5.0F, tool_y, tool_width - 6.0F, tool_height}, "AGRICULTURA", UiAction::open_agriculture_panel, true, model.active_tool == UiTool::agriculture);
    add_button({kMargin + 4.0F + tool_width * 6.0F, tool_y, tool_width - 6.0F, tool_height}, "DECORACAO", UiAction::activate_decoration, true, model.active_tool == UiTool::decoration);

    if (model.placement_rotatable && model.active_tool == UiTool::buildings) {
        constexpr float rotation_gap = 6.0F;
        const float rotation_width = std::max(72.0F, (context_width - 18.0F - rotation_gap) * 0.5F);
        const float rotation_y = toolbar_y + 39.0F;
        add_button({context_x + 6.0F, rotation_y, rotation_width, 28.0F}, "ESQ", UiAction::rotate_left);
        add_button({context_x + 12.0F + rotation_width, rotation_y, rotation_width, 28.0F}, "DIR", UiAction::rotate_right);
    }

    if (model.build_panel_open) {
        const float maximum_panel_width = std::max(320.0F, width - kMargin * 2.0F);
        const float panel_width = std::min(maximum_panel_width, std::clamp(width * 0.62F, 480.0F, 760.0F));
        const float panel_y = 84.0F;
        const float panel_height = std::max(180.0F, toolbar_y - panel_y - 8.0F);
        const UiRect panel_bounds = {kMargin, panel_y, panel_width, panel_height};
        add_panel(panel_bounds);
        build_panel_bounds_ = panel_bounds;

        std::vector<std::string> categories;
        for (const UiBuildItem& item : model.build_items) {
            if (std::find(categories.begin(), categories.end(), item.category) == categories.end()) categories.push_back(item.category);
        }
        if (build_category_filter_ != "TODOS" &&
            std::find(categories.begin(), categories.end(), build_category_filter_) == categories.end()) {
            build_category_filter_ = "TODOS";
            build_scroll_offset_ = 0.0F;
        }

        constexpr float tab_gap = 6.0F;
        constexpr float tab_height = 30.0F;
        constexpr float desired_tab_width = 138.0F;
        const float tabs_available_width = panel_width - 16.0F;
        const int tabs_per_row = std::max(1, static_cast<int>((tabs_available_width + tab_gap) / (desired_tab_width + tab_gap)));
        const std::size_t tab_count = categories.size() + 1U;
        const int tab_rows = std::max(1, static_cast<int>((tab_count + static_cast<std::size_t>(tabs_per_row) - 1U) /
                                                          static_cast<std::size_t>(tabs_per_row)));
        const float tab_width = (tabs_available_width - tab_gap * static_cast<float>(tabs_per_row - 1)) /
                                static_cast<float>(tabs_per_row);
        const float tabs_y = panel_y + 45.0F;
        build_panel_header_height_ = 51.0F + static_cast<float>(tab_rows) * (tab_height + tab_gap);

        std::vector<std::string> tab_labels;
        tab_labels.push_back("TODOS");
        tab_labels.insert(tab_labels.end(), categories.begin(), categories.end());
        for (std::size_t index = 0; index < tab_labels.size(); ++index) {
            const int row = static_cast<int>(index) / tabs_per_row;
            const int column = static_cast<int>(index) % tabs_per_row;
            const std::string& category = tab_labels[index];
            add_button({panel_bounds.x + 8.0F + static_cast<float>(column) * (tab_width + tab_gap),
                        tabs_y + static_cast<float>(row) * (tab_height + tab_gap), tab_width, tab_height},
                       category, UiAction::none, true, category == build_category_filter_, "build_category:" + category);
        }

        std::vector<const UiBuildItem*> filtered_items;
        for (const UiBuildItem& item : model.build_items) {
            if (build_category_filter_ == "TODOS" || item.category == build_category_filter_) filtered_items.push_back(&item);
        }

        constexpr float card_height = 108.0F;
        constexpr float card_gap = 8.0F;
        constexpr float horizontal_padding = 8.0F;
        const int columns = panel_width >= 620.0F ? 2 : 1;
        const float scrollbar_reserve = 8.0F;
        const float cards_width = panel_width - horizontal_padding * 2.0F - scrollbar_reserve;
        const float card_width = (cards_width - card_gap * static_cast<float>(columns - 1)) / static_cast<float>(columns);
        const float content_top = panel_y + build_panel_header_height_;
        const float visible_height = std::max(1.0F, panel_height - build_panel_header_height_ - 8.0F);
        const std::size_t row_count = (filtered_items.size() + static_cast<std::size_t>(columns) - 1U) /
                                      static_cast<std::size_t>(columns);
        const float content_height = static_cast<float>(row_count) * (card_height + card_gap);
        build_scroll_max_ = std::max(0.0F, content_height - visible_height);
        build_scroll_offset_ = std::clamp(build_scroll_offset_, 0.0F, build_scroll_max_);

        for (std::size_t index = 0; index < filtered_items.size(); ++index) {
            const int row = static_cast<int>(index / static_cast<std::size_t>(columns));
            const int column = static_cast<int>(index % static_cast<std::size_t>(columns));
            const float card_x = panel_bounds.x + horizontal_padding + static_cast<float>(column) * (card_width + card_gap);
            const float card_y = content_top + static_cast<float>(row) * (card_height + card_gap) - build_scroll_offset_;
            const UiRect card_bounds = {card_x, card_y, card_width, card_height};
            if (card_bounds.y >= content_top && card_bounds.y + card_bounds.height <= panel_bounds.y + panel_bounds.height - 6.0F) {
                const UiBuildItem& item = *filtered_items[index];
                add_build_card(card_bounds, item, item.definition_id == model.selected_building_id, UiAction::select_building);
            }
        }
    } else if (model.farming_panel_open || model.active_tool == UiTool::decoration) {
        constexpr float panel_width = 410.0F;
        const float header_height = model.farming_panel_open ? 60.0F : 42.0F;
        build_panel_header_height_ = header_height;
        constexpr float card_height = 96.0F;
        constexpr float card_gap = 6.0F;
        const float panel_y = 84.0F;
        const float panel_height = std::max(120.0F, toolbar_y - panel_y - 8.0F);
        const UiRect panel_bounds = {kMargin, panel_y, panel_width, panel_height};
        add_panel(panel_bounds);
        build_panel_bounds_ = panel_bounds;
        const float visible_height = panel_height - header_height - 8.0F;
        const std::vector<UiBuildItem>& panel_items = model.farming_panel_open ? model.farming_items : model.decor_items;
        const UiAction panel_action = model.farming_panel_open ? UiAction::select_farming_item : UiAction::select_building;
        const std::string& panel_selected_id = model.farming_panel_open ? model.selected_farming_id : model.selected_building_id;
        const float content_height = static_cast<float>(panel_items.size()) * (card_height + card_gap);
        build_scroll_max_ = std::max(0.0F, content_height - visible_height);
        build_scroll_offset_ = std::clamp(build_scroll_offset_, 0.0F, build_scroll_max_);
        float item_y = panel_y + header_height - build_scroll_offset_;
        for (const UiBuildItem& item : panel_items) {
            const UiRect card_bounds = {panel_bounds.x + 8.0F, item_y, panel_bounds.width - 16.0F, card_height};
            if (card_bounds.y >= panel_bounds.y + header_height && card_bounds.y + card_bounds.height <= panel_bounds.y + panel_bounds.height - 6.0F)
                add_build_card(card_bounds, item, item.definition_id == panel_selected_id, panel_action);
            item_y += card_height + card_gap;
        }
    } else {
        build_scroll_offset_ = 0.0F;
        build_scroll_max_ = 0.0F;
        build_panel_header_height_ = 42.0F;
    }

    if (model.land_details && model.active_tool == UiTool::land) add_panel({kMargin, 84.0F, 300.0F, 62.0F});

    if (model.selected_building) {
        const float panel_width = 330.0F;
        const float panel_y = 84.0F;
        const float panel_x = width - panel_width - kMargin;
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
        for (const std::string& detail : details) if (!detail.empty()) detail_lines += wrap_debug_text(detail, 306.0F).size();
        const float service_height = item.has_service_pricing ? 218.0F : 0.0F;
        const float color_height = item.has_color_customization ? 122.0F : 0.0F;
        const float required_height = 126.0F + service_height + color_height + static_cast<float>(detail_lines) * 17.0F;
        const float maximum_height = std::max(120.0F, toolbar_y - 92.0F);
        const float panel_height = std::min(maximum_height, std::max(308.0F, required_height));
        add_panel({panel_x, panel_y, panel_width, panel_height});
        add_button({width - 38.0F, 92.0F, 18.0F, 18.0F}, "X", UiAction::close_selection);
        if (item.has_service_pricing) {
            add_button({panel_x + 194.0F, panel_y + 143.0F, 34.0F, 30.0F}, "-",
                       UiAction::decrease_service_price, item.can_decrease_service_price);
            add_button({panel_x + 282.0F, panel_y + 143.0F, 34.0F, 30.0F}, "+",
                       UiAction::increase_service_price, item.can_increase_service_price);
        }
        if (item.has_color_customization) {
            const float color_top = panel_y + panel_height - 116.0F;
            constexpr float swatch_size = 26.0F;
            constexpr float swatch_gap = 5.0F;
            const auto add_palette_row = [&](const float y, const UiAction action, const bool customized,
                                             const int current_r, const int current_g, const int current_b) {
                for (std::size_t index = 0; index < kBuildingColorPalette.size(); ++index) {
                    const BuildingColorSwatch swatch = kBuildingColorPalette[index];
                    const bool active = customized && current_r == swatch.r && current_g == swatch.g && current_b == swatch.b;
                    add_button({panel_x + 96.0F + static_cast<float>(index) * (swatch_size + swatch_gap), y, swatch_size, swatch_size},
                               "", action, true, active, color_payload(swatch));
                    UiButton& button = buttons_.back();
                    button.color_swatch = true;
                    button.swatch_r = swatch.r; button.swatch_g = swatch.g; button.swatch_b = swatch.b;
                }
            };
            add_palette_row(color_top + 21.0F, UiAction::set_wall_color, item.wall_color_customized,
                            item.wall_tint_r, item.wall_tint_g, item.wall_tint_b);
            add_palette_row(color_top + 53.0F, UiAction::set_roof_color, item.roof_color_customized,
                            item.roof_tint_r, item.roof_tint_g, item.roof_tint_b);
            add_button({panel_x + 216.0F, color_top + 84.0F, 100.0F, 24.0F}, "ORIGINAL",
                       UiAction::reset_building_colors, item.wall_color_customized || item.roof_color_customized);
        }
    }

    if (!model.status.empty()) {
        const float left_edge = build_panel_bounds_ ? build_panel_bounds_->x + build_panel_bounds_->width + 8.0F : kMargin;
        const float right_edge = model.selected_building ? width - 354.0F : width - kMargin;
        const float available_width = std::max(180.0F, right_edge - left_edge);
        const float toast_width = std::min(440.0F, available_width);
        add_panel({left_edge + (available_width - toast_width) * 0.5F, 84.0F, toast_width, 28.0F});
    }
    if (model.debug_visible) {
        const float debug_height = 18.0F + static_cast<float>(model.debug_lines.size()) * 18.0F;
        add_panel({kMargin, 120.0F, 460.0F, debug_height});
    }

    if (model.overlay == UiOverlay::pause) {
        const float panel_width = std::min(520.0F, std::max(320.0F, width - 48.0F));
        const float panel_height = std::min(570.0F, std::max(460.0F, height - 48.0F));
        const UiRect panel = {(width - panel_width) * 0.5F, (height - panel_height) * 0.5F, panel_width, panel_height};
        overlay_bounds_ = panel;
        const float horizontal_padding = std::clamp(panel.width * 0.065F, 22.0F, 34.0F);
        const float button_width = panel.width - horizontal_padding * 2.0F;
        const float button_gap = 9.0F;
        const float button_top = panel.y + 118.0F;
        const float footer_reserve = 48.0F;
        const float button_height = std::clamp((panel.height - (button_top - panel.y) - footer_reserve - button_gap * 5.0F) / 6.0F, 42.0F, 52.0F);
        const float button_x = panel.x + horizontal_padding;
        const auto pause_button = [&](int index, const char* label, UiAction action, bool enabled) {
            add_button({button_x, button_top + static_cast<float>(index) * (button_height + button_gap), button_width, button_height}, label, action, enabled);
        };
        pause_button(0, "CONTINUAR", UiAction::resume_game, true);
        pause_button(1, "SALVAR JOGO", UiAction::open_save_load, true);
        pause_button(2, "CARREGAR JOGO", UiAction::open_save_load, true);
        pause_button(3, "CONFIGURACOES", UiAction::open_settings, true);
        pause_button(4, "MENU PRINCIPAL", UiAction::open_main_menu, true);
        pause_button(5, "SAIR DO JOGO", UiAction::open_quit_confirm, true);
    } else if (model.overlay == UiOverlay::main_menu) {
        const float panel_width = std::min(560.0F, std::max(340.0F, width - 48.0F));
        const float panel_height = std::min(520.0F, std::max(430.0F, height - 64.0F));
        const UiRect panel = {(width - panel_width) * 0.5F, (height - panel_height) * 0.5F, panel_width, panel_height};
        overlay_bounds_ = panel;
        const float padding = std::clamp(panel.width * 0.065F, 22.0F, 36.0F);
        const float button_width = panel.width - padding * 2.0F;
        const float button_top = panel.y + 190.0F;
        const float button_gap = 10.0F;
        const float button_height = 48.0F;
        if (model.startup_main_menu) {
            add_button({panel.x + padding, button_top, button_width, button_height}, "NOVA CIDADE", UiAction::start_new_city);
            add_button({panel.x + padding, button_top + (button_height + button_gap), button_width, button_height},
                       "CONTINUAR CIDADE", UiAction::continue_saved_city, model.save_available);
        } else {
            add_button({panel.x + padding, button_top, button_width, button_height}, "CONTINUAR CIDADE", UiAction::resume_game);
            add_button({panel.x + padding, button_top + (button_height + button_gap), button_width, button_height},
                       "SALVAR / CARREGAR", UiAction::open_save_load);
        }
        add_button({panel.x + padding, button_top + (button_height + button_gap) * 2.0F, button_width, button_height}, "CONFIGURACOES", UiAction::open_settings);
        add_button({panel.x + padding, button_top + (button_height + button_gap) * 3.0F, button_width, button_height}, "SAIR DO JOGO", UiAction::open_quit_confirm);
    } else if (model.overlay == UiOverlay::quit_confirm) {
        const float panel_width = std::min(500.0F, std::max(340.0F, width - 48.0F));
        const float panel_height = std::min(300.0F, std::max(260.0F, height - 96.0F));
        const UiRect panel = {(width - panel_width) * 0.5F, (height - panel_height) * 0.5F, panel_width, panel_height};
        overlay_bounds_ = panel;
        const float padding = std::clamp(panel.width * 0.07F, 24.0F, 36.0F);
        const float gap = 12.0F;
        const float button_width = (panel.width - padding * 2.0F - gap) * 0.5F;
        const float button_y = panel.y + panel.height - 70.0F;
        add_button({panel.x + padding, button_y, button_width, 44.0F}, "CANCELAR", UiAction::cancel_quit);
        add_button({panel.x + padding + button_width + gap, button_y, button_width, 44.0F}, "SAIR", UiAction::quit_game);
    } else if (model.overlay == UiOverlay::save_load) {
        const float panel_width = std::min(620.0F, std::max(360.0F, width - 48.0F));
        const float panel_height = std::min(440.0F, std::max(370.0F, height - 64.0F));
        const UiRect panel = {(width - panel_width) * 0.5F, (height - panel_height) * 0.5F, panel_width, panel_height};
        overlay_bounds_ = panel;
        const float horizontal_padding = std::clamp(panel.width * 0.06F, 22.0F, 36.0F);
        const float button_gap = 12.0F;
        const float button_y = panel.y + panel.height - 70.0F;
        const float available = panel.width - horizontal_padding * 2.0F - button_gap * 2.0F;
        const float button_width = available / 3.0F;
        add_button({panel.x + horizontal_padding, button_y, button_width, 42.0F}, "SALVAR AGORA", UiAction::save_game);
        add_button({panel.x + horizontal_padding + button_width + button_gap, button_y, button_width, 42.0F}, "CARREGAR", UiAction::load_game, model.save_available);
        add_button({panel.x + horizontal_padding + (button_width + button_gap) * 2.0F, button_y, button_width, 42.0F}, "VOLTAR", UiAction::back_from_save_load);
    } else if (model.overlay == UiOverlay::settings) {
        const float panel_width = std::min(620.0F, std::max(360.0F, width - 48.0F));
        const float panel_height = std::min(470.0F, std::max(390.0F, height - 64.0F));
        const UiRect panel = {(width - panel_width) * 0.5F, (height - panel_height) * 0.5F, panel_width, panel_height};
        overlay_bounds_ = panel;
        const float meter_x = panel.x + std::clamp(panel.width * 0.10F, 28.0F, 54.0F);
        const float meter_width = panel.width - (meter_x - panel.x) * 2.0F;
        settings_master_slider_bounds_ = UiRect{meter_x, panel.y + 157.0F, meter_width, 20.0F};
        settings_effects_slider_bounds_ = UiRect{meter_x, panel.y + 235.0F, meter_width, 20.0F};
        const float horizontal_padding = std::clamp(panel.width * 0.06F, 22.0F, 36.0F);
        const float button_gap = 12.0F;
        const float button_y = panel.y + panel.height - 72.0F;
        const float available = panel.width - horizontal_padding * 2.0F - button_gap * 2.0F;
        const float button_width = available / 3.0F;
        add_button({panel.x + horizontal_padding, button_y, button_width, 42.0F}, "PADRAO", UiAction::settings_reset);
        add_button({panel.x + horizontal_padding + button_width + button_gap, button_y, button_width, 42.0F}, "CANCELAR", UiAction::settings_cancel);
        add_button({panel.x + horizontal_padding + (button_width + button_gap) * 2.0F, button_y, button_width, 42.0F}, "APLICAR", UiAction::settings_apply);
    } else if (model.overlay == UiOverlay::administration) {
        const float panel_width = std::min(760.0F, std::max(420.0F, width - 48.0F));
        const float panel_height = std::min(560.0F, std::max(430.0F, height - 64.0F));
        const UiRect panel = {(width - panel_width) * 0.5F, (height - panel_height) * 0.5F, panel_width, panel_height};
        overlay_bounds_ = panel;
        const float padding = std::clamp(panel.width * 0.055F, 24.0F, 40.0F);
        const float button_gap = 12.0F;
        const float button_width = (panel.width - padding * 2.0F - button_gap) * 0.5F;
        const float button_y = panel.y + panel.height - 70.0F;
        add_button({panel.x + padding, button_y, button_width, 42.0F}, "RELATORIOS", UiAction::open_reports);
        add_button({panel.x + padding + button_width + button_gap, button_y, button_width, 42.0F}, "FECHAR", UiAction::close_modal);
    } else if (model.overlay == UiOverlay::reports) {
        const float panel_width = std::min(760.0F, std::max(420.0F, width - 48.0F));
        const float panel_height = std::min(560.0F, std::max(430.0F, height - 64.0F));
        const UiRect panel = {(width - panel_width) * 0.5F, (height - panel_height) * 0.5F, panel_width, panel_height};
        overlay_bounds_ = panel;
        const float padding = std::clamp(panel.width * 0.055F, 24.0F, 40.0F);
        const float button_gap = 12.0F;
        const float button_width = (panel.width - padding * 2.0F - button_gap) * 0.5F;
        const float button_y = panel.y + panel.height - 70.0F;
        add_button({panel.x + padding, button_y, button_width, 42.0F}, "VOLTAR", UiAction::open_administration);
        add_button({panel.x + padding + button_width + button_gap, button_y, button_width, 42.0F}, "FECHAR", UiAction::close_modal);
    }

    handle_mouse_motion(mouse_x_, mouse_y_);
}

void GameplayUi::handle_mouse_motion(float mouse_x, float mouse_y) {
    mouse_x_ = mouse_x; mouse_y_ = mouse_y;
    if (primary_pressed_ && settings_drag_target_ != SettingsDragTarget::none) {
        update_settings_draft_from_pointer(settings_drag_target_, mouse_x_);
    }
    for (UiButton& button : buttons_) button.state = state_for(button, mouse_x_, mouse_y_, primary_pressed_);
}

bool GameplayUi::handle_mouse_wheel(float mouse_x, float mouse_y, float wheel_y) {
    if (model_.overlay != UiOverlay::none) return true;
    if (!build_panel_bounds_ || !build_panel_bounds_->contains(mouse_x, mouse_y) || build_scroll_max_ <= 0.0F) return false;
    build_scroll_offset_ = std::clamp(build_scroll_offset_ - wheel_y * 48.0F, 0.0F, build_scroll_max_);
    update_layout(viewport_width_, viewport_height_, model_);
    return true;
}

void GameplayUi::release_renderer_resources() {
    for (const auto& [path, thumbnail] : thumbnails_) { (void)path; if (thumbnail.texture != nullptr) SDL_DestroyTexture(thumbnail.texture); }
    thumbnails_.clear();
}

UiInputResult GameplayUi::handle_mouse_button_down(float mouse_x, float mouse_y, bool primary_button) {
    handle_mouse_motion(mouse_x, mouse_y);
    UiInputResult result; result.consumed = consumes_point(mouse_x, mouse_y);
    if (!result.consumed || !primary_button) return result;
    primary_pressed_ = true;
    if (model_.overlay == UiOverlay::settings) {
        if (settings_master_slider_bounds_ && settings_master_slider_bounds_->contains(mouse_x, mouse_y)) {
            settings_drag_target_ = SettingsDragTarget::master;
            update_settings_draft_from_pointer(settings_drag_target_, mouse_x);
            return result;
        }
        if (settings_effects_slider_bounds_ && settings_effects_slider_bounds_->contains(mouse_x, mouse_y)) {
            settings_drag_target_ = SettingsDragTarget::effects;
            update_settings_draft_from_pointer(settings_drag_target_, mouse_x);
            return result;
        }
    }
    for (auto it = buttons_.rbegin(); it != buttons_.rend(); ++it) {
        UiButton& button = *it;
        button.state = state_for(button, mouse_x_, mouse_y_, true);
        if (!button.bounds.contains(mouse_x, mouse_y)) continue;
        if (button.enabled) {
            if (button.action == UiAction::none && button.payload.rfind("build_category:", 0) == 0) {
                build_category_filter_ = button.payload.substr(std::string("build_category:").size());
                build_scroll_offset_ = 0.0F;
                update_layout(viewport_width_, viewport_height_, model_);
                return result;
            }
            if (button.action == UiAction::settings_reset) {
                settings_draft_master_percent_ = 100;
                settings_draft_effects_percent_ = 100;
            }
            std::string payload = button.payload;
            if (button.action == UiAction::settings_apply) {
                payload = std::to_string(settings_draft_master_percent_) + ":" +
                          std::to_string(settings_draft_effects_percent_);
            }
            result.action = UiActionEvent{button.action, std::move(payload)};
        }
        break;
    }
    return result;
}

void GameplayUi::handle_mouse_button_up(float mouse_x, float mouse_y) {
    primary_pressed_ = false;
    settings_drag_target_ = SettingsDragTarget::none;
    handle_mouse_motion(mouse_x, mouse_y);
}

bool GameplayUi::consumes_point(float mouse_x, float mouse_y) const {
    if (model_.overlay != UiOverlay::none) return true;
    return std::any_of(panels_.begin(), panels_.end(), [mouse_x, mouse_y](const UiRect& panel) { return panel.contains(mouse_x, mouse_y); });
}

void GameplayUi::render(SDL_Renderer* renderer) const {
    if (renderer == nullptr) return;
    const auto draw_ui_icon = [&](const char* name, const SDL_FRect& bounds) {
        if (const UiThumbnail* icon = thumbnail_for(renderer, ui_icon_path(name))) {
            const float scale = std::min(bounds.w / icon->width, bounds.h / icon->height);
            const SDL_FRect destination = {bounds.x + (bounds.w - icon->width * scale) * 0.5F, bounds.y + (bounds.h - icon->height * scale) * 0.5F, icon->width * scale, icon->height * scale};
            SDL_RenderTexture(renderer, icon->texture, nullptr, &destination);
        }
    };
    const auto draw_service_icon = [&](const char* name, const SDL_FRect& bounds) {
        if (const UiThumbnail* icon = thumbnail_for(renderer, ui_service_icon_path(name))) {
            const float scale = std::min(bounds.w / icon->width, bounds.h / icon->height);
            const SDL_FRect destination = {bounds.x + (bounds.w - icon->width * scale) * 0.5F,
                                           bounds.y + (bounds.h - icon->height * scale) * 0.5F,
                                           icon->width * scale, icon->height * scale};
            SDL_RenderTexture(renderer, icon->texture, nullptr, &destination);
        }
    };
    const auto draw_chrome_button = [&](const UiButton& button) -> bool {
        if (is_primary_tool_action(button.action)) return false;
        const char* chrome_name = chrome_name_for(button.action);
        if (chrome_name == nullptr) return false;
        const UiThumbnail* chrome = thumbnail_for(renderer, ui_chrome_path(chrome_name));
        if (chrome == nullptr) return false;
        const SDL_FRect destination = {button.bounds.x, button.bounds.y, button.bounds.width, button.bounds.height};
        SDL_RenderTexture(renderer, chrome->texture, nullptr, &destination);
        if (!button.enabled) { SDL_SetRenderDrawColor(renderer, 7, 13, 18, 150); SDL_RenderFillRect(renderer, &destination); }
        else if (button.active || button.state == UiButtonState::pressed) { SDL_SetRenderDrawColor(renderer, 60, 222, 255, 58); SDL_RenderFillRect(renderer, &destination); }
        else if (button.state == UiButtonState::hover) { SDL_SetRenderDrawColor(renderer, 176, 244, 255, 36); SDL_RenderFillRect(renderer, &destination); }
        return true;
    };
    const auto draw_state_atlas_button = [&](const UiButton& button) -> bool {
        if (button.build_card || is_primary_tool_action(button.action) ||
            (button.action == UiAction::none && button.payload.rfind("build_category:", 0) == 0)) return false;
        const UiButtonState state = !button.enabled ? UiButtonState::disabled : (button.active ? UiButtonState::pressed : button.state);
        const bool is_close = button.action == UiAction::close_modal || button.action == UiAction::close_selection;
        const bool is_back = button.action == UiAction::open_administration && model_.overlay == UiOverlay::reports;
        const UiThumbnail* atlas = thumbnail_for(renderer, is_close || is_back ? ui_goals_controls_atlas_path() : ui_button_state_atlas_path());
        if (atlas == nullptr) return false;
        const SDL_FRect source = is_close ? goals_close_source_for(state) : is_back ? goals_back_source_for(state) : atlas_source_for(button);
        const SDL_FRect destination = {button.bounds.x, button.bounds.y, button.bounds.width, button.bounds.height};
        SDL_RenderTexture(renderer, atlas->texture, &source, &destination);
        return true;
    };

    for (std::size_t index = 0; index < panels_.size(); ++index) {
        if (index == 0) draw_hud_panel(renderer, panels_[index]);
        else if (index == 1) draw_toolbar_panel(renderer, panels_[index]);
        else draw_panel(renderer, panels_[index]);
    }
    if (panels_.size() > 1) {
        const UiRect& toolbar = panels_[1];
        const float context_width = std::clamp(toolbar.width * 0.25F, 190.0F, 330.0F);
        const float context_x = toolbar.x + toolbar.width - context_width;
        SDL_SetRenderDrawColor(renderer, 55, 91, 111, SDL_ALPHA_OPAQUE);
        SDL_RenderLine(renderer, context_x - 8.0F, toolbar.y + 7.0F, context_x - 8.0F, toolbar.y + toolbar.height - 7.0F);
        std::string title = "SELECIONE UMA FERRAMENTA";
        std::string description = "ESCOLHA UMA CATEGORIA ABAIXO";
        switch (model_.active_tool) {
            case UiTool::buildings:
                title = "MODO CONSTRUCOES";
                description = model_.placement_rotatable ? "ROTACIONE COM Z/X OU OS BOTOES" :
                    (model_.build_panel_open ? "SELECIONE UM ITEM PARA POSICIONAR" : "ESCOLHA UMA CONSTRUCAO");
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
        draw_hud_stat(renderer, block_x + block_width, HudIcon::calendar, "DATA", model_.day_month.empty() ? model_.date : model_.day_month, model_.year);
        draw_hud_stat(renderer, block_x + block_width * 2.0F, HudIcon::people, "POPULACAO", model_.population + " / " + model_.residential_capacity);
        draw_hud_stat(renderer, block_x + block_width * 3.0F, HudIcon::energy, "ENERGIA", model_.power_demand + " / " + model_.power_capacity);
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
        if (model_.build_panel_open) {
            std::size_t filtered_count = 0;
            for (const UiBuildItem& item : model_.build_items) {
                if (build_category_filter_ == "TODOS" || item.category == build_category_filter_) ++filtered_count;
            }
            draw_text(renderer, panel.x + 12.0F, panel.y + 10.0F, "CATALOGO DE CONSTRUCAO", 232, 240, 244);
            draw_text_fit(renderer, panel.x + 12.0F, panel.y + 26.0F, panel.width - 24.0F,
                          std::to_string(filtered_count) + " DE " + std::to_string(model_.build_items.size()) +
                          " ITENS  |  " + build_category_filter_, 151, 178, 192);
            SDL_SetRenderDrawColor(renderer, 55, 91, 111, SDL_ALPHA_OPAQUE);
            const float separator_y = panel.y + build_panel_header_height_ - 5.0F;
            SDL_RenderLine(renderer, panel.x + 8.0F, separator_y, panel.x + panel.width - 8.0F, separator_y);
        } else {
            const bool farming = model_.farming_panel_open;
            draw_text(renderer, panel.x + 12.0F, panel.y + 12.0F, farming ? "AGRICULTURA" : "DECORACAO", 232, 240, 244);
            if (farming) {
                draw_text_fit(renderer, panel.x + 12.0F, panel.y + 27.0F, panel.width - 24.0F, model_.farming_infrastructure, 151, 178, 192);
                draw_text_fit(renderer, panel.x + 12.0F, panel.y + 42.0F, panel.width - 24.0F,
                              model_.farming_stock + " | " + model_.farming_tile_status, 151, 178, 192);
            } else {
                draw_text(renderer, panel.x + 12.0F, panel.y + 27.0F,
                          std::to_string(model_.decor_items.size()) + " ITENS", 151, 178, 192);
            }
            SDL_SetRenderDrawColor(renderer, 55, 91, 111, SDL_ALPHA_OPAQUE);
            const float separator_y = panel.y + build_panel_header_height_ - 4.0F;
            SDL_RenderLine(renderer, panel.x + 8.0F, separator_y, panel.x + panel.width - 8.0F, separator_y);
        }
        if (build_scroll_max_ > 0.0F) {
            const float track_y = panel.y + build_panel_header_height_;
            const float track_height = std::max(20.0F, panel.height - build_panel_header_height_ - 8.0F);
            const float visible_height = track_height;
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
        float panel_height = 0.0F;
        for (const UiRect& panel : panels_) if (panel.width == 330.0F && panel.y == 84.0F) {
            panel_x = panel.x; panel_height = panel.height; break;
        }
        const SDL_FRect preview = {panel_x + 12.0F, 116.0F, 78.0F, 68.0F};
        SDL_SetRenderDrawColor(renderer, 13, 34, 47, SDL_ALPHA_OPAQUE); SDL_RenderFillRect(renderer, &preview);
        if (const UiThumbnail* thumbnail = thumbnail_for(renderer, item.thumbnail_path)) {
            const float scale = std::min(preview.w / thumbnail->width, preview.h / thumbnail->height);
            const SDL_FRect destination = {preview.x + (preview.w - thumbnail->width * scale) * 0.5F, preview.y + (preview.h - thumbnail->height * scale) * 0.5F, thumbnail->width * scale, thumbnail->height * scale};
            SDL_RenderTexture(renderer, thumbnail->texture, nullptr, &destination);
        } else { SDL_SetRenderDrawColor(renderer, 74, 112, 127, SDL_ALPHA_OPAQUE); SDL_RenderRect(renderer, &preview); }
        draw_text_fit(renderer, panel_x + 102.0F, 96.0F, 212.0F, item.name, 236, 244, 248);
        draw_text_fit(renderer, panel_x + 102.0F, 113.0F, 212.0F, item.category, 164, 193, 205);
        draw_text_fit(renderer, panel_x + 102.0F, 133.0F, 212.0F, "CUSTO: " + item.cost, 214, 230, 236);
        draw_text_fit(renderer, panel_x + 102.0F, 151.0F, 212.0F, "ROTACAO: " + item.rotation, 164, 193, 205);

        float detail_y = 198.0F;
        if (item.has_service_pricing) {
            const SDL_FRect service_card = {panel_x + 10.0F, 192.0F, 310.0F, 216.0F};
            SDL_SetRenderDrawColor(renderer, 12, 35, 48, 244);
            SDL_RenderFillRect(renderer, &service_card);
            SDL_SetRenderDrawColor(renderer, 55, 91, 111, SDL_ALPHA_OPAQUE);
            SDL_RenderRect(renderer, &service_card);

            draw_service_icon("bakery_products", {panel_x + 16.0F, 198.0F, 48.0F, 48.0F});
            draw_text_fit(renderer, panel_x + 72.0F, 199.0F, 238.0F, "VENDE: " + item.service_name, 236, 223, 184);

            draw_service_icon("service_price", {panel_x + 72.0F, 218.0F, 18.0F, 18.0F});
            draw_text_fit(renderer, panel_x + 94.0F, 222.0F, 126.0F, "PRECO AO CLIENTE", 164, 193, 205);
            draw_text_centered_fit(renderer, {panel_x + 232.0F, 227.0F, 46.0F, 24.0F}, 235.0F, item.service_price,
                                   238, 246, 249);
            draw_text_fit(renderer, panel_x + 72.0F, 258.0F, 238.0F, item.service_price_range, 118, 151, 166);

            const auto service_metric = [&](const char* icon_name, const float y, const std::string& label,
                                            const std::string& value, const Uint8 red, const Uint8 green,
                                            const Uint8 blue) {
                draw_service_icon(icon_name, {panel_x + 18.0F, y - 3.0F, 18.0F, 18.0F});
                draw_text_fit(renderer, panel_x + 42.0F, y, 268.0F, label + ": " + value, red, green, blue);
            };

            service_metric("service_demand", 280.0F, "DEMANDA", item.service_price_demand, 202, 219, 227);
            service_metric("service_customers", 301.0F, "CLIENTES / MES", item.service_customers_per_month, 202, 219, 227);
            service_metric("service_stock", 322.0F, "INSUMOS", item.service_supply_status,
                           item.service_supply_status.find("100%") != std::string::npos ? 181 : 255,
                           item.service_supply_status.find("100%") != std::string::npos ? 221 : 188,
                           item.service_supply_status.find("100%") != std::string::npos ? 154 : 128);
            service_metric("service_revenue", 343.0F, "RECEITA VENDAS", item.service_revenue_per_month, 181, 221, 154);
            service_metric("service_profit", 364.0F, "RESULTADO", item.service_net_per_month, 137, 226, 242);
            service_metric("service_maintenance", 385.0F, "MANUTENCAO", item.monthly_maintenance + "/MES", 202, 219, 227);
            detail_y = 418.0F;
        }
        const auto detail = [&](const std::string& label, const std::string& value) {
            if (value.empty()) return;
            detail_y += 17.0F * static_cast<float>(draw_text_wrapped(renderer, panel_x + 12.0F, detail_y, 306.0F, label + ": " + value, 202, 219, 227));
        };
        detail("ACESSO A RUA", item.road_access_requirement + " / " + item.road_access);
        detail("CONSUMO ENERGIA", item.energy_consumption); detail("PRODUCAO ENERGIA", item.energy_production);
        if (!item.residential_capacity.empty()) { detail("CAPACIDADE RESIDENCIAL", item.residential_capacity); detail("IPTU ANUAL", item.property_tax_per_year); }
        if (!item.commercial_demand.empty()) {
            detail("RECEITA BASE", item.monthly_tax + "/MES"); detail("DEMANDA", item.commercial_demand);
            detail("RECEITA ESTIMADA", item.commercial_current_revenue + "/MES"); detail("MANUTENCAO", item.monthly_maintenance + "/MES");
        }
        detail("ABASTECIMENTO LOCAL", item.local_supply);
        if (item.has_color_customization) {
            const float color_top = 84.0F + panel_height - 116.0F;
            SDL_SetRenderDrawColor(renderer, 55, 91, 111, SDL_ALPHA_OPAQUE);
            SDL_RenderLine(renderer, panel_x + 12.0F, color_top + 5.0F, panel_x + 316.0F, color_top + 5.0F);
            draw_text(renderer, panel_x + 12.0F, color_top + 28.0F, "PAREDE", 164, 193, 205);
            draw_text(renderer, panel_x + 12.0F, color_top + 60.0F, "TELHADO", 164, 193, 205);
            draw_text(renderer, panel_x + 12.0F, color_top + 91.0F,
                      item.wall_color_customized || item.roof_color_customized ? "CORES PERSONALIZADAS" : "CORES ORIGINAIS",
                      118, 151, 166);
        }
    }

    if (!model_.status.empty()) {
        const UiRect* toast = nullptr;
        for (const UiRect& panel : panels_) if (panel.y == 84.0F && panel.height == 28.0F) toast = &panel;
        if (toast != nullptr) draw_text_fit(renderer, toast->x + 10.0F, 94.0F, toast->width - 20.0F, model_.status);
    }
    if (model_.debug_visible) {
        float line_y = 130.0F;
        for (const std::string& line : model_.debug_lines) { draw_text(renderer, 22.0F, line_y, line); line_y += 18.0F; }
    }

    // Gameplay controls render normally. Modal controls are redrawn after the
    // dimmer/panel below so they remain visible and interactive.
    for (const UiButton& button : buttons_) {
        if (button.build_card) render_build_card(renderer, button);
        else if (button.color_swatch) draw_color_swatch_button(renderer, button);
        else if (!draw_chrome_button(button)) {
            if (draw_state_atlas_button(button)) draw_button_content(renderer, button);
            else draw_button(renderer, button);
        }
    }
    for (const UiButton& button : buttons_) {
        if (button.build_card) continue;
        if (button.action == UiAction::close_selection || button.action == UiAction::close_modal) continue;
        if (const char* icon_name = icon_name_for(button.action)) {
            const bool primary_tool = is_primary_tool_action(button.action);
            const SDL_FRect icon_bounds = primary_tool
                ? SDL_FRect{button.bounds.x + std::max(4.0F, (button.bounds.width - 30.0F) * 0.5F), button.bounds.y + 4.0F, 30.0F, 27.0F}
                : SDL_FRect{button.bounds.x + 5.0F, button.bounds.y + 5.0F, 22.0F, 22.0F};
            draw_ui_icon(icon_name, icon_bounds);
        }
    }

    if (model_.overlay != UiOverlay::none && overlay_bounds_) {
        const SDL_FRect screen = {0.0F, 0.0F, static_cast<float>(viewport_width_), static_cast<float>(viewport_height_)};
        SDL_SetRenderDrawColor(renderer, 1, 9, 14, 178); SDL_RenderFillRect(renderer, &screen);
        const UiRect& panel = *overlay_bounds_;

        if (model_.overlay == UiOverlay::pause) {
            draw_pause_panel(renderer, panel);
            draw_text_centered(renderer, panel, panel.y + 39.0F, "JOGO PAUSADO", 238, 246, 249);
            draw_text_centered(renderer, panel, panel.y + 70.0F, "CITY HORIZON", 158, 186, 199);
            draw_text_centered(renderer, panel, panel.y + 88.0F, "SESSAO ATUAL PRESERVADA", 118, 151, 166);
            for (const UiButton& button : buttons_) {
                if (button.bounds.x >= panel.x && button.bounds.x + button.bounds.width <= panel.x + panel.width &&
                    button.bounds.y >= panel.y + 100.0F && button.bounds.y + button.bounds.height <= panel.y + panel.height) {
                    draw_pause_button(renderer, button);
                }
            }
            draw_text_centered(renderer, panel, panel.y + panel.height - 25.0F, "ESC  -  CONTINUAR", 158, 186, 199);
            return;
        }

        if (model_.overlay == UiOverlay::main_menu) {
            draw_pause_panel(renderer, panel);
            draw_text_centered(renderer, panel, panel.y + 38.0F, "CITY HORIZON", 238, 246, 249);
            draw_text_centered(renderer, panel, panel.y + 68.0F, "MENU PRINCIPAL", 158, 186, 199);

            const float info_x = panel.x + std::clamp(panel.width * 0.08F, 28.0F, 44.0F);
            const float info_width = panel.width - (info_x - panel.x) * 2.0F;
            const SDL_FRect info = {info_x, panel.y + 98.0F, info_width, 68.0F};
            SDL_SetRenderDrawColor(renderer, 20, 44, 59, 252);
            SDL_RenderFillRect(renderer, &info);
            SDL_SetRenderDrawColor(renderer, 64, 103, 123, SDL_ALPHA_OPAQUE);
            SDL_RenderRect(renderer, &info);
            if (model_.startup_main_menu) {
                draw_text(renderer, info.x + 14.0F, info.y + 12.0F, "BEM-VINDO", 158, 186, 199);
                draw_text_fit(renderer, info.x + 14.0F, info.y + 33.0F, info.w - 28.0F,
                              "ESCOLHA COMO COMECAR SUA CIDADE", 219, 232, 238);
                draw_text_fit(renderer, info.x + 14.0F, info.y + 50.0F, info.w - 28.0F,
                              model_.save_available ? "SAVE EXISTENTE DETECTADO" : "NENHUM SAVE EXISTENTE",
                              158, 186, 199);
            } else {
                draw_text(renderer, info.x + 14.0F, info.y + 12.0F, "CIDADE ATUAL", 158, 186, 199);
                draw_text_fit(renderer, info.x + 14.0F, info.y + 33.0F, info.w - 28.0F,
                              model_.day_month + " | " + model_.year + " | " + model_.funds, 219, 232, 238);
                draw_text_fit(renderer, info.x + 14.0F, info.y + 50.0F, info.w - 28.0F,
                              "POPULACAO " + model_.population + " / " + model_.residential_capacity, 158, 186, 199);
            }

            for (const UiButton& button : buttons_) {
                if (button.action == UiAction::resume_game || button.action == UiAction::start_new_city ||
                    button.action == UiAction::continue_saved_city || button.action == UiAction::open_save_load ||
                    button.action == UiAction::open_settings || button.action == UiAction::open_quit_confirm) {
                    draw_pause_button(renderer, button);
                }
            }
            draw_text_centered(renderer, panel, panel.y + panel.height - 20.0F,
                               model_.startup_main_menu ? "ESC  -  SAIR" : "ESC  -  VOLTAR AO PAUSE", 158, 186, 199);
            return;
        }

        if (model_.overlay == UiOverlay::quit_confirm) {
            draw_pause_panel(renderer, panel);
            draw_text_centered(renderer, panel, panel.y + 42.0F, "SAIR DO JOGO?", 238, 246, 249);
            draw_text_centered(renderer, panel, panel.y + 82.0F, "ALTERACOES NAO SALVAS SERAO PERDIDAS", 255, 180, 160);
            draw_text_centered(renderer, panel, panel.y + 108.0F, "SALVE A CIDADE ANTES DE ENCERRAR SE NECESSARIO", 158, 186, 199);
            for (const UiButton& button : buttons_) {
                if (button.action == UiAction::cancel_quit || button.action == UiAction::quit_game) {
                    draw_pause_button(renderer, button);
                }
            }
            draw_text_centered(renderer, panel, panel.y + panel.height - 20.0F, "ESC  -  CANCELAR", 158, 186, 199);
            return;
        }

        if (model_.overlay == UiOverlay::save_load) {
            draw_pause_panel(renderer, panel);
            draw_text_centered(renderer, panel, panel.y + 36.0F, "SALVAR / CARREGAR", 238, 246, 249);
            draw_text_centered(renderer, panel, panel.y + 66.0F, "SLOT PRINCIPAL", 158, 186, 199);

            const float card_x = panel.x + std::clamp(panel.width * 0.08F, 28.0F, 48.0F);
            const float card_width = panel.width - (card_x - panel.x) * 2.0F;
            const UiRect slot_card = {card_x, panel.y + 102.0F, card_width, 156.0F};
            const SDL_FRect slot_rect = {slot_card.x, slot_card.y, slot_card.width, slot_card.height};
            SDL_SetRenderDrawColor(renderer, 20, 44, 59, 252);
            SDL_RenderFillRect(renderer, &slot_rect);
            SDL_SetRenderDrawColor(renderer, model_.save_available ? 91 : 64, model_.save_available ? 188 : 91,
                                   model_.save_available ? 211 : 104, SDL_ALPHA_OPAQUE);
            SDL_RenderRect(renderer, &slot_rect);

            draw_text(renderer, slot_card.x + 18.0F, slot_card.y + 18.0F, "CITY HORIZON - SLOT 1", 238, 246, 249);
            draw_text(renderer, slot_card.x + 18.0F, slot_card.y + 43.0F,
                      model_.save_available ? "SAVE DISPONIVEL" : "NENHUM SAVE ENCONTRADO",
                      model_.save_available ? 151 : 158, model_.save_available ? 229 : 151,
                      model_.save_available ? 240 : 166);
            draw_text(renderer, slot_card.x + 18.0F, slot_card.y + 78.0F, "CIDADE ATUAL", 158, 186, 199);
            draw_text_fit(renderer, slot_card.x + 18.0F, slot_card.y + 100.0F, slot_card.width - 36.0F,
                          model_.day_month + " | " + model_.year + " | FUNDOS " + model_.funds, 219, 232, 238);
            draw_text_fit(renderer, slot_card.x + 18.0F, slot_card.y + 121.0F, slot_card.width - 36.0F,
                          "POPULACAO " + model_.population + " / " + model_.residential_capacity, 158, 186, 199);

            draw_text_fit(renderer, card_x, panel.y + 278.0F, card_width, model_.status, 158, 186, 199);
            for (const UiButton& button : buttons_) {
                if (button.action == UiAction::save_game || button.action == UiAction::load_game ||
                    button.action == UiAction::back_to_pause) {
                    draw_pause_button(renderer, button);
                }
            }
            draw_text_centered(renderer, panel, panel.y + panel.height - 20.0F, "ESC  -  VOLTAR AO PAUSE", 158, 186, 199);
            return;
        }

        if (model_.overlay == UiOverlay::settings) {
            draw_pause_panel(renderer, panel);
            draw_text_centered(renderer, panel, panel.y + 36.0F, "CONFIGURACOES", 238, 246, 249);
            draw_text_centered(renderer, panel, panel.y + 66.0F, "AUDIO", 158, 186, 199);
            draw_text_centered(renderer, panel, panel.y + 86.0F, "VALORES ATUAIS DO JOGO", 118, 151, 166);

            const auto draw_meter = [&](const UiRect& slider, const char* label, int percent) {
                percent = std::clamp(percent, 0, 100);
                const float label_y = slider.y - 25.0F;
                draw_text(renderer, slider.x, label_y, label, 219, 232, 238);
                draw_text_fit(renderer, slider.x + slider.width - 48.0F, label_y, 48.0F,
                              std::to_string(percent) + "%", 238, 246, 249);
                const SDL_FRect track = {slider.x, slider.y + 2.0F, slider.width, 16.0F};
                SDL_SetRenderDrawColor(renderer, 25, 48, 61, SDL_ALPHA_OPAQUE);
                SDL_RenderFillRect(renderer, &track);
                SDL_SetRenderDrawColor(renderer, 64, 91, 104, SDL_ALPHA_OPAQUE);
                SDL_RenderRect(renderer, &track);
                const float fill_width = (slider.width - 4.0F) * static_cast<float>(percent) / 100.0F;
                const SDL_FRect fill = {slider.x + 2.0F, slider.y + 4.0F, fill_width, 12.0F};
                SDL_SetRenderDrawColor(renderer, 91, 188, 211, SDL_ALPHA_OPAQUE);
                SDL_RenderFillRect(renderer, &fill);
                const float knob_x = slider.x + 2.0F + fill_width;
                const SDL_FRect knob = {std::clamp(knob_x - 4.0F, slider.x, slider.x + slider.width - 8.0F),
                                        slider.y - 1.0F, 8.0F, 22.0F};
                SDL_SetRenderDrawColor(renderer, 218, 242, 251, SDL_ALPHA_OPAQUE);
                SDL_RenderFillRect(renderer, &knob);
            };
            if (settings_master_slider_bounds_) {
                draw_meter(*settings_master_slider_bounds_, "VOLUME GERAL", settings_draft_master_percent_);
            }
            if (settings_effects_slider_bounds_) {
                draw_meter(*settings_effects_slider_bounds_, "EFEITOS", settings_draft_effects_percent_);
            }
            draw_text_centered(renderer, panel, panel.y + 286.0F, "CLIQUE OU ARRASTE PARA AJUSTAR", 158, 186, 199);
            draw_text_centered(renderer, panel, panel.y + 306.0F, "AS ALTERACOES SO SAO SALVAS AO APLICAR", 118, 151, 166);

            for (const UiButton& button : buttons_) {
                if (button.action == UiAction::settings_reset || button.action == UiAction::settings_cancel ||
                    button.action == UiAction::settings_apply) {
                    draw_pause_button(renderer, button);
                }
            }
            draw_text_centered(renderer, panel, panel.y + panel.height - 22.0F, "ESC  -  FECHAR", 158, 186, 199);
            return;
        }

        if (model_.overlay == UiOverlay::administration) {
            draw_pause_panel(renderer, panel);
            draw_text_centered(renderer, panel, panel.y + 34.0F, "ADMINISTRACAO", 238, 246, 249);
            draw_text_centered(renderer, panel, panel.y + 59.0F, "PAINEL DA CIDADE", 158, 186, 199);

            const float padding = std::clamp(panel.width * 0.055F, 24.0F, 40.0F);
            const float gap = 12.0F;
            const float card_width = (panel.width - padding * 2.0F - gap) * 0.5F;
            const float left_x = panel.x + padding;
            const float right_x = left_x + card_width + gap;
            const auto card = [&](float x, float y, float h, const char* title) {
                const SDL_FRect rect = {x, y, card_width, h};
                SDL_SetRenderDrawColor(renderer, 20, 44, 59, 252);
                SDL_RenderFillRect(renderer, &rect);
                SDL_SetRenderDrawColor(renderer, 64, 103, 123, SDL_ALPHA_OPAQUE);
                SDL_RenderRect(renderer, &rect);
                draw_text(renderer, x + 14.0F, y + 13.0F, title, 158, 186, 199);
            };

            card(left_x, panel.y + 92.0F, 148.0F, "ECONOMIA MENSAL");
            draw_text(renderer, left_x + 14.0F, panel.y + 126.0F, "RECEITA", 158, 186, 199);
            draw_text_fit(renderer, left_x + 112.0F, panel.y + 126.0F, card_width - 126.0F, model_.monthly_revenue, 112, 238, 135);
            draw_text(renderer, left_x + 14.0F, panel.y + 153.0F, "DESPESAS", 158, 186, 199);
            draw_text_fit(renderer, left_x + 112.0F, panel.y + 153.0F, card_width - 126.0F, model_.monthly_expenses, 255, 139, 139);
            draw_text(renderer, left_x + 14.0F, panel.y + 180.0F, "SALDO", 158, 186, 199);
            draw_text_fit(renderer, left_x + 112.0F, panel.y + 180.0F, card_width - 126.0F, model_.monthly_balance, 122, 225, 250);
            draw_text(renderer, left_x + 14.0F, panel.y + 207.0F, "FUNDOS", 158, 186, 199);
            draw_text_fit(renderer, left_x + 112.0F, panel.y + 207.0F, card_width - 126.0F, model_.funds, 238, 246, 249);

            card(right_x, panel.y + 92.0F, 148.0F, "CIDADE");
            draw_text(renderer, right_x + 14.0F, panel.y + 126.0F, "POPULACAO", 158, 186, 199);
            draw_text_fit(renderer, right_x + 118.0F, panel.y + 126.0F, card_width - 132.0F,
                          model_.population + " / " + model_.residential_capacity, 238, 246, 249);
            draw_text(renderer, right_x + 14.0F, panel.y + 153.0F, "ENERGIA", 158, 186, 199);
            draw_text_fit(renderer, right_x + 118.0F, panel.y + 153.0F, card_width - 132.0F,
                          model_.power_demand + " / " + model_.power_capacity, 238, 246, 249);
            draw_text(renderer, right_x + 14.0F, panel.y + 180.0F, "DATA", 158, 186, 199);
            draw_text_fit(renderer, right_x + 118.0F, panel.y + 180.0F, card_width - 132.0F,
                          model_.day_month + " | " + model_.year, 238, 246, 249);
            draw_text(renderer, right_x + 14.0F, panel.y + 207.0F, "SERVICOS", 158, 186, 199);
            draw_text_fit(renderer, right_x + 118.0F, panel.y + 207.0F, card_width - 132.0F,
                          model_.administration_services, 238, 246, 249);

            const SDL_FRect alert_rect = {left_x, panel.y + 258.0F, panel.width - padding * 2.0F, 112.0F};
            SDL_SetRenderDrawColor(renderer, 20, 44, 59, 252);
            SDL_RenderFillRect(renderer, &alert_rect);
            SDL_SetRenderDrawColor(renderer, 64, 103, 123, SDL_ALPHA_OPAQUE);
            SDL_RenderRect(renderer, &alert_rect);
            draw_text(renderer, left_x + 14.0F, panel.y + 272.0F, "STATUS / ALERTAS", 158, 186, 199);
            draw_text_wrapped(renderer, left_x + 14.0F, panel.y + 299.0F, alert_rect.w - 28.0F,
                              model_.administration_alerts, 219, 232, 238);

            for (const UiButton& button : buttons_) {
                if (button.action == UiAction::open_reports || button.action == UiAction::close_modal) draw_pause_button(renderer, button);
            }
            draw_text_centered(renderer, panel, panel.y + panel.height - 20.0F, "ESC  -  FECHAR", 158, 186, 199);
            return;
        }

        if (model_.overlay == UiOverlay::reports) {
            draw_pause_panel(renderer, panel);
            draw_text_centered(renderer, panel, panel.y + 34.0F, "RELATORIOS", 238, 246, 249);
            draw_text_centered(renderer, panel, panel.y + 59.0F, "RESUMO OPERACIONAL", 158, 186, 199);

            const float padding = std::clamp(panel.width * 0.055F, 24.0F, 40.0F);
            const float content_x = panel.x + padding;
            const float content_width = panel.width - padding * 2.0F;
            const float gap = 12.0F;
            const float card_width = (content_width - gap) * 0.5F;
            const auto report_card = [&](float x, float y, float h, const char* title) {
                const SDL_FRect rect = {x, y, card_width, h};
                SDL_SetRenderDrawColor(renderer, 20, 44, 59, 252);
                SDL_RenderFillRect(renderer, &rect);
                SDL_SetRenderDrawColor(renderer, 64, 103, 123, SDL_ALPHA_OPAQUE);
                SDL_RenderRect(renderer, &rect);
                draw_text(renderer, x + 14.0F, y + 13.0F, title, 158, 186, 199);
            };

            report_card(content_x, panel.y + 92.0F, 196.0F, "FINANCAS");
            draw_text(renderer, content_x + 14.0F, panel.y + 128.0F, "RECEITA MENSAL", 158, 186, 199);
            draw_text_fit(renderer, content_x + 14.0F, panel.y + 149.0F, card_width - 28.0F, model_.monthly_revenue, 112, 238, 135);
            draw_text(renderer, content_x + 14.0F, panel.y + 180.0F, "DESPESAS MENSAIS", 158, 186, 199);
            draw_text_fit(renderer, content_x + 14.0F, panel.y + 201.0F, card_width - 28.0F, model_.monthly_expenses, 255, 139, 139);
            draw_text(renderer, content_x + 14.0F, panel.y + 232.0F, "RESULTADO", 158, 186, 199);
            draw_text_fit(renderer, content_x + 14.0F, panel.y + 253.0F, card_width - 28.0F, model_.monthly_balance, 122, 225, 250);

            const float right_x = content_x + card_width + gap;
            report_card(right_x, panel.y + 92.0F, 196.0F, "CAPACIDADE DA CIDADE");
            draw_text(renderer, right_x + 14.0F, panel.y + 128.0F, "POPULACAO / CAPACIDADE", 158, 186, 199);
            draw_text_fit(renderer, right_x + 14.0F, panel.y + 149.0F, card_width - 28.0F,
                          model_.population + " / " + model_.residential_capacity, 238, 246, 249);
            draw_text(renderer, right_x + 14.0F, panel.y + 180.0F, "ENERGIA / CAPACIDADE", 158, 186, 199);
            draw_text_fit(renderer, right_x + 14.0F, panel.y + 201.0F, card_width - 28.0F,
                          model_.power_demand + " / " + model_.power_capacity, 238, 246, 249);
            draw_text(renderer, right_x + 14.0F, panel.y + 232.0F, "SERVICOS", 158, 186, 199);
            draw_text_fit(renderer, right_x + 14.0F, panel.y + 253.0F, card_width - 28.0F,
                          model_.administration_services, 238, 246, 249);

            const SDL_FRect notes = {content_x, panel.y + 306.0F, content_width, 70.0F};
            SDL_SetRenderDrawColor(renderer, 20, 44, 59, 252);
            SDL_RenderFillRect(renderer, &notes);
            SDL_SetRenderDrawColor(renderer, 64, 103, 123, SDL_ALPHA_OPAQUE);
            SDL_RenderRect(renderer, &notes);
            draw_text(renderer, content_x + 14.0F, panel.y + 320.0F, "OBSERVACOES", 158, 186, 199);
            draw_text_fit(renderer, content_x + 14.0F, panel.y + 343.0F, content_width - 28.0F,
                          model_.administration_alerts, 219, 232, 238);

            for (const UiButton& button : buttons_) {
                if (button.action == UiAction::open_administration || button.action == UiAction::close_modal) draw_pause_button(renderer, button);
            }
            draw_text_centered(renderer, panel, panel.y + panel.height - 20.0F, "ESC  -  FECHAR", 158, 186, 199);
            return;
        }
    }
}

const std::vector<UiButton>& GameplayUi::buttons() const { return buttons_; }
const std::vector<UiRect>& GameplayUi::panels() const { return panels_; }

void GameplayUi::add_button(UiRect bounds, std::string label, UiAction action, bool enabled, bool active, std::string payload) {
    UiButton button; button.bounds = bounds; button.label = std::move(label); button.action = action; button.payload = std::move(payload);
    button.enabled = enabled; button.active = active; buttons_.push_back(std::move(button));
}

void GameplayUi::add_build_card(UiRect bounds, const UiBuildItem& item, bool active, UiAction action) {
    UiButton card; card.bounds = bounds; card.label = item.name; card.action = action; card.payload = item.definition_id;
    card.enabled = item.enabled; card.active = active; card.detail = item.category + "  |  " + item.build_cost + "  |  " + item.footprint;
    card.requirements = item.requirements; card.thumbnail_path = item.thumbnail_path; card.build_card = true; buttons_.push_back(std::move(card));
}

void GameplayUi::add_panel(UiRect bounds) { panels_.push_back(bounds); }

void GameplayUi::update_settings_draft_from_pointer(SettingsDragTarget target, float mouse_x) {
    const std::optional<UiRect>* bounds = nullptr;
    if (target == SettingsDragTarget::master) bounds = &settings_master_slider_bounds_;
    else if (target == SettingsDragTarget::effects) bounds = &settings_effects_slider_bounds_;
    if (bounds == nullptr || !*bounds || (*bounds)->width <= 0.0F) return;

    const float normalized = std::clamp((mouse_x - (*bounds)->x) / (*bounds)->width, 0.0F, 1.0F);
    const int percent = std::clamp(static_cast<int>(normalized * 100.0F + 0.5F), 0, 100);
    if (target == SettingsDragTarget::master) settings_draft_master_percent_ = percent;
    else if (target == SettingsDragTarget::effects) settings_draft_effects_percent_ = percent;
}

const GameplayUi::UiThumbnail* GameplayUi::thumbnail_for(SDL_Renderer* renderer, const std::string& path) const {
    if (path.empty()) return nullptr;
    if (const auto found = thumbnails_.find(path); found != thumbnails_.end()) return found->second.texture == nullptr ? nullptr : &found->second;
    UiThumbnail thumbnail;
    SDL_Surface* surface = SDL_LoadPNG(path.c_str());
    if (surface != nullptr) {
        thumbnail.width = static_cast<float>(surface->w); thumbnail.height = static_cast<float>(surface->h);
        thumbnail.texture = SDL_CreateTextureFromSurface(renderer, surface); SDL_DestroySurface(surface);
        if (thumbnail.texture != nullptr) { SDL_SetTextureBlendMode(thumbnail.texture, SDL_BLENDMODE_BLEND); SDL_SetTextureScaleMode(thumbnail.texture, SDL_SCALEMODE_LINEAR); }
    }
    return thumbnails_.emplace(path, thumbnail).first->second.texture == nullptr ? nullptr : &thumbnails_.find(path)->second;
}

void GameplayUi::render_build_card(SDL_Renderer* renderer, const UiButton& button) const {
    std::string category = button.detail;
    std::string cost;
    std::string footprint;
    const std::string separator = "  |  ";
    const std::size_t first = category.find(separator);
    if (first != std::string::npos) {
        cost = category.substr(first + separator.size());
        category.resize(first);
        const std::size_t second = cost.find(separator);
        if (second != std::string::npos) {
            footprint = cost.substr(second + separator.size());
            cost.resize(second);
        }
    }

    const SDL_FRect shadow = {button.bounds.x + 2.0F, button.bounds.y + 3.0F, button.bounds.width, button.bounds.height};
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 68);
    SDL_RenderFillRect(renderer, &shadow);

    Uint8 red = 20, green = 49, blue = 65;
    Uint8 border_red = 59, border_green = 104, border_blue = 126;
    if (!button.enabled) {
        red = 30; green = 38; blue = 43;
        border_red = 62; border_green = 70; border_blue = 75;
    } else if (button.state == UiButtonState::pressed || button.active) {
        red = 22; green = 72; blue = 91;
        border_red = 100; border_green = 197; border_blue = 219;
    } else if (button.state == UiButtonState::hover) {
        red = 25; green = 62; blue = 80;
        border_red = 77; border_green = 145; border_blue = 169;
    }

    const SDL_FRect card = {button.bounds.x, button.bounds.y, button.bounds.width, button.bounds.height};
    SDL_SetRenderDrawColor(renderer, red, green, blue, SDL_ALPHA_OPAQUE);
    SDL_RenderFillRect(renderer, &card);
    SDL_SetRenderDrawColor(renderer, border_red, border_green, border_blue, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &card);
    if (button.active && button.enabled) {
        const SDL_FRect accent = {button.bounds.x + 1.0F, button.bounds.y + 1.0F, 4.0F, button.bounds.height - 2.0F};
        SDL_SetRenderDrawColor(renderer, 103, 208, 228, SDL_ALPHA_OPAQUE);
        SDL_RenderFillRect(renderer, &accent);
    }

    const float preview_size = std::clamp(button.bounds.height - 16.0F, 64.0F, 92.0F);
    const SDL_FRect preview = {button.bounds.x + 8.0F, button.bounds.y + 8.0F, preview_size, preview_size};
    SDL_SetRenderDrawColor(renderer, 10, 28, 40, SDL_ALPHA_OPAQUE);
    SDL_RenderFillRect(renderer, &preview);
    SDL_SetRenderDrawColor(renderer, 48, 86, 105, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &preview);
    if (const UiThumbnail* thumbnail = thumbnail_for(renderer, button.thumbnail_path)) {
        const float scale = std::min(preview.w / thumbnail->width, preview.h / thumbnail->height);
        const SDL_FRect destination = {preview.x + (preview.w - thumbnail->width * scale) * 0.5F,
                                       preview.y + (preview.h - thumbnail->height * scale) * 0.5F,
                                       thumbnail->width * scale, thumbnail->height * scale};
        SDL_RenderTexture(renderer, thumbnail->texture, nullptr, &destination);
    } else if (button.thumbnail_path.empty()) {
        draw_text(renderer, preview.x + preview.w * 0.5F - 4.0F, preview.y + preview.h * 0.5F - 4.0F,
                  "$", 182, 210, 111);
    }

    const float text_x = preview.x + preview.w + 11.0F;
    const float text_width = std::max(24.0F, button.bounds.x + button.bounds.width - text_x - 9.0F);
    draw_text_fit(renderer, text_x, button.bounds.y + 9.0F, text_width, button.label,
                  button.enabled ? 238 : 145, button.enabled ? 246 : 151, button.enabled ? 249 : 156);
    if (button.bounds.height >= 104.0F) {
        draw_text_fit(renderer, text_x, button.bounds.y + 26.0F, text_width, category,
                      button.enabled ? 143 : 105, button.enabled ? 178 : 116, button.enabled ? 194 : 123);
        draw_text_fit(renderer, text_x, button.bounds.y + 44.0F, text_width, "CUSTO  " + cost,
                      button.enabled ? 181 : 113, button.enabled ? 221 : 125, button.enabled ? 154 : 120);
        draw_text_fit(renderer, text_x, button.bounds.y + 61.0F, text_width, "LOTE  " + footprint,
                      button.enabled ? 183 : 116, button.enabled ? 207 : 128, button.enabled ? 218 : 134);
        draw_text_fit(renderer, text_x, button.bounds.y + 78.0F, text_width, button.requirements,
                      button.enabled ? 202 : 126, button.enabled ? 219 : 137, button.enabled ? 227 : 144);
    } else {
        draw_text_fit(renderer, text_x, button.bounds.y + 29.0F, text_width, "CUSTO  " + cost,
                      button.enabled ? 181 : 113, button.enabled ? 221 : 125, button.enabled ? 154 : 120);
        draw_text_fit(renderer, text_x, button.bounds.y + 46.0F, text_width, "LOTE  " + footprint,
                      button.enabled ? 183 : 116, button.enabled ? 207 : 128, button.enabled ? 218 : 134);
        draw_text_fit(renderer, text_x, button.bounds.y + 63.0F, text_width, button.requirements,
                      button.enabled ? 202 : 126, button.enabled ? 219 : 137, button.enabled ? 227 : 144);
    }
    const float state_y = button.bounds.y + button.bounds.height - 14.0F;
    if (button.active) draw_text_fit(renderer, text_x, state_y, text_width, "SELECIONADO", 137, 226, 242);
    else if (!button.enabled) draw_text_fit(renderer, text_x, state_y, text_width, "INDISPONIVEL", 211, 147, 138);
}

UiButtonState GameplayUi::state_for(const UiButton& button, float mouse_x, float mouse_y, bool pressed) {
    if (!button.enabled) return UiButtonState::disabled;
    if (!button.bounds.contains(mouse_x, mouse_y)) return UiButtonState::normal;
    return pressed ? UiButtonState::pressed : UiButtonState::hover;
}
