#pragma once

#include "building_composer.h"

#include <QImage>
#include <QJsonObject>
#include <QSize>

namespace ch::studio {

// Advanced roof layer used by the Building Composer. It keeps the canonical
// building renderer as the source for walls/modules, then replaces the roof cap
// with a profile driven by the roof-editor parameters in BuildingComposerSpec.
class BuildingRoofEditorRenderer final {
public:
    static QImage renderView(const BuildingComposerSpec& spec, BuildingView view,
                             QSize canvas = QSize(320, 280));
    static QImage renderSpriteSheet(const BuildingComposerSpec& spec,
                                    QSize cell = QSize(320, 280));
    static QImage renderReviewSheet(const BuildingComposerSpec& spec,
                                    QSize cell = QSize(300, 260));
    static QJsonObject roofEditorManifest(const BuildingComposerSpec& spec);
};

} // namespace ch::studio
