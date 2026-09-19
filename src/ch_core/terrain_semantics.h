#pragma once

#include <string>
#include <string_view>
#include <unordered_map>

namespace ch {

// Parsed from the declarative CH_TERRAIN_SEMANTICS_V1 catalog. This type is
// deliberately independent from image assets and CH_MASK_V1.
struct TerrainSemanticDefinition {
    std::string id;
    std::string visual_material;
    std::string surface;
    bool pedestrian_walkable = false;
    bool vehicle_driveable = false;
    bool buildable = false;
    bool farmable = false;
};

class TerrainSemanticCatalog {
public:
    // The JSON must be {"definitions":[ ... ]}. Any malformed or unknown
    // property invalidates the whole catalog (fail closed).
    explicit TerrainSemanticCatalog(std::string json = {});
    [[nodiscard]] bool valid() const { return valid_; }
    [[nodiscard]] const std::string& error() const { return error_; }
    [[nodiscard]] const TerrainSemanticDefinition* find(std::string_view id) const;

private:
    bool valid_ = false;
    std::string error_;
    std::unordered_map<std::string, TerrainSemanticDefinition> definitions_;
};

} // namespace ch
