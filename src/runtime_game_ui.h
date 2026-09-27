#pragma once

#include "src/camera_rotation_ui.h"
#include "src/runtime_game_state.h"
#include "src/runtime_view_state.h"
#include "road_system.h"

#include <algorithm>
#include <string>

// Runtime-only gameplay shell layered over the existing HUD/camera controls.
// It adds lightweight 2D procedural overlays without introducing image
// dependencies: tutorial, citizen status bars and bankruptcy Game Over.
class ChRuntimeGameplayUi : public ChGameplayUi {
public:
    void update_layout(const int viewport_width, const int viewport_height,
                       const GameplayUiModel& model) {
        ChGameplayUi::update_layout(viewport_width, viewport_height, model);
        viewport_width_ = std::max(viewport_width, 1);
        viewport_height_ = std::max(viewport_height, 1);
        citizen_status_ = model.citizen_status;

        if (model.startup_main_menu) tutorial_armed_ = true;
        if (model.overlay == UiOverlay::none && tutorial_armed_ && !tutorial_shown_) {
            tutorial_visible_ = true;
            tutorial_shown_ = true;
        }
    }

    void handle_mouse_motion(const float mouse_x, const float mouse_y) {
        mouse_x_ = mouse_x;
        mouse_y_ = mouse_y;
        ChGameplayUi::handle_mouse_motion(mouse_x, mouse_y);
    }

    [[nodiscard]] bool handle_mouse_wheel(const float mouse_x, const float mouse_y,
                                          const float wheel_y) {
        if (tutorial_visible_ || ch::runtime_game_state::game_over) return true;
        return ChGameplayUi::handle_mouse_wheel(mouse_x, mouse_y, wheel_y);
    }

    [[nodiscard]] UiInputResult handle_mouse_button_down(const float mouse_x,
                                                         const float mouse_y,
                                                         const bool primary_button) {
        mouse_x_ = mouse_x;
        mouse_y_ = mouse_y;
        if (tutorial_visible_) {
            UiInputResult result;
            result.consumed = true;
            if (primary_button) tutorial_visible_ = false;
            return result;
        }
        if (ch::runtime_game_state::game_over) {
            UiInputResult result;
            result.consumed = true;
            if (primary_button && game_over_menu_bounds().contains(mouse_x, mouse_y)) {
                ch::runtime_game_state::reset();
                result.action = UiActionEvent{UiAction::open_main_menu, "bankruptcy_game_over"};
            }
            return result;
        }
        return ChGameplayUi::handle_mouse_button_down(mouse_x, mouse_y, primary_button);
    }

    void handle_mouse_button_up(const float mouse_x, const float mouse_y) {
        if (tutorial_visible_ || ch::runtime_game_state::game_over) return;
        ChGameplayUi::handle_mouse_button_up(mouse_x, mouse_y);
    }

    [[nodiscard]] bool consumes_point(const float mouse_x, const float mouse_y) const {
        if (tutorial_visible_ || ch::runtime_game_state::game_over) return true;
        return ChGameplayUi::consumes_point(mouse_x, mouse_y);
    }

    void render(SDL_Renderer* renderer) const {
        ChGameplayUi::render(renderer);
        if (renderer == nullptr) return;
        if (!tutorial_visible_ && !ch::runtime_game_state::game_over && citizen_status_) {
            render_citizen_status(renderer, *citizen_status_);
        }
        if (tutorial_visible_) render_tutorial(renderer);
        if (ch::runtime_game_state::game_over) render_game_over(renderer);
    }

private:
    static void text(SDL_Renderer* renderer, const float x, const float y,
                     const char* value, const Uint8 r = 238,
                     const Uint8 g = 244, const Uint8 b = 238) {
        SDL_SetRenderDrawColor(renderer, r, g, b, SDL_ALPHA_OPAQUE);
        SDL_RenderDebugText(renderer, x, y, value);
    }

    static void centered_text(SDL_Renderer* renderer, const float center_x,
                              const float y, const std::string& value,
                              const Uint8 r = 238, const Uint8 g = 244,
                              const Uint8 b = 238) {
        const float width = static_cast<float>(value.size()) * 8.0F;
        text(renderer, center_x - width * 0.5F, y, value.c_str(), r, g, b);
    }

