#include "animation_preview_renderer.h"

#include "building_facade_renderer.h"

#include <QFont>
#include <QPainter>
#include <QTransform>

#include <algorithm>
#include <cmath>

namespace ch::studio {

QImage AnimationPreviewRenderer::renderFrame(const AnimatedAssetSpec& asset,
                                             const AnimationClip& clip,
                                             const int frame_index) {
    QImage frame(asset.frame_size, QImage::Format_ARGB32_Premultiplied);
    frame.fill(Qt::transparent);

    const AnimationFrameSample sample = AnimationCore::sampleFrame(clip, frame_index);
    if (!sample.root.visible) return frame;

    const QImage base = BuildingFacadeRenderer::renderView(
        asset.base_building, asset.view, asset.frame_size);

    const QPointF anchor(asset.anchor_normalized.x() * asset.frame_size.width(),
                         asset.anchor_normalized.y() * asset.frame_size.height());

    QPainter painter(&frame);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setRenderHint(QPainter::SmoothPixmapTransform, true);
    painter.setOpacity(std::clamp(static_cast<qreal>(sample.root.opacity), 0.0, 1.0));

    QTransform transform;
    transform.translate(anchor.x() + sample.root.offset_x_px,
                        anchor.y() + sample.root.offset_y_px);
    transform.rotate(sample.root.rotation_degrees);
    transform.scale(sample.root.scale, sample.root.scale);
    transform.translate(-anchor.x(), -anchor.y());
    painter.setTransform(transform);
    painter.drawImage(QPointF(0.0, 0.0), base);
    painter.end();
    return frame;
}

QImage AnimationPreviewRenderer::renderSpriteSheet(const AnimatedAssetSpec& asset,
                                                   const AnimationClip& clip,
                                                   int columns) {
    const int frame_count = std::max(2, clip.frame_count);
    if (columns <= 0) columns = static_cast<int>(std::ceil(std::sqrt(static_cast<double>(frame_count))));
    columns = std::clamp(columns, 1, frame_count);
    const int rows = (frame_count + columns - 1) / columns;

    QImage sheet(asset.frame_size.width() * columns,
                 asset.frame_size.height() * rows,
                 QImage::Format_ARGB32_Premultiplied);
    sheet.fill(Qt::transparent);

    QPainter painter(&sheet);
    for (int frame_index = 0; frame_index < frame_count; ++frame_index) {
        const int column = frame_index % columns;
        const int row = frame_index / columns;
        painter.drawImage(QPoint(column * asset.frame_size.width(),
                                 row * asset.frame_size.height()),
                          renderFrame(asset, clip, frame_index));
    }
    painter.end();
    return sheet;
}

QImage AnimationPreviewRenderer::renderPreviewSheet(const AnimatedAssetSpec& asset,
                                                    const AnimationClip& clip,
                                                    const QSize canvas) {
    QImage preview(canvas, QImage::Format_ARGB32_Premultiplied);
    preview.fill(QColor("#10171b"));

    QPainter painter(&preview);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setRenderHint(QPainter::SmoothPixmapTransform, true);

    QFont title(QStringLiteral("Arial"));
    title.setBold(true);
    title.setPointSize(11);
    painter.setFont(title);
    painter.setPen(QColor("#edf3f5"));
    painter.drawText(QRect(16, 8, canvas.width() - 32, 26),
                     Qt::AlignLeft | Qt::AlignVCenter,
                     QStringLiteral("ANIMATION CORE PREVIEW · %1 · %2 frames")
                         .arg(clip.name).arg(clip.frame_count));

    QFont subtitle(QStringLiteral("Arial"));
    subtitle.setPointSize(8);
    painter.setFont(subtitle);
    painter.setPen(QColor("#aebbc0"));
    painter.drawText(QRect(16, 34, canvas.width() - 32, 20),
                     Qt::AlignLeft | Qt::AlignVCenter,
                     QStringLiteral("Stable anchor · deterministic sampling · %1 s · %2")
                         .arg(clip.duration_seconds, 0, 'f', 2)
                         .arg(clip.loop ? QStringLiteral("loop") : QStringLiteral("one-shot")));

    constexpr int kTop = 62;
    constexpr int kMargin = 12;
    constexpr int kGap = 8;
    const int frame_count = std::max(2, clip.frame_count);
    const int columns = std::clamp(static_cast<int>(std::ceil(std::sqrt(static_cast<double>(frame_count)))), 1, 6);
    const int rows = (frame_count + columns - 1) / columns;
    const int cell_width = std::max(1, (canvas.width() - kMargin * 2 - kGap * (columns - 1)) / columns);
    const int cell_height = std::max(1, (canvas.height() - kTop - kMargin - kGap * (rows - 1)) / rows);

    QFont label(QStringLiteral("Arial"));
    label.setPointSize(7);
    label.setBold(true);
    painter.setFont(label);

    for (int frame_index = 0; frame_index < frame_count; ++frame_index) {
        const int column = frame_index % columns;
        const int row = frame_index / columns;
        const QRect cell(kMargin + column * (cell_width + kGap),
                         kTop + row * (cell_height + kGap),
                         cell_width, cell_height);
        painter.fillRect(cell, QColor("#1b272c"));

        const AnimationFrameSample sample = AnimationCore::sampleFrame(clip, frame_index);
        painter.setPen(QColor("#dce7ea"));
        painter.drawText(QRect(cell.left() + 6, cell.top() + 3, cell.width() - 12, 18),
                         Qt::AlignLeft | Qt::AlignVCenter,
                         QStringLiteral("F%1 · %2s")
                             .arg(frame_index + 1, 2, 10, QLatin1Char('0'))
                             .arg(sample.time_seconds, 0, 'f', 3));

        const QImage rendered = renderFrame(asset, clip, frame_index);
        const QSize available(std::max(1, cell.width() - 10), std::max(1, cell.height() - 26));
        const QImage scaled = rendered.scaled(available, Qt::KeepAspectRatio, Qt::SmoothTransformation);
        painter.drawImage(QPoint(cell.center().x() - scaled.width() / 2,
                                 cell.top() + 23 + (available.height() - scaled.height()) / 2), scaled);
    }

    painter.end();
    return preview;
}

} // namespace ch::studio
