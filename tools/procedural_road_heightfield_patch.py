from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    assert count == 1, f"{label} drifted: expected 1, found {count}"
    return text.replace(old, new, 1)

# 1) Shared procedural road renderer: project XY geometry through terrain height.
network = Path("src/ch_render/procedural_road_network_renderer.h")
text = network.read_text(encoding="utf-8")
text = replace_once(
    text,
    '#include "src/ch_core/projection.h"\n',
    '#include "src/ch_core/projection.h"\n#include "src/ch_core/terrain_projection.h"\n',
    "terrain projection include",
)
text = replace_once(
    text,
    '''[[nodiscard]] inline bool render_procedural_road_2d_mesh(
    SDL_Renderer* renderer,
    const ProceduralRoad2DMesh& mesh,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const ProceduralRoad2DRenderStyle& style = {}) {''',
    '''[[nodiscard]] inline bool render_procedural_road_2d_mesh(
    SDL_Renderer* renderer,
    const ProceduralRoad2DMesh& mesh,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const ProceduralRoad2DRenderStyle& style = {},
    const TerrainHeightField* heightfield = nullptr) {''',
    "procedural mesh signature",
)
text = replace_once(
    text,
    '''        const ScreenPoint screen = world_to_screen_point(
            source.position.x, source.position.y,
            camera, viewport_width, viewport_height);''',
    '''        const ScreenPoint screen = heightfield != nullptr
            ? terrain_world_to_screen_point(source.position.x, source.position.y, *heightfield,
                                            camera, viewport_width, viewport_height)
            : world_to_screen_point(source.position.x, source.position.y,
                                    camera, viewport_width, viewport_height);''',
    "procedural mesh projection",
)
text = replace_once(
    text,
    '''[[nodiscard]] inline bool render_procedural_road_center_markings(
    SDL_Renderer* renderer,
    const ProceduralRoadGraph& graph,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height) {''',
    '''[[nodiscard]] inline bool render_procedural_road_center_markings(
    SDL_Renderer* renderer,
    const ProceduralRoadGraph& graph,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const TerrainHeightField* heightfield = nullptr) {''',
    "center marking signature",
)
text = replace_once(
    text,
    '''            const ScreenPoint screen_a = world_to_screen_point(
                point_a.x, point_a.y, camera, viewport_width, viewport_height);
            const ScreenPoint screen_b = world_to_screen_point(
                point_b.x, point_b.y, camera, viewport_width, viewport_height);''',
    '''            const ScreenPoint screen_a = heightfield != nullptr
                ? terrain_world_to_screen_point(point_a.x, point_a.y, *heightfield,
                                                camera, viewport_width, viewport_height)
                : world_to_screen_point(point_a.x, point_a.y, camera, viewport_width, viewport_height);
            const ScreenPoint screen_b = heightfield != nullptr
                ? terrain_world_to_screen_point(point_b.x, point_b.y, *heightfield,
                                                camera, viewport_width, viewport_height)
                : world_to_screen_point(point_b.x, point_b.y, camera, viewport_width, viewport_height);''',
    "center marking projection",
)
text = replace_once(
    text,
    '''[[nodiscard]] inline bool render_procedural_road_ground_plan(
    SDL_Renderer* renderer,
    const ProceduralRoadGroundRenderPlan& plan,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const ProceduralRoad2DRenderStyle& style = {}) {''',
    '''[[nodiscard]] inline bool render_procedural_road_ground_plan(
    SDL_Renderer* renderer,
    const ProceduralRoadGroundRenderPlan& plan,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const ProceduralRoad2DRenderStyle& style = {},
    const TerrainHeightField* heightfield = nullptr) {''',
    "ground plan signature",
)
old_call = '''                renderer, mesh, camera, viewport_width, viewport_height, style))'''
new_call = '''                renderer, mesh, camera, viewport_width, viewport_height, style, heightfield))'''
assert text.count(old_call) == 1, f"segment mesh call drifted: {text.count(old_call)}"
text = text.replace(old_call, new_call, 1)
old_patch_call = '''                renderer, patch, camera, viewport_width, viewport_height, style))'''
new_patch_call = '''                renderer, patch, camera, viewport_width, viewport_height, style, heightfield))'''
assert text.count(old_patch_call) == 1, f"junction mesh call drifted: {text.count(old_patch_call)}"
text = text.replace(old_patch_call, new_patch_call, 1)
network.write_text(text, encoding="utf-8")

