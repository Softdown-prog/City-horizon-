#pragma once

#include "building_composer.h"

#include <QImage>
#include <QJsonObject>
#include <QSize>
#include <QString>

namespace ch::studio {

class BuildingRoofEditorRenderer final {
public:
    static QString roofProfileName(BuildingRoofStyle style) {
        switch (style) {
            case BuildingRoofStyle::Gable: return QStringLiteral("gable");
            case BuildingRoofStyle::Hip: return QStringLiteral("hip");
            case BuildingRoofStyle::Pyramid: return QStringLiteral("pyramid");
            case BuildingRoofStyle::Flat: return QStringLiteral("flat");
            case BuildingRoofStyle::Shed: return QStringLiteral("shed");
            case BuildingRoofStyle::Mansard: return QStringLiteral("mansard");
        }
        return QStringLiteral("gable");
    }

    static QImage renderView(const BuildingComposerSpec& spec, BuildingView view,
                             QSize canvas = QSize(320, 280));
    static QImage renderSpriteSheet(const BuildingComposerSpec& spec,
                                    QSize cell = QSize(320, 280));
    static QImage renderReviewSheet(const BuildingComposerSpec& spec,
                                    QSize cell = QSize(300, 260));
    static QJsonObject roofEditorManifest(const BuildingComposerSpec& spec);
};

} // namespace ch::studio
