// First visual nine-slice pilot: only the construction catalog frame.
// This file is included inside GameplayUi::render after the legacy UI has
// rendered, so the existing procedural panel remains the fallback whenever the
// authored PNG is unavailable or invalid.
if (renderer != nullptr && model_.overlay == UiOverlay::none &&
    model_.build_panel_open && build_panel_bounds_) {
    const UiRect& panel = *build_panel_bounds_;
    const auto* skin = thumbnail_for(
        renderer, ui_chrome_path("panel_build_catalog_9slice_v1"));

    constexpr ch::ui::NineSliceInsets kInsets = {
        10.0F,
        10.0F,
        10.0F,
        10.0F,
    };
    constexpr float kMinimumSkinWidth = kInsets.left + kInsets.right;
    constexpr float kMinimumSkinHeight = kInsets.top + kInsets.bottom;

    if (skin != nullptr && skin->texture != nullptr &&
        skin->width >= kMinimumSkinWidth && skin->height >= kMinimumSkinHeight) {
        const SDL_FRect destination = {
            panel.x,
            panel.y,
            panel.width,
            panel.height,
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
