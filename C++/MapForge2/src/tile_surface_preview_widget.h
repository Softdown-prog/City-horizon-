#pragma once

#include <QHash>
#include <QPixmap>
#include <QWidget>

namespace ch::studio {

class TileSurfacePreviewWidget final : public QWidget {
public:
    explicit TileSurfacePreviewWidget(QWidget* parent = nullptr);

    void setTile(const QPixmap& tile);
    void setAutotileTiles(const QHash<int, QPixmap>& tiles);
    void clearTile();
    void clearAutotileTiles();
    void setRepeatCount(int repeat_x, int repeat_y);
    void setShowGrid(bool show_grid);
    void setAutotileMask(int mask);

protected:
    void paintEvent(QPaintEvent* event) override;

private:
    [[nodiscard]] QPointF projectTile(qreal tile_x, qreal tile_y) const;
    [[nodiscard]] const QPixmap* tileForMask(int mask) const;

    QPixmap tile_;
    QHash<int, QPixmap> autotile_tiles_;
    int repeat_x_ = 5;
    int repeat_y_ = 5;
    bool show_grid_ = true;
    int autotile_mask_ = 15;
};

} // namespace ch::studio
