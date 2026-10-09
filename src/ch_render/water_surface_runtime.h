#pragma once

#include "../ch_core/asset_registry.h"
#include "palette_bank.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>

namespace ch {

struct WaterSurfaceAnimationSpec {
    int world_period_tiles = 4;
    int frame_count = 16;
    int frame_duration_ms = 125;
    int atlas_columns = 4;
    int atlas_rows = 4;
    int frame_width_px = 256;
    int frame_height_px = 256;
    int gutter_px = 1;
    int stride_px = 258;

    [[nodiscard]] bool valid() const noexcept {
        return world_period_tiles > 0 && frame_count > 0 && frame_duration_ms > 0 &&
               atlas_columns > 0 && atlas_rows > 0 && frame_width_px > 0 && frame_height_px > 0 &&
               gutter_px >= 0 && stride_px >= frame_width_px &&
               frame_count <= atlas_columns * atlas_rows;
    }

    [[nodiscard]] bool matches_current_rgba_atlas_layout() const noexcept {
        return world_period_tiles == 4 && frame_count == 16 && atlas_columns == 4 && atlas_rows == 4 &&
               frame_width_px == 256 && frame_height_px == 256 && gutter_px == 1 && stride_px == 258;
    }
};

struct WaterSurfaceRuntimeDefinition {
    std::string id;
    std::string display_name;
    int build_cost = 0;
    std::string base_asset_id;
    std::string original_overlay_asset_id;
    std::string indexed_overlay_asset_id;
    std::string rgba_atlas_asset_id;
    std::string coverage_palette_range;
};

class WaterSurfaceRuntimeCatalog {
public:
    WaterSurfaceRuntimeCatalog() { reset_defaults(); }

    [[nodiscard]] bool load_manifest(const std::filesystem::path& manifest_path) {
        std::ifstream input(manifest_path, std::ios::binary);
        if (!input.is_open()) return false;
        std::ostringstream output;
        output << input.rdbuf();
        const std::string json = output.str();

        const auto contract = string_value(json, "contract");
        if (!contract || *contract != "CH_WATER_SURFACE_V1") return false;

        WaterSurfaceRuntimeCatalog candidate;
        candidate.contract_ = *contract;
        candidate.manifest_loaded_ = true;
        candidate.assets_.clear();
        candidate.surfaces_.clear();

        candidate.animation_.world_period_tiles =
            int_value(json, "worldPeriodTiles").value_or(candidate.animation_.world_period_tiles);
        candidate.animation_.frame_count =
            int_value(json, "frameCount").value_or(candidate.animation_.frame_count);
        candidate.animation_.frame_duration_ms =
            int_value(json, "frameDurationMs").value_or(candidate.animation_.frame_duration_ms);
        candidate.animation_.atlas_columns =
            int_value(json, "atlasColumns").value_or(candidate.animation_.atlas_columns);
        candidate.animation_.atlas_rows =
            int_value(json, "atlasRows").value_or(candidate.animation_.atlas_rows);
        candidate.animation_.gutter_px =
            int_value(json, "gutterPx").value_or(candidate.animation_.gutter_px);
        candidate.animation_.stride_px =
            int_value(json, "stridePx").value_or(candidate.animation_.stride_px);
        if (const auto frame_size = int_pair_value(json, "frameSize")) {
            candidate.animation_.frame_width_px = frame_size->first;
            candidate.animation_.frame_height_px = frame_size->second;
        }

        // The current renderer samples the already-approved 4x4 RGBA atlas.
        // Refuse silent contract drift until render_water_surface_tile becomes
        // fully generic rather than drawing a differently shaped atlas wrong.
        if (!candidate.animation_.valid() || !candidate.animation_.matches_current_rgba_atlas_layout()) {
            return false;
        }

        const auto surfaces = object_body(json, "surfaces");
        if (!surfaces) return false;
        if (!candidate.load_surface(*surfaces, "water_shallow", true) ||
            !candidate.load_surface(*surfaces, "water_deep", false)) {
            return false;
        }

        *this = std::move(candidate);
        return true;
    }

