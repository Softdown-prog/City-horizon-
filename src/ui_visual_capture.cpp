#include "ui_manager.h"

#include <SDL3/SDL.h>

#include <algorithm>
#include <filesystem>
#include <iostream>
#include <optional>
#include <string>

namespace {

constexpr int kWidth = 1280;
constexpr int kHeight = 800;

[[nodiscard]] const UiButton* floor_card(const GameplayUi& ui, const std::string& style) {
    const auto found = std::find_if(ui.buttons().begin(), ui.buttons().end(), [&](const UiButton& button) {
        return button.action == UiAction::select_sidewalk_style && button.payload == style;
    });
    return found == ui.buttons().end() ? nullptr : &*found;
}

[[nodiscard]] bool validate_floor_catalog(const GameplayUi& ui, const std::string& selected_style) {
    int floor_cards = 0;
    int active_cards = 0;
    for (const std::string style : {"dirt_path", "sand_path", "grass"}) {
        const UiButton* card = floor_card(ui, style);
        if (card == nullptr) {
            std::cerr << "ui capture failed: missing floor card " << style << '\n';
            return false;
        }
        if (!card->build_card) {
            std::cerr << "ui capture failed: floor option is not using the catalog-card renderer: " << style << '\n';
            return false;
        }
        if (card->thumbnail_path.empty() || !std::filesystem::exists(card->thumbnail_path)) {
            std::cerr << "ui capture failed: thumbnail missing for " << style
                      << " at " << card->thumbnail_path << '\n';
            return false;
        }
        ++floor_cards;
        if (card->active) {
            ++active_cards;
            if (card->payload != selected_style) {
                std::cerr << "ui capture failed: unexpected selected floor card " << card->payload << '\n';
                return false;
            }
        }
    }
    if (floor_cards != 3 || active_cards != 1) {
        std::cerr << "ui capture failed: expected 3 floor cards and exactly 1 selected card\n";
        return false;
    }
    return true;
}

void draw_map_backdrop(SDL_Renderer* renderer) {
    SDL_SetRenderDrawColor(renderer, 41, 55, 48, SDL_ALPHA_OPAQUE);
    SDL_RenderClear(renderer);

    // A deterministic isometric backdrop makes the capture easier to compare
    // with the in-game composition without pretending to be a MapForge render.
    SDL_SetRenderDrawColor(renderer, 67, 85, 71, 150);
    constexpr float tile_w = 96.0F;
    constexpr float tile_h = 48.0F;
    constexpr float origin_x = 760.0F;
    constexpr float origin_y = 180.0F;
    for (int y = -4; y <= 11; ++y) {
        for (int x = -4; x <= 11; ++x) {
            const float cx = origin_x + static_cast<float>(x - y) * tile_w * 0.5F;
            const float cy = origin_y + static_cast<float>(x + y) * tile_h * 0.5F;
            const float left_x = cx - tile_w * 0.5F;
            const float right_x = cx + tile_w * 0.5F;
            const float top_y = cy - tile_h * 0.5F;
            const float bottom_y = cy + tile_h * 0.5F;
            SDL_RenderLine(renderer, cx, top_y, right_x, cy);
            SDL_RenderLine(renderer, right_x, cy, cx, bottom_y);
            SDL_RenderLine(renderer, cx, bottom_y, left_x, cy);
            SDL_RenderLine(renderer, left_x, cy, cx, top_y);
        }
    }
}

[[nodiscard]] bool save_capture(GameplayUi& ui, SDL_Renderer* renderer,
                                const std::filesystem::path& output_path,
                                const int settle_frames) {
    for (int frame = 0; frame < std::max(1, settle_frames); ++frame) {
        draw_map_backdrop(renderer);
        ui.render(renderer);
        if (!SDL_RenderPresent(renderer)) {
            std::cerr << "ui capture failed: SDL_RenderPresent: " << SDL_GetError() << '\n';
            return false;
        }
        if (frame + 1 < settle_frames) SDL_Delay(16);
    }

    SDL_Surface* pixels = SDL_RenderReadPixels(renderer, nullptr);
    if (pixels == nullptr) {
        std::cerr << "ui capture failed: SDL_RenderReadPixels: " << SDL_GetError() << '\n';
        return false;
    }
    const bool saved = SDL_SavePNG(pixels, output_path.string().c_str());
    if (!saved) {
        std::cerr << "ui capture failed: SDL_SavePNG: " << SDL_GetError() << '\n';
    }
    SDL_DestroySurface(pixels);
    return saved;
}

GameplayUiModel capture_model() {
    GameplayUiModel model;
    model.funds = "$50.000";
    model.date = "DIA 01 / MES 01 / ANO 1";
    model.day_month = "DIA 01 | MES 01";
    model.year = "ANO 1";
    model.monthly_revenue = "$3.250";
    model.monthly_expenses = "$1.180";
    model.monthly_balance = "+$2.070";
    model.population = "128";
    model.residential_capacity = "160";
    model.speed = "1x";
    model.status = "PISO: SELECIONE UM TILE E CLIQUE/ARRASTE NO TERRENO";
    model.active_tool = UiTool::sidewalks;
    model.sidewalk_style = "dirt_path";
    return model;
}

[[nodiscard]] std::pair<float, float> card_center(const UiButton& button) {
    return {button.bounds.x + button.bounds.width * 0.5F,
            button.bounds.y + button.bounds.height * 0.5F};
}

}  // namespace

