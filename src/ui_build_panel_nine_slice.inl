// Construction catalog uses the canonical CH_WINDOW_FRAME_V2 contract. The
// procedural SDL panel remains underneath as a safe fallback/background.
if (renderer != nullptr && model_.overlay == UiOverlay::none &&
    model_.build_panel_open && build_panel_bounds_) {
    const UiRect& panel = *build_panel_bounds_;
    const auto* skin = thumbnail_for(
        renderer, ui_chrome_path(ch::ui::kWindowFrameV2AssetStem));

    if (skin != nullptr && skin->texture != nullptr &&
        skin->width >= ch::ui::kWindowFrameV2MinimumWidth &&
        skin->height >= ch::ui::kWindowFrameV2MinimumHeight) {
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
            ch::ui::kWindowFrameV2Insets);
    }
}
