#include "src/ch_core/map_document.h"
#include <fstream>
#include <sstream>
#include <iostream>

namespace ch {

namespace {

std::optional<std::string> json_string(const std::string_view json, const std::string_view key) {
    const std::string key_pattern = "\"" + std::string(key) + "\"";
    const auto key_pos = json.find(key_pattern);
    if (key_pos == std::string_view::npos) return std::nullopt;

    const auto colon_pos = json.find(':', key_pos);
    if (colon_pos == std::string_view::npos) return std::nullopt;

    const auto quote_start = json.find('"', colon_pos);
    if (quote_start == std::string_view::npos) return std::nullopt;

    const auto quote_end = json.find('"', quote_start + 1);
    if (quote_end == std::string_view::npos) return std::nullopt;

    return std::string(json.substr(quote_start + 1, quote_end - quote_start - 1));
}

std::optional<int> json_int(const std::string_view json, const std::string_view key) {
    const std::string key_pattern = "\"" + std::string(key) + "\"";
    const auto key_pos = json.find(key_pattern);
    if (key_pos == std::string_view::npos) return std::nullopt;

    const auto colon_pos = json.find(':', key_pos);
    if (colon_pos == std::string_view::npos) return std::nullopt;

    std::size_t pos = colon_pos + 1;
    while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t' || json[pos] == '\n' || json[pos] == '\r')) {
        ++pos;
    }

    try {
        std::size_t end_pos = pos;
        if (pos < json.size() && (json[pos] == '-' || (json[pos] >= '0' && json[pos] <= '9'))) {
            ++end_pos;
            while (end_pos < json.size() && json[end_pos] >= '0' && json[end_pos] <= '9') {
                ++end_pos;
            }
            return std::stoi(std::string(json.substr(pos, end_pos - pos)));
        }
    } catch (...) {}
    return std::nullopt;
}

std::string resolve_legacy_terrain_definition(const std::string& texture_path) {
    if (texture_path.empty()) return "unresolved_legacy_terrain";
    static const std::unordered_map<std::string, std::string> kLegacyTable = {
        {"assets/terrain/grass_isometric_01.png", "grass"},
        {"assets/terrain/sand_isometric_01.png", "sand_center"},
        {"assets/terrain/coast_adjusted/coast_sand_center_01.png", "sand_center"},
        {"assets/terrain/coast_adjusted/coast_sand_wet_01.png", "sand_wet"},
        {"assets/terrain/coast_adjusted/coast_shallow_transition.png", "ocean_shallow"},
        {"assets/terrain/coast_adjusted/ocean_shallow_01.png", "ocean_shallow"},
        {"assets/terrain/coast_adjusted/ocean_shallow_02.png", "ocean_shallow"},
        {"assets/terrain/coast_adjusted/ocean_deep_04.png", "ocean_deep"},
        {"assets/terrain/coast_water_shallow.png", "ocean_shallow"},
        {"assets/terrain/coast_water_deep.png", "ocean_deep"},
        {"assets/materials/terrain/dirt_01.png", "grass"},
        {"assets/materials/terrain/stone_01.png", "grass"}
    };
    auto it = kLegacyTable.find(texture_path);
    if (it != kLegacyTable.end()) {
        return it->second;
    }
    return "unresolved_legacy_terrain"; // Fail-closed
}

} // namespace

MapDocument::MapDocument(std::string raw_json_content)
    : raw_content_(std::move(raw_json_content)) {
    parse_all();
}

std::optional<MapDocument> MapDocument::load_from_file(const std::string& filepath) {
    std::ifstream file(filepath);
    if (!file) return std::nullopt;

    std::stringstream ss;
    ss << file.rdbuf();
    return MapDocument(ss.str());
}

