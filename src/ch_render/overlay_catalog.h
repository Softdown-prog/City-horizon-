#ifndef CITY_HORIZON_CH_RENDER_OVERLAY_CATALOG_H
#define CITY_HORIZON_CH_RENDER_OVERLAY_CATALOG_H

#include <filesystem>
#include <string>
#include <unordered_map>
#include <vector>
#include <cstdint>
#include <optional>

namespace ch {

struct OverlayRegionDef {
    uint8_t id = 0;
    std::string name;
    uint8_t diagnostic_r = 255;
    uint8_t diagnostic_g = 0;
    uint8_t diagnostic_b = 255;
};

struct OverlayLayerDef {
    std::string type; // e.g. "snow"
    std::string texture_path;
    std::vector<uint8_t> region_ids;
    float opacity = 1.0F;
};

struct OverlayDefinition {
    std::string contract = "CH_OVERLAY_V1";
    std::string asset_id;
    std::string texture_space = "asset";
    bool preserve_alpha = true;
    std::string mask_path;
    std::unordered_map<uint8_t, OverlayRegionDef> regions;
    std::unordered_map<std::string, OverlayLayerDef> overlays;
};

class OverlayCatalog {
public:
    OverlayCatalog() = default;

    bool load_manifest(const std::filesystem::path& manifest_path);
    bool load_directory(const std::filesystem::path& directory_path);

    [[nodiscard]] const OverlayDefinition* find_overlay(const std::string& asset_id) const;

    void clear() { catalog_.clear(); }

private:
    std::unordered_map<std::string, OverlayDefinition> catalog_;
};

} // namespace ch

#endif // CITY_HORIZON_CH_RENDER_OVERLAY_CATALOG_H
