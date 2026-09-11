#pragma once

#include <array>
#include <cstdint>
#include <filesystem>
#include <string>

// Visual data is intentionally separate from RoadManager and its connectivity.
// Each final road PNG is an explicit isometric 128x64 tile for one mask.
struct RoadVisual {
    std::string texture_path;
};

class RoadVisualCatalog {
public:
    RoadVisualCatalog();

    // Keeps the explicit built-in paths if the JSON cannot be loaded, so the
    // renderer can fall back safely while assets are still being produced.
    [[nodiscard]] bool load_from_file(const std::filesystem::path& path);
    [[nodiscard]] const RoadVisual* get_for_mask(std::uint8_t mask) const;
    [[nodiscard]] bool loaded_from_file() const;

private:
    void set_default_paths();

    std::array<RoadVisual, 16> visuals_;
    bool loaded_from_file_ = false;
};