void MapDocument::parse_all() {
    // 1. Terrain Tiles
    const std::size_t terrain_pos = raw_content_.find("\"terrain\"");
    if (terrain_pos != std::string::npos) {
        const std::size_t array_start = raw_content_.find('[', terrain_pos);
        const std::size_t array_end = raw_content_.find(']', array_start);
        if (array_start != std::string::npos && array_end != std::string::npos) {
            std::string_view array_str(raw_content_.data() + array_start, array_end - array_start + 1);
            std::size_t pos = 0;
            while ((pos = array_str.find('{', pos)) != std::string_view::npos) {
                const std::size_t end_obj = array_str.find('}', pos);
                if (end_obj == std::string_view::npos) break;

                std::string_view obj = array_str.substr(pos, end_obj - pos + 1);
                const auto tx = json_int(obj, "tileX");
                const auto ty = json_int(obj, "tileY");
                const auto tex = json_string(obj, "texture");
                const auto terrain_definition = json_string(obj, "terrainDefinition");

                if (tx && ty && (tex || terrain_definition)) {
                    std::string def_id = terrain_definition.value_or("");
                    std::string tex_path = tex.value_or("");
                    if (def_id.empty() && !tex_path.empty()) {
                        def_id = resolve_legacy_terrain_definition(tex_path);
                    }
                    std::size_t idx = cached_terrain_.size();
                    cached_terrain_.push_back({*tx, *ty, tex_path, def_id});
                    terrain_index_[pack_key(*tx, *ty)] = idx;
                }
                pos = end_obj + 1;
            }
        }
    }

    // 2. Buildings
    const std::size_t b_pos = raw_content_.find("\"buildings\"");
    if (b_pos != std::string::npos) {
        const std::size_t array_start = raw_content_.find('[', b_pos);
        const std::size_t array_end = raw_content_.find(']', array_start);
        if (array_start != std::string::npos && array_end != std::string::npos) {
            std::string_view array_str(raw_content_.data() + array_start, array_end - array_start + 1);
            std::size_t pos = 0;
            while ((pos = array_str.find('{', pos)) != std::string_view::npos) {
                const std::size_t end_obj = array_str.find('}', pos);
                if (end_obj == std::string_view::npos) break;

                std::string_view obj = array_str.substr(pos, end_obj - pos + 1);
                const auto iid = json_int(obj, "instanceId");
                const auto did = json_string(obj, "definitionId");
                const auto tx = json_int(obj, "tileX");
                const auto ty = json_int(obj, "tileY");
                const auto rot = json_int(obj, "rotation");

                if (did && tx && ty) {
                    std::size_t idx = cached_buildings_.size();
                    cached_buildings_.push_back({
                        static_cast<std::size_t>(iid.value_or(0)),
                        *did,
                        *tx,
                        *ty,
                        rot.value_or(0)
                    });
                    building_index_[pack_key(*tx, *ty)] = idx;
                }
                pos = end_obj + 1;
            }
        }
    }

    // 3. Roads
    const std::size_t r_pos = raw_content_.find("\"roads\"");
    if (r_pos != std::string::npos) {
        const std::size_t array_start = raw_content_.find('[', r_pos);
        const std::size_t array_end = raw_content_.find(']', array_start);
        if (array_start != std::string::npos && array_end != std::string::npos) {
            std::string_view array_str(raw_content_.data() + array_start, array_end - array_start + 1);
            std::size_t pos = 0;
            while ((pos = array_str.find('{', pos)) != std::string_view::npos) {
                const std::size_t end_obj = array_str.find('}', pos);
                if (end_obj == std::string_view::npos) break;

                std::string_view obj = array_str.substr(pos, end_obj - pos + 1);
                const auto tx = json_int(obj, "tileX");
                const auto ty = json_int(obj, "tileY");

                if (tx && ty) {
                    cached_roads_.push_back({*tx, *ty});
                    road_index_.insert(pack_key(*tx, *ty));
                }
                pos = end_obj + 1;
            }
        }
    }
}

std::optional<TerrainTileEntry> MapDocument::get_terrain_at(const int tile_x, const int tile_y) const {
    auto it = terrain_index_.find(pack_key(tile_x, tile_y));
    if (it != terrain_index_.end()) {
        return cached_terrain_[it->second];
    }
    return std::nullopt;
}

std::optional<BuildingInstanceEntry> MapDocument::get_building_at(const int tile_x, const int tile_y) const {
    auto it = building_index_.find(pack_key(tile_x, tile_y));
    if (it != building_index_.end()) {
        return cached_buildings_[it->second];
    }
    return std::nullopt;
}

bool MapDocument::is_road_at(const int tile_x, const int tile_y) const {
    return road_index_.find(pack_key(tile_x, tile_y)) != road_index_.end();
}

void MapDocument::set_terrain_texture_at(int tile_x, int tile_y, const std::string& texture_path) {
    uint64_t key = pack_key(tile_x, tile_y);
    auto it = terrain_index_.find(key);
    if (it != terrain_index_.end()) {
        cached_terrain_[it->second].texture = texture_path;
    } else {
        std::size_t idx = cached_terrain_.size();
        cached_terrain_.push_back({tile_x, tile_y, texture_path, "grass"});
        terrain_index_[key] = idx;
    }
}

void MapDocument::set_terrain_definition_at(int tile_x, int tile_y, const std::string& terrain_def_id, const std::string& texture_path) {
    uint64_t key = pack_key(tile_x, tile_y);
    auto it = terrain_index_.find(key);
    if (it != terrain_index_.end()) {
        cached_terrain_[it->second].terrain_definition = terrain_def_id;
        if (!texture_path.empty()) {
            cached_terrain_[it->second].texture = texture_path;
        }
    } else {
        std::size_t idx = cached_terrain_.size();
        cached_terrain_.push_back({tile_x, tile_y, texture_path, terrain_def_id});
        terrain_index_[key] = idx;
    }
}

void MapDocument::paint_terrain_at(int tile_x, int tile_y, const std::string& terrain_def_id, const std::string& texture_path) {
    const uint64_t key = pack_key(tile_x, tile_y);
    const auto it = terrain_index_.find(key);
    if (it != terrain_index_.end()) {
        cached_terrain_[it->second].terrain_definition = terrain_def_id;
        cached_terrain_[it->second].texture = texture_path;
    } else {
        terrain_index_[key] = cached_terrain_.size();
        cached_terrain_.push_back({tile_x, tile_y, texture_path, terrain_def_id});
    }
}

MapDocument MapDocument::create_empty(const std::string& name, int width, int height) {
    (void)name;
    MapDocument doc("{}");
    doc.cached_terrain_.reserve(width * height);
    for (int y = -height / 2; y < height / 2; ++y) {
        for (int x = -width / 2; x < width / 2; ++x) {
            uint64_t key = pack_key(x, y);
            std::size_t idx = doc.cached_terrain_.size();
            doc.cached_terrain_.push_back({x, y, "assets/terrain/grass_isometric_01.png", "grass"});
            doc.terrain_index_[key] = idx;
        }
    }
    return doc;
}

} // namespace ch
