// First visual nine-slice pilot: only the construction catalog frame.
// This file is included inside GameplayUi::render after the legacy UI has
// rendered, so the transparent center preserves the existing panel/content as
// a visual fallback while the authored frame proves the nine-slice path.
if (renderer != nullptr && model_.overlay == UiOverlay::none &&
    model_.build_panel_open && build_panel_bounds_) {
    const UiRect& panel = *build_panel_bounds_;
    const auto* skin = thumbnail_for(
        renderer, ui_chrome_path("panel_build_catalog_9slice_v1"));
    if (skin != nullptr && skin->texture != nullptr) {
        const SDL_FRect destination = {
            panel.x,
            panel.y,
            panel.width,
            panel.height,
        };
        constexpr ch::ui::NineSliceInsets kInsets = {
            10.0F,
            10.0F,
            10.0F,
            10.0F,
        };
        (void)ch::ui::render_nine_slice(
            renderer,
            skin->texture,
            skin->width,
            skin->height,
            destination,
            kInsets);
    }
}
