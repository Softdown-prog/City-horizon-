#include "src/ch_render/animated_prop_catalog.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <stdexcept>

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

std::optional<float> get_json_float(const std::string_view json, const std::string_view key) {
    const std::string key_pattern = "\"" + std::string(key) + "\"";
    const auto key_pos = json.find(key_pattern);
    if (key_pos == std::string_view::npos) return std::nullopt;

    const auto colon_pos = json.find(':', key_pos);
    if (colon_pos == std::string_view::npos) return std::nullopt;

    std::size_t pos = colon_pos + 1;
    while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t' || json[pos] == '\n' || json[pos] == '\r')) {
        ++pos;
    }

    try {
        std::size_t end_pos = pos;
        if (pos < json.size() && (json[pos] == '-' || (json[pos] >= '0' && json[pos] <= '9') || json[pos] == '.')) {
            ++end_pos;
            while (end_pos < json.size() && ((json[end_pos] >= '0' && json[end_pos] <= '9') || json[end_pos] == '.')) {
                ++end_pos;
            }
            return std::stof(std::string(json.substr(pos, end_pos - pos)));
        }
    } catch (...) {}
    return std::nullopt;
}

} // namespace

bool AnimatedPropCatalog::load_manifest(const std::filesystem::path& manifest_path) {
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
        if (!contract_opt || *contract_opt != "CH_ANIMATED_PROP_V1") {
            std::cerr << "AnimatedPropCatalog: Invalid contract in " << manifest_path << '\n';
            return false;
        }

        AnimatedPropDefinition def;
        def.contract = *contract_opt;
        def.id = get_json_string(content, "id").value_or("");
        def.base_static_path = get_json_string(content, "base_static").value_or("assets/props/windmill_base.png");

        if (def.id.empty()) {
            std::cerr << "AnimatedPropCatalog: Missing id in " << manifest_path << '\n';
            return false;
        }

        // Parse PoC layer (Rotor)
        AnimatedPropLayerDef layer;
        layer.id = "rotor";
        layer.sprite_path = get_json_string(content, "atlas").value_or("assets/props/windmill_rotor.png");
        layer.driver = AnimationDriver::Rotation;
        
        std::string pres_str = get_json_string(content, "presentation").value_or("transform_rotation");
        if (pres_str == "atlas_phase") {
            layer.presentation = VisualPresentation::AtlasPhase;
        } else {
            layer.presentation = VisualPresentation::TransformRotation;
        }

        layer.mount_point_x = get_json_float(content, "mountPointX").value_or(64.0F);
        layer.mount_point_y = get_json_float(content, "mountPointY").value_or(48.0F);
        layer.pivot_x = get_json_float(content, "pivotX").value_or(64.0F);
        layer.pivot_y = get_json_float(content, "pivotY").value_or(64.0F);
        layer.render_order = 1;

        def.layers.push_back(layer);
        catalog_[def.id] = def;
        return true;
    } catch (const std::exception& ex) {
        std::cerr << "AnimatedPropCatalog::load_manifest error: " << ex.what() << '\n';
        return false;
    }
}

bool AnimatedPropCatalog::load_directory(const std::filesystem::path& directory_path) {
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

const AnimatedPropDefinition* AnimatedPropCatalog::find_prop(const std::string& prop_id) const {
    auto it = catalog_.find(prop_id);
    if (it != catalog_.end()) {
        return &it->second;
    }
    return nullptr;
}

} // namespace ch