    void reset_defaults() {
        contract_ = "CH_WATER_SURFACE_V1";
        manifest_loaded_ = false;
        animation_ = {};
        assets_.clear();
        surfaces_.clear();
        palette_ = PaletteBank({
            {80, 163, 194, 255},
            {115, 200, 210, 255},
        });
        (void)palette_.define_range("water_deep_coverage", {0, 1});
        (void)palette_.define_range("water_shallow_coverage", {1, 1});

        add_default_surface(
            "water_shallow", "Agua rasa", 50, "water_shallow_coverage",
            "assets/terrain/water/water_shallow_world.png",
            "assets/terrain/water/water_shallow_glint_overlay.png",
            "assets/terrain/water/water_shallow_glint_indices.png",
            "assets/terrain/water/water_shallow_glint_cycle_atlas.png");
        add_default_surface(
            "water_deep", "Agua profunda", 100, "water_deep_coverage",
            "assets/terrain/water/water_deep_world.png",
            "assets/terrain/water/water_deep_glint_overlay.png",
            "assets/terrain/water/water_deep_glint_indices.png",
            "assets/terrain/water/water_deep_glint_cycle_atlas.png");
    }

    [[nodiscard]] std::string_view contract() const noexcept { return contract_; }
    [[nodiscard]] bool manifest_loaded() const noexcept { return manifest_loaded_; }
    [[nodiscard]] const WaterSurfaceAnimationSpec& animation() const noexcept { return animation_; }
    [[nodiscard]] const AssetRegistry& assets() const noexcept { return assets_; }
    [[nodiscard]] const PaletteBank& palette() const noexcept { return palette_; }

    [[nodiscard]] const WaterSurfaceRuntimeDefinition* find_surface(const std::string_view id) const {
        const auto found = surfaces_.find(std::string(id));
        return found == surfaces_.end() ? nullptr : &found->second;
    }

    [[nodiscard]] const AssetDescriptor* find_asset(const std::string_view asset_id) const {
        return assets_.find(asset_id);
    }

    [[nodiscard]] const Rgba8* coverage_color(const WaterSurfaceRuntimeDefinition& surface) const noexcept {
        const auto selected = palette_.range(surface.coverage_palette_range);
        return !selected || selected->count == 0 ? nullptr : palette_.color(selected->first);
    }

    [[nodiscard]] int frame_at_seconds(const float seconds) const noexcept {
        if (!std::isfinite(seconds) || seconds <= 0.0F || !animation_.valid()) return 0;
        const double milliseconds = static_cast<double>(seconds) * 1000.0;
        const auto frame = static_cast<std::uint64_t>(
            std::floor(milliseconds / static_cast<double>(animation_.frame_duration_ms)));
        return static_cast<int>(frame % static_cast<std::uint64_t>(animation_.frame_count));
    }

private:
    static std::optional<std::size_t> value_position(const std::string_view json,
                                                      const std::string_view key) {
        const std::string key_pattern = "\"" + std::string(key) + "\"";
        const auto found = json.find(key_pattern);
        if (found == std::string_view::npos) return std::nullopt;
        const auto colon = json.find(':', found + key_pattern.size());
        if (colon == std::string_view::npos) return std::nullopt;
        std::size_t position = colon + 1;
        while (position < json.size() &&
               (json[position] == ' ' || json[position] == '\t' ||
                json[position] == '\n' || json[position] == '\r')) {
            ++position;
        }
        return position;
    }

    static std::optional<std::string> string_value(const std::string_view json,
                                                    const std::string_view key) {
        const auto position = value_position(json, key);
        if (!position || *position >= json.size() || json[*position] != '"') return std::nullopt;
        const auto end = json.find('"', *position + 1);
        if (end == std::string_view::npos) return std::nullopt;
        return std::string(json.substr(*position + 1, end - *position - 1));
    }

    static std::optional<int> int_value(const std::string_view json, const std::string_view key) {
        const auto position = value_position(json, key);
        if (!position) return std::nullopt;
        try {
            std::size_t consumed = 0;
            const int value = std::stoi(std::string(json.substr(*position)), &consumed);
            return consumed == 0 ? std::nullopt : std::optional(value);
        } catch (...) {
            return std::nullopt;
        }
    }

    static std::optional<std::pair<int, int>> int_pair_value(const std::string_view json,
                                                              const std::string_view key) {
        const auto position = value_position(json, key);
        if (!position || *position >= json.size() || json[*position] != '[') return std::nullopt;
        const auto comma = json.find(',', *position + 1);
        const auto end = comma == std::string_view::npos
            ? std::string_view::npos
            : json.find(']', comma + 1);
        if (comma == std::string_view::npos || end == std::string_view::npos) return std::nullopt;
        try {
            const int first = std::stoi(
                std::string(json.substr(*position + 1, comma - *position - 1)));
            const int second = std::stoi(
                std::string(json.substr(comma + 1, end - comma - 1)));
            return std::pair{first, second};
        } catch (...) {
            return std::nullopt;
        }
    }

