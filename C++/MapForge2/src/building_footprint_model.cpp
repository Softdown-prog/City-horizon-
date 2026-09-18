#include "building_footprint_model.h"

#include <QJsonArray>

#include <algorithm>

namespace ch::studio {

bool BuildingFootprintMask::contains(const int x, const int y) const {
    return std::find(occupied_cells.begin(), occupied_cells.end(), QPoint(x, y)) != occupied_cells.end();
}

QString BuildingFootprintModel::shapeId(const BuildingFootprintShape shape) {
    switch (shape) {
        case BuildingFootprintShape::Rectangle: return QStringLiteral("rectangle");
        case BuildingFootprintShape::LShape: return QStringLiteral("l_shape");
        case BuildingFootprintShape::Courtyard: return QStringLiteral("courtyard");
        case BuildingFootprintShape::Annex: return QStringLiteral("annex");
    }
    return QStringLiteral("rectangle");
}

QString BuildingFootprintModel::shapeName(const BuildingFootprintShape shape) {
    switch (shape) {
        case BuildingFootprintShape::Rectangle: return QStringLiteral("Rectangle");
        case BuildingFootprintShape::LShape: return QStringLiteral("L shape");
        case BuildingFootprintShape::Courtyard: return QStringLiteral("Courtyard");
        case BuildingFootprintShape::Annex: return QStringLiteral("Annex / stepped");
    }
    return QStringLiteral("Rectangle");
}

BuildingFootprintMask BuildingFootprintModel::mask(const BuildingComposerSpec& spec) {
    BuildingFootprintMask result;
    result.width = std::clamp(spec.footprint_width_tiles, 1, 8);
    result.depth = std::clamp(spec.footprint_depth_tiles, 1, 8);

    const int cut_w = std::clamp(spec.footprint_cutout_width_tiles, 1, std::max(1, result.width - 1));
    const int cut_d = std::clamp(spec.footprint_cutout_depth_tiles, 1, std::max(1, result.depth - 1));
    const int annex_d = std::clamp(spec.footprint_annex_depth_tiles, 1, result.depth);
    const int annex_offset = std::clamp(spec.footprint_annex_offset_tiles, 0, std::max(0, result.depth - annex_d));

    for (int y = 0; y < result.depth; ++y) {
        for (int x = 0; x < result.width; ++x) {
            bool occupied = true;
            switch (spec.footprint_shape) {
                case BuildingFootprintShape::Rectangle:
                    occupied = true;
                    break;
                case BuildingFootprintShape::LShape:
                    if (result.width < 2 || result.depth < 2) {
                        occupied = true;
                    } else {
                        occupied = !(x >= result.width - cut_w && y < cut_d);
                    }
                    break;
                case BuildingFootprintShape::Courtyard: {
                    if (result.width < 3 || result.depth < 3) {
                        occupied = true;
                        break;
                    }
                    const int inner_w = std::clamp(cut_w, 1, result.width - 2);
                    const int inner_d = std::clamp(cut_d, 1, result.depth - 2);
                    const int inner_x0 = (result.width - inner_w) / 2;
                    const int inner_y0 = (result.depth - inner_d) / 2;
                    occupied = !(x >= inner_x0 && x < inner_x0 + inner_w &&
                                 y >= inner_y0 && y < inner_y0 + inner_d);
                    break;
                }
                case BuildingFootprintShape::Annex:
                    if (result.width < 2) {
                        occupied = true;
                    } else {
                        occupied = x < result.width - 1 ||
                                   (y >= annex_offset && y < annex_offset + annex_d);
                    }
                    break;
            }
            if (occupied) result.occupied_cells.emplace_back(x, y);
        }
    }
    return result;
}

bool BuildingFootprintModel::isValid(const BuildingComposerSpec& spec, QString* reason) {
    const int width = spec.footprint_width_tiles;
    const int depth = spec.footprint_depth_tiles;
    if (width < 1 || width > 8 || depth < 1 || depth > 8) {
        if (reason) *reason = QStringLiteral("footprint envelope must stay inside 1..8 tiles per axis");
        return false;
    }
    if (spec.footprint_shape == BuildingFootprintShape::LShape && (width < 2 || depth < 2)) {
        if (reason) *reason = QStringLiteral("L shape requires at least a 2x2 envelope");
        return false;
    }
    if (spec.footprint_shape == BuildingFootprintShape::Courtyard && (width < 3 || depth < 3)) {
        if (reason) *reason = QStringLiteral("courtyard requires at least a 3x3 envelope");
        return false;
    }
    if (spec.footprint_shape == BuildingFootprintShape::Annex && width < 2) {
        if (reason) *reason = QStringLiteral("annex shape requires at least 2 tiles of width");
        return false;
    }
    for (const float setback : {spec.footprint_setback_front_tiles, spec.footprint_setback_back_tiles,
                                spec.footprint_setback_left_tiles, spec.footprint_setback_right_tiles}) {
        if (setback < 0.0F || setback > 2.0F) {
            if (reason) *reason = QStringLiteral("setbacks must remain inside 0..2 tiles");
            return false;
        }
    }
    const BuildingFootprintMask generated = mask(spec);
    if (generated.occupied_cells.empty()) {
        if (reason) *reason = QStringLiteral("footprint must contain at least one occupied cell");
        return false;
    }
    if (reason) reason->clear();
    return true;
}

QJsonObject BuildingFootprintModel::manifest(const BuildingComposerSpec& spec) {
    const BuildingFootprintMask generated = mask(spec);
    QJsonArray cells;
    for (const QPoint& cell : generated.occupied_cells)
        cells.append(QJsonObject{{"x", cell.x()}, {"y", cell.y()}});

    QString validation_reason;
    const bool valid = isValid(spec, &validation_reason);
    return QJsonObject{
        {"version", QStringLiteral("flexible_footprint_1")},
        {"shape", shapeId(spec.footprint_shape)},
        {"envelope", QJsonObject{{"widthTiles", generated.width}, {"depthTiles", generated.depth}}},
        {"occupiedCellCount", generated.occupiedCount()},
        {"occupiedCells", cells},
        {"cutout", QJsonObject{
            {"widthTiles", spec.footprint_cutout_width_tiles},
            {"depthTiles", spec.footprint_cutout_depth_tiles},
        }},
        {"annex", QJsonObject{
            {"depthTiles", spec.footprint_annex_depth_tiles},
            {"offsetTiles", spec.footprint_annex_offset_tiles},
        }},
        {"setbacks", QJsonObject{
            {"frontTiles", static_cast<double>(spec.footprint_setback_front_tiles)},
            {"backTiles", static_cast<double>(spec.footprint_setback_back_tiles)},
            {"leftTiles", static_cast<double>(spec.footprint_setback_left_tiles)},
            {"rightTiles", static_cast<double>(spec.footprint_setback_right_tiles)},
        }},
        {"placementUsesOccupiedCells", true},
        {"rotatesWithBuilding", true},
        {"valid", valid},
        {"validationReason", validation_reason},
    };
}

} // namespace ch::studio
