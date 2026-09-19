#include "terrain_semantics_catalog.h"
#include <fstream>
#include <sstream>
#include <iostream>

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
} // namespace

const TerrainSemanticsCatalog& TerrainSemanticsCatalog::global_instance() {
    if (!g_has_global) {
        // Pre-populate built-in default definitions for safety
        TerrainSemanticsDefinition grass;
        grass.id = "grass"; grass.surface = "grass"; grass.buildable = true; grass.water = false; grass.pedestrian_traversable = true; grass.navigation_type = "none";
        g_global_catalog.catalog_["grass"] = grass;

        TerrainSemanticsDefinition cement;
        cement.id = "cement_path"; cement.surface = "sidewalk"; cement.buildable = false; cement.water = false; cement.pedestrian_traversable = true; cement.navigation_type = "pedestrian";
        g_global_catalog.catalog_["cement_path"] = cement;

        TerrainSemanticsDefinition sand_c;
        sand_c.id = "sand_center"; sand_c.surface = "sand"; sand_c.buildable = true; sand_c.water = false; sand_c.pedestrian_traversable = true; sand_c.navigation_type = "none";
        g_global_catalog.catalog_["sand_center"] = sand_c;

        TerrainSemanticsDefinition sand_w;
        sand_w.id = "sand_wet"; sand_w.surface = "sand"; sand_w.buildable = true; sand_w.water = false; sand_w.pedestrian_traversable = true; sand_w.navigation_type = "none";
        g_global_catalog.catalog_["sand_wet"] = sand_w;

        TerrainSemanticsDefinition o_s;
        o_s.id = "ocean_shallow"; o_s.surface = "water"; o_s.buildable = false; o_s.water = true; o_s.pedestrian_traversable = false; o_s.navigation_type = "water";
        g_global_catalog.catalog_["ocean_shallow"] = o_s;

        TerrainSemanticsDefinition o_d;
        o_d.id = "ocean_deep"; o_d.surface = "water"; o_d.buildable = false; o_d.water = true; o_d.pedestrian_traversable = false; o_d.navigation_type = "water";
        g_global_catalog.catalog_["ocean_deep"] = o_d;

        g_has_global = true;
    }
    return g_global_catalog;
}

void TerrainSemanticsCatalog::set_global_instance(const TerrainSemanticsCatalog& catalog) {
    g_global_catalog = catalog;
    g_has_global = true;
}

bool TerrainSemanticsCatalog::load_manifest(const std::filesystem::path& manifest_path) {
    if (!std::filesystem::exists(manifest_path)) return false;

    try {
        std::ifstream file(manifest_path, std::ios::in | std::ios::binary);
        if (!file.is_open()) return false;

        std::ostringstream ss;
        ss << file.rdbuf();
        const std::string content = ss.str();

        auto contract_opt = get_json_string(content, "contract");
        if (!contract_opt || *contract_opt != "CH_TERRAIN_SEMANTICS_V1") return false;

        // Parse definitions block
        std::vector<std::string> known_ids = {
            "grass", "cement_path", "sand_center", "sand_wet", "ocean_shallow", "ocean_deep"
        };

        for (const auto& id : known_ids) {
            auto pos = content.find("\"" + id + "\"");
            if (pos != std::string::npos) {
                auto block_start = content.find('{', pos);
                auto block_end = content.find('}', block_start);
                if (block_start != std::string::npos && block_end != std::string::npos) {
                    const std::string_view sub = std::string_view(content).substr(block_start, block_end - block_start + 1);
                    TerrainSemanticsDefinition def;
                    def.contract = *contract_opt;
                    def.id = id;
                    def.surface = get_json_string(sub, "surface").value_or("grass");
                    def.buildable = get_json_bool(sub, "buildable").value_or(false);
                    def.water = get_json_bool(sub, "water").value_or(false);
                    def.pedestrian_traversable = get_json_bool(sub, "pedestrianTraversable").value_or(false);
                    def.navigation_type = get_json_string(sub, "navigationType").value_or("none");

                    catalog_[id] = def;
                }
            }
        }
        return true;
    } catch (...) {
        return false;
    }
}

const TerrainSemanticsDefinition* TerrainSemanticsCatalog::find(const std::string& terrain_def_id) const {
    auto it = catalog_.find(terrain_def_id);
    if (it != catalog_.end()) {
        return &it->second;
    }
    return nullptr;
}

} // namespace ch
