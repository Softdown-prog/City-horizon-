from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    assert count == 1, f"{label} drifted: expected 1, found {count}"
    return text.replace(old, new, 1)

# Canonical MapRenderer sidewalk contract and implementation.
header = Path("src/ch_render/map_renderer.h")
text = header.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    static void render_sidewalks(SDL_Renderer* renderer, const SidewalkManager& sidewalks,
                                const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                const std::filesystem::path& asset_root, const CameraState& camera,
                                float viewport_width, float viewport_height);''',
    '''    static void render_sidewalks(SDL_Renderer* renderer, const SidewalkManager& sidewalks,
                                const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                const std::filesystem::path& asset_root, const CameraState& camera,
                                float viewport_width, float viewport_height,
                                const MapDocument* document = nullptr);''',
    "canonical sidewalk declaration",
)
header.write_text(text, encoding="utf-8")

cpp = Path("src/ch_render/map_renderer.cpp")
text = cpp.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''void MapRenderer::render_sidewalks(SDL_Renderer* renderer, const SidewalkManager& sidewalks,
                                  const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                  const std::filesystem::path& asset_root, const CameraState& camera,
                                  const float viewport_width, const float viewport_height) {''',
    '''void MapRenderer::render_sidewalks(SDL_Renderer* renderer, const SidewalkManager& sidewalks,
                                  const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                  const std::filesystem::path& asset_root, const CameraState& camera,
                                  const float viewport_width, const float viewport_height,
                                  const MapDocument* document) {''',
    "canonical sidewalk definition",
)
old_draw = '''        if (const TextureAsset* texture = find_texture(asset_root / sidewalk_sprite(tile.style_id, visual_connections))) {
            const WorldPoint visual_top = tile_visual_top_world(tile.tile_x, tile.tile_y, camera.rotation);
            const ScreenPoint top = world_to_screen_point(visual_top.x, visual_top.y, camera, viewport_width, viewport_height);
            const float scale = (kTileWidth / texture->source_width) * camera.zoom;
            const SDL_FRect dst{top.x - texture->source_width * scale * 0.5F, top.y, texture->source_width * scale, texture->source_height * scale};
            SDL_RenderTexture(renderer, texture->texture, nullptr, &dst);
        }'''
new_draw = '''        if (const TextureAsset* texture = find_texture(asset_root / sidewalk_sprite(tile.style_id, visual_connections))) {
            if (document != nullptr) {
                render_heightfield_terrain_tile(renderer, *texture, tile.tile_x, tile.tile_y, *document,
                                                camera, viewport_width, viewport_height, false);
            } else {
                const WorldPoint visual_top = tile_visual_top_world(tile.tile_x, tile.tile_y, camera.rotation);
                const ScreenPoint top = world_to_screen_point(visual_top.x, visual_top.y, camera, viewport_width, viewport_height);
                const float scale = (kTileWidth / texture->source_width) * camera.zoom;
                const SDL_FRect dst{top.x - texture->source_width * scale * 0.5F, top.y, texture->source_width * scale, texture->source_height * scale};
                SDL_RenderTexture(renderer, texture->texture, nullptr, &dst);
            }
        }'''
text = replace_once(text, old_draw, new_draw, "canonical sidewalk draw")
cpp.write_text(text, encoding="utf-8")

