from pathlib import Path

path = Path('src/ui_manager.cpp')
text = path.read_text(encoding='utf-8')

old_layout = '''    } else if (model.overlay != UiOverlay::none) {
        const float scale = std::min(width * 0.94F / 1280.0F, height * 0.90F / 960.0F);
        const UiRect panel = {(width - 1280.0F * scale) * 0.5F, (height - 960.0F * scale) * 0.5F, 1280.0F * scale, 960.0F * scale};
        overlay_bounds_ = panel;
        const auto source_rect = [&](const float x, const float y, const float w, const float h) {
            return UiRect{panel.x + x * scale, panel.y + y * scale, w * scale, h * scale};
        };
        add_button(source_rect(1160.0F, 88.0F, 78.0F, 78.0F), "X", UiAction::close_modal);
        if (model.overlay == UiOverlay::administration) add_button(source_rect(926.0F, 820.0F, 286.0F, 72.0F), "RELATORIOS", UiAction::open_reports);
        if (model.overlay == UiOverlay::reports) add_button(source_rect(1010.0F, 876.0F, 216.0F, 64.0F), "VOLTAR", UiAction::open_administration);
    }
'''
new_layout = '''    } else if (model.overlay == UiOverlay::administration) {
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
'''
if old_layout not in text:
    raise SystemExit('old administration/reports layout block not found')
text = text.replace(old_layout, new_layout, 1)

old_render = '''        const SDL_FRect destination = {panel.x, panel.y, panel.width, panel.height};
        if (const UiThumbnail* artwork = thumbnail_for(renderer, ui_overlay_path(model_.overlay))) SDL_RenderTexture(renderer, artwork->texture, nullptr, &destination);
        else { draw_panel(renderer, panel); draw_text(renderer, panel.x + 24.0F, panel.y + 24.0F, "UI ARTWORK NOT FOUND", 255, 160, 130); }

        const float scale = panel.width / 1280.0F;
        const auto text_at = [&](const float x, const float y, const std::string& value, const Uint8 r = 232, const Uint8 g = 244, const Uint8 b = 248) {
            draw_text_fit(renderer, panel.x + x * scale, panel.y + y * scale, 210.0F * scale, value, r, g, b);
        };
        if (model_.overlay == UiOverlay::administration || model_.overlay == UiOverlay::reports) {
            text_at(520.0F, 338.0F, model_.monthly_revenue, 112, 238, 135);
            text_at(520.0F, 405.0F, model_.monthly_expenses, 255, 139, 139);
            text_at(520.0F, 470.0F, model_.monthly_balance, 122, 225, 250);
            text_at(900.0F, 340.0F, model_.population + " / " + model_.residential_capacity);
            text_at(92.0F, 650.0F, model_.power_demand + " / " + model_.power_capacity);
            text_at(330.0F, 852.0F, model_.administration_alerts, 188, 215, 228);
        }
'''
new_render = '''        if (model_.overlay == UiOverlay::administration) {
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
'''
if old_render not in text:
    raise SystemExit('old administration/reports render block not found')
text = text.replace(old_render, new_render, 1)

old_overlay_path = '''std::string ui_overlay_path(const UiOverlay overlay) {
    const char* base_path = SDL_GetBasePath();
    const std::filesystem::path root = base_path == nullptr ? std::filesystem::path(".") : std::filesystem::path(base_path);
    switch (overlay) {
        case UiOverlay::administration: return (root / "assets" / "ui" / "panels" / "administration_panel.png").string();
        case UiOverlay::reports: return (root / "assets" / "ui" / "panels" / "reports_panel.png").string();
        case UiOverlay::settings:
        case UiOverlay::save_load:
        case UiOverlay::pause:
        case UiOverlay::none: break;
    }
    return {};
}

'''
if old_overlay_path not in text:
    raise SystemExit('old ui_overlay_path block not found')
text = text.replace(old_overlay_path, '', 1)

path.write_text(text, encoding='utf-8')
