#pragma once

#include <QPixmap>
#include <QPointF>
#include <QSize>
#include <QWidget>

namespace ch::studio {

class AssetGridPreviewWidget final : public QWidget {
public:
    explicit AssetGridPreviewWidget(QWidget* parent = nullptr);

    void setSprite(const QPixmap& sprite);
    void clearSprite();
    void setFootprint(const QSize& footprint_tiles);
    void setAnchorNormalized(const QPointF& anchor_normalized);
    void setDirectionLabel(const QString& direction_label);

protected:
    void paintEvent(QPaintEvent* event) override;

private:
    [[nodiscard]] QPointF projectTile(qreal tile_x, qreal tile_y) const;

    QPixmap sprite_;
    QSize footprint_tiles_{1, 1};
    QPointF anchor_normalized_{0.5, 1.0};
    QString direction_label_ = QStringLiteral("SOUTH");
};

} // namespace ch::studio
