#pragma once

#include "building_composer.h"

#include <QJsonObject>
#include <QStringList>

namespace ch::studio {

struct BuildingUrbanIntegrationValidation {
    bool valid = false;
    bool sidewalk_contact_valid = false;
    bool road_socket_valid = false;
    bool access_alignment_valid = false;
    bool facade_clearance_valid = false;
    bool visual_outset_valid = false;
    QStringList issues;
    QJsonObject details;

    QString summary() const;
    QJsonObject toJson() const;
};

class BuildingUrbanIntegrationValidator final {
public:
    // Authoring-time validation. Runtime placement still has to verify that a
    // compatible road actually exists beside the rotated socket on the map.
    static BuildingUrbanIntegrationValidation validate(const BuildingComposerSpec& spec);
};

} // namespace ch::studio
