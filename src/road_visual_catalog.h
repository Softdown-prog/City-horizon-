#pragma once

#include "tile_topology.h"

#include <array>
#include <cstdint>
#include <filesystem>
#include <string>

// Visual data is intentionally separate from RoadManager and its connectivity.
// Each final road PNG is an explicit isometric 128x64 tile for one canonical
// CH_PATH_TOPOLOGY_V1 mask. The semantic topology kind is carried beside the
// texture so render/debug/UI code does not need to re-invent mask rules.
struct RoadVisual {
    std::string texture_path;
    TileTopologyKind topology = TileTopologyKind::isolated;
};

class RoadVisualCatalog {
public:
    RoadVisualCatalog();

    // Keeps the explicit built-in paths if the JSON cannot be loaded, so the
    // renderer can fall back safely while assets are still being produced.
    [[nodiscard]] bool load_from_file(const std::filesystem::path& path);
    [[nodiscard]] const RoadVisual* get_for_mask(TileConnectionMask mask) const;
    [[nodiscard]] bool loaded_from_file() const;

private:
    void set_default_paths();

    std::array<RoadVisual, 16> visuals_;
    bool loaded_from_file_ = false;
};
