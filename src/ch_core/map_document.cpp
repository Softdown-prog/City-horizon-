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

} // namespace

MapDocument::MapDocument(std::string raw_json_content)
    : raw_content_(std::move(raw_json_content)) {}

std::optional<MapDocument> MapDocument::load_from_file(const std::string& filepath) {
    std::ifstream file(filepath);
    if (!file) return std::nullopt;

    std::stringstream ss;
    ss << file.rdbuf();
    return MapDocument(ss.str());
}

std::vector<TerrainTileEntry> MapDocument::terrain_tiles() const {
    std::vector<TerrainTileEntry> result;
    const std::size_t terrain_pos = raw_content_.find("\"terrain\"");
    if (terrain_pos == std::string::npos) return result;

    const std::size_t array_start = raw_content_.find('[', terrain_pos);
    const std::size_t array_end = raw_content_.find(']', array_start);
    if (array_start == std::string::npos || array_end == std::string::npos) return result;

    std::string_view array_str(raw_content_.data() + array_start, array_end - array_start + 1);
    std::size_t pos = 0;
    while ((pos = array_str.find('{', pos)) != std::string_view::npos) {
        const std::size_t end_obj = array_str.find('}', pos);
        if (end_obj == std::string_view::npos) break;

        std::string_view obj = array_str.substr(pos, end_obj - pos + 1);
        const auto tx = json_int(obj, "tileX");
        const auto ty = json_int(obj, "tileY");
        const auto tex = json_string(obj, "texture");

        if (tx && ty && tex) {
            result.push_back({*tx, *ty, *tex});
        }
        pos = end_obj + 1;
    }
    return result;
}

std::vector<BuildingInstanceEntry> MapDocument::buildings() const {
    std::vector<BuildingInstanceEntry> result;
    const std::size_t b_pos = raw_content_.find("\"buildings\"");
    if (b_pos == std::string::npos) return result;

    const std::size_t array_start = raw_content_.find('[', b_pos);
    const std::size_t array_end = raw_content_.find(']', array_start);
    if (array_start == std::string::npos || array_end == std::string::npos) return result;

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
            result.push_back({
                static_cast<std::size_t>(iid.value_or(0)),
                *did,
                *tx,
                *ty,
                rot.value_or(0)
            });
        }
        pos = end_obj + 1;
    }
    return result;
}

std::vector<RoadTileEntry> MapDocument::roads() const {
    std::vector<RoadTileEntry> result;
    const std::size_t r_pos = raw_content_.find("\"roads\"");
    if (r_pos == std::string::npos) return result;

    const std::size_t array_start = raw_content_.find('[', r_pos);
    const std::size_t array_end = raw_content_.find(']', array_start);
    if (array_start == std::string::npos || array_end == std::string::npos) return result;

    std::string_view array_str(raw_content_.data() + array_start, array_end - array_start + 1);
    std::size_t pos = 0;
    while ((pos = array_str.find('{', pos)) != std::string_view::npos) {
        const std::size_t end_obj = array_str.find('}', pos);
        if (end_obj == std::string_view::npos) break;

        std::string_view obj = array_str.substr(pos, end_obj - pos + 1);
        const auto tx = json_int(obj, "tileX");
        const auto ty = json_int(obj, "tileY");

        if (tx && ty) {
            result.push_back({*tx, *ty});
        }
        pos = end_obj + 1;
    }
    return result;
}

std::optional<TerrainTileEntry> MapDocument::get_terrain_at(const int tile_x, const int tile_y) const {
    for (const auto& t : terrain_tiles()) {
        if (t.tile_x == tile_x && t.tile_y == tile_y) return t;
    }
    return std::nullopt;
}

std::optional<BuildingInstanceEntry> MapDocument::get_building_at(const int tile_x, const int tile_y) const {
    for (const auto& b : buildings()) {
        if (b.tile_x == tile_x && b.tile_y == tile_y) return b;
    }
    return std::nullopt;
}

bool MapDocument::is_road_at(const int tile_x, const int tile_y) const {
    for (const auto& r : roads()) {
        if (r.tile_x == tile_x && r.tile_y == tile_y) return true;
    }
    return false;
}

} // namespace ch