    static int clamped_percent(const int value) {
        return std::clamp(value, 0, 100);
    }

    static void render_need_bar(SDL_Renderer* renderer, const float x, const float y,
                                const float width, const char* label, const int value,
                                const Uint8 r, const Uint8 g, const Uint8 b,
                                const bool lowest) {
        const int clamped = clamped_percent(value);
        const float bar_x = x + 84.0F;
        const float bar_y = y + 1.0F;
        const float bar_h = 12.0F;
        const SDL_FRect background{bar_x, bar_y, width, bar_h};
        SDL_SetRenderDrawColor(renderer, 25, 31, 35, 235);
        SDL_RenderFillRect(renderer, &background);
        SDL_SetRenderDrawColor(renderer, 76, 89, 94, 255);
        SDL_RenderRect(renderer, &background);

        const float fill_width = width * static_cast<float>(clamped) / 100.0F;
        if (fill_width > 0.0F) {
            const SDL_FRect fill{bar_x + 1.0F, bar_y + 1.0F,
                                 std::max(0.0F, fill_width - 2.0F), bar_h - 2.0F};
            SDL_SetRenderDrawColor(renderer, r, g, b, 245);
            SDL_RenderFillRect(renderer, &fill);
        }

        text(renderer, x, y + 3.0F, label,
             lowest ? 255 : 220, lowest ? 219 : 228, lowest ? 132 : 226);
        const std::string value_text = std::to_string(clamped);
        text(renderer, bar_x + width + 9.0F, y + 3.0F, value_text.c_str(), 231, 237, 232);
    }

    void render_citizen_status(SDL_Renderer* renderer, const UiCitizenStatus& status) const {
        SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
        const float panel_w = 318.0F;
        const float panel_h = 128.0F;
        const float panel_x = 18.0F;
        const float panel_y = std::max(18.0F, static_cast<float>(viewport_height_) - panel_h - 18.0F);
        const SDL_FRect panel{panel_x, panel_y, panel_w, panel_h};

        SDL_SetRenderDrawColor(renderer, 12, 29, 37, 236);
        SDL_RenderFillRect(renderer, &panel);
        SDL_SetRenderDrawColor(renderer, 76, 164, 181, 255);
        SDL_RenderRect(renderer, &panel);
        SDL_RenderLine(renderer, panel.x + 2.0F, panel.y + 3.0F,
                       panel.x + panel.w - 2.0F, panel.y + 3.0F);

        text(renderer, panel.x + 14.0F, panel.y + 15.0F,
             status.title.c_str(), 151, 229, 240);
        text(renderer, panel.x + 14.0F, panel.y + 31.0F,
             status.activity.c_str(), 193, 209, 204);
        text(renderer, panel.x + 190.0F, panel.y + 31.0F,
             status.money.c_str(), 178, 217, 186);

        const int lowest_value = std::min(status.hunger, std::min(status.thirst, status.fun));
        const float row_x = panel.x + 14.0F;
        const float bar_width = 158.0F;
        render_need_bar(renderer, row_x, panel.y + 55.0F, bar_width,
                        "FOME", status.hunger, 214, 143, 72, status.hunger == lowest_value);
        render_need_bar(renderer, row_x, panel.y + 77.0F, bar_width,
                        "SEDE", status.thirst, 80, 164, 212, status.thirst == lowest_value);
        render_need_bar(renderer, row_x, panel.y + 99.0F, bar_width,
                        "DIVERSAO", status.fun, 174, 104, 193, status.fun == lowest_value);
    }

    [[nodiscard]] UiRect game_over_menu_bounds() const {
        const float width = 210.0F;
        return {
            (static_cast<float>(viewport_width_) - width) * 0.5F,
            static_cast<float>(viewport_height_) * 0.5F + 65.0F,
            width,
            38.0F,
        };
    }

