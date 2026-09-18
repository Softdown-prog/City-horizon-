#pragma once

#include "building_composer.h"

#include <QJsonObject>
#include <QPoint>
#include <QString>
#include <vector>

namespace ch::studio {

struct BuildingFootprintMask {
    int width = 1;
    int depth = 1;
    std::vector<QPoint> occupied_cells;

    bool contains(int x, int y) const;
    int occupiedCount() const { return static_cast<int>(occupied_cells.size()); }
};

class BuildingFootprintModel final {
public:
    static QString shapeId(BuildingFootprintShape shape);
    static QString shapeName(BuildingFootprintShape shape);
    static BuildingFootprintMask mask(const BuildingComposerSpec& spec);
    static bool isValid(const BuildingComposerSpec& spec, QString* reason = nullptr);
    static QJsonObject manifest(const BuildingComposerSpec& spec);
};

} // namespace ch::studio
