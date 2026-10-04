#include "src/ch_render/animated_prop_catalog.h"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string_view>

namespace ch {

namespace {

std::optional<std::string> get_json_string(const std::string_view json, const std::string_view key) {
    const std::string key_pattern = "\"" + std::string(key) + "\"";
    const auto key_pos = json.find(key_pattern);
    if (key_pos == std::string_view::npos) return std::nullopt;

    const auto colon_pos = json.find(':', key_pos + key_pattern.size());
    if (colon_pos == std::string_view::npos) return std::nullopt;

    const auto quote_start = json.find('"', colon_pos + 1);
    if (quote_start == std::string_view::npos) return std::nullopt;

    const auto quote_end = json.find('"', quote_start + 1);
    if (quote_end == std::string_view::npos) return std::nullopt;

    return std::string(json.substr(quote_start + 1, quote_end - quote_start - 1));
}

std::optional<float> get_json_float(const std::string_view json, const std::string_view key) {
    const std::string key_pattern = "\"" + std::string(key) + "\"";
    const auto key_pos = json.find(key_pattern);
    if (key_pos == std::string_view::npos) return std::nullopt;

    const auto colon_pos = json.find(':', key_pos + key_pattern.size());
    if (colon_pos == std::string_view::npos) return std::nullopt;

    std::size_t pos = colon_pos + 1;
    while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t' || json[pos] == '\n' || json[pos] == '\r')) {
        ++pos;
    }

    try {
        std::size_t consumed = 0;
        const float value = std::stof(std::string(json.substr(pos)), &consumed);
        if (consumed == 0) return std::nullopt;
        return value;
    } catch (...) {
        return std::nullopt;
    }
}

std::optional<int> get_json_int(const std::string_view json, const std::string_view key) {
    const auto value = get_json_float(json, key);
    if (!value.has_value()) return std::nullopt;
    return static_cast<int>(*value);
}

std::optional<bool> get_json_bool(const std::string_view json, const std::string_view key) {
    const std::string key_pattern = "\"" + std::string(key) + "\"";
    const auto key_pos = json.find(key_pattern);
    if (key_pos == std::string_view::npos) return std::nullopt;

    const auto colon_pos = json.find(':', key_pos + key_pattern.size());
    if (colon_pos == std::string_view::npos) return std::nullopt;

    std::size_t pos = colon_pos + 1;
    while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t' || json[pos] == '\n' || json[pos] == '\r')) {
        ++pos;
    }

    if (json.substr(pos, 4) == "true") return true;
    if (json.substr(pos, 5) == "false") return false;
    return std::nullopt;
}

std::vector<std::string_view> get_json_object_array(const std::string_view json, const std::string_view key) {
    std::vector<std::string_view> result;
    const std::string key_pattern = "\"" + std::string(key) + "\"";
    const auto key_pos = json.find(key_pattern);
    if (key_pos == std::string_view::npos) return result;

    const auto array_start = json.find('[', key_pos + key_pattern.size());
    if (array_start == std::string_view::npos) return result;

    bool in_string = false;
    bool escaped = false;
    int object_depth = 0;
    std::size_t object_start = std::string_view::npos;

    for (std::size_t pos = array_start + 1; pos < json.size(); ++pos) {
        const char c = json[pos];
        if (in_string) {
            if (escaped) {
                escaped = false;
            } else if (c == '\\') {
                escaped = true;
            } else if (c == '"') {
                in_string = false;
            }
            continue;
        }

        if (c == '"') {
            in_string = true;
            continue;
        }
        if (c == '{') {
            if (object_depth == 0) object_start = pos;
            ++object_depth;
            continue;
        }
        if (c == '}') {
            if (object_depth <= 0) return {};
            --object_depth;
            if (object_depth == 0 && object_start != std::string_view::npos) {
                result.push_back(json.substr(object_start, pos - object_start + 1));
                object_start = std::string_view::npos;
            }
            continue;
        }
        if (c == ']' && object_depth == 0) break;
    }

    return result;
}

AnimationDriver parse_driver(const std::string_view value) {
    if (value == "time") return AnimationDriver::Time;
    if (value == "oscillate") return AnimationDriver::Oscillate;
    if (value == "path") return AnimationDriver::Path;
    if (value == "state") return AnimationDriver::State;
    if (value == "distance") return AnimationDriver::Distance;
    return AnimationDriver::Rotation;
}

