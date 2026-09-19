#include "animation_preview_renderer.h"

#include "animation_visual_source_renderer.h"
#include "building_facade_renderer.h"

#include <QFont>
#include <QPainter>
#include <QTransform>

#include <algorithm>
#include <cmath>
#include <vector>

namespace ch::studio {
namespace {

QTransform rootTransform(const AnimatedAssetSpec& asset, const AnimationFrameSample& sample) {
    const QPointF anchor(asset.anchor_normalized.x() * asset.frame_size.width(),
                         asset.anchor_normalized.y() * asset.frame_size.height());
    QTransform transform;
    transform.translate(anchor.x() + sample.root.offset_x_px,
                        anchor.y() + sample.root.offset_y_px);
    transform.rotate(sample.root.rotation_degrees);
    transform.scale(sample.root.scale, sample.root.scale);
    transform.translate(-anchor.x(), -anchor.y());
    return transform;
}

QTransform nodeOriginTransform(const AnimatedAssetSpec& asset,
                               const AnimationFrameSample& sample,
                               const AnimationNodeSpec& node,
                               const QTransform& root_transform) {
    std::vector<const AnimationNodeSpec*> chain;
    const AnimationNodeSpec* current = &node;
    while (current) {
        chain.push_back(current);
        if (current->parent_id == QStringLiteral("root")) break;
        current = AnimationCore::findNode(asset, current->parent_id);
    }
    std::reverse(chain.begin(), chain.end());

    QTransform transform = root_transform;
    for (const AnimationNodeSpec* item : chain) {
        const AnimationNodeState* state = AnimationCore::findNodeState(sample, item->id);
        if (!state) continue;
        transform.translate(item->position_px.x() + state->offset_x_px,
                            item->position_px.y() + state->offset_y_px);
        transform.rotate(state->rotation_degrees);
        transform.scale(state->scale, state->scale);
    }
    return transform;
}

bool nodeVisible(const AnimatedAssetSpec& asset,
                 const AnimationFrameSample& sample,
                 const AnimationNodeSpec& node) {
    if (!sample.root.visible) return false;
    const AnimationNodeSpec* current = &node;
    while (current) {
        const AnimationNodeState* state = AnimationCore::findNodeState(sample, current->id);
        if (!state || !state->visible) return false;
        if (current->parent_id == QStringLiteral("root")) break;
        current = AnimationCore::findNode(asset, current->parent_id);
    }
    return true;
}

qreal nodeOpacity(const AnimatedAssetSpec& asset,
                  const AnimationFrameSample& sample,
                  const AnimationNodeSpec& node) {
    qreal opacity = std::clamp(static_cast<qreal>(sample.root.opacity), 0.0, 1.0);
    const AnimationNodeSpec* current = &node;
    while (current) {
        const AnimationNodeState* state = AnimationCore::findNodeState(sample, current->id);
        if (!state) return 0.0;
        opacity *= std::clamp(static_cast<qreal>(state->opacity), 0.0, 1.0);
        if (current->parent_id == QStringLiteral("root")) break;
        current = AnimationCore::findNode(asset, current->parent_id);
    }
    return std::clamp(opacity, 0.0, 1.0);
}

void drawMissingSource(QPainter& painter, const AnimationNodeSpec& node) {
    const qreal width = std::max(6.0, node.visual_size_px.width());
    const qreal height = std::max(6.0, node.visual_size_px.height());
    const QRectF bounds(-node.pivot_normalized.x() * width,
                        -node.pivot_normalized.y() * height,
                        width, height);
    painter.setPen(QPen(QColor("#ff4f9a"), 1.4));
    painter.setBrush(QColor(80, 20, 52, 100));
    painter.drawRect(bounds);
    painter.drawLine(bounds.topLeft(), bounds.bottomRight());
    painter.drawLine(bounds.topRight(), bounds.bottomLeft());
}

void drawNodeVisual(QPainter& painter,
                    const AnimatedAssetSpec& asset,
                    const AnimationFrameSample& sample,
                    const AnimationNodeSpec& node,
                    const QTransform& root_transform) {
    if (!nodeVisible(asset, sample, node)
        || node.visual_kind == AnimationNodeVisualKind::None) {
        return;
    }

    const AnimationNodeState* state = AnimationCore::findNodeState(sample, node.id);
    const int visual_variant = state ? state->visual_variant : node.visual_variant;

    painter.save();
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setRenderHint(QPainter::SmoothPixmapTransform, node.visual_smooth_scaling);
    painter.setOpacity(nodeOpacity(asset, sample, node));
    painter.setWorldTransform(nodeOriginTransform(asset, sample, node, root_transform));

    QString source_reason;
    const QImage source = AnimationVisualSourceRenderer::renderSource(
        asset, node, visual_variant, &source_reason);
    if (source.isNull()) {
        drawMissingSource(painter, node);
        painter.restore();
        return;
    }

    const QPointF top_left(-node.pivot_normalized.x() * source.width(),
                           -node.pivot_normalized.y() * source.height());
    painter.drawImage(top_left, source);
    painter.restore();
}

std::vector<const AnimationNodeSpec*> sortedNodes(const AnimatedAssetSpec& asset,
                                                  const AnimationFrameSample& sample) {
    std::vector<const AnimationNodeSpec*> nodes;
    nodes.reserve(asset.nodes.size());
    for (const AnimationNodeSpec& node : asset.nodes) nodes.push_back(&node);
    std::stable_sort(nodes.begin(), nodes.end(), [&](const AnimationNodeSpec* lhs,
                                                     const AnimationNodeSpec* rhs) {
        const AnimationNodeState* lhs_state = AnimationCore::findNodeState(sample, lhs->id);
        const AnimationNodeState* rhs_state = AnimationCore::findNodeState(sample, rhs->id);
        const int lhs_order = lhs_state ? lhs_state->draw_order : lhs->draw_order;
        const int rhs_order = rhs_state ? rhs_state->draw_order : rhs->draw_order;
        return lhs_order < rhs_order;
    });
    return nodes;
}

int resolvedDrawOrder(const AnimationFrameSample& sample, const AnimationNodeSpec& node) {
    const AnimationNodeState* state = AnimationCore::findNodeState(sample, node.id);
    return state ? state->draw_order : node.draw_order;
}

} // namespace

QImage AnimationPreviewRenderer::renderFrame(const AnimatedAssetSpec& asset,
                                             const AnimationClip& clip,
                                             const int frame_index) {
    QImage frame(asset.frame_size, QImage::Format_ARGB32_Premultiplied);
    frame.fill(Qt::transparent);

    const AnimationFrameSample sample = AnimationCore::sampleFrame(asset, clip, frame_index);
    const QTransform root_transform = rootTransform(asset, sample);
    const std::vector<const AnimationNodeSpec*> nodes = sortedNodes(asset, sample);

    QPainter painter(&frame);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setRenderHint(QPainter::SmoothPixmapTransform, true);

    for (const AnimationNodeSpec* node : nodes) {
        if (resolvedDrawOrder(sample, *node) >= 0) break;
        drawNodeVisual(painter, asset, sample, *node, root_transform);
    }

    if (asset.render_base_building && sample.root.visible) {
        const QImage base = BuildingFacadeRenderer::renderView(
            asset.base_building, asset.view, asset.frame_size);
        painter.save();
        painter.setOpacity(std::clamp(static_cast<qreal>(sample.root.opacity), 0.0, 1.0));
        painter.setWorldTransform(root_transform);
        painter.drawImage(QPointF(0.0, 0.0), base);
        painter.restore();
    }

    for (const AnimationNodeSpec* node : nodes) {
        if (resolvedDrawOrder(sample, *node) < 0) continue;
        drawNodeVisual(painter, asset, sample, *node, root_transform);
    }

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
                     QStringLiteral("Stable anchor · dynamic depth · visual variants · deterministic sampling · %1 s · %2")
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

        const AnimationFrameSample sample = AnimationCore::sampleFrame(asset, clip, frame_index);
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
