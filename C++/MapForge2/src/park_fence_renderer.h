#pragma once

#include <QColor>
#include <QImage>
#include <QSize>

namespace ch::studio {

enum class ParkFencePiece {
    Straight,
    Corner,
    End,
    Gate,
};

enum class ParkFenceRotation {
    South = 0,
    East = 1,
    North = 2,
    West = 3,
};

struct ParkFenceSpec {
    QColor metal = QColor("#173d31");
    QColor metal_light = QColor("#2d6652");
    QColor metal_shadow = QColor("#0c241d");
    QColor finial = QColor("#315f50");
    QColor shadow = QColor(18, 24, 20, 58);

    qreal fence_height_px = 36.0;
    qreal post_height_px = 47.0;
    qreal post_width_px = 7.0;
    qreal rail_width_px = 3.0;
    qreal picket_width_px = 2.0;
    qreal picket_spacing_px = 9.0;
    qreal spear_height_px = 4.5;
    qreal gate_gap_world = 0.52;
    qreal gate_open_depth_world = 0.30;
};

class ParkFenceRenderer final {
public:
    static constexpr const char* kStyleId = "city_park_classic_iron_v1";
    static constexpr int kTileWidthPx = 128;
    static constexpr int kTileHeightPx = 64;

    static QImage renderPiece(const ParkFenceSpec& spec,
                              ParkFencePiece piece,
                              ParkFenceRotation rotation,
                              const QSize& canvas = QSize(192, 144));

    static QImage renderReviewSheet(const ParkFenceSpec& spec,
                                    const QSize& cell = QSize(220, 170));
};

} // namespace ch::studio
