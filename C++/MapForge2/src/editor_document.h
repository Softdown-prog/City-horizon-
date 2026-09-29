#pragma once

#include "src/fence_system.h"

#include <cstdint>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

namespace ch::editor {

struct TileState {
    std::string terrain_id = "grass";
    bool road = false;

    bool operator==(const TileState&) const = default;
};

class EditorDocument {
public:
    EditorDocument();

    bool loadScenario(const std::string& path, std::string* error = nullptr);
    void newEmpty(int width = 64, int height = 64);
    // Resizes the editable map bounds while preserving all tiles and fence
    // vertices that remain inside the new rectangle.
    bool resize(int width, int height);

    [[nodiscard]] int width() const { return width_; }
    [[nodiscard]] int height() const { return height_; }
    [[nodiscard]] int minX() const { return min_x_; }
    [[nodiscard]] int minY() const { return min_y_; }
    [[nodiscard]] int maxX() const { return max_x_; }
    [[nodiscard]] int maxY() const { return max_y_; }
    [[nodiscard]] bool inBounds(int x, int y) const;
    [[nodiscard]] TileState tile(int x, int y) const;

    void setTile(int x, int y, const TileState& state);
    void setTerrain(int x, int y, std::string terrainId);
    void setRoad(int x, int y, bool road);

    // Scratch-map fence authoring uses the same FenceManager as runtime. The
    // editor contributes input only; N/E/S/W topology and visual resolution stay
    // canonical in src/fence_system.*.
    [[nodiscard]] const FenceManager& fences() const { return *fences_; }
    [[nodiscard]] bool placeFenceDrag(FenceVertex start, FenceVertex end);
    [[nodiscard]] bool removeFenceNode(int vertexX, int vertexY);
    void clearFences();

    [[nodiscard]] const std::string& sourcePath() const { return source_path_; }
    [[nodiscard]] std::uint64_t revision() const { return revision_; }

private:
    static std::uint64_t key(int x, int y);
    static int keyX(std::uint64_t packed);
    static int keyY(std::uint64_t packed);
    void resetFenceManager(bool preserve);

    int width_ = 64;
    int height_ = 64;
    int min_x_ = 0;
    int min_y_ = 0;
    int max_x_ = 63;
    int max_y_ = 63;
    std::string source_path_;
    std::unordered_map<std::uint64_t, TileState> tiles_;
    std::unique_ptr<FenceManager> fences_;
    std::uint64_t revision_ = 0;
};

} // namespace ch::editor
