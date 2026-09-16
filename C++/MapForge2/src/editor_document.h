#pragma once

#include <cstdint>
#include <string>
#include <unordered_map>

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
    // Resizes the editable map bounds while preserving all tiles that remain
    // inside the new rectangle. The current minimum grid coordinate is kept
    // stable so growing a map never shifts authored content.
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

    [[nodiscard]] const std::string& sourcePath() const { return source_path_; }
    [[nodiscard]] std::uint64_t revision() const { return revision_; }

private:
    static std::uint64_t key(int x, int y);
    static int keyX(std::uint64_t packed);
    static int keyY(std::uint64_t packed);

    int width_ = 64;
    int height_ = 64;
    int min_x_ = 0;
    int min_y_ = 0;
    int max_x_ = 63;
    int max_y_ = 63;
    std::string source_path_;
    std::unordered_map<std::uint64_t, TileState> tiles_;
    std::uint64_t revision_ = 0;
};

} // namespace ch::editor
