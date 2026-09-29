// Construction-catalog nine-slice pilot V2. The frame is now the same reusable
// window skin used by the first modal migration stage. The procedural SDL panel
// remains underneath as a safe fallback/background.
if (renderer != nullptr && model_.overlay == UiOverlay::none &&
    model_.build_panel_open && build_panel_bounds_) {
    const UiRect& panel = *build_panel_bounds_;
    const auto* skin = thumbnail_for(
        renderer, ui_chrome_path("panel_window_9slice_v2"));

    constexpr ch::ui::NineSliceInsets kInsets = {
        32.0F,
        32.0F,
        32.0F,
        32.0F,
    };
    constexpr float kMinimumSkinWidth = kInsets.left + kInsets.right;
    constexpr float kMinimumSkinHeight = kInsets.top + kInsets.bottom;

    if (skin != nullptr && skin->texture != nullptr &&
        skin->width >= kMinimumSkinWidth && skin->height >= kMinimumSkinHeight) {
        // Preserve the supplied pixel-art character of the frame instead of
        // adding another linear-filtering pass while the 9 slices are scaled.
        SDL_SetTextureScaleMode(skin->texture, SDL_SCALEMODE_NEAREST);

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
