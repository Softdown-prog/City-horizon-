#include "editor_document.h"

#include "src/ch_core/map_document.h"

#include <algorithm>
#include <utility>

namespace ch::editor {

EditorDocument::EditorDocument() = default;

std::uint64_t EditorDocument::key(const int x, const int y) {
    return (static_cast<std::uint64_t>(static_cast<std::uint32_t>(x)) << 32U)
        | static_cast<std::uint32_t>(y);
}

bool EditorDocument::inBounds(const int x, const int y) const {
    return x >= 0 && y >= 0 && x < width_ && y < height_;
}

TileState EditorDocument::tile(const int x, const int y) const {
    const auto it = tiles_.find(key(x, y));
    if (it != tiles_.end()) {
        return it->second;
    }
    return {};
}

void EditorDocument::setTile(const int x, const int y, const TileState& state) {
    if (!inBounds(x, y)) {
        return;
    }
    const auto k = key(x, y);
    const auto current = tile(x, y);
    if (current == state) {
        return;
    }
    if (state == TileState{}) {
        tiles_.erase(k);
    } else {
        tiles_[k] = state;
    }
    ++revision_;
}

void EditorDocument::setTerrain(const int x, const int y, std::string terrainId) {
    auto state = tile(x, y);
    state.terrain_id = std::move(terrainId);
    setTile(x, y, state);
}

void EditorDocument::setRoad(const int x, const int y, const bool road) {
    auto state = tile(x, y);
    state.road = road;
    setTile(x, y, state);
}

void EditorDocument::newEmpty(const int width, const int height) {
    width_ = std::max(1, width);
    height_ = std::max(1, height);
    source_path_.clear();
    tiles_.clear();
    ++revision_;
}

bool EditorDocument::loadScenario(const std::string& path, std::string* error) {
    const auto parsed = ch::MapDocument::load_from_file(path);
    if (!parsed) {
        if (error != nullptr) {
            *error = "Unable to open scenario: " + path;
        }
        return false;
    }

    tiles_.clear();
    int max_x = 63;
    int max_y = 63;

    for (const auto& terrain : parsed->terrain_tiles()) {
        auto state = tile(terrain.tile_x, terrain.tile_y);
        state.terrain_id = terrain.texture.empty() ? "grass" : terrain.texture;
        tiles_[key(terrain.tile_x, terrain.tile_y)] = std::move(state);
        max_x = std::max(max_x, terrain.tile_x);
        max_y = std::max(max_y, terrain.tile_y);
    }

    for (const auto& road : parsed->roads()) {
        auto state = tile(road.tile_x, road.tile_y);
        state.road = true;
        tiles_[key(road.tile_x, road.tile_y)] = std::move(state);
        max_x = std::max(max_x, road.tile_x);
        max_y = std::max(max_y, road.tile_y);
    }

    width_ = std::max(64, max_x + 1);
    height_ = std::max(64, max_y + 1);
    source_path_ = path;
    ++revision_;
    return true;
}

} // namespace ch::editor
