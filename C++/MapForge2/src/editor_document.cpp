#include "editor_document.h"

#include "src/ch_core/map_document.h"

#include <algorithm>
#include <cstdint>
#include <utility>
#include <vector>

namespace ch::editor {

EditorDocument::EditorDocument() {
    resetFenceManager(false);
}

std::uint64_t EditorDocument::key(const int x, const int y) {
    return (static_cast<std::uint64_t>(static_cast<std::uint32_t>(x)) << 32U)
        | static_cast<std::uint32_t>(y);
}

int EditorDocument::keyX(const std::uint64_t packed) {
    return static_cast<std::int32_t>(static_cast<std::uint32_t>(packed >> 32U));
}

int EditorDocument::keyY(const std::uint64_t packed) {
    return static_cast<std::int32_t>(static_cast<std::uint32_t>(packed & 0xFFFFFFFFULL));
}

bool EditorDocument::inBounds(const int x, const int y) const {
    return x >= min_x_ && y >= min_y_ && x <= max_x_ && y <= max_y_;
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

void EditorDocument::resetFenceManager(const bool preserve) {
    std::vector<FenceNode> old_nodes;
    std::vector<FenceSegment> old_segments;
    if (preserve && fences_) {
        old_nodes = fences_->nodes();
        old_segments = fences_->segments();
    }

    // FenceManager currently accepts one inclusive coordinate interval for both
    // axes. EditorDocument keeps the stricter rectangular bounds at its API.
    const int fence_min = std::min(min_x_, min_y_);
    const int fence_max = std::max(max_x_, max_y_);
    fences_ = std::make_unique<FenceManager>(fence_min, fence_max);

    if (!preserve) return;
    for (const FenceNode& node : old_nodes) {
        if (!inBounds(node.vertex_x, node.vertex_y)) continue;
        if (fences_->place_node(node.vertex_x, node.vertex_y, node.orientation_hint)
            && node.kind == FenceNodeKind::gate) {
            (void)fences_->set_gate(node.vertex_x, node.vertex_y, true);
        }
    }
    for (const FenceSegment& segment : old_segments) {
        if (!segment.open_gate) continue;
        if (!inBounds(segment.from.x, segment.from.y) || !inBounds(segment.to.x, segment.to.y)) continue;
        (void)fences_->set_open_gate(segment.from, segment.to, true);
    }
}

bool EditorDocument::placeFenceDrag(const FenceVertex start, const FenceVertex end) {
    if (!inBounds(start.x, start.y) || !inBounds(end.x, end.y)) return false;
    const std::vector<FenceVertex> path = fences_->line_between(start, end);
    if (path.empty() || std::any_of(path.begin(), path.end(), [this](const FenceVertex vertex) {
            return !inBounds(vertex.x, vertex.y);
        })) {
        return false;
    }
    const int placed = fences_->place_run(path);
    if (placed <= 0) return false;
    ++revision_;
    return true;
}

bool EditorDocument::removeFenceNode(const int vertexX, const int vertexY) {
    if (!inBounds(vertexX, vertexY) || !fences_->remove_node(vertexX, vertexY)) return false;
    ++revision_;
    return true;
}

void EditorDocument::clearFences() {
    if (fences_->nodes().empty()) return;
    fences_->clear();
    ++revision_;
}

void EditorDocument::newEmpty(const int width, const int height) {
    width_ = std::max(1, width);
    height_ = std::max(1, height);
    min_x_ = 0;
    min_y_ = 0;
    max_x_ = width_ - 1;
    max_y_ = height_ - 1;
    source_path_.clear();
    tiles_.clear();
    resetFenceManager(false);
    ++revision_;
}

bool EditorDocument::resize(const int width, const int height) {
    const int new_width = std::max(1, width);
    const int new_height = std::max(1, height);
    if (new_width == width_ && new_height == height_) {
        return false;
    }

    const int new_max_x = min_x_ + new_width - 1;
    const int new_max_y = min_y_ + new_height - 1;

    for (auto it = tiles_.begin(); it != tiles_.end();) {
        const int x = keyX(it->first);
        const int y = keyY(it->first);
        if (x < min_x_ || y < min_y_ || x > new_max_x || y > new_max_y) {
            it = tiles_.erase(it);
        } else {
            ++it;
        }
    }

    width_ = new_width;
    height_ = new_height;
    max_x_ = new_max_x;
    max_y_ = new_max_y;
    resetFenceManager(true);
    ++revision_;
    return true;
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
    bool has_content = false;
    int min_x = 0;
    int min_y = 0;
    int max_x = 0;
    int max_y = 0;

    auto includeCoordinate = [&](const int x, const int y) {
        if (!has_content) {
            min_x = max_x = x;
            min_y = max_y = y;
            has_content = true;
            return;
        }
        min_x = std::min(min_x, x);
        min_y = std::min(min_y, y);
        max_x = std::max(max_x, x);
        max_y = std::max(max_y, y);
    };

    for (const auto& terrain : parsed->terrain_tiles()) {
        auto state = tile(terrain.tile_x, terrain.tile_y);
        state.terrain_id = terrain.texture.empty() ? "grass" : terrain.texture;
        tiles_[key(terrain.tile_x, terrain.tile_y)] = std::move(state);
        includeCoordinate(terrain.tile_x, terrain.tile_y);
    }

    for (const auto& road : parsed->roads()) {
        auto state = tile(road.tile_x, road.tile_y);
        state.road = true;
        tiles_[key(road.tile_x, road.tile_y)] = std::move(state);
        includeCoordinate(road.tile_x, road.tile_y);
    }

    for (const auto& building : parsed->buildings()) {
        includeCoordinate(building.tile_x, building.tile_y);
    }

    if (!has_content) {
        min_x = 0;
        min_y = 0;
        max_x = 63;
        max_y = 63;
    }

    min_x_ = min_x;
    min_y_ = min_y;
    max_x_ = max_x;
    max_y_ = max_y;
    width_ = std::max(1, max_x_ - min_x_ + 1);
    height_ = std::max(1, max_y_ - min_y_ + 1);
    source_path_ = path;
    resetFenceManager(false);
    ++revision_;
    return true;
}

} // namespace ch::editor