# 2) Runtime culling/markings: same terrain-aware projection for visible dashes.
culling = Path("src/runtime_procedural_road_culling.h")
text = culling.read_text(encoding="utf-8")
text = replace_once(
    text,
    '#include "src/ch_core/projection.h"\n',
    '#include "src/ch_core/projection.h"\n#include "src/ch_core/terrain_projection.h"\n',
    "runtime culling terrain include",
)
text = replace_once(
    text,
    '''[[nodiscard]] inline bool render_visible_procedural_road_center_markings(
    SDL_Renderer* renderer,
    const ProceduralRoadPlacementBridge& bridge,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const ProceduralRoad2DWorldBounds& bounds) {''',
    '''[[nodiscard]] inline bool render_visible_procedural_road_center_markings(
    SDL_Renderer* renderer,
    const ProceduralRoadPlacementBridge& bridge,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const ProceduralRoad2DWorldBounds& bounds,
    const TerrainHeightField* heightfield = nullptr) {''',
    "visible marking signature",
)
text = replace_once(
    text,
    '''            const ScreenPoint screen_a = world_to_screen_point(
                point_a.x, point_a.y, camera, viewport_width, viewport_height);
            const ScreenPoint screen_b = world_to_screen_point(
                point_b.x, point_b.y, camera, viewport_width, viewport_height);''',
    '''            const ScreenPoint screen_a = heightfield != nullptr
                ? terrain_world_to_screen_point(point_a.x, point_a.y, *heightfield,
                                                camera, viewport_width, viewport_height)
                : world_to_screen_point(point_a.x, point_a.y, camera, viewport_width, viewport_height);
            const ScreenPoint screen_b = heightfield != nullptr
                ? terrain_world_to_screen_point(point_b.x, point_b.y, *heightfield,
                                                camera, viewport_width, viewport_height)
                : world_to_screen_point(point_b.x, point_b.y, camera, viewport_width, viewport_height);''',
    "visible marking projection",
)
culling.write_text(text, encoding="utf-8")

