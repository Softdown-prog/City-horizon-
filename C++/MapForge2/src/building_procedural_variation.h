#pragma once

#include "building_composer.h"

#include <QJsonObject>

namespace ch::studio {

class BuildingProceduralVariation final {
public:
    static BuildingComposerSpec generate(const BuildingComposerSpec& base);
    static QJsonObject manifest(const BuildingComposerSpec& spec);
};

} // namespace ch::studio
