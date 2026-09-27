#include "terrain_semantics_catalog.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <optional>

namespace ch {

namespace {
static TerrainSemanticsCatalog g_global_catalog;
static bool g_has_global = false;

std::optional<std::string> get_json_string(const std::string_view json, const std::string_view key) {
    const std::string key_pattern = "\"" + std::string(key) + "\"";
    std::size_t pos = 0;
    while ((pos = json.find(key_pattern, pos)) != std::string_view::npos) {
        const auto colon_pos = json.find(':', pos + key_pattern.size());
        if (colon_pos != std::string_view::npos && colon_pos - (pos + key_pattern.size()) < 10) {
            const auto quote_start = json.find('"', colon_pos + 1);
            if (quote_start != std::string_view::npos && quote_start < colon_pos + 10) {
                const auto quote_end = json.find('"', quote_start + 1);
                if (quote_end != std::string_view::npos) {
                    return std::string(json.substr(quote_start + 1, quote_end - quote_start - 1));
                }
            }
        }
        pos += key_pattern.size();
    }
    return std::nullopt;
}

std::optional<bool> get_json_bool(const std::string_view json, const std::string_view key) {
    const std::string key_pattern = "\"" + std::string(key) + "\"";
    std::size_t pos = 0;
    while ((pos = json.find(key_pattern, pos)) != std::string_view::npos) {
        const auto colon_pos = json.find(':', pos + key_pattern.size());
        if (colon_pos != std::string_view::npos && colon_pos - (pos + key_pattern.size()) < 10) {
            std::size_t val_pos = colon_pos + 1;
            while (val_pos < json.size() && (json[val_pos] == ' ' || json[val_pos] == '\t' || json[val_pos] == '\n' || json[val_pos] == '\r')) {
                ++val_pos;
            }
            if (json.substr(val_pos, 4) == "true") return true;
            if (json.substr(val_pos, 5) == "false") return false;
        }
        pos += key_pattern.size();
    }
    return std::nullopt;
}

}  // namespace

bool TerrainSemanticsCatalog::load_manifest(const std::filesystem::path& manifest_path) {
    std::ifstream file(manifest_path, std::ios::binary);
    if (!file) return false;
    std::ostringstream stream;
    stream << file.rdbuf();
    const std::string content = stream.str();
    if (content.empty()) return false;

    definitions_.clear();

    const std::string object_token = "\"id\"";
    std::size_t cursor = 0;
    while ((cursor = content.find(object_token, cursor)) != std::string::npos) {
        const auto object_start = content.rfind('{', cursor);
        if (object_start == std::string::npos) break;
        const auto object_end = content.find('}', cursor);
        if (object_end == std::string::npos) break;

        const std::string_view object{content.data() + object_start, object_end - object_start + 1};
        const auto id = get_json_string(object, "id");
        if (id && !id->empty()) {
            TerrainSemanticDefinition definition;
            definition.id = *id;
            definition.category = get_json_string(object, "category").value_or("");
            definition.material = get_json_string(object, "material").value_or("");
            definition.buildable = get_json_bool(object, "buildable").value_or(false);
            definition.walkable = get_json_bool(object, "walkable").value_or(false);
            definition.drivable = get_json_bool(object, "drivable").value_or(false);
            definitions_[definition.id] = std::move(definition);
        }
        cursor = object_end + 1;
    }

    const bool success = !definitions_.empty();
    if (!success) {
        std::cerr << "Terrain semantics catalog loaded no definitions from " << manifest_path << '\n';
    }
    return success;
}

const TerrainSemanticDefinition* TerrainSemanticsCatalog::find(const std::string_view id) const {
    const auto found = definitions_.find(std::string(id));
    return found == definitions_.end() ? nullptr : &found->second;
}

bool TerrainSemanticsCatalog::has(const std::string_view id) const {
    return find(id) != nullptr;
}

void set_global_terrain_semantics_catalog(TerrainSemanticsCatalog catalog) {
    g_global_catalog = std::move(catalog);
    g_has_global = true;
}

const TerrainSemanticsCatalog* global_terrain_semantics_catalog() {
    return g_has_global ? &g_global_catalog : nullptr;
}

}  // namespace ch
