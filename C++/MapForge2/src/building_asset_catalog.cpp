#include "building_asset_catalog.h"

#include "building_footprint_model.h"
#include "building_roof_editor_renderer.h"

#include <QDir>
#include <QDirIterator>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>

#include <algorithm>

namespace ch::studio {
namespace {

template <typename Enum>
int enumValue(const Enum value) { return static_cast<int>(value); }

template <typename Enum>
Enum enumFrom(const QJsonObject& object, const char* key, const Enum fallback) {
    const QJsonValue value = object.value(QLatin1String(key));
    return value.isDouble() ? static_cast<Enum>(value.toInt(enumValue(fallback))) : fallback;
}

QJsonObject colorObject(const QColor& color) {
    return QJsonObject{{"rgba", color.name(QColor::HexArgb)}};
}

QColor colorFrom(const QJsonObject& object, const char* key, const QColor& fallback) {
    const QJsonObject color = object.value(QLatin1String(key)).toObject();
    const QString text = color.value(QStringLiteral("rgba")).toString();
    const QColor parsed(text);
    return parsed.isValid() ? parsed : fallback;
}

QJsonObject moduleJson(const BuildingFacadeModulePlacement& module) {
    return QJsonObject{
        {"kind", enumValue(module.kind)},
        {"edge", enumValue(module.edge)},
        {"floor", module.floor_index},
        {"position", static_cast<double>(module.position)},
        {"width", static_cast<double>(module.width)},
        {"enabled", module.enabled},
    };
}

} // namespace

QJsonObject BuildingAssetCatalog::serializeSpec(const BuildingComposerSpec& spec) {
    QJsonArray modules;
    for (const auto& module : spec.facade_modules) modules.append(moduleJson(module));

    return QJsonObject{
        {"version", QStringLiteral("building_authoring_spec_1")},
        {"visualPreset", enumValue(spec.visual_preset)},
        {"typology", enumValue(spec.building_typology)},
        {"footprintShape", enumValue(spec.footprint_shape)},
        {"footprintWidthTiles", spec.footprint_width_tiles},
        {"footprintDepthTiles", spec.footprint_depth_tiles},
        {"footprintCutoutWidthTiles", spec.footprint_cutout_width_tiles},
        {"footprintCutoutDepthTiles", spec.footprint_cutout_depth_tiles},
        {"footprintAnnexDepthTiles", spec.footprint_annex_depth_tiles},
        {"footprintAnnexOffsetTiles", spec.footprint_annex_offset_tiles},
        {"setbackFrontTiles", static_cast<double>(spec.footprint_setback_front_tiles)},
        {"setbackBackTiles", static_cast<double>(spec.footprint_setback_back_tiles)},
        {"setbackLeftTiles", static_cast<double>(spec.footprint_setback_left_tiles)},
        {"setbackRightTiles", static_cast<double>(spec.footprint_setback_right_tiles)},
        {"floorCount", spec.floor_count},
        {"floorHeightPx", spec.floor_height_px},
        {"floorBandsEnabled", spec.floor_bands_enabled},
        {"wallHeightPx", spec.wall_height_px},
        {"roofHeightPx", spec.roof_height_px},
        {"roofStyle", enumValue(spec.roof_style)},
        {"roofPitchDegrees", static_cast<double>(spec.roof_pitch_degrees)},
        {"roofOverhang", static_cast<double>(spec.roof_overhang)},
        {"roofFasciaThicknessPx", static_cast<double>(spec.roof_fascia_thickness_px)},
        {"roofRidgeScale", static_cast<double>(spec.roof_ridge_scale)},
        {"roofFasciaEnabled", spec.roof_fascia_enabled},
        {"roofRidgeEnabled", spec.roof_ridge_enabled},
        {"facadeEditorEnabled", spec.facade_editor_enabled},
        {"facadeModules", modules},
        {"sidewalkEnabled", spec.sidewalk_enabled},
        {"sidewalkDepthTiles", static_cast<double>(spec.sidewalk_depth_tiles)},
        {"sidewalkLateralMarginTiles", static_cast<double>(spec.sidewalk_lateral_margin_tiles)},
        {"roadSocketEnabled", spec.road_socket_enabled},
        {"roadSocketEdge", enumValue(spec.road_socket_edge)},
        {"roadSocketType", enumValue(spec.road_socket_type)},
        {"roadSocketPosition", static_cast<double>(spec.road_socket_position)},
        {"roadSocketWidthTiles", static_cast<double>(spec.road_socket_width_tiles)},
        {"wallColor", colorObject(spec.wall_color)},
        {"roofColor", colorObject(spec.roof_color)},
        {"trimColor", colorObject(spec.trim_color)},
        {"glassColor", colorObject(spec.glass_color)},
        {"doorColor", colorObject(spec.door_color)},
        {"accentColor", colorObject(spec.accent_color)},
        {"windows", spec.windows},
        {"southDoor", spec.south_door},
        {"southAwning", spec.south_awning},
        {"southSign", spec.south_sign},
        {"roofChimney", spec.roof_chimney},
        {"castShadow", spec.cast_shadow},
        {"doorPosition", enumValue(spec.door_position)},
        {"windowPattern", enumValue(spec.window_pattern)},
        {"wallMaterial", enumValue(spec.wall_material)},
        {"roofMaterial", enumValue(spec.roof_material)},
        {"materialStrength", static_cast<double>(spec.material_strength)},
        {"materialScale", static_cast<double>(spec.material_scale)},
        {"materialVariation", static_cast<double>(spec.material_variation)},
        {"materialContrast", static_cast<double>(spec.material_contrast)},
        {"materialSeed", spec.material_seed},
        {"proceduralVariationEnabled", spec.procedural_variation_enabled},
        {"proceduralVariationApplied", spec.procedural_variation_applied},
        {"proceduralVariationSeed", spec.procedural_variation_seed},
        {"proceduralVariationStrength", static_cast<double>(spec.procedural_variation_strength)},
        {"proceduralVaryPalette", spec.procedural_vary_palette},
        {"proceduralVaryMaterials", spec.procedural_vary_materials},
        {"proceduralVaryRoof", spec.procedural_vary_roof},
        {"proceduralVaryModules", spec.procedural_vary_modules},
    };
}

bool BuildingAssetCatalog::deserializeSpec(const QJsonObject& object, BuildingComposerSpec* spec,
                                           QString* error) {
    if (!spec) {
        if (error) *error = QStringLiteral("No destination spec supplied.");
        return false;
    }
    if (object.value(QStringLiteral("version")).toString() != QStringLiteral("building_authoring_spec_1")) {
        if (error) *error = QStringLiteral("Unsupported or missing building authoring spec.");
        return false;
    }

    BuildingComposerSpec result = BuildingComposer::presetSpec();
    result.visual_preset = enumFrom(object, "visualPreset", result.visual_preset);
    result.building_typology = enumFrom(object, "typology", result.building_typology);
    result.footprint_shape = enumFrom(object, "footprintShape", result.footprint_shape);
    result.footprint_width_tiles = std::clamp(object.value("footprintWidthTiles").toInt(2), 1, 8);
    result.footprint_depth_tiles = std::clamp(object.value("footprintDepthTiles").toInt(1), 1, 8);
    result.footprint_cutout_width_tiles = object.value("footprintCutoutWidthTiles").toInt(1);
    result.footprint_cutout_depth_tiles = object.value("footprintCutoutDepthTiles").toInt(1);
    result.footprint_annex_depth_tiles = object.value("footprintAnnexDepthTiles").toInt(1);
    result.footprint_annex_offset_tiles = object.value("footprintAnnexOffsetTiles").toInt(0);
    result.footprint_setback_front_tiles = static_cast<float>(object.value("setbackFrontTiles").toDouble(0.0));
    result.footprint_setback_back_tiles = static_cast<float>(object.value("setbackBackTiles").toDouble(0.0));
    result.footprint_setback_left_tiles = static_cast<float>(object.value("setbackLeftTiles").toDouble(0.0));
    result.footprint_setback_right_tiles = static_cast<float>(object.value("setbackRightTiles").toDouble(0.0));
    result.floor_count = std::clamp(object.value("floorCount").toInt(1), 1, 8);
    result.floor_height_px = std::clamp(object.value("floorHeightPx").toInt(82), 36, 132);
    result.floor_bands_enabled = object.value("floorBandsEnabled").toBool(true);
    result.wall_height_px = object.value("wallHeightPx").toInt(result.floor_height_px);
    result.roof_height_px = object.value("roofHeightPx").toInt(34);
    result.roof_style = enumFrom(object, "roofStyle", result.roof_style);
    result.roof_pitch_degrees = static_cast<float>(object.value("roofPitchDegrees").toDouble(35.0));
    result.roof_overhang = static_cast<float>(object.value("roofOverhang").toDouble(0.10));
    result.roof_fascia_thickness_px = static_cast<float>(object.value("roofFasciaThicknessPx").toDouble(2.8));
    result.roof_ridge_scale = static_cast<float>(object.value("roofRidgeScale").toDouble(1.0));
    result.roof_fascia_enabled = object.value("roofFasciaEnabled").toBool(true);
    result.roof_ridge_enabled = object.value("roofRidgeEnabled").toBool(true);
    result.facade_editor_enabled = object.value("facadeEditorEnabled").toBool(false);
    result.facade_modules.clear();
    for (const QJsonValue& value : object.value("facadeModules").toArray()) {
        const QJsonObject module = value.toObject();
        BuildingFacadeModulePlacement placement;
        placement.kind = enumFrom(module, "kind", placement.kind);
        placement.edge = enumFrom(module, "edge", placement.edge);
        placement.floor_index = std::clamp(module.value("floor").toInt(0), 0, result.floor_count - 1);
        placement.position = static_cast<float>(module.value("position").toDouble(0.50));
        placement.width = static_cast<float>(module.value("width").toDouble(0.22));
        placement.enabled = module.value("enabled").toBool(true);
        result.facade_modules.push_back(placement);
    }
    result.sidewalk_enabled = object.value("sidewalkEnabled").toBool(true);
    result.sidewalk_depth_tiles = static_cast<float>(object.value("sidewalkDepthTiles").toDouble(0.30));
    result.sidewalk_lateral_margin_tiles = static_cast<float>(object.value("sidewalkLateralMarginTiles").toDouble(0.55));
    result.road_socket_enabled = object.value("roadSocketEnabled").toBool(true);
    result.road_socket_edge = enumFrom(object, "roadSocketEdge", result.road_socket_edge);
    result.road_socket_type = enumFrom(object, "roadSocketType", result.road_socket_type);
    result.road_socket_position = static_cast<float>(object.value("roadSocketPosition").toDouble(0.50));
    result.road_socket_width_tiles = static_cast<float>(object.value("roadSocketWidthTiles").toDouble(0.36));
    result.wall_color = colorFrom(object, "wallColor", result.wall_color);
    result.roof_color = colorFrom(object, "roofColor", result.roof_color);
    result.trim_color = colorFrom(object, "trimColor", result.trim_color);
    result.glass_color = colorFrom(object, "glassColor", result.glass_color);
    result.door_color = colorFrom(object, "doorColor", result.door_color);
    result.accent_color = colorFrom(object, "accentColor", result.accent_color);
    result.windows = object.value("windows").toBool(true);
    result.south_door = object.value("southDoor").toBool(true);
    result.south_awning = object.value("southAwning").toBool(false);
    result.south_sign = object.value("southSign").toBool(false);
    result.roof_chimney = object.value("roofChimney").toBool(false);
    result.cast_shadow = object.value("castShadow").toBool(true);
    result.door_position = enumFrom(object, "doorPosition", result.door_position);
    result.window_pattern = enumFrom(object, "windowPattern", result.window_pattern);
    result.wall_material = enumFrom(object, "wallMaterial", result.wall_material);
    result.roof_material = enumFrom(object, "roofMaterial", result.roof_material);
    result.material_strength = static_cast<float>(object.value("materialStrength").toDouble(0.45));
    result.material_scale = static_cast<float>(object.value("materialScale").toDouble(1.0));
    result.material_variation = static_cast<float>(object.value("materialVariation").toDouble(0.35));
    result.material_contrast = static_cast<float>(object.value("materialContrast").toDouble(0.45));
    result.material_seed = object.value("materialSeed").toInt(17);
    result.procedural_variation_enabled = object.value("proceduralVariationEnabled").toBool(false);
    result.procedural_variation_applied = object.value("proceduralVariationApplied").toBool(false);
    result.procedural_variation_seed = object.value("proceduralVariationSeed").toInt(101);
    result.procedural_variation_strength = static_cast<float>(object.value("proceduralVariationStrength").toDouble(0.35));
    result.procedural_vary_palette = object.value("proceduralVaryPalette").toBool(true);
    result.procedural_vary_materials = object.value("proceduralVaryMaterials").toBool(true);
    result.procedural_vary_roof = object.value("proceduralVaryRoof").toBool(true);
    result.procedural_vary_modules = object.value("proceduralVaryModules").toBool(true);

    *spec = result;
    return true;
}

QVector<BuildingAssetRecord> BuildingAssetCatalog::scan(const QString& root_directory,
                                                        QString* error) {
    QVector<BuildingAssetRecord> records;
    const QDir root(root_directory);
    if (!root.exists()) {
        if (error) *error = QStringLiteral("Asset library folder does not exist: %1").arg(root_directory);
        return records;
    }

    QDirIterator iterator(root_directory, QStringList{QStringLiteral("*_manifest.json")},
                          QDir::Files, QDirIterator::Subdirectories);
    while (iterator.hasNext()) {
        const QString manifest_path = iterator.next();
        QFile file(manifest_path);
        if (!file.open(QIODevice::ReadOnly)) continue;
        QJsonParseError parse_error;
        const QJsonDocument document = QJsonDocument::fromJson(file.readAll(), &parse_error);
        if (parse_error.error != QJsonParseError::NoError || !document.isObject()) continue;
        const QJsonObject manifest = document.object();
        const QFileInfo info(manifest_path);

        BuildingAssetRecord record;
        record.manifest_path = manifest_path;
        record.directory = info.absolutePath();
        record.stem = info.completeBaseName();
        if (record.stem.endsWith(QStringLiteral("_manifest"))) record.stem.chop(9);

        const QJsonObject geometry = manifest.value(QStringLiteral("geometry")).toObject();
        const QJsonObject footprint = geometry.value(QStringLiteral("flexibleFootprint")).toObject();
        record.footprint_shape = footprint.value(QStringLiteral("shape")).toString(QStringLiteral("rectangle"));
        record.footprint_width = geometry.value(QStringLiteral("validatedFootprint")).toObject().value(QStringLiteral("widthTiles")).toInt();
        record.footprint_depth = geometry.value(QStringLiteral("validatedFootprint")).toObject().value(QStringLiteral("depthTiles")).toInt();
        record.floor_count = geometry.value(QStringLiteral("floorCount")).toInt(1);

        const QJsonObject facade = manifest.value(QStringLiteral("facadeEditor")).toObject();
        const QJsonObject typology = facade.value(QStringLiteral("typologyPreset")).toObject();
        record.typology_id = typology.value(QStringLiteral("id")).toString(QStringLiteral("custom"));
        record.typology_name = typology.value(QStringLiteral("name")).toString(QStringLiteral("Custom"));

        const QJsonObject pipeline = manifest.value(QStringLiteral("exportPipeline")).toObject();
        record.export_ready = pipeline.value(QStringLiteral("packageValidated")).toBool(false);
        record.lod_valid = pipeline.value(QStringLiteral("lodVisualValidated")).toBool(
            manifest.value(QStringLiteral("lodVisualGate")).toObject().value(QStringLiteral("valid")).toBool(false));
        record.urban_valid = pipeline.value(QStringLiteral("urbanIntegrationValidated")).toBool(false);

        const QJsonObject files = manifest.value(QStringLiteral("files")).toObject();
        const QString thumbnail_file = files.value(QStringLiteral("thumbnail")).toString(record.stem + QStringLiteral("_thumb.png"));
        record.thumbnail_path = QDir(record.directory).filePath(thumbnail_file);

        QString reopen_error;
        record.can_reopen = deserializeSpec(manifest.value(QStringLiteral("authoringSpec")).toObject(),
                                            &record.authoring_spec, &reopen_error);
        records.push_back(record);
    }

    std::sort(records.begin(), records.end(), [](const BuildingAssetRecord& a, const BuildingAssetRecord& b) {
        if (a.typology_name != b.typology_name) return a.typology_name.localeAwareCompare(b.typology_name) < 0;
        return a.stem.localeAwareCompare(b.stem) < 0;
    });
    if (error) error->clear();
    return records;
}

QJsonObject BuildingAssetCatalog::contractManifest() {
    return QJsonObject{
        {"version", QStringLiteral("building_asset_browser_1")},
        {"indexSource", QStringLiteral("validated_export_manifests")},
        {"manifestGlob", QStringLiteral("*_manifest.json")},
        {"recursiveScan", true},
        {"filters", QJsonArray{QStringLiteral("text"), QStringLiteral("typology"), QStringLiteral("footprint"), QStringLiteral("floors"), QStringLiteral("status")}},
        {"thumbnailFromPackage", true},
        {"reopenRequires", QStringLiteral("authoringSpec.version == building_authoring_spec_1")},
        {"legacyPackagesRemainBrowseable", true},
        {"legacyPackagesWithoutAuthoringSpecReopenable", false},
        {"reexportUsesNormalValidationGate", true},
    };
}

} // namespace ch::studio
