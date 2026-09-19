#pragma once

#include "building_composer.h"

#include <QImage>
#include <QJsonObject>
#include <QSize>

namespace ch::studio {

class BuildingVisualReferenceGate final {
public:
    static BuildingComposerSpec referenceSpec();

    static QImage renderHeroReview(QSize canvas = QSize(1040, 640));
    static QImage renderMaterialBoard(QSize canvas = QSize(1040, 720));
    static QImage renderShadowBoard(QSize canvas = QSize(1040, 430));
    static QImage renderLodBoard(QSize canvas = QSize(1040, 430));
    static QImage renderBlockBoard(QSize canvas = QSize(1040, 620));

    static QJsonObject manifest();
};

} // namespace ch::studio