AnimatedPropLayerDef parse_layer(const std::string_view json, const int fallback_index) {
    AnimatedPropLayerDef layer;
    layer.id = get_json_string(json, "id").value_or("layer_" + std::to_string(fallback_index));
    layer.sprite_path = get_json_string(json, "atlas")
        .value_or(get_json_string(json, "sprite").value_or("assets/props/windmill_rotor.png"));
    layer.driver = parse_driver(get_json_string(json, "driver").value_or("rotation"));

    const std::string presentation = get_json_string(json, "presentation").value_or("transform_rotation");
    layer.presentation = presentation == "atlas_phase"
        ? VisualPresentation::AtlasPhase
        : VisualPresentation::TransformRotation;

    layer.mount_point_x = get_json_float(json, "mountPointX").value_or(64.0F);
    layer.mount_point_y = get_json_float(json, "mountPointY").value_or(48.0F);
    layer.pivot_x = get_json_float(json, "pivotX").value_or(64.0F);
    layer.pivot_y = get_json_float(json, "pivotY").value_or(64.0F);
    layer.render_order = get_json_int(json, "renderOrder").value_or(fallback_index + 1);

    layer.atlas.frame_count = get_json_int(json, "frameCount").value_or(1);
    layer.atlas.columns = get_json_int(json, "columns").value_or(layer.atlas.frame_count);
    layer.atlas.rows = get_json_int(json, "rows").value_or(1);
    layer.atlas.phase_offset = get_json_float(json, "phaseOffset").value_or(0.0F);
    layer.atlas.loop = get_json_bool(json, "loop").value_or(true);

    return layer;
}

} // namespace

bool AnimatedPropCatalog::load_manifest(const std::filesystem::path& manifest_path) {
    if (!std::filesystem::exists(manifest_path)) return false;

    try {
        std::ifstream file(manifest_path, std::ios::in | std::ios::binary);
        if (!file.is_open()) return false;

        std::ostringstream ss;
        ss << file.rdbuf();
        const std::string content = ss.str();

        const auto contract = get_json_string(content, "contract");
        if (!contract || *contract != "CH_ANIMATED_PROP_V1") {
            return false;
        }

        AnimatedPropDefinition def;
        def.contract = *contract;
        def.id = get_json_string(content, "id").value_or("");
        def.base_static_path = get_json_string(content, "base_static").value_or("assets/props/windmill_base.png");
        def.base_width = get_json_float(content, "baseWidth").value_or(0.0F);
        def.base_height = get_json_float(content, "baseHeight").value_or(0.0F);

        if (def.id.empty()) {
            std::cerr << "AnimatedPropCatalog: Missing id in " << manifest_path << '\n';
            return false;
        }

        const std::vector<std::string_view> layer_objects = get_json_object_array(content, "layers");
        if (!layer_objects.empty()) {
            def.layers.reserve(layer_objects.size());
            for (std::size_t index = 0; index < layer_objects.size(); ++index) {
                AnimatedPropLayerDef layer = parse_layer(layer_objects[index], static_cast<int>(index));
                if (layer.sprite_path.empty()) {
                    std::cerr << "AnimatedPropCatalog: Missing layer sprite in " << manifest_path << '\n';
                    return false;
                }
                if (layer.presentation == VisualPresentation::AtlasPhase && !layer.atlas.valid()) {
                    std::cerr << "AnimatedPropCatalog: Invalid atlas metadata in " << manifest_path << '\n';
                    return false;
                }
                def.layers.push_back(std::move(layer));
            }
        } else {
            // Backward compatibility with the original single-layer proof-of-concept manifest.
            AnimatedPropLayerDef layer = parse_layer(content, 0);
            layer.id = get_json_string(content, "layerId").value_or("rotor");
            def.layers.push_back(std::move(layer));
        }

        std::stable_sort(def.layers.begin(), def.layers.end(), [](const AnimatedPropLayerDef& left, const AnimatedPropLayerDef& right) {
            return left.render_order < right.render_order;
        });

        catalog_[def.id] = std::move(def);
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
    for (const auto& entry : std::filesystem::recursive_directory_iterator(
             directory_path, std::filesystem::directory_options::skip_permission_denied)) {
        if (entry.is_regular_file() && entry.path().extension() == ".json") {
            if (load_manifest(entry.path())) loaded_any = true;
        }
    }
    return loaded_any;
}

const AnimatedPropDefinition* AnimatedPropCatalog::find_prop(const std::string& prop_id) const {
    const auto it = catalog_.find(prop_id);
    return it != catalog_.end() ? &it->second : nullptr;
}

} // namespace ch
