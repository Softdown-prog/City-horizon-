#pragma once

#include "animation_core.h"

#include <QImage>
#include <QJsonObject>
#include <QPointF>
#include <QSizeF>
#include <QString>
#include <QStringList>

namespace ch::studio {

class CarouselPartLibrary final {
public:
    static constexpr const char* kVersion = "carousel_parts_2";

    static QStringList partIds();
    static bool contains(const QString& part_id);
    static QString displayName(const QString& part_id);
    static QSizeF defaultSize(const QString& part_id);
    static QPointF defaultPivot(const QString& part_id);
    static int variantCount(const QString& part_id);

    static AnimationNodeSpec makeNode(const QString& part_id,
                                      const QString& node_id,
                                      const QString& parent_id,
                                      const QPointF& position_px,
                                      int draw_order,
                                      const QColor& primary = QColor("#c9554f"),
                                      const QColor& outline = QColor("#343638"));

    // Canonical base artwork renderer retained for compatibility and library QA.
    static QImage renderPart(const QString& part_id,
                             const QSize& target_size,
                             const QColor& primary,
                             const QColor& outline,
                             QString* reason = nullptr);

    // Directional presentation of the same persistent part. Horse variants are
    // 0=east, 1=south, 2=west, 3=north; non-directional parts resolve to 0.
    static QImage renderPartVariant(const QString& part_id,
                                    const QSize& target_size,
                                    const QColor& primary,
                                    const QColor& outline,
                                    int visual_variant,
                                    QString* reason = nullptr);

    static QJsonObject manifest();
};

} // namespace ch::studio
