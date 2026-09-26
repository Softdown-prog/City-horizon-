#ifndef CITY_HORIZON_CH_CORE_MAP_DOCUMENT_H
#define CITY_HORIZON_CH_CORE_MAP_DOCUMENT_H

#include "src/ch_core/grid.h"
#include <string>
#include <vector>
#include <optional>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <cstdint>

namespace ch {

struct TerrainTileEntry {
    int tile_x = 0;
    int tile_y = 0;
    std::string texture;
    // Declarative gameplay authority. Texture remains a renderer cache only.
    std::string terrain_definition;
};

struct BuildingInstanceEntry {
    std::size_t instance_id = 0;
    std::string definition_id;
    int tile_x = 0;
    int tile_y = 0;
    int rotation = 0;
};

struct RoadTileEntry {
    int tile_x = 0;
    int tile_y = 0;
};

class MapDocument {
public:
    explicit MapDocument(std::string raw_json_content);

    [[nodiscard]] const std::string& raw_content() const { return raw_content_; }

    [[nodiscard]] const std::vector<TerrainTileEntry>& terrain_tiles() const { return cached_terrain_; }
    [[nodiscard]] const std::vector<BuildingInstanceEntry>& buildings() const { return cached_buildings_; }
    [[nodiscard]] const std::vector<RoadTileEntry>& roads() const { return cached_roads_; }

    [[nodiscard]] std::optional<TerrainTileEntry> get_terrain_at(int tile_x, int tile_y) const;
    [[nodiscard]] std::optional<BuildingInstanceEntry> get_building_at(int tile_x, int tile_y) const;
    [[nodiscard]] bool is_road_at(int tile_x, int tile_y) const;

    void set_terrain_texture_at(int tile_x, int tile_y, const std::string& texture_path);
    void set_terrain_definition_at(int tile_x, int tile_y, const std::string& terrain_def_id, const std::string& texture_path = "");
    // Gameplay brush: an empty texture means the implicit grass tile.
    void paint_terrain_at(int tile_x, int tile_y, const std::string& terrain_def_id, const std::string& texture_path);

    [[nodiscard]] static std::optional<MapDocument> load_from_file(const std::string& filepath);
    static MapDocument create_empty(const std::string& name = "Untitled City", int width = 32, int height = 32);

private:
    void parse_all();
    static uint64_t pack_key(int x, int y) {
        return (static_cast<uint64_t>(x) << 32) | (static_cast<uint64_t>(y) & 0xFFFFFFFFULL);
    }

    std::string raw_content_;
    std::vector<TerrainTileEntry> cached_terrain_;
    std::vector<BuildingInstanceEntry> cached_buildings_;
    std::vector<RoadTileEntry> cached_roads_;

    std::unordered_map<uint64_t, std::size_t> terrain_index_;
    std::unordered_map<uint64_t, std::size_t> building_index_;
    std::unordered_set<uint64_t> road_index_;
};

} // namespace ch

#endif // CITY_HORIZON_CH_CORE_MAP_DOCUMENT_H
