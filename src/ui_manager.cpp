#include "ui_manager.h"

// Keep the established UI implementation intact while removing energy from the
// public gameplay surface. The compatibility names let older layout/render
// code continue to serve unrelated panels without exposing the retired system.
#define update_layout update_layout_legacy
#define render render_legacy
#include "ui_manager_legacy_impl.inl"
#undef render
#undef update_layout

namespace {

bool contains_energy_term(const std::string& value) {
    return value.find("ENERGIA") != std::string::npos ||
           value.find("POWER") != std::string::npos;
}

std::string remove_energy_segments(const std::string& value, const std::string& separator) {
    std::string result;
    std::size_t start = 0;
    while (start <= value.size()) {
        const std::size_t end = value.find(separator, start);
        const std::string part = value.substr(
            start, end == std::string::npos ? std::string::npos : end - start);
        if (!part.empty() && !contains_energy_term(part)) {
            if (!result.empty()) result += separator;
            result += part;
        }
        if (end == std::string::npos) break;
        start = end + separator.size();
    }
    return result;
}

GameplayUiModel energy_free_ui_model(GameplayUiModel model) {
    model.power_demand.clear();
    model.power_capacity.clear();
    model.administration_services = remove_energy_segments(model.administration_services, " / ");

    if (model.selected_building) {
        model.selected_building->energy_consumption.clear();
        model.selected_building->energy_production.clear();
    }

    for (UiBuildItem& item : model.build_items) {
        item.requirements = remove_energy_segments(item.requirements, " | ");
    }
    for (UiBuildItem& item : model.decor_items) {
        item.requirements = remove_energy_segments(item.requirements, " | ");
    }

    model.debug_lines.erase(
        std::remove_if(model.debug_lines.begin(), model.debug_lines.end(),
                       [](const std::string& line) { return contains_energy_term(line); }),
        model.debug_lines.end());

    const std::size_t deficit = model.status.find(" | POWER DEFICIT");
    if (deficit != std::string::npos) model.status.erase(deficit);

    return model;
}

void fill_rect(SDL_Renderer* renderer, const SDL_FRect& rect,
               const Uint8 r, const Uint8 g, const Uint8 b,
               const Uint8 a = SDL_ALPHA_OPAQUE) {
    SDL_SetRenderDrawColor(renderer, r, g, b, a);
    SDL_RenderFillRect(renderer, &rect);
}

}  // namespace

void GameplayUi::update_layout(const int viewport_width, const int viewport_height,
                               const GameplayUiModel& model) {
    update_layout_legacy(viewport_width, viewport_height, energy_free_ui_model(model));
}

void GameplayUi::render(SDL_Renderer* renderer) const {
    render_legacy(renderer);
    if (renderer == nullptr || panels_.empty()) return;

    const UiRect& hud = panels_.front();
    const float width = static_cast<float>(viewport_width_);
    const float settings_x = std::max(kMargin + 270.0F, width - 50.0F);
    const float administration_x = std::max(kMargin + 120.0F, settings_x - 112.0F);
    const float pause_x = std::max(kMargin, administration_x - 124.0F);

    // Redraw the normal top HUD as three stats. This removes both the energy
    // number and the lightning icon without disturbing the existing controls.
    if (model_.overlay == UiOverlay::none) {
        const float stats_left = hud.x + 2.0F;
        const float stats_right = std::max(stats_left, pause_x);
        const SDL_FRect stats_background = {
            stats_left,
            hud.y + 2.0F,
            std::max(0.0F, stats_right - stats_left),
            std::max(0.0F, hud.height - 4.0F),
        };
        fill_rect(renderer, stats_background, 16, 39, 56, 244);
        SDL_SetRenderDrawColor(renderer, 35, 71, 92, SDL_ALPHA_OPAQUE);
        SDL_RenderLine(renderer, stats_left, hud.y + hud.height - 2.0F,
                       stats_right, hud.y + hud.height - 2.0F);

        const float block_x = hud.x + 16.0F;
        const float block_width = std::max(1.0F, (stats_right - block_x) / 3.0F);
        draw_hud_stat(renderer, block_x, HudIcon::coins, "FUNDOS", model_.funds);
        draw_hud_stat(renderer, block_x + block_width, HudIcon::calendar, "DATA",
                      model_.day_month.empty() ? model_.date : model_.day_month,
                      model_.year);
        draw_hud_stat(renderer, block_x + block_width * 2.0F, HudIcon::people,
                      "POPULACAO", model_.population + " / " + model_.residential_capacity);

        const auto draw_icon = [&](const char* name, const SDL_FRect& bounds) {
            if (const UiThumbnail* icon = thumbnail_for(renderer, ui_icon_path(name))) {
                const float scale = std::min(bounds.w / icon->width, bounds.h / icon->height);
                const SDL_FRect destination = {
                    bounds.x + (bounds.w - icon->width * scale) * 0.5F,
                    bounds.y + (bounds.h - icon->height * scale) * 0.5F,
                    icon->width * scale,
                    icon->height * scale,
                };
                SDL_RenderTexture(renderer, icon->texture, nullptr, &destination);
            }
        };
        draw_icon("funds", {block_x - 1.0F, 28.0F, 22.0F, 24.0F});
        draw_icon("calendar", {block_x + block_width - 1.0F, 28.0F, 22.0F, 24.0F});
        draw_icon("population", {block_x + block_width * 2.0F - 1.0F, 28.0F, 22.0F, 24.0F});

        SDL_SetRenderDrawColor(renderer, 55, 91, 111, SDL_ALPHA_OPAQUE);
        for (int separator = 1; separator < 3; ++separator) {
            const float separator_x = block_x + block_width * static_cast<float>(separator) - 12.0F;
            SDL_RenderLine(renderer, separator_x, hud.y + 12.0F,
                           separator_x, hud.y + hud.height - 12.0F);
        }
    }

    // Legacy modal layouts still reserve the old row. Paint only that retired
    // row back to the card background so Administration/Reports contain no
    // energy label or value.
    if (model_.overlay == UiOverlay::administration && overlay_bounds_) {
        const UiRect& panel = *overlay_bounds_;
        const float padding = std::clamp(panel.width * 0.055F, 24.0F, 40.0F);
        const float gap = 12.0F;
        const float card_width = (panel.width - padding * 2.0F - gap) * 0.5F;
        const float right_x = panel.x + padding + card_width + gap;
        fill_rect(renderer,
                  {right_x + 8.0F, panel.y + 145.0F, card_width - 16.0F, 28.0F},
                  20, 44, 59, 252);
    } else if (model_.overlay == UiOverlay::reports && overlay_bounds_) {
        const UiRect& panel = *overlay_bounds_;
        const float padding = std::clamp(panel.width * 0.055F, 24.0F, 40.0F);
        const float content_x = panel.x + padding;
        const float content_width = panel.width - padding * 2.0F;
        const float gap = 12.0F;
        const float card_width = (content_width - gap) * 0.5F;
        const float right_x = content_x + card_width + gap;
        fill_rect(renderer,
                  {right_x + 8.0F, panel.y + 172.0F, card_width - 16.0F, 51.0F},
                  20, 44, 59, 252);
    }
}