    void render_tutorial(SDL_Renderer* renderer) const {
        SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
        const SDL_FRect veil{0.0F, 0.0F, static_cast<float>(viewport_width_),
                            static_cast<float>(viewport_height_)};
        SDL_SetRenderDrawColor(renderer, 5, 14, 21, 126);
        SDL_RenderFillRect(renderer, &veil);

        const float panel_width = std::min(620.0F, static_cast<float>(viewport_width_) - 48.0F);
        const float panel_height = 210.0F;
        const SDL_FRect panel{
            (static_cast<float>(viewport_width_) - panel_width) * 0.5F,
            86.0F,
            panel_width,
            panel_height,
        };
        SDL_SetRenderDrawColor(renderer, 13, 35, 48, 246);
        SDL_RenderFillRect(renderer, &panel);
        SDL_SetRenderDrawColor(renderer, 88, 190, 211, SDL_ALPHA_OPAQUE);
        SDL_RenderRect(renderer, &panel);
        SDL_RenderLine(renderer, panel.x + 2.0F, panel.y + 3.0F,
                       panel.x + panel.w - 2.0F, panel.y + 3.0F);

        centered_text(renderer, panel.x + panel.w * 0.5F, panel.y + 24.0F,
                      "PRIMEIROS PASSOS", 151, 229, 240);
        text(renderer, panel.x + 28.0F, panel.y + 61.0F,
             "1. SUA CIDADE PRECISA DE UMA CONEXAO COM O MUNDO EXTERIOR.");
        text(renderer, panel.x + 28.0F, panel.y + 84.0F,
             "2. CONSTRUA UMA RUA ATE A ENTRADA RODOVIARIA NA BORDA OESTE.");
        text(renderer, panel.x + 28.0F, panel.y + 107.0F,
             "3. DEPOIS CONSTRUA MORADIAS. CASAS VAZIAS RECEBERAO NOVOS MORADORES.");
        text(renderer, panel.x + 28.0F, panel.y + 130.0F,
             "4. O MES DURA 5 MINUTOS EM 1X. CONTROLE RECEITA E MANUTENCAO.");
        centered_text(renderer, panel.x + panel.w * 0.5F, panel.y + 174.0F,
                      "CLIQUE PARA CONTINUAR", 178, 217, 186);

        const ch::runtime_view::ViewSnapshot view = ch::runtime_view::snapshot();
        if (!view.valid) return;

        const ch::ScreenPoint outside = ch::world_to_screen_point(
            static_cast<float>(kExternalRoadGatewayX) - 0.5F,
            static_cast<float>(kExternalRoadGatewayY) + 0.5F,
            view.camera, view.viewport_width, view.viewport_height);
        const ch::ScreenPoint gateway = ch::world_to_screen_point(
            static_cast<float>(kExternalRoadGatewayX) + 0.5F,
            static_cast<float>(kExternalRoadGatewayY) + 0.5F,
            view.camera, view.viewport_width, view.viewport_height);

        SDL_SetRenderDrawColor(renderer, 55, 60, 63, 245);
        SDL_RenderLine(renderer, outside.x, outside.y - 5.0F, gateway.x, gateway.y - 5.0F);
        SDL_RenderLine(renderer, outside.x, outside.y, gateway.x, gateway.y);
        SDL_RenderLine(renderer, outside.x, outside.y + 5.0F, gateway.x, gateway.y + 5.0F);
        SDL_SetRenderDrawColor(renderer, 224, 190, 70, 225);
        SDL_RenderLine(renderer, outside.x, outside.y, gateway.x, gateway.y);

        const float sign_x = outside.x - 64.0F;
        const float sign_y = outside.y - 86.0F;
        const SDL_FRect sign{sign_x, sign_y, 150.0F, 46.0F};
        SDL_SetRenderDrawColor(renderer, 28, 92, 79, 248);
        SDL_RenderFillRect(renderer, &sign);
        SDL_SetRenderDrawColor(renderer, 216, 225, 218, SDL_ALPHA_OPAQUE);
        SDL_RenderRect(renderer, &sign);
        SDL_SetRenderDrawColor(renderer, 112, 120, 110, SDL_ALPHA_OPAQUE);
        SDL_RenderLine(renderer, sign.x + 24.0F, sign.y + sign.h,
                       sign.x + 24.0F, sign.y + sign.h + 22.0F);
        SDL_RenderLine(renderer, sign.x + sign.w - 24.0F, sign.y + sign.h,
                       sign.x + sign.w - 24.0F, sign.y + sign.h + 22.0F);
        centered_text(renderer, sign.x + sign.w * 0.5F, sign.y + 10.0F,
                      "CITY HORIZON", 242, 247, 239);
        centered_text(renderer, sign.x + sign.w * 0.5F, sign.y + 27.0F,
                      "ENTRADA DA CIDADE", 205, 224, 214);

        const float radius = 11.0F;
        SDL_SetRenderDrawColor(renderer, 255, 192, 62, SDL_ALPHA_OPAQUE);
        const SDL_FRect marker{gateway.x - radius, gateway.y - radius,
                               radius * 2.0F, radius * 2.0F};
        SDL_RenderRect(renderer, &marker);
        text(renderer, gateway.x + 18.0F, gateway.y - 5.0F,
             "LIGUE SUA RUA AQUI", 255, 215, 112);
    }

