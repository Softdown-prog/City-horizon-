#pragma once

#include "building_composer.h"

#include <QImage>
#include <QJsonArray>
#include <QJsonObject>
#include <QSize>

namespace ch::studio {

class BuildingFacadeRenderer final {
public:
    static QImage renderView(const BuildingComposerSpec& spec, BuildingView view,
                             QSize canvas = QSize(320, 280));
    static QImage renderSpriteSheet(const BuildingComposerSpec& spec,
                                    QSize cell = QSize(320, 280));
    static QImage renderReviewSheet(const BuildingComposerSpec& spec,
                                    QSize cell = QSize(300, 260));
    static QJsonObject manifest(const BuildingComposerSpec& spec);
};

} // namespace ch::studio
