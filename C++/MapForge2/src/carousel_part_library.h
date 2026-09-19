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
    static constexpr const char* kVersion = "carousel_parts_5";

    static QStringList partIds();
    static bool contains(const QString& part_id);
    static QString displayName(const QString& part_id);
    static QSizeF defaultSize(const QString& part_id);
    static QPointF defaultPivot(const QString& part_id);
    static int variantCount(const QString& part_id);

    static QString assetPath(const QString& part_id, int visual_variant = 0);
    static bool assetBacked(const QString& part_id);
    static bool assetAvailable(const QString& part_id, int visual_variant = 0);

    static AnimationNodeSpec makeNode(const QString& part_id,
                                      const QString& node_id,
                                      const QString& parent_id,
                                      const QPointF& position_px,
                                      int draw_order,
                                      const QColor& primary = QColor("#a9433f"),
                                      const QColor& outline = QColor("#3a332f"));

    static QImage renderPart(const QString& part_id,
                             const QSize& target_size,
                             const QColor& primary,
                             const QColor& outline,
                             QString* reason = nullptr);

    static QImage renderPartVariant(const QString& part_id,
                                    const QSize& target_size,
                                    const QColor& primary,
                                    const QColor& outline,
                                    int visual_variant,
                                    QString* reason = nullptr);

    static QJsonObject manifest();
};

} // namespace ch::studio
