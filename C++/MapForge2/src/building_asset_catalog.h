#pragma once

#include "building_composer.h"

#include <QJsonObject>
#include <QString>
#include <QVector>

namespace ch::studio {

struct BuildingAssetRecord {
    QString stem;
    QString manifest_path;
    QString directory;
    QString thumbnail_path;
    QString typology_id;
    QString typology_name;
    QString footprint_shape;
    int footprint_width = 0;
    int footprint_depth = 0;
    int floor_count = 0;
    bool export_ready = false;
    bool lod_valid = false;
    bool urban_valid = false;
    bool can_reopen = false;
    BuildingComposerSpec authoring_spec;
};

class BuildingAssetCatalog final {
public:
    static QJsonObject serializeSpec(const BuildingComposerSpec& spec);
    static bool deserializeSpec(const QJsonObject& object, BuildingComposerSpec* spec,
                                QString* error = nullptr);

    static QVector<BuildingAssetRecord> scan(const QString& root_directory,
                                             QString* error = nullptr);
    static QJsonObject contractManifest();
};

} // namespace ch::studio
