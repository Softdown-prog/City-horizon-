#include "src/ch_render/shoreline_catalog.h"

namespace ch {

std::string ShorelineCatalog::get_piece_texture_path(ShorelinePiece piece, const std::string& set_name) {
    std::string base_dir = "assets/terrain/" + set_name + "/";
    switch (piece) {
        case ShorelinePiece::border_north: return base_dir + "coast_border_north.png";
        case ShorelinePiece::border_east:  return base_dir + "coast_border_east.png";
        case ShorelinePiece::border_south: return base_dir + "coast_border_south.png";
        case ShorelinePiece::border_west:  return base_dir + "coast_border_west.png";

        case ShorelinePiece::outer_ne:     return base_dir + "coast_corner_outer_ne.png";
        case ShorelinePiece::outer_se:     return base_dir + "coast_corner_outer_se.png";
        case ShorelinePiece::outer_sw:     return base_dir + "coast_corner_outer_sw.png";
        case ShorelinePiece::outer_nw:     return base_dir + "coast_corner_outer_nw.png";

        case ShorelinePiece::inner_ne:     return base_dir + "coast_corner_inner_ne.png";
        case ShorelinePiece::inner_se:     return base_dir + "coast_corner_inner_se.png";
        case ShorelinePiece::inner_sw:     return base_dir + "coast_corner_inner_sw.png";
        case ShorelinePiece::inner_nw:     return base_dir + "coast_corner_inner_nw.png";
    }
    return base_dir + "coast_border_north.png";
}

} // namespace ch
