#include "asset_document.h"

#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QSaveFile>

#include <algorithm>
#include <cmath>

namespace ch::studio {
namespace {

bool fail(QString* reason, const QString& message) {
    if (reason) *reason = message;
    return false;
}

bool validPersistentId(const QString& id) {
    static const QRegularExpression pattern(QStringLiteral("^[a-z0-9][a-z0-9._-]*$"));
    return pattern.match(id).hasMatch();
}

QJsonObject pointJson(const QPointF& point) {
    return QJsonObject{{"x", point.x()}, {"y", point.y()}};
}

QPointF pointFromJson(const QJsonObject& json, const QPointF& fallback) {
    return QPointF(json.value(QStringLiteral("x")).toDouble(fallback.x()),
                   json.value(QStringLiteral("y")).toDouble(fallback.y()));
}

QJsonObject transformJson(const AssetTransform2D& transform) {
    return QJsonObject{
        {"positionPx", pointJson(transform.position_px)},
        {"scale", pointJson(transform.scale)},
        {"rotationDegrees", transform.rotation_degrees},
        {"pivotNormalized", pointJson(transform.pivot_normalized)},
    };
}

AssetTransform2D transformFromJson(const QJsonObject& json) {
    AssetTransform2D transform;
    transform.position_px = pointFromJson(json.value(QStringLiteral("positionPx")).toObject(), QPointF(0.0, 0.0));
    transform.scale = pointFromJson(json.value(QStringLiteral("scale")).toObject(), QPointF(1.0, 1.0));
    transform.rotation_degrees = json.value(QStringLiteral("rotationDegrees")).toDouble(0.0);
    transform.pivot_normalized = pointFromJson(json.value(QStringLiteral("pivotNormalized")).toObject(), QPointF(0.5, 0.5));
    return transform;
}

QJsonObject layerJson(const AssetLayer& layer) {
    return QJsonObject{
        {"id", layer.id},
        {"name", layer.name},
        {"type", assetLayerTypeId(layer.type)},
        {"parentId", layer.parent_id},
        {"visible", layer.visible},
        {"locked", layer.locked},
        {"opacity", layer.opacity},
        {"blendMode", layer.blend_mode},
        {"transform", transformJson(layer.transform)},
        {"sourcePath", layer.source_path},
        {"payload", layer.payload},
    };
}

bool layerFromJson(const QJsonObject& json, AssetLayer* layer, QString* reason) {
    if (!layer) return fail(reason, QStringLiteral("layer output is null"));

    AssetLayer parsed;
    parsed.id = json.value(QStringLiteral("id")).toString();
    parsed.name = json.value(QStringLiteral("name")).toString(parsed.id);
    parsed.parent_id = json.value(QStringLiteral("parentId")).toString();
    parsed.visible = json.value(QStringLiteral("visible")).toBool(true);
    parsed.locked = json.value(QStringLiteral("locked")).toBool(false);
    parsed.opacity = json.value(QStringLiteral("opacity")).toDouble(1.0);
    parsed.blend_mode = json.value(QStringLiteral("blendMode")).toString(QStringLiteral("normal"));
    parsed.transform = transformFromJson(json.value(QStringLiteral("transform")).toObject());
    parsed.source_path = json.value(QStringLiteral("sourcePath")).toString();
    parsed.payload = json.value(QStringLiteral("payload")).toObject();

    if (!assetLayerTypeFromId(json.value(QStringLiteral("type")).toString(), &parsed.type))
        return fail(reason, QStringLiteral("unknown layer type for '%1'").arg(parsed.id));

    *layer = parsed;
    if (reason) reason->clear();
    return true;
}

} // namespace

QString assetLayerTypeId(const AssetLayerType type) {
    switch (type) {
        case AssetLayerType::Group: return QStringLiteral("group");
        case AssetLayerType::Raster: return QStringLiteral("raster");
        case AssetLayerType::Vector: return QStringLiteral("vector");
        case AssetLayerType::Mask: return QStringLiteral("mask");
        case AssetLayerType::Adjustment: return QStringLiteral("adjustment");
        case AssetLayerType::Reference: return QStringLiteral("reference");
        case AssetLayerType::Object2_5D: return QStringLiteral("object_2_5d");
    }
    return QStringLiteral("group");
}

bool assetLayerTypeFromId(const QString& id, AssetLayerType* type) {
    if (!type) return false;
    if (id == QLatin1String("group")) *type = AssetLayerType::Group;
    else if (id == QLatin1String("raster")) *type = AssetLayerType::Raster;
    else if (id == QLatin1String("vector")) *type = AssetLayerType::Vector;
    else if (id == QLatin1String("mask")) *type = AssetLayerType::Mask;
    else if (id == QLatin1String("adjustment")) *type = AssetLayerType::Adjustment;
    else if (id == QLatin1String("reference")) *type = AssetLayerType::Reference;
    else if (id == QLatin1String("object_2_5d")) *type = AssetLayerType::Object2_5D;
    else return false;
    return true;
}

AssetDocument::AssetDocument() = default;

void AssetDocument::newDocument(const QString& asset_id,
                                const QString& display_name,
                                const QSize& canvas_size) {
    asset_id_ = asset_id.trimmed();
    display_name_ = display_name.trimmed();
    category_ = QStringLiteral("unclassified");
    canvas_size_ = QSize(std::max(1, canvas_size.width()), std::max(1, canvas_size.height()));
    camera_contract_ = QStringLiteral("CH_CAMERA_V1");
    style_preset_ = QStringLiteral("CH_CLASSIC_TYCOON_STYLE_V1");
    anchor_normalized_ = QPointF(0.5, 1.0);
    layers_.clear();
    metadata_ = QJsonObject{};
    touch();
}

void AssetDocument::setDisplayName(const QString& value) {
    if (display_name_ == value) return;
    display_name_ = value;
    touch();
}

void AssetDocument::setCategory(const QString& value) {
    if (category_ == value) return;
    category_ = value;
    touch();
}

void AssetDocument::setCanvasSize(const QSize& value) {
    const QSize normalized(std::max(1, value.width()), std::max(1, value.height()));
    if (canvas_size_ == normalized) return;
    canvas_size_ = normalized;
    touch();
}

void AssetDocument::setCameraContract(const QString& value) {
    if (camera_contract_ == value) return;
    camera_contract_ = value;
    touch();
}

void AssetDocument::setStylePreset(const QString& value) {
    if (style_preset_ == value) return;
    style_preset_ = value;
    touch();
}

void AssetDocument::setAnchorNormalized(const QPointF& value) {
    if (anchor_normalized_ == value) return;
    anchor_normalized_ = value;
    touch();
}

void AssetDocument::setMetadata(const QJsonObject& value) {
    if (metadata_ == value) return;
    metadata_ = value;
    touch();
}

int AssetDocument::layerIndex(const QString& layer_id) const {
    for (int i = 0; i < layers_.size(); ++i)
        if (layers_[i].id == layer_id) return i;
    return -1;
}

const AssetLayer* AssetDocument::layer(const QString& layer_id) const {
    const int index = layerIndex(layer_id);
    return index >= 0 ? &layers_[index] : nullptr;
}

AssetLayer* AssetDocument::layer(const QString& layer_id) {
    const int index = layerIndex(layer_id);
    return index >= 0 ? &layers_[index] : nullptr;
}

bool AssetDocument::addLayer(const AssetLayer& layer_value, int index, QString* reason) {
    if (!validPersistentId(layer_value.id))
        return fail(reason, QStringLiteral("layer id is not a valid persistent id: %1").arg(layer_value.id));
    if (layerIndex(layer_value.id) >= 0)
        return fail(reason, QStringLiteral("duplicate layer id: %1").arg(layer_value.id));
    if (!layer_value.parent_id.isEmpty() && !layer(layer_value.parent_id))
        return fail(reason, QStringLiteral("layer parent does not exist: %1").arg(layer_value.parent_id));
    if (layer_value.opacity < 0.0 || layer_value.opacity > 1.0)
        return fail(reason, QStringLiteral("layer opacity must be inside 0..1"));

    if (index < 0 || index > layers_.size()) index = layers_.size();
    layers_.insert(index, layer_value);
    touch();
    if (reason) reason->clear();
    return true;
}

bool AssetDocument::removeLayer(const QString& layer_id, QString* reason) {
    if (layerIndex(layer_id) < 0)
        return fail(reason, QStringLiteral("layer does not exist: %1").arg(layer_id));

    QSet<QString> removed{layer_id};
    bool expanded = true;
    while (expanded) {
        expanded = false;
        for (const AssetLayer& candidate : layers_) {
            if (!removed.contains(candidate.id) && removed.contains(candidate.parent_id)) {
                removed.insert(candidate.id);
                expanded = true;
            }
        }
    }

    layers_.erase(std::remove_if(layers_.begin(), layers_.end(), [&](const AssetLayer& candidate) {
        return removed.contains(candidate.id);
    }), layers_.end());
    touch();
    if (reason) reason->clear();
    return true;
}

bool AssetDocument::moveLayer(const QString& layer_id, int new_index, QString* reason) {
    const int current = layerIndex(layer_id);
    if (current < 0) return fail(reason, QStringLiteral("layer does not exist: %1").arg(layer_id));
    if (layers_.isEmpty()) return false;

    new_index = std::clamp(new_index, 0, layers_.size() - 1);
    if (current == new_index) {
        if (reason) reason->clear();
        return true;
    }
    const AssetLayer value = layers_.takeAt(current);
    layers_.insert(new_index, value);
    touch();
    if (reason) reason->clear();
    return true;
}

bool AssetDocument::setLayerVisibility(const QString& layer_id, const bool visible, QString* reason) {
    AssetLayer* value = layer(layer_id);
    if (!value) return fail(reason, QStringLiteral("layer does not exist: %1").arg(layer_id));
    if (value->visible != visible) {
        value->visible = visible;
        touch();
    }
    if (reason) reason->clear();
    return true;
}

bool AssetDocument::setLayerLocked(const QString& layer_id, const bool locked, QString* reason) {
    AssetLayer* value = layer(layer_id);
    if (!value) return fail(reason, QStringLiteral("layer does not exist: %1").arg(layer_id));
    if (value->locked != locked) {
        value->locked = locked;
        touch();
    }
    if (reason) reason->clear();
    return true;
}

bool AssetDocument::setLayerOpacity(const QString& layer_id, const qreal opacity, QString* reason) {
    if (opacity < 0.0 || opacity > 1.0)
        return fail(reason, QStringLiteral("layer opacity must be inside 0..1"));
    AssetLayer* value = layer(layer_id);
    if (!value) return fail(reason, QStringLiteral("layer does not exist: %1").arg(layer_id));
    if (!qFuzzyCompare(value->opacity + 1.0, opacity + 1.0)) {
        value->opacity = opacity;
        touch();
    }
    if (reason) reason->clear();
    return true;
}

bool AssetDocument::setLayerTransform(const QString& layer_id,
                                      const AssetTransform2D& transform,
                                      QString* reason) {
    AssetLayer* value = layer(layer_id);
    if (!value) return fail(reason, QStringLiteral("layer does not exist: %1").arg(layer_id));
    if (value->transform != transform) {
        value->transform = transform;
        touch();
    }
    if (reason) reason->clear();
    return true;
}

bool AssetDocument::setLayerPayload(const QString& layer_id,
                                    const QJsonObject& payload,
                                    QString* reason) {
    AssetLayer* value = layer(layer_id);
    if (!value) return fail(reason, QStringLiteral("layer does not exist: %1").arg(layer_id));
    if (value->payload != payload) {
        value->payload = payload;
        touch();
    }
    if (reason) reason->clear();
    return true;
}

bool AssetDocument::validate(QString* reason) const {
    if (!validPersistentId(asset_id_))
        return fail(reason, QStringLiteral("asset id is not a valid persistent id"));
    if (canvas_size_.width() <= 0 || canvas_size_.height() <= 0)
        return fail(reason, QStringLiteral("canvas size must be positive"));
    if (camera_contract_.trimmed().isEmpty())
        return fail(reason, QStringLiteral("camera contract is empty"));
    if (style_preset_.trimmed().isEmpty())
        return fail(reason, QStringLiteral("style preset is empty"));
    if (anchor_normalized_.x() < 0.0 || anchor_normalized_.x() > 1.0
        || anchor_normalized_.y() < 0.0 || anchor_normalized_.y() > 1.0)
        return fail(reason, QStringLiteral("anchor must be normalized inside 0..1"));

    QSet<QString> ids;
    for (const AssetLayer& value : layers_) {
        if (!validPersistentId(value.id))
            return fail(reason, QStringLiteral("invalid layer id: %1").arg(value.id));
        if (ids.contains(value.id))
            return fail(reason, QStringLiteral("duplicate layer id: %1").arg(value.id));
        ids.insert(value.id);
        if (value.opacity < 0.0 || value.opacity > 1.0)
            return fail(reason, QStringLiteral("invalid opacity for layer: %1").arg(value.id));
        if (value.transform.scale.x() == 0.0 || value.transform.scale.y() == 0.0)
            return fail(reason, QStringLiteral("zero scale is not allowed for layer: %1").arg(value.id));
        const QPointF pivot = value.transform.pivot_normalized;
        if (pivot.x() < 0.0 || pivot.x() > 1.0 || pivot.y() < 0.0 || pivot.y() > 1.0)
            return fail(reason, QStringLiteral("invalid pivot for layer: %1").arg(value.id));
    }

    for (const AssetLayer& value : layers_) {
        if (!value.parent_id.isEmpty() && !ids.contains(value.parent_id))
            return fail(reason, QStringLiteral("missing parent '%1' for layer '%2'").arg(value.parent_id, value.id));

        QSet<QString> ancestry;
        QString parent = value.parent_id;
        while (!parent.isEmpty()) {
            if (parent == value.id || ancestry.contains(parent))
                return fail(reason, QStringLiteral("layer hierarchy cycle involving: %1").arg(value.id));
            ancestry.insert(parent);
            const AssetLayer* parent_layer = layer(parent);
            if (!parent_layer) break;
            parent = parent_layer->parent_id;
        }
    }

    if (reason) reason->clear();
    return true;
}

QJsonObject AssetDocument::toJson() const {
    QJsonArray layer_array;
    for (const AssetLayer& value : layers_) layer_array.append(layerJson(value));

    return QJsonObject{
        {"contract", QString::fromLatin1(kContractVersion)},
        {"assetId", asset_id_},
        {"displayName", display_name_},
        {"category", category_},
        {"canvas", QJsonObject{{"width", canvas_size_.width()}, {"height", canvas_size_.height()}}},
        {"cameraContract", camera_contract_},
        {"stylePreset", style_preset_},
        {"anchorNormalized", pointJson(anchor_normalized_)},
        {"layers", layer_array},
        {"metadata", metadata_},
    };
}

bool AssetDocument::fromJson(const QJsonObject& json, AssetDocument* document, QString* reason) {
    if (!document) return fail(reason, QStringLiteral("document output is null"));
    if (json.value(QStringLiteral("contract")).toString() != QLatin1String(kContractVersion))
        return fail(reason, QStringLiteral("unsupported .chasset contract"));

    AssetDocument parsed;
    parsed.asset_id_ = json.value(QStringLiteral("assetId")).toString();
    parsed.display_name_ = json.value(QStringLiteral("displayName")).toString();
    parsed.category_ = json.value(QStringLiteral("category")).toString(QStringLiteral("unclassified"));
    const QJsonObject canvas = json.value(QStringLiteral("canvas")).toObject();
    parsed.canvas_size_ = QSize(canvas.value(QStringLiteral("width")).toInt(512),
                                canvas.value(QStringLiteral("height")).toInt(512));
    parsed.camera_contract_ = json.value(QStringLiteral("cameraContract")).toString(QStringLiteral("CH_CAMERA_V1"));
    parsed.style_preset_ = json.value(QStringLiteral("stylePreset")).toString(QStringLiteral("CH_CLASSIC_TYCOON_STYLE_V1"));
    parsed.anchor_normalized_ = pointFromJson(json.value(QStringLiteral("anchorNormalized")).toObject(), QPointF(0.5, 1.0));
    parsed.metadata_ = json.value(QStringLiteral("metadata")).toObject();

    const QJsonArray layers = json.value(QStringLiteral("layers")).toArray();
    parsed.layers_.reserve(layers.size());
    for (const QJsonValue& layer_value : layers) {
        if (!layer_value.isObject()) return fail(reason, QStringLiteral("layer entry must be an object"));
        AssetLayer parsed_layer;
        if (!layerFromJson(layer_value.toObject(), &parsed_layer, reason)) return false;
        parsed.layers_.push_back(parsed_layer);
    }

    if (!parsed.validate(reason)) return false;
    parsed.revision_ = 1;
    *document = parsed;
    if (reason) reason->clear();
    return true;
}

bool AssetDocument::save(const QString& path, QString* reason) const {
    QString validation_reason;
    if (!validate(&validation_reason))
        return fail(reason, QStringLiteral("invalid asset document: %1").arg(validation_reason));

    QSaveFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate))
        return fail(reason, QStringLiteral("unable to open .chasset for writing: %1").arg(path));
    const QByteArray bytes = QJsonDocument(toJson()).toJson(QJsonDocument::Indented);
    if (file.write(bytes) != bytes.size())
        return fail(reason, QStringLiteral("unable to write complete .chasset file"));
    if (!file.commit())
        return fail(reason, QStringLiteral("unable to atomically commit .chasset file"));
    if (reason) reason->clear();
    return true;
}

