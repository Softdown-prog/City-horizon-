#pragma once

#include <QJsonObject>
#include <QPointF>
#include <QSet>
#include <QSize>
#include <QString>
#include <QVector>

#include <cstdint>

namespace ch::studio {

enum class AssetLayerType {
    Group,
    Raster,
    Vector,
    Mask,
    Adjustment,
    Reference,
    Object2_5D,
};

QString assetLayerTypeId(AssetLayerType type);
bool assetLayerTypeFromId(const QString& id, AssetLayerType* type);

struct AssetTransform2D {
    QPointF position_px{0.0, 0.0};
    QPointF scale{1.0, 1.0};
    qreal rotation_degrees = 0.0;
    QPointF pivot_normalized{0.5, 0.5};

    bool operator==(const AssetTransform2D&) const = default;
};

struct AssetLayer {
    QString id;
    QString name;
    AssetLayerType type = AssetLayerType::Group;
    QString parent_id;
    bool visible = true;
    bool locked = false;
    qreal opacity = 1.0;
    QString blend_mode = QStringLiteral("normal");
    AssetTransform2D transform;
    QString source_path;
    QJsonObject payload;

    bool operator==(const AssetLayer&) const = default;
};

struct AssetDocumentSnapshot {
    QString asset_id;
    QString display_name;
    QString category;
    QSize canvas_size{512, 512};
    QString camera_contract = QStringLiteral("CH_CAMERA_V1");
    QString style_preset = QStringLiteral("CH_CLASSIC_TYCOON_STYLE_V1");
    QPointF anchor_normalized{0.5, 1.0};
    QVector<AssetLayer> layers;
    QJsonObject metadata;

    bool operator==(const AssetDocumentSnapshot&) const = default;
};

class AssetDocument final {
public:
    static constexpr const char* kContractVersion = "CH_ASSET_DOCUMENT_V1";
    static constexpr const char* kFileExtension = ".chasset";

    AssetDocument();

    void newDocument(const QString& asset_id,
                     const QString& display_name,
                     const QSize& canvas_size = QSize(512, 512));

    [[nodiscard]] const QString& assetId() const { return asset_id_; }
    [[nodiscard]] const QString& displayName() const { return display_name_; }
    [[nodiscard]] const QString& category() const { return category_; }
    [[nodiscard]] const QSize& canvasSize() const { return canvas_size_; }
    [[nodiscard]] const QString& cameraContract() const { return camera_contract_; }
    [[nodiscard]] const QString& stylePreset() const { return style_preset_; }
    [[nodiscard]] const QPointF& anchorNormalized() const { return anchor_normalized_; }
    [[nodiscard]] const QVector<AssetLayer>& layers() const { return layers_; }
    [[nodiscard]] const QJsonObject& metadata() const { return metadata_; }
    [[nodiscard]] std::uint64_t revision() const { return revision_; }

    void setDisplayName(const QString& value);
    void setCategory(const QString& value);
    void setCanvasSize(const QSize& value);
    void setCameraContract(const QString& value);
    void setStylePreset(const QString& value);
    void setAnchorNormalized(const QPointF& value);
    void setMetadata(const QJsonObject& value);

    [[nodiscard]] int layerIndex(const QString& layer_id) const;
    [[nodiscard]] const AssetLayer* layer(const QString& layer_id) const;
    [[nodiscard]] AssetLayer* layer(const QString& layer_id);

    bool addLayer(const AssetLayer& layer, int index = -1, QString* reason = nullptr);
    bool removeLayer(const QString& layer_id, QString* reason = nullptr);
    bool moveLayer(const QString& layer_id, int new_index, QString* reason = nullptr);
    bool setLayerVisibility(const QString& layer_id, bool visible, QString* reason = nullptr);
    bool setLayerLocked(const QString& layer_id, bool locked, QString* reason = nullptr);
    bool setLayerOpacity(const QString& layer_id, qreal opacity, QString* reason = nullptr);
    bool setLayerTransform(const QString& layer_id,
                           const AssetTransform2D& transform,
                           QString* reason = nullptr);
    bool setLayerPayload(const QString& layer_id,
                         const QJsonObject& payload,
                         QString* reason = nullptr);

    [[nodiscard]] bool validate(QString* reason = nullptr) const;
    [[nodiscard]] QJsonObject toJson() const;
    static bool fromJson(const QJsonObject& json, AssetDocument* document, QString* reason = nullptr);

    bool save(const QString& path, QString* reason = nullptr) const;
    static bool load(const QString& path, AssetDocument* document, QString* reason = nullptr);

    [[nodiscard]] AssetDocumentSnapshot snapshot() const;
    void restore(const AssetDocumentSnapshot& snapshot);

private:
    void touch();

    QString asset_id_;
    QString display_name_;
    QString category_ = QStringLiteral("unclassified");
    QSize canvas_size_{512, 512};
    QString camera_contract_ = QStringLiteral("CH_CAMERA_V1");
    QString style_preset_ = QStringLiteral("CH_CLASSIC_TYCOON_STYLE_V1");
    QPointF anchor_normalized_{0.5, 1.0};
    QVector<AssetLayer> layers_;
    QJsonObject metadata_;
    std::uint64_t revision_ = 0;
};

} // namespace ch::studio
