#include "semantic_renderer.h"
#include "map_renderer.h"
#include <algorithm>

namespace ch {

void SemanticRenderer::render_semantic_overlays(
    SDL_Renderer* renderer,
    const MapDocument& document,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const SemanticChannel active_channels,
    const float channel_opacity
) {
    if (renderer == nullptr || channel_opacity <= 0.001F) return;

    const Uint8 alpha = static_cast<Uint8>(std::clamp(channel_opacity, 0.0F, 1.0F) * 255.0F);

    // 1. Render Footprint & Occupancy Channels
    const bool show_footprint = (active_channels & (SemanticChannel::footprint | SemanticChannel::occupancy)) != SemanticChannel::none;
    if (show_footprint) {
        for (const auto& b : document.buildings()) {
            int w = 1;
            int h = 1;

            SDL_SetRenderDrawColor(renderer, 0, 230, 180, alpha);
            for (int dy = 0; dy < h; ++dy) {
                for (int dx = 0; dx < w; ++dx) {
                    MapRenderer::render_tile_outline(renderer, b.tile_x + dx, b.tile_y + dy, camera, viewport_width, viewport_height);
                }
            }
        }
    }

    // 2. Render Road / Infrastructure Channels
    const bool show_road = (active_channels & SemanticChannel::road) != SemanticChannel::none;
    if (show_road) {
        SDL_SetRenderDrawColor(renderer, 255, 170, 0, alpha);
        for (const auto& r : document.roads()) {
            MapRenderer::render_tile_outline(renderer, r.tile_x, r.tile_y, camera, viewport_width, viewport_height);
        }
    }

    // 3. Render Semantic Ground Anchors / Pivots
    const bool show_pivot = (active_channels & (SemanticChannel::pivot | SemanticChannel::connector)) != SemanticChannel::none;
    if (show_pivot) {
        SDL_SetRenderDrawColor(renderer, 0, 220, 255, alpha);
        for (const auto& b : document.buildings()) {
            int w = 1;
            int h = 1;

            const WorldPoint ground = building_visual_ground_world(b.tile_x, b.tile_y, w, h, camera.rotation);
            const ScreenPoint sp = world_to_screen_point(ground.x, ground.y, camera, viewport_width, viewport_height);

            // Draw crosshair at resolved ground anchor
            const float cross_size = 10.0F * camera.zoom;
            SDL_RenderLine(renderer, sp.x - cross_size, sp.y, sp.x + cross_size, sp.y);
            SDL_RenderLine(renderer, sp.x, sp.y - cross_size, sp.x, sp.y + cross_size);
        }
    }
}

} // namespace ch