# Runtime facade: preserve culling but project sidewalk sprites onto the document heightfield.
runtime = Path("src/runtime_map_renderer.h")
text = runtime.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    static void render_sidewalks(SDL_Renderer* renderer, const SidewalkManager& sidewalks,
                                 const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                 const std::filesystem::path& asset_root, const CameraState& camera,
                                 const float viewport_width, const float viewport_height) {''',
    '''    static void render_sidewalks(SDL_Renderer* renderer, const SidewalkManager& sidewalks,
                                 const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                                 const std::filesystem::path& asset_root, const CameraState& camera,
                                 const float viewport_width, const float viewport_height,
                                 const MapDocument* document = nullptr) {''',
    "runtime sidewalk signature",
)
old_runtime_draw = '''            if (const TextureAsset* texture = find_texture(
                    asset_root / runtime_render_detail::sidewalk_sprite(tile.style_id, connections))) {
                const WorldPoint visual_top = tile_visual_top_world(tile.tile_x, tile.tile_y, camera.rotation);
                const ScreenPoint top = world_to_screen_point(visual_top.x, visual_top.y, camera,
                                                              viewport_width, viewport_height);
                const float scale = (static_cast<float>(contracts::kTileWidth) / texture->source_width) * camera.zoom;
                const SDL_FRect destination = {'''
new_runtime_draw = '''            if (const TextureAsset* texture = find_texture(
                    asset_root / runtime_render_detail::sidewalk_sprite(tile.style_id, connections))) {
                if (document != nullptr) {
                    MapRenderer::render_heightfield_terrain_tile(renderer, *texture, tile.tile_x, tile.tile_y,
                                                                *document, camera, viewport_width, viewport_height, false);
                    return;
                }
                const WorldPoint visual_top = tile_visual_top_world(tile.tile_x, tile.tile_y, camera.rotation);
                const ScreenPoint top = world_to_screen_point(visual_top.x, visual_top.y, camera,
                                                              viewport_width, viewport_height);
                const float scale = (static_cast<float>(contracts::kTileWidth) / texture->source_width) * camera.zoom;
                const SDL_FRect destination = {'''
text = replace_once(text, old_runtime_draw, new_runtime_draw, "runtime sidewalk draw")
runtime.write_text(text, encoding="utf-8")

# Game wrappers: pass active document to sidewalks and crosswalks.
main = Path("src/main_runtime_impl.cpp")
text = main.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''void render_sidewalks(SDL_Renderer* renderer, const SidewalkManager& sidewalks, const TextureCache& textures,
                      const std::filesystem::path& root, const Camera& camera, float vw, float vh) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_sidewalks(renderer, sidewalks,
                                     [&textures](const std::filesystem::path& p) { return textures.find(p); },
                                     root, cs, vw, vh);
}''',
    '''void render_sidewalks(SDL_Renderer* renderer, const SidewalkManager& sidewalks, const TextureCache& textures,
                      const std::filesystem::path& root, const Camera& camera, float vw, float vh,
                      const ch::MapDocument* document) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_sidewalks(renderer, sidewalks,
                                     [&textures](const std::filesystem::path& p) { return textures.find(p); },
                                     root, cs, vw, vh, document);
}''',
    "main sidewalk wrapper",
)
text = replace_once(
    text,
    '''void render_crosswalks(SDL_Renderer* renderer, const CrosswalkManager& crosswalks,
                       TextureCache& textures, const std::filesystem::path& asset_root,
                       const Camera& camera, const float viewport_width, const float viewport_height) {''',
    '''void render_crosswalks(SDL_Renderer* renderer, const CrosswalkManager& crosswalks,
                       TextureCache& textures, const std::filesystem::path& asset_root,
                       const Camera& camera, const float viewport_width, const float viewport_height,
                       const ch::MapDocument* document) {''',
    "main crosswalk signature",
)
text = replace_once(
    text,
    '''        if (texture != nullptr) {
            ch::MapRenderer::render_road_sprite(renderer, *texture, portal.tile_x, portal.tile_y,
                                                cs, viewport_width, viewport_height);
        }''',
    '''        if (texture != nullptr) {
            if (document != nullptr) {
                ch::MapRenderer::render_heightfield_terrain_tile(renderer, *texture, portal.tile_x, portal.tile_y,
                                                                 *document, cs, viewport_width, viewport_height, false);
            } else {
                ch::MapRenderer::render_road_sprite(renderer, *texture, portal.tile_x, portal.tile_y,
                                                    cs, viewport_width, viewport_height);
            }
        }''',
    "crosswalk draw",
)
text = replace_once(
    text,
    '''        render_crosswalks(renderer, crosswalk_runtime::crosswalks(), textures, asset_root, camera,
                          static_cast<float>(viewport_width), static_cast<float>(viewport_height));
        render_sidewalks(renderer, sidewalks, textures, asset_root, camera, static_cast<float>(viewport_width), static_cast<float>(viewport_height));''',
    '''        render_crosswalks(renderer, crosswalk_runtime::crosswalks(), textures, asset_root, camera,
                          static_cast<float>(viewport_width), static_cast<float>(viewport_height),
                          active_map_doc ? &*active_map_doc : nullptr);
        render_sidewalks(renderer, sidewalks, textures, asset_root, camera,
                         static_cast<float>(viewport_width), static_cast<float>(viewport_height),
                         active_map_doc ? &*active_map_doc : nullptr);''',
    "ground overlay render calls",
)
main.write_text(text, encoding="utf-8")