# 3) Runtime promotion bridge: carry terrain heightfield into asphalt + markings.
runtime_proc = Path("src/runtime_procedural_road_renderer.h")
text = runtime_proc.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''[[nodiscard]] inline bool try_render_procedural_roads_runtime(
    SDL_Renderer* renderer,
    const RoadManager& roads,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height) {''',
    '''[[nodiscard]] inline bool try_render_procedural_roads_runtime(
    SDL_Renderer* renderer,
    const RoadManager& roads,
    const CameraState& camera,
    const float viewport_width,
    const float viewport_height,
    const TerrainHeightField* heightfield = nullptr) {''',
    "runtime procedural road signature",
)
text = replace_once(
    text,
    '''    if (!render_procedural_road_ground_plan(
            renderer, plan, camera, viewport_width, viewport_height)) {''',
    '''    if (!render_procedural_road_ground_plan(
            renderer, plan, camera, viewport_width, viewport_height, {}, heightfield)) {''',
    "runtime ground plan call",
)
text = replace_once(
    text,
    '''    (void)render_visible_procedural_road_center_markings(
        renderer, mirror, camera, viewport_width, viewport_height, visible_bounds);''',
    '''    (void)render_visible_procedural_road_center_markings(
        renderer, mirror, camera, viewport_width, viewport_height, visible_bounds, heightfield);''',
    "runtime visible markings call",
)
runtime_proc.write_text(text, encoding="utf-8")

# 4) Runtime map facade: explicitly accept MapDocument and terrain-deform fallback tiles too.
runtime_map = Path("src/runtime_map_renderer.h")
text = runtime_map.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    static void render_roads(SDL_Renderer* renderer, const RoadManager& roads,
                             const RoadVisualCatalog& visuals,
                             const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                             const std::filesystem::path& asset_root, const CameraState& camera,
                             const float viewport_width, const float viewport_height) {''',
    '''    static void render_roads(SDL_Renderer* renderer, const RoadManager& roads,
                             const RoadVisualCatalog& visuals,
                             const std::function<const TextureAsset*(const std::filesystem::path&)>& find_texture,
                             const std::filesystem::path& asset_root, const CameraState& camera,
                             const float viewport_width, const float viewport_height,
                             const MapDocument* document = nullptr) {''',
    "runtime map road signature",
)
text = replace_once(
    text,
    '''        if (try_render_procedural_roads_runtime(
                renderer, roads, camera, viewport_width, viewport_height)) {''',
    '''        const TerrainHeightField* heightfield = document == nullptr
            ? nullptr : &document->terrain_heightfield();
        if (try_render_procedural_roads_runtime(
                renderer, roads, camera, viewport_width, viewport_height, heightfield)) {''',
    "runtime procedural road bridge call",
)
text = replace_once(
    text,
    '''        constexpr SDL_FColor kRoadAsphalt = {52.0F / 255.0F, 57.0F / 255.0F, 60.0F / 255.0F, 1.0F};
        for (const RoadTile* tile : visible_tiles) {
            MapRenderer::render_tile_fill(renderer, tile->tile_x, tile->tile_y, camera,
                                          viewport_width, viewport_height, kRoadAsphalt);
        }''',
    '''        constexpr SDL_FColor kRoadAsphalt = {52.0F / 255.0F, 57.0F / 255.0F, 60.0F / 255.0F, 1.0F};
        for (const RoadTile* tile : visible_tiles) {
            if (document != nullptr) {
                MapRenderer::render_heightfield_tile_fill(renderer, tile->tile_x, tile->tile_y, *document,
                                                          camera, viewport_width, viewport_height, kRoadAsphalt);
            } else {
                MapRenderer::render_tile_fill(renderer, tile->tile_x, tile->tile_y, camera,
                                              viewport_width, viewport_height, kRoadAsphalt);
            }
        }''',
    "runtime road fallback underlay",
)
text = replace_once(
    text,
    '''            if (texture != nullptr) {
                MapRenderer::render_road_sprite(renderer, *texture, tile->tile_x, tile->tile_y,
                                                camera, viewport_width, viewport_height);
            } else {
                MapRenderer::render_road_tile(renderer, tile->tile_x, tile->tile_y, camera,
                    viewport_width, viewport_height,
                    runtime_render_detail::road_placeholder_color(roads.visual_type(tile->tile_x, tile->tile_y)));
            }''',
    '''            if (texture != nullptr) {
                if (document != nullptr) {
                    MapRenderer::render_heightfield_terrain_tile(renderer, *texture, tile->tile_x, tile->tile_y,
                                                                *document, camera, viewport_width, viewport_height, false);
                } else {
                    MapRenderer::render_road_sprite(renderer, *texture, tile->tile_x, tile->tile_y,
                                                    camera, viewport_width, viewport_height);
                }
            } else {
                const SDL_FColor placeholder = runtime_render_detail::road_placeholder_color(
                    roads.visual_type(tile->tile_x, tile->tile_y));
                if (document != nullptr) {
                    MapRenderer::render_heightfield_tile_fill(renderer, tile->tile_x, tile->tile_y, *document,
                                                              camera, viewport_width, viewport_height, placeholder);
                } else {
                    MapRenderer::render_road_tile(renderer, tile->tile_x, tile->tile_y, camera,
                                                  viewport_width, viewport_height, placeholder);
                }
            }''',
    "runtime road fallback texture",
)
runtime_map.write_text(text, encoding="utf-8")

# 5) Game loop: pass active MapDocument explicitly to the runtime road facade.
main_impl = Path("src/main_runtime_impl.cpp")
text = main_impl.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''void render_roads(SDL_Renderer* renderer, const RoadManager& roads, const RoadVisualCatalog& visuals,
                  const TextureCache& textures, const std::filesystem::path& asset_root, const Camera& camera,
                  float viewport_width, float viewport_height) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_roads(renderer, roads, visuals,
                                  [&textures](const std::filesystem::path& p) { return textures.find(p); },
                                  asset_root, cs, viewport_width, viewport_height);
}''',
    '''void render_roads(SDL_Renderer* renderer, const RoadManager& roads, const RoadVisualCatalog& visuals,
                  const TextureCache& textures, const std::filesystem::path& asset_root, const Camera& camera,
                  float viewport_width, float viewport_height, const ch::MapDocument* document) {
    const ch::CameraState cs{camera.pan_x, camera.pan_y, camera.zoom, static_cast<ch::CameraRotation>(camera.rotation)};
    ch::MapRenderer::render_roads(renderer, roads, visuals,
                                  [&textures](const std::filesystem::path& p) { return textures.find(p); },
                                  asset_root, cs, viewport_width, viewport_height, document);
}''',
    "game render_roads wrapper",
)
text = replace_once(
    text,
    '''        render_roads(renderer, roads, road_visuals, textures, asset_root, camera,
                     static_cast<float>(viewport_width), static_cast<float>(viewport_height));''',
    '''        render_roads(renderer, roads, road_visuals, textures, asset_root, camera,
                     static_cast<float>(viewport_width), static_cast<float>(viewport_height),
                     active_map_doc ? &*active_map_doc : nullptr);''',
    "game road render call",
)
main_impl.write_text(text, encoding="utf-8")
