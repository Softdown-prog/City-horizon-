#pragma once

#include "src/camera_rotation_ui.h"
#include "src/runtime_game_state.h"
#include "src/runtime_view_state.h"
#include "road_system.h"

#include <algorithm>
#include <string>

// Runtime-only gameplay shell layered over the existing HUD/camera controls.
// It adds two lightweight 2D procedural overlays without introducing image
// dependencies: an initial road-connection tutorial and the bankruptcy Game Over.
class ChRuntimeGameplayUi : public ChGameplayUi {
public:
    void update_layout(const int viewport_width, const int viewport_height,
                       const GameplayUiModel& model) {
        ChGameplayUi::update_layout(viewport_width, viewport_height, model);
        viewport_width_ = std::max(viewport_width, 1);
        viewport_height_ = std::max(viewport_height, 1);

        if (model.startup_main_menu) tutorial_armed_ = true;
        if (model.overlay == UiOverlay::none && tutorial_armed_ && !tutorial_shown_) {
            tutorial_visible_ = true;
            tutorial_shown_ = true;
        }
    }

    void handle_mouse_motion(const float mouse_x, const float mouse_y) {
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
        if (tutorial_visible_) {
            UiInputResult result;
            result.consumed = true;
            if (primary_button) tutorial_visible_ = false;
            return result;
        }
        if (ch::runtime_game_state::game_over) {
            UiInputResult result;
            result.consumed = true;
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
             "2. CONSTRUA UMA RUA ATE O PORTAL NA BORDA OESTE DO TERRENO INICIAL.");
        text(renderer, panel.x + 28.0F, panel.y + 107.0F,
             "3. DEPOIS CONSTRUA MORADIAS. CASAS VAZIAS RECEBERAO NOVOS MORADORES.");
        text(renderer, panel.x + 28.0F, panel.y + 130.0F,
             "4. O MES DURA 5 MINUTOS EM 1X. CONTROLE RECEITA E MANUTENCAO.");
        centered_text(renderer, panel.x + panel.w * 0.5F, panel.y + 174.0F,
                      "CLIQUE PARA CONTINUAR", 178, 217, 186);

        // World-space marker for the road gateway. It occupies no tile by itself;
        // it is only a tutorial beacon over the exact logical connection point.
        const ch::runtime_view::ViewSnapshot view = ch::runtime_view::snapshot();
        if (!view.valid) return;
        const ch::ScreenPoint gateway = ch::world_to_screen_point(
            static_cast<float>(kExternalRoadGatewayX) + 0.5F,
            static_cast<float>(kExternalRoadGatewayY) + 0.5F,
            view.camera, view.viewport_width, view.viewport_height);
        const float radius = 13.0F;
        SDL_SetRenderDrawColor(renderer, 255, 192, 62, SDL_ALPHA_OPAQUE);
        const SDL_FRect marker{gateway.x - radius, gateway.y - radius,
                               radius * 2.0F, radius * 2.0F};
        SDL_RenderRect(renderer, &marker);
        SDL_RenderLine(renderer, gateway.x - radius - 8.0F, gateway.y,
                       gateway.x + radius + 8.0F, gateway.y);
        SDL_RenderLine(renderer, gateway.x, gateway.y - radius - 8.0F,
                       gateway.x, gateway.y + radius + 8.0F);
        text(renderer, gateway.x + 20.0F, gateway.y - 5.0F,
             "PORTAL RODOVIARIO", 255, 215, 112);
    }

    void render_game_over(SDL_Renderer* renderer) const {
        SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
        const SDL_FRect veil{0.0F, 0.0F, static_cast<float>(viewport_width_),
                            static_cast<float>(viewport_height_)};
        SDL_SetRenderDrawColor(renderer, 16, 5, 7, 218);
        SDL_RenderFillRect(renderer, &veil);

        const float panel_width = std::min(560.0F, static_cast<float>(viewport_width_) - 48.0F);
        const float panel_height = 220.0F;
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
        centered_text(renderer, panel.x + panel.w * 0.5F, panel.y + 174.0F,
                      "PRESSIONE ESC PARA ACESSAR O MENU.", 255, 205, 140);
    }

    int viewport_width_ = 1;
    int viewport_height_ = 1;
    bool tutorial_armed_ = true;
    bool tutorial_shown_ = false;
    bool tutorial_visible_ = false;
};
