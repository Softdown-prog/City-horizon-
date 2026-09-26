#pragma once

#include <QColor>
#include <QImage>
#include <QSize>

namespace ch::studio {

struct PineTreeSpec {
    QColor trunk = QColor("#5f3b24");
    QColor trunk_light = QColor("#8b5a34");
    QColor trunk_shadow = QColor("#3b281c");

    QColor foliage = QColor("#2f6548");
    QColor foliage_light = QColor("#4f8660");
    QColor foliage_mid = QColor("#397554");
    QColor foliage_shadow = QColor("#173d31");
    QColor foliage_deep = QColor("#102f27");

    QColor contact_shadow = QColor(20, 31, 25, 72);

    qreal crown_height_px = 318.0;
    qreal crown_half_width_px = 104.0;
    qreal trunk_height_px = 86.0;
    qreal trunk_half_width_px = 10.0;
    int tier_count = 7;
    unsigned int seed = 260926u;
};

class PineTreeRenderer final {
public:
    static constexpr const char* kStyleId = "ch_stylized_pine_2d_v1";

    static QImage renderTree(const PineTreeSpec& spec,
                             const QSize& canvas = QSize(320, 448));

    static QImage renderReviewSheet(const PineTreeSpec& spec,
                                    const QSize& canvas = QSize(720, 720));
};

} // namespace ch::studio
