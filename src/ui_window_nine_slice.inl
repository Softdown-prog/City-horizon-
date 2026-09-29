// Reusable nine-slice window frame for the first modal migration stage.
// The existing procedural panel stays underneath as the fallback/background;
// this pass only replaces the authored chrome around supported windows.
if (renderer != nullptr && overlay_bounds_ &&
    (model_.overlay == UiOverlay::pause ||
     model_.overlay == UiOverlay::settings ||
     model_.overlay == UiOverlay::administration)) {
    const UiRect& panel = *overlay_bounds_;
    const auto* skin = thumbnail_for(
        renderer, ui_chrome_path("panel_window_9slice_v2"));

    constexpr ch::ui::NineSliceInsets kWindowInsets = {
        32.0F,
        32.0F,
        32.0F,
        32.0F,
    };
    constexpr float kMinimumWindowSkinWidth =
        kWindowInsets.left + kWindowInsets.right;
    constexpr float kMinimumWindowSkinHeight =
        kWindowInsets.top + kWindowInsets.bottom;

    if (skin != nullptr && skin->texture != nullptr &&
        skin->width >= kMinimumWindowSkinWidth &&
        skin->height >= kMinimumWindowSkinHeight) {
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
            kWindowInsets);
    }
}
