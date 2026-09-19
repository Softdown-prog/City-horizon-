#pragma once

#include "building_composer.h"

#include <QImage>
#include <QJsonArray>
#include <QJsonObject>
#include <QSize>
#include <QString>

namespace ch::studio {

struct BuildingLodLevelValidation {
    QString id;
    QString label;
    float scale = 1.0F;
    bool valid = false;
    int visible_width_px = 0;
    int visible_height_px = 0;
    int visible_alpha_pixels = 0;
    int luminance_range = 0;
    QString reason;

    QJsonObject toJson() const;
};

struct BuildingLodValidation {
    bool valid = false;
    BuildingLodLevelValidation distant;
    BuildingLodLevelValidation medium;
    BuildingLodLevelValidation close;

    QString summary() const;
    QJsonObject toJson() const;
};

class BuildingLodValidator final {
public:
    static BuildingLodValidation validate(const BuildingComposerSpec& spec);
    static QImage renderReviewSheet(const BuildingComposerSpec& spec,
                                    QSize canvas = QSize(960, 420));
    static QJsonObject manifest(const BuildingComposerSpec& spec);
};

} // namespace ch::studio
