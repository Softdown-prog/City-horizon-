#include "carousel_part_library.h"

#include <QPainter>

#include <algorithm>

namespace ch::studio {

int CarouselPartLibrary::variantCount(const QString& part_id) {
    return part_id == QStringLiteral("carousel.horse.classic.v1") ? 4 : 1;
}

QImage CarouselPartLibrary::renderPartVariant(const QString& part_id,
                                              const QSize& target_size,
                                              const QColor& primary,
                                              const QColor& outline,
                                              int visual_variant,
                                              QString* reason) {
    QImage base = renderPart(part_id, target_size, primary, outline, reason);
    if (base.isNull()) return {};

    if (part_id != QStringLiteral("carousel.horse.classic.v1")) {
        if (reason) reason->clear();
        return base;
    }

    const int variant = ((visual_variant % 4) + 4) % 4;
    if (variant == 0) {
        if (reason) reason->clear();
        return base;
    }
    if (variant == 2) {
        if (reason) reason->clear();
        return base.mirrored(true, false);
    }

    // North/south use a narrower foreshortened presentation of the canonical
    // profile. This keeps palette, silhouette identity and pivot stable while
    // giving the orbit four deterministic directional readings.
    const qreal width_scale = 0.72;
    const int narrowed_width = std::max(1, static_cast<int>(base.width() * width_scale));
    QImage narrowed = base.scaled(narrowed_width, base.height(),
                                  Qt::IgnoreAspectRatio, Qt::SmoothTransformation);
    if (variant == 3) narrowed = narrowed.mirrored(true, false);

    QImage result(base.size(), QImage::Format_ARGB32_Premultiplied);
    result.fill(Qt::transparent);
    QPainter painter(&result);
    painter.setRenderHint(QPainter::SmoothPixmapTransform, true);
    painter.drawImage(QPoint((result.width() - narrowed.width()) / 2, 0), narrowed);

    // Rear-facing/north gets a restrained cool shade so north/south remain
    // legible at game scale without introducing a different palette identity.
    if (variant == 3) {
        painter.setCompositionMode(QPainter::CompositionMode_SourceAtop);
        painter.fillRect(result.rect(), QColor(45, 57, 68, 24));
    }
    painter.end();

    if (reason) reason->clear();
    return result;
}

} // namespace ch::studio
