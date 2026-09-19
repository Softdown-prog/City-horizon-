#pragma once

#include "building_composer.h"

#include <QImage>
#include <QJsonObject>
#include <QSize>

namespace ch::studio {

class BuildingBlockPreviewRenderer final {
public:
    static QImage render(const BuildingComposerSpec& focus_spec,
                         QSize canvas = QSize(960, 560),
                         int neighborhood_seed = 401);
    static QJsonObject manifest(int neighborhood_seed = 401);
};

} // namespace ch::studio
