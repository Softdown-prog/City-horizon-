from pathlib import Path

path = Path('src/ui_manager.cpp')
text = path.read_text(encoding='utf-8')

old = '''void draw_bakery_service_icon(SDL_Renderer* renderer, const UiRect& bounds) {
    const SDL_FRect background = {bounds.x, bounds.y, bounds.width, bounds.height};
    SDL_SetRenderDrawColor(renderer, 26, 52, 64, SDL_ALPHA_OPAQUE);
    SDL_RenderFillRect(renderer, &background);
    SDL_SetRenderDrawColor(renderer, 68, 111, 130, SDL_ALPHA_OPAQUE);
    SDL_RenderRect(renderer, &background);

    const SDL_FRect loaf = {bounds.x + 7.0F, bounds.y + 11.0F, 28.0F, 22.0F};
    SDL_SetRenderDrawColor(renderer, 211, 163, 88, SDL_ALPHA_OPAQUE);
    SDL_RenderFillRect(renderer, &loaf);
    SDL_SetRenderDrawColor(renderer, 245, 208, 139, SDL_ALPHA_OPAQUE);
    SDL_RenderLine(renderer, loaf.x + 7.0F, loaf.y + 4.0F, loaf.x + 3.0F, loaf.y + 12.0F);
    SDL_RenderLine(renderer, loaf.x + 16.0F, loaf.y + 4.0F, loaf.x + 12.0F, loaf.y + 12.0F);
    SDL_RenderLine(renderer, loaf.x + 25.0F, loaf.y + 4.0F, loaf.x + 21.0F, loaf.y + 12.0F);

    const SDL_FRect sweet = {bounds.x + 34.0F, bounds.y + 29.0F, 12.0F, 12.0F};
    SDL_SetRenderDrawColor(renderer, 220, 126, 151, SDL_ALPHA_OPAQUE);
    SDL_RenderFillRect(renderer, &sweet);
    SDL_SetRenderDrawColor(renderer, 248, 193, 207, SDL_ALPHA_OPAQUE);
    SDL_RenderLine(renderer, sweet.x - 5.0F, sweet.y + 2.0F, sweet.x, sweet.y + 6.0F);
    SDL_RenderLine(renderer, sweet.x - 5.0F, sweet.y + 10.0F, sweet.x, sweet.y + 6.0F);
    SDL_RenderLine(renderer, sweet.x + sweet.w, sweet.y + 6.0F, sweet.x + sweet.w + 5.0F, sweet.y + 2.0F);
    SDL_RenderLine(renderer, sweet.x + sweet.w, sweet.y + 6.0F, sweet.x + sweet.w + 5.0F, sweet.y + 10.0F);
}

'''
if old not in text:
    raise SystemExit('old procedural bakery icon block not found')
text = text.replace(old, '', 1)

old = '''std::string ui_icon_path(const char* icon_name) {
    const char* base_path = SDL_GetBasePath();
    const std::filesystem::path root = base_path == nullptr ? std::filesystem::path(".") : std::filesystem::path(base_path);
    return (root / "assets" / "ui" / "icons" / (std::string(icon_name) + ".png")).string();
}
'''
new = old + '''\nstd::string ui_service_icon_path(const char* icon_name) {
    const char* base_path = SDL_GetBasePath();
    const std::filesystem::path root = base_path == nullptr ? std::filesystem::path(".") : std::filesystem::path(base_path);
    return (root / "assets" / "ui" / "icons" / "service" / (std::string(icon_name) + ".png")).string();
}
'''
if old not in text:
    raise SystemExit('ui_icon_path block not found')
text = text.replace(old, new, 1)

old = '''        const float service_height = item.has_service_pricing ? 176.0F : 0.0F;'''
new = '''        const float service_height = item.has_service_pricing ? 218.0F : 0.0F;'''
if old not in text:
    raise SystemExit('service height block not found')
text = text.replace(old, new, 1)

old = '''    const auto draw_ui_icon = [&](const char* name, const SDL_FRect& bounds) {
        if (const UiThumbnail* icon = thumbnail_for(renderer, ui_icon_path(name))) {
            const float scale = std::min(bounds.w / icon->width, bounds.h / icon->height);
            const SDL_FRect destination = {bounds.x + (bounds.w - icon->width * scale) * 0.5F, bounds.y + (bounds.h - icon->height * scale) * 0.5F, icon->width * scale, icon->height * scale};
            SDL_RenderTexture(renderer, icon->texture, nullptr, &destination);
        }
    };
'''
new = old + '''    const auto draw_service_icon = [&](const char* name, const SDL_FRect& bounds) {
        if (const UiThumbnail* icon = thumbnail_for(renderer, ui_service_icon_path(name))) {
            const float scale = std::min(bounds.w / icon->width, bounds.h / icon->height);
            const SDL_FRect destination = {bounds.x + (bounds.w - icon->width * scale) * 0.5F,
                                           bounds.y + (bounds.h - icon->height * scale) * 0.5F,
                                           icon->width * scale, icon->height * scale};
            SDL_RenderTexture(renderer, icon->texture, nullptr, &destination);
        }
    };
'''
if old not in text:
    raise SystemExit('draw_ui_icon block not found')
text = text.replace(old, new, 1)

old = '''        float detail_y = 198.0F;
        if (item.has_service_pricing) {
            const UiRect service_icon = {panel_x + 12.0F, 196.0F, 54.0F, 54.0F};
            draw_bakery_service_icon(renderer, service_icon);
            draw_text_fit(renderer, panel_x + 78.0F, 197.0F, 238.0F, "VENDE: " + item.service_name, 236, 223, 184);
            draw_text_fit(renderer, panel_x + 78.0F, 214.0F, 238.0F, "PRECO AO CLIENTE", 164, 193, 205);
            draw_text_centered_fit(renderer, {panel_x + 232.0F, 227.0F, 46.0F, 24.0F}, 235.0F, item.service_price,
                                   238, 246, 249);
            draw_text_fit(renderer, panel_x + 78.0F, 258.0F, 238.0F, item.service_price_range, 118, 151, 166);
            draw_text_fit(renderer, panel_x + 78.0F, 278.0F, 238.0F, "DEMANDA PELO PRECO: " + item.service_price_demand, 202, 219, 227);
            draw_text_fit(renderer, panel_x + 78.0F, 296.0F, 238.0F, "CLIENTES / MES: " + item.service_customers_per_month, 202, 219, 227);
            draw_text_fit(renderer, panel_x + 78.0F, 314.0F, 238.0F, "RECEITA VENDAS: " + item.service_revenue_per_month, 181, 221, 154);
            draw_text_fit(renderer, panel_x + 78.0F, 332.0F, 238.0F, "RESULTADO: " + item.service_net_per_month, 137, 226, 242);
            draw_text_fit(renderer, panel_x + 78.0F, 350.0F, 238.0F, item.service_supply_status,
                          item.service_supply_status.find("100%") != std::string::npos ? 181 : 255,
                          item.service_supply_status.find("100%") != std::string::npos ? 221 : 188,
                          item.service_supply_status.find("100%") != std::string::npos ? 154 : 128);
            detail_y = 375.0F;
        }
'''
new = '''        float detail_y = 198.0F;
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
'''
if old not in text:
    raise SystemExit('service pricing render block not found')
text = text.replace(old, new, 1)

path.write_text(text, encoding='utf-8')