    void render_game_over(SDL_Renderer* renderer) const {
        SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
        const SDL_FRect veil{0.0F, 0.0F, static_cast<float>(viewport_width_),
                            static_cast<float>(viewport_height_)};
        SDL_SetRenderDrawColor(renderer, 16, 5, 7, 218);
        SDL_RenderFillRect(renderer, &veil);

        const float panel_width = std::min(560.0F, static_cast<float>(viewport_width_) - 48.0F);
        const float panel_height = 250.0F;
        const SDL_FRect panel{
            (static_cast<float>(viewport_width_) - panel_width) * 0.5F,
            (static_cast<float>(viewport_height_) - panel_height) * 0.5F,
            panel_width,
            panel_height,
        };
        SDL_SetRenderDrawColor(renderer, 44, 15, 20, 250);
        SDL_RenderFillRect(renderer, &panel);
        SDL_SetRenderDrawColor(renderer, 221, 92, 92, SDL_ALPHA_OPAQUE);
        SDL_RenderRect(renderer, &panel);
        SDL_RenderLine(renderer, panel.x + 2.0F, panel.y + 3.0F,
                       panel.x + panel.w - 2.0F, panel.y + 3.0F);

        centered_text(renderer, panel.x + panel.w * 0.5F, panel.y + 35.0F,
                      "GAME OVER", 255, 128, 128);
        centered_text(renderer, panel.x + panel.w * 0.5F, panel.y + 72.0F,
                      "PREFEITURA EM FALENCIA", 245, 225, 225);
        centered_text(renderer, panel.x + panel.w * 0.5F, panel.y + 104.0F,
                      "O CAIXA FICOU NEGATIVO POR 3 MESES CONSECUTIVOS.",
                      220, 201, 201);
        centered_text(renderer, panel.x + panel.w * 0.5F, panel.y + 135.0F,
                      "A SIMULACAO FOI PAUSADA.", 220, 201, 201);

        const UiRect button = game_over_menu_bounds();
        const bool hovered = button.contains(mouse_x_, mouse_y_);
        const SDL_FRect rect{button.x, button.y, button.width, button.height};
        SDL_SetRenderDrawColor(renderer, hovered ? 109 : 77, hovered ? 54 : 38,
                               hovered ? 58 : 44, SDL_ALPHA_OPAQUE);
        SDL_RenderFillRect(renderer, &rect);
        SDL_SetRenderDrawColor(renderer, hovered ? 255 : 221, hovered ? 164 : 92,
                               hovered ? 164 : 92, SDL_ALPHA_OPAQUE);
        SDL_RenderRect(renderer, &rect);
        centered_text(renderer, button.x + button.width * 0.5F, button.y + 15.0F,
                      "MENU PRINCIPAL", 255, 230, 230);
    }

    int viewport_width_ = 1;
    int viewport_height_ = 1;
    float mouse_x_ = -1000.0F;
    float mouse_y_ = -1000.0F;
    bool tutorial_armed_ = true;
    bool tutorial_shown_ = false;
    bool tutorial_visible_ = false;
    std::optional<UiCitizenStatus> citizen_status_;
};
