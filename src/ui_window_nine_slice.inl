// CH_WINDOW_FRAME_V2 is the canonical resizable-window frame for City Horizon.
// The existing procedural panel stays underneath as the fallback/background;
// this pass only replaces the authored chrome around supported windows.
if (renderer != nullptr && overlay_bounds_ &&
    (model_.overlay == UiOverlay::pause ||
     model_.overlay == UiOverlay::settings ||
     model_.overlay == UiOverlay::administration ||
     model_.overlay == UiOverlay::reports ||
     model_.overlay == UiOverlay::main_menu ||
     model_.overlay == UiOverlay::save_load ||
     model_.overlay == UiOverlay::quit_confirm)) {
    const UiRect& panel = *overlay_bounds_;
    const auto* skin = thumbnail_for(
        renderer, ui_chrome_path(ch::ui::kWindowFrameV2AssetStem));

    if (skin != nullptr && skin->texture != nullptr &&
        skin->width >= ch::ui::kWindowFrameV2MinimumWidth &&
        skin->height >= ch::ui::kWindowFrameV2MinimumHeight) {
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