bool AssetDocument::load(const QString& path, AssetDocument* document, QString* reason) {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly))
        return fail(reason, QStringLiteral("unable to open .chasset: %1").arg(path));

    QJsonParseError parse_error;
    const QJsonDocument json = QJsonDocument::fromJson(file.readAll(), &parse_error);
    if (parse_error.error != QJsonParseError::NoError || !json.isObject())
        return fail(reason, QStringLiteral("invalid .chasset JSON: %1").arg(parse_error.errorString()));
    return fromJson(json.object(), document, reason);
}

AssetDocumentSnapshot AssetDocument::snapshot() const {
    AssetDocumentSnapshot value;
    value.asset_id = asset_id_;
    value.display_name = display_name_;
    value.category = category_;
    value.canvas_size = canvas_size_;
    value.camera_contract = camera_contract_;
    value.style_preset = style_preset_;
    value.anchor_normalized = anchor_normalized_;
    value.layers = layers_;
    value.metadata = metadata_;
    return value;
}

void AssetDocument::restore(const AssetDocumentSnapshot& snapshot_value) {
    asset_id_ = snapshot_value.asset_id;
    display_name_ = snapshot_value.display_name;
    category_ = snapshot_value.category;
    canvas_size_ = snapshot_value.canvas_size;
    camera_contract_ = snapshot_value.camera_contract;
    style_preset_ = snapshot_value.style_preset;
    anchor_normalized_ = snapshot_value.anchor_normalized;
    layers_ = snapshot_value.layers;
    metadata_ = snapshot_value.metadata;
    touch();
}

void AssetDocument::touch() {
    ++revision_;
}

} // namespace ch::studio
