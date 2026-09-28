#ifndef CITY_HORIZON_CH_CORE_TERRAIN_SEMANTICS_CATALOG_H
#define CITY_HORIZON_CH_CORE_TERRAIN_SEMANTICS_CATALOG_H

#include <cstdint>
#include <filesystem>
#include <string>
#include <unordered_map>
#include <vector>

namespace ch {

struct TerrainSemanticsDefinition {
    std::string contract = "CH_TERRAIN_SEMANTICS_V1";
    std::string id;
    std::string surface = "grass";
    bool buildable = false;
    bool water = false;
    bool pedestrian_traversable = false;
    std::string navigation_type = "none"; // "none", "pedestrian", "water"
    std::string display_name;
    std::int64_t build_cost = 0; // Whole dollars per tile when painted by the player.
};

class TerrainSemanticsCatalog {
public:
    TerrainSemanticsCatalog() = default;

    bool load_manifest(const std::filesystem::path& manifest_path);
    [[nodiscard]] const TerrainSemanticsDefinition* find(const std::string& terrain_def_id) const;

    void clear() { catalog_.clear(); }

    [[nodiscard]] static const TerrainSemanticsCatalog& global_instance();
    static void set_global_instance(const TerrainSemanticsCatalog& catalog);

private:
    std::unordered_map<std::string, TerrainSemanticsDefinition> catalog_;
};

} // namespace ch

#endif // CITY_HORIZON_CH_CORE_TERRAIN_SEMANTICS_CATALOG_H
