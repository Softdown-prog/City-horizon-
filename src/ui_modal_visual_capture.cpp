#include "ui_manager.h"

#include <SDL3/SDL.h>

#include <algorithm>
#include <filesystem>
#include <iostream>
#include <string>

namespace {

constexpr int kWidth = 1280;
constexpr int kHeight = 800;

void draw_map_backdrop(SDL_Renderer* renderer) {
    SDL_SetRenderDrawColor(renderer, 41, 55, 48, SDL_ALPHA_OPAQUE);
    SDL_RenderClear(renderer);

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

[[nodiscard]] bool has_enabled_action(const GameplayUi& ui, const UiAction action) {
    return std::any_of(ui.buttons().begin(), ui.buttons().end(), [action](const UiButton& button) {
        return button.action == action && button.enabled;
    });
}

[[nodiscard]] bool save_capture(GameplayUi& ui, SDL_Renderer* renderer,
                                const std::filesystem::path& output_path) {
    draw_map_backdrop(renderer);
    ui.render(renderer);
    if (!SDL_RenderPresent(renderer)) {
        std::cerr << "modal capture failed: SDL_RenderPresent: " << SDL_GetError() << '\n';
        return false;
    }

    SDL_Surface* pixels = SDL_RenderReadPixels(renderer, nullptr);
    if (pixels == nullptr) {
        std::cerr << "modal capture failed: SDL_RenderReadPixels: " << SDL_GetError() << '\n';
        return false;
    }
    const bool saved = SDL_SavePNG(pixels, output_path.string().c_str());
    if (!saved) {
        std::cerr << "modal capture failed: SDL_SavePNG: " << SDL_GetError() << '\n';
    }
    SDL_DestroySurface(pixels);
    return saved;
}

GameplayUiModel base_model() {
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
    model.administration_services = "SAUDE OK / EDUCACAO OK / AGUA OK";
    model.administration_alerts = "SEM ALERTAS CRITICOS";
    model.master_volume_percent = 78;
    model.effects_volume_percent = 64;
    model.active_tool = UiTool::none;
    return model;
}

[[nodiscard]] bool capture_overlay(GameplayUi& ui, SDL_Renderer* renderer,
                                   GameplayUiModel model, const UiOverlay overlay,
                                   const UiAction required_action,
                                   const std::filesystem::path& output_path) {
    model.overlay = overlay;
    model.paused = overlay == UiOverlay::pause;
    ui.update_layout(kWidth, kHeight, model);
    ui.handle_mouse_motion(1100.0F, 700.0F);

    if (!has_enabled_action(ui, required_action)) {
        std::cerr << "modal capture failed: expected action missing for "
                  << output_path.string() << '\n';
        return false;
    }
    return save_capture(ui, renderer, output_path);
}

}  // namespace

int main(int argc, char** argv) {
    const std::filesystem::path output_dir = argc > 1 ? argv[1] : "ui_modal_capture";
    std::error_code directory_error;
    std::filesystem::create_directories(output_dir, directory_error);
    if (directory_error) {
        std::cerr << "modal capture failed: cannot create output directory: "
                  << directory_error.message() << '\n';
        return 1;
    }

    if (!SDL_Init(SDL_INIT_VIDEO)) {
        std::cerr << "modal capture failed: SDL_Init: " << SDL_GetError() << '\n';
        return 1;
    }

    SDL_Surface* canvas = SDL_CreateSurface(kWidth, kHeight, SDL_PIXELFORMAT_RGBA32);
    if (canvas == nullptr) {
        std::cerr << "modal capture failed: SDL_CreateSurface: " << SDL_GetError() << '\n';
        SDL_Quit();
        return 1;
    }

    SDL_Renderer* renderer = SDL_CreateSoftwareRenderer(canvas);
    if (renderer == nullptr) {
        std::cerr << "modal capture failed: SDL_CreateSoftwareRenderer: " << SDL_GetError() << '\n';
        SDL_DestroySurface(canvas);
        SDL_Quit();
        return 1;
    }

    GameplayUi ui;
    const GameplayUiModel model = base_model();

    const bool pause_ok = capture_overlay(
        ui, renderer, model, UiOverlay::pause, UiAction::resume_game,
        output_dir / "modal_pause.png");
    const bool settings_ok = capture_overlay(
        ui, renderer, model, UiOverlay::settings, UiAction::settings_apply,
        output_dir / "modal_settings.png");
    const bool administration_ok = capture_overlay(
        ui, renderer, model, UiOverlay::administration, UiAction::open_reports,
        output_dir / "modal_administration.png");

    ui.release_renderer_resources();
    SDL_DestroyRenderer(renderer);
    SDL_DestroySurface(canvas);
    SDL_Quit();

    if (!pause_ok || !settings_ok || !administration_ok) return 1;
    std::cout << "modal nine-slice visual capture passed: " << output_dir.string() << '\n';
    return 0;
}
