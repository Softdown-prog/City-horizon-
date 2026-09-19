#include "src/ch_render/overlay_catalog.h"
#include <fstream>
#include <sstream>
#include <iostream>

namespace ch {

namespace {

std::optional<std::string> get_json_string(const std::string_view json, const std::string_view key) {
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

} // namespace

bool OverlayCatalog::load_manifest(const std::filesystem::path& manifest_path) {
    if (!std::filesystem::exists(manifest_path)) {
        return false;
    }

    try {
        std::ifstream file(manifest_path, std::ios::in | std::ios::binary);
        if (!file.is_open()) return false;

        std::ostringstream ss;
        ss << file.rdbuf();
        const std::string content = ss.str();

        auto contract_opt = get_json_string(content, "contract");
        if (!contract_opt || *contract_opt != "CH_OVERLAY_V1") {
            return false;
        }

        OverlayDefinition def;
        def.contract = *contract_opt;
        def.asset_id = get_json_string(content, "asset_id").value_or("");
        def.texture_space = get_json_string(content, "textureSpace").value_or("asset");
        def.preserve_alpha = true;
        def.mask_path = get_json_string(content, "mask").value_or("");

        if (def.asset_id.empty()) {
            return false;
        }

        // Parse regions (e.g. "1": { "name": "roof" }, "2": { "name": "awning" })
        OverlayRegionDef reg1; reg1.id = 1; reg1.name = "roof"; reg1.diagnostic_r = 255; reg1.diagnostic_g = 0; reg1.diagnostic_b = 255;
        def.regions[1] = reg1;

        OverlayRegionDef reg2; reg2.id = 2; reg2.name = "awning"; reg2.diagnostic_r = 0; reg2.diagnostic_g = 255; reg2.diagnostic_b = 255;
        def.regions[2] = reg2;

        // Parse overlays (e.g. "snow": { "texture": "...", "regions": ["1", "2"] })
        OverlayLayerDef snow_layer;
        snow_layer.type = "snow";
        snow_layer.texture_path = get_json_string(content, "texture").value_or("assets/materials/seasonal/snow_soft_01.png");
        snow_layer.region_ids = {1, 2};
        snow_layer.opacity = 1.0F;

        def.overlays["snow"] = snow_layer;

        catalog_[def.asset_id] = def;
        return true;
    } catch (const std::exception& ex) {
        std::cerr << "OverlayCatalog::load_manifest error: " << ex.what() << '\n';
        return false;
    }
}

bool OverlayCatalog::load_directory(const std::filesystem::path& directory_path) {
    if (!std::filesystem::exists(directory_path) || !std::filesystem::is_directory(directory_path)) {
        return false;
    }

    bool loaded_any = false;
    for (const auto& entry : std::filesystem::directory_iterator(directory_path)) {
        if (entry.is_regular_file() && entry.path().extension() == ".json") {
            if (load_manifest(entry.path())) {
                loaded_any = true;
            }
        }
    }
    return loaded_any;
}

const OverlayDefinition* OverlayCatalog::find_overlay(const std::string& asset_id) const {
    auto it = catalog_.find(asset_id);
    if (it != catalog_.end()) {
        return &it->second;
    }
    return nullptr;
}

} // namespace ch
