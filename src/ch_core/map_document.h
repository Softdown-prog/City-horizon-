#ifndef CITY_HORIZON_CH_CORE_MAP_DOCUMENT_H
#define CITY_HORIZON_CH_CORE_MAP_DOCUMENT_H

#include "src/ch_core/grid.h"
#include <string>
#include <vector>
#include <optional>
#include <string_view>

namespace ch {

struct TerrainTileEntry {
    int tile_x = 0;
    int tile_y = 0;
    std::string texture;
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

    [[nodiscard]] std::vector<TerrainTileEntry> terrain_tiles() const;
    [[nodiscard]] std::vector<BuildingInstanceEntry> buildings() const;
    [[nodiscard]] std::vector<RoadTileEntry> roads() const;

    [[nodiscard]] std::optional<TerrainTileEntry> get_terrain_at(int tile_x, int tile_y) const;
    [[nodiscard]] std::optional<BuildingInstanceEntry> get_building_at(int tile_x, int tile_y) const;
    [[nodiscard]] bool is_road_at(int tile_x, int tile_y) const;

    [[nodiscard]] static std::optional<MapDocument> load_from_file(const std::string& filepath);

private:
    std::string raw_content_;
};

} // namespace ch

#endif // CITY_HORIZON_CH_CORE_MAP_DOCUMENT_H
