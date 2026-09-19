#pragma once

#include "semantic_contracts.h"
#include "map_document.h"
#include "terrain_semantics.h"
#include <vector>
#include <memory>
#include <string_view>

namespace ch {

struct AssetFootprintInfo {
    int width = 1;
    int height = 1;
    bool declared = false;
};

// Pure Core interface for resolving asset footprints without depending on BuildingCatalog/BuildingSystem
class IAssetCatalogView {
public:
    virtual ~IAssetCatalogView() = default;
    virtual AssetFootprintInfo get_footprint(std::string_view asset_id) const = 0;
};

// View structure referencing existing world authorities (no logic duplicated)
struct SemanticWorldView {
    const MapDocument* map_document{nullptr};
    const TerrainSemanticCatalog* terrain_catalog{nullptr};
    int map_min{contracts::kMapMin};
    int map_max{contracts::kMapMax};
};

class SemanticGrid {
public:
    static TileSemanticInfo inspect_tile_channels(const SemanticWorldView& world, GridCoord tile);
    static std::vector<SemanticDivergence> validate_map_semantics(const SemanticWorldView& world, const IAssetCatalogView& catalog);
};

} // namespace ch
