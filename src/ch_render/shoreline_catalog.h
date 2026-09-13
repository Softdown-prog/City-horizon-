#ifndef CITY_HORIZON_CH_RENDER_SHORELINE_CATALOG_H
#define CITY_HORIZON_CH_RENDER_SHORELINE_CATALOG_H

#include "src/ch_core/shoreline_contracts.h"
#include <string>
#include <filesystem>

namespace ch {

class ShorelineCatalog {
public:
    static std::string get_piece_texture_path(ShorelinePiece piece, const std::string& set_name = "coast_adjusted");
};

} // namespace ch

#endif // CITY_HORIZON_CH_RENDER_SHORELINE_CATALOG_H