    static std::optional<std::string_view> object_body(const std::string_view json,
                                                        const std::string_view key) {
        const auto position = value_position(json, key);
        if (!position || *position >= json.size() || json[*position] != '{') return std::nullopt;
        int depth = 0;
        bool quoted = false;
        for (std::size_t index = *position; index < json.size(); ++index) {
            if (json[index] == '"' && (index == 0 || json[index - 1] != '\\')) quoted = !quoted;
            if (quoted) continue;
            if (json[index] == '{') ++depth;
            if (json[index] == '}' && --depth == 0) {
                return json.substr(*position + 1, index - *position - 1);
            }
        }
        return std::nullopt;
    }

    [[nodiscard]] bool load_surface(const std::string_view surfaces_json,
                                    const std::string_view surface_key,
                                    const bool shallow) {
        const auto body = object_body(surfaces_json, surface_key);
        if (!body) return false;
        const std::string id = string_value(*body, "id").value_or("");
        const std::string base = string_value(*body, "base").value_or("");
        const std::string original_overlay =
            string_value(*body, "originalOverlay").value_or("");
        const std::string indexed_overlay =
            string_value(*body, "indexedOverlay").value_or("");
        const std::string rgba_atlas =
            string_value(*body, "rgbaFrameAtlas").value_or("");
        if (id.empty() || base.empty() || rgba_atlas.empty()) return false;

        // Defaults carry the validated opaque seam-coverage colours. The
        // manifest owns authored textures, costs and cadence; the PaletteBank
        // owns semantic runtime colours without touching approved PNG pixels.
        WaterSurfaceRuntimeDefinition definition;
        definition.id = id;
        definition.display_name = string_value(*body, "displayName").value_or(id);
        definition.build_cost = int_value(*body, "buildCost").value_or(0);
        definition.coverage_palette_range = shallow
            ? "water_shallow_coverage"
            : "water_deep_coverage";
        definition.base_asset_id = id + ".base";
        definition.original_overlay_asset_id = id + ".original_overlay";
        definition.indexed_overlay_asset_id = id + ".indexed_overlay";
        definition.rgba_atlas_asset_id = id + ".rgba_atlas";

        if (!register_asset(definition.base_asset_id, AssetKind::Terrain, base) ||
            !register_asset(definition.rgba_atlas_asset_id, AssetKind::Overlay, rgba_atlas)) {
            return false;
        }
        if (!original_overlay.empty() &&
            !register_asset(definition.original_overlay_asset_id, AssetKind::Overlay, original_overlay)) {
            return false;
        }
        if (!indexed_overlay.empty() &&
            !register_asset(definition.indexed_overlay_asset_id, AssetKind::Overlay, indexed_overlay)) {
            return false;
        }
        surfaces_[definition.id] = std::move(definition);
        return true;
    }

    void add_default_surface(const std::string& id,
                             const std::string& display_name,
                             const int build_cost,
                             const std::string& coverage_range,
                             const std::string& base,
                             const std::string& original_overlay,
                             const std::string& indexed_overlay,
                             const std::string& rgba_atlas) {
        WaterSurfaceRuntimeDefinition definition;
        definition.id = id;
        definition.display_name = display_name;
        definition.build_cost = build_cost;
        definition.coverage_palette_range = coverage_range;
        definition.base_asset_id = id + ".base";
        definition.original_overlay_asset_id = id + ".original_overlay";
        definition.indexed_overlay_asset_id = id + ".indexed_overlay";
        definition.rgba_atlas_asset_id = id + ".rgba_atlas";
        (void)register_asset(definition.base_asset_id, AssetKind::Terrain, base);
        (void)register_asset(definition.original_overlay_asset_id, AssetKind::Overlay, original_overlay);
        (void)register_asset(definition.indexed_overlay_asset_id, AssetKind::Overlay, indexed_overlay);
        (void)register_asset(definition.rgba_atlas_asset_id, AssetKind::Overlay, rgba_atlas);
        surfaces_[definition.id] = std::move(definition);
    }

    [[nodiscard]] bool register_asset(const std::string& id,
                                      const AssetKind kind,
                                      const std::string& path) {
        if (path.empty()) return true;
        return assets_.register_asset({
            .id = id,
            .kind = kind,
            .logical_path = path,
            .source_group = "terrain.water",
            .contract = contract_,
        }) == AssetRegistrationResult::Inserted;
    }

    std::string contract_ = "CH_WATER_SURFACE_V1";
    bool manifest_loaded_ = false;
    WaterSurfaceAnimationSpec animation_{};
    AssetRegistry assets_{};
    PaletteBank palette_{};
    std::unordered_map<std::string, WaterSurfaceRuntimeDefinition> surfaces_;
};

}  // namespace ch
