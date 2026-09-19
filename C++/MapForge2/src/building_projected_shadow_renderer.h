#pragma once

#include "building_composer.h"

#include <QJsonObject>
#include <QSize>

class QPainter;

namespace ch::studio {

// Draws the ground-projected building shadow used by the production facade path.
// The direction is defined in world space so all four sprite views remain under
// the same sun instead of rotating the light with the camera.
class BuildingProjectedShadowRenderer final {
public:
    static void draw(QPainter& painter,
                     const BuildingComposerSpec& spec,
                     BuildingView view,
                     QSize canvas);

    static QJsonObject manifest();
};

} // namespace ch::studio
