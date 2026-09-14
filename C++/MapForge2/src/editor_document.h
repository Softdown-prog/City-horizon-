#pragma once

#include <cstdint>
#include <optional>
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

    [[nodiscard]] int width() const { return width_; }
    [[nodiscard]] int height() const { return height_; }
    [[nodiscard]] bool inBounds(int x, int y) const;
    [[nodiscard]] TileState tile(int x, int y) const;

    void setTile(int x, int y, const TileState& state);
    void setTerrain(int x, int y, std::string terrainId);
    void setRoad(int x, int y, bool road);

    [[nodiscard]] const std::string& sourcePath() const { return source_path_; }
    [[nodiscard]] std::uint64_t revision() const { return revision_; }

private:
    static std::uint64_t key(int x, int y);

    int width_ = 64;
    int height_ = 64;
    std::string source_path_;
    std::unordered_map<std::uint64_t, TileState> tiles_;
    std::uint64_t revision_ = 0;
};

} // namespace ch::editor