int main(int argc, char** argv) {
    const std::filesystem::path output_dir = argc > 1 ? argv[1] : "ui_capture";
    std::error_code directory_error;
    std::filesystem::create_directories(output_dir, directory_error);
    if (directory_error) {
        std::cerr << "ui capture failed: cannot create output directory: "
                  << directory_error.message() << '\n';
        return 1;
    }

    if (!SDL_Init(SDL_INIT_VIDEO)) {
        std::cerr << "ui capture failed: SDL_Init: " << SDL_GetError() << '\n';
        return 1;
    }

    SDL_Surface* canvas = SDL_CreateSurface(kWidth, kHeight, SDL_PIXELFORMAT_RGBA32);
    if (canvas == nullptr) {
        std::cerr << "ui capture failed: SDL_CreateSurface: " << SDL_GetError() << '\n';
        SDL_Quit();
        return 1;
    }

    SDL_Renderer* renderer = SDL_CreateSoftwareRenderer(canvas);
    if (renderer == nullptr) {
        std::cerr << "ui capture failed: SDL_CreateSoftwareRenderer: " << SDL_GetError() << '\n';
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 1;
    }

    GameplayUi ui;
    GameplayUiModel model = capture_model();
    ui.update_layout(kWidth, kHeight, model);

    if (!validate_floor_catalog(ui, "dirt_path")) {
        SDL_DestroyRenderer(renderer);
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 1;
    }

    ui.handle_mouse_motion(1000.0F, 500.0F);
    if (!save_capture(ui, renderer, output_dir / "floor_catalog_idle.png", 2)) {
        SDL_DestroyRenderer(renderer);
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 1;
    }

    const UiButton* sand = floor_card(ui, "sand_path");
    if (sand == nullptr) return 1;
    const auto [sand_x, sand_y] = card_center(*sand);
    ui.handle_mouse_motion(sand_x, sand_y);
    if (!save_capture(ui, renderer, output_dir / "floor_catalog_hover_sand.png", 12)) {
        SDL_DestroyRenderer(renderer);
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 1;
    }

    const UiButton* grass = floor_card(ui, "grass");
    if (grass == nullptr) return 1;
    const auto [grass_x, grass_y] = card_center(*grass);
    ui.handle_mouse_motion(grass_x, grass_y);
    const UiInputResult press = ui.handle_mouse_button_down(grass_x, grass_y, true);
    if (!press.consumed || !press.action || press.action->action != UiAction::select_sidewalk_style ||
        press.action->payload != "grass") {
        std::cerr << "ui capture failed: grass card did not dispatch select_sidewalk_style\n";
        SDL_DestroyRenderer(renderer);
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 1;
    }
    if (!save_capture(ui, renderer, output_dir / "floor_catalog_pressed_grass.png", 8)) {
        SDL_DestroyRenderer(renderer);
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 1;
    }
    ui.handle_mouse_button_up(grass_x, grass_y);

    model.sidewalk_style = "grass";
    ui.update_layout(kWidth, kHeight, model);
    ui.handle_mouse_motion(1000.0F, 500.0F);
    if (!validate_floor_catalog(ui, "grass") ||
        !save_capture(ui, renderer, output_dir / "floor_catalog_selected_grass.png", 10)) {
        SDL_DestroyRenderer(renderer);
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 1;
    }

    ui.release_renderer_resources();
    SDL_DestroyRenderer(renderer);
    SDL_DestroySurface(canvas);
    SDL_Quit();

    std::cout << "ui visual capture passed: " << output_dir.string() << '\n';
    return 0;
}
