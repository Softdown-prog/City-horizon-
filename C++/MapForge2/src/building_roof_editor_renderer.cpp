#include "building_roof_editor_renderer.h"

#include "src/ch_core/contracts.h"

#include <QFont>
#include <QJsonArray>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QPolygonF>

#include <algorithm>
#include <array>
#include <cmath>
#include <vector>

namespace ch::studio {
namespace {

struct Point3 {
    float x = 0.0F;
    float y = 0.0F;
    float z = 0.0F;
};

struct RoofFace {
    QPolygonF polygon;
    int index = 0;
};

constexpr std::array<BuildingView, 4> kViews = {
    BuildingView::South,
    BuildingView::East,
    BuildingView::West,
    BuildingView::North,
};

int quarterTurns(const BuildingView view) {
    switch (view) {
        case BuildingView::South: return 0;
        case BuildingView::East: return 1;
        case BuildingView::West: return 3;
        case BuildingView::North: return 2;
    }
    return 0;
}

Point3 rotatePoint(const Point3 point, const BuildingView view) {
    switch (quarterTurns(view)) {
        case 1: return {-point.y, point.x, point.z};
        case 2: return {-point.x, -point.y, point.z};
        case 3: return {point.y, -point.x, point.z};
        default: return point;
    }
}

QPointF projectPoint(const Point3 point, const BuildingView view, const QSize canvas) {
    const Point3 rotated = rotatePoint(point, view);
    const float half_tile_w = static_cast<float>(ch::contracts::kTileWidth) * 0.5F;
    const float half_tile_h = static_cast<float>(ch::contracts::kTileHeight) * 0.5F;
    const float center_x = static_cast<float>(canvas.width()) * 0.5F;
    const float ground_y = static_cast<float>(canvas.height()) - 42.0F;
    return {
        center_x + (rotated.x - rotated.y) * half_tile_w,
        ground_y + (rotated.x + rotated.y) * half_tile_h - rotated.z,
    };
}

QColor scaledColor(const QColor color, const float factor) {
    return QColor::fromRgbF(
        std::clamp(color.redF() * factor, 0.0F, 1.0F),
        std::clamp(color.greenF() * factor, 0.0F, 1.0F),
        std::clamp(color.blueF() * factor, 0.0F, 1.0F),
        color.alphaF());
}

QColor alphaColor(QColor color, const int alpha) {
    color.setAlpha(std::clamp(alpha, 0, 255));
    return color;
}

float averageY(const QPolygonF& polygon) {
    float total = 0.0F;
    for (const QPointF& point : polygon) total += static_cast<float>(point.y());
    return polygon.isEmpty() ? 0.0F : total / static_cast<float>(polygon.size());
}

QPointF lerpScreen(const QPointF& a, const QPointF& b, const float t) {
    return {
        a.x() + (b.x() - a.x()) * t,
        a.y() + (b.y() - a.y()) * t,
    };
}

void drawRoofMaterial(QPainter& painter, const BuildingComposerSpec& spec,
                      const QPolygonF& polygon, const int face_index) {
    if (spec.roof_material == BuildingRoofMaterial::Solid || polygon.size() < 3) return;

    QPainterPath clip;
    clip.addPolygon(polygon);
    clip.closeSubpath();

    const QRectF bounds = polygon.boundingRect();
    const float strength = std::clamp(spec.material_strength, 0.0F, 1.0F);
    const float scale = std::clamp(spec.material_scale, 0.55F, 2.0F);
    const float variation = std::clamp(spec.material_variation, 0.0F, 1.0F);
    const float contrast = std::clamp(spec.material_contrast, 0.0F, 1.0F);

    painter.save();
    painter.setClipPath(clip);
    painter.setBrush(Qt::NoBrush);

    if (spec.roof_material == BuildingRoofMaterial::MetalSeam) {
        const qreal spacing = std::max<qreal>(8.0, 15.0 * scale);
        painter.setPen(QPen(alphaColor(scaledColor(spec.roof_color, 0.55F),
                                      65 + static_cast<int>(100.0F * strength)),
                            0.72 + 0.42 * contrast));
        for (qreal x = bounds.left() + spacing; x < bounds.right(); x += spacing) {
            painter.drawLine(QPointF(x, bounds.top() - 8.0), QPointF(x - bounds.height() * 0.35, bounds.bottom() + 8.0));
        }
        painter.setPen(QPen(alphaColor(scaledColor(spec.roof_color, 1.16F),
                                      18 + static_cast<int>(52.0F * strength)), 0.48));
        for (qreal x = bounds.left() + spacing + 1.6; x < bounds.right(); x += spacing) {
            painter.drawLine(QPointF(x, bounds.top() - 8.0), QPointF(x - bounds.height() * 0.35, bounds.bottom() + 8.0));
        }
    } else {
        const qreal course = std::max<qreal>(5.0, (spec.roof_material == BuildingRoofMaterial::CeramicTile ? 7.0 : 9.0) * scale);
        const QColor dark = alphaColor(
            scaledColor(spec.roof_color, 0.62F - 0.16F * contrast),
            35 + static_cast<int>(95.0F * strength));
        painter.setPen(QPen(dark, 0.58 + 0.36 * contrast));
        int row = 0;
        for (qreal y = bounds.top() + course; y < bounds.bottom(); y += course, ++row) {
            painter.drawLine(QPointF(bounds.left() - 10.0, y), QPointF(bounds.right() + 10.0, y));
            const qreal tab = std::max<qreal>(8.0, 13.0 * scale);
            const qreal offset = (row % 2 == 0 ? 0.0 : tab * 0.5);
            for (qreal x = bounds.left() + offset; x < bounds.right(); x += tab) {
                const qreal h = spec.roof_material == BuildingRoofMaterial::CeramicTile ? course * 0.55 : course * 0.45;
                painter.drawLine(QPointF(x, y - h), QPointF(x, y));
            }
        }

        if (variation > 0.02F) {
            painter.setPen(QPen(alphaColor(scaledColor(spec.roof_color, 1.10F),
                                          10 + static_cast<int>(32.0F * strength * variation)), 0.52));
            const int accents = std::max(1, static_cast<int>(4.0F * variation));
            for (int i = 0; i < accents; ++i) {
                const qreal y = bounds.top() + bounds.height() * (0.24 + 0.16 * i);
                painter.drawLine(QPointF(bounds.left() + 5.0 + face_index, y),
                                 QPointF(bounds.right() - 5.0, y));
            }
        }
    }

    painter.restore();
}

void drawFace(QPainter& painter, const BuildingComposerSpec& spec,
              const RoofFace& face, const QSize canvas) {
    if (face.polygon.size() < 3) return;
    const float factor = face.polygon.boundingRect().center().x() < canvas.width() * 0.5F ? 0.86F : 1.06F;
    const QColor fill = scaledColor(spec.roof_color, factor);
    const QColor outline = alphaColor(scaledColor(spec.roof_color, 0.34F), 225);
    QPen pen(outline, 1.20, Qt::SolidLine, Qt::SquareCap, Qt::MiterJoin);
    pen.setMiterLimit(3.0);
    painter.setPen(pen);
    painter.setBrush(fill);
    painter.drawPolygon(face.polygon);
    drawRoofMaterial(painter, spec, face.polygon, face.index);
}

void drawCapLine(QPainter& painter, const BuildingComposerSpec& spec,
                 const QPointF& a, const QPointF& b, const qreal base_width) {
    if (!spec.roof_ridge_enabled) return;
    const qreal scale = std::clamp<qreal>(spec.roof_ridge_scale, 0.5, 1.8);
    painter.setPen(QPen(alphaColor(scaledColor(spec.roof_color, 0.30F), 220),
                        base_width * scale, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
    painter.drawLine(a, b);
    painter.setPen(QPen(alphaColor(scaledColor(spec.roof_color, 0.72F), 235),
                        base_width * 0.66 * scale, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
    painter.drawLine(a, b);
    painter.setPen(QPen(alphaColor(scaledColor(spec.roof_color, 1.08F), 145),
                        base_width * 0.22 * scale, Qt::SolidLine, Qt::RoundCap));
    painter.drawLine(a, b);
}

void drawFascia(QPainter& painter, const BuildingComposerSpec& spec,
                const Point3& a, const Point3& b, const float wall_h,
                const BuildingView view, const QSize canvas) {
    if (!spec.roof_fascia_enabled) return;
    const float thickness = std::clamp(spec.roof_fascia_thickness_px, 0.5F, 6.0F);
    const QPointF top_a = projectPoint({a.x, a.y, wall_h}, view, canvas);
    const QPointF top_b = projectPoint({b.x, b.y, wall_h}, view, canvas);
    const QPointF low_a = projectPoint({a.x, a.y, wall_h - thickness}, view, canvas);
    const QPointF low_b = projectPoint({b.x, b.y, wall_h - thickness}, view, canvas);
    const QPolygonF fascia = {top_a, top_b, low_b, low_a};
    painter.setPen(QPen(alphaColor(scaledColor(spec.roof_color, 0.28F), 220), 0.85));
    painter.setBrush(scaledColor(spec.roof_color, 0.48F));
    painter.drawPolygon(fascia);
    painter.setPen(QPen(alphaColor(scaledColor(spec.roof_color, 0.22F), 220), 0.72));
    painter.drawLine(low_a, low_b);
}

QImage renderAdvancedRoof(const BuildingComposerSpec& spec, const BuildingView view, const QSize canvas) {
    BuildingComposerSpec body = spec;
    body.roof_style = BuildingRoofStyle::Flat;
    body.roof_height_px = 8;
    body.roof_material = BuildingRoofMaterial::Solid;
    body.roof_chimney = false;
    body.roof_color = spec.wall_color;

    QImage image = BuildingComposer::renderView(body, view, canvas);
    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);

    const float half_w = std::max(1, spec.footprint_width_tiles) * 0.5F;
    const float half_d = std::max(1, spec.footprint_depth_tiles) * 0.5F;
    const float wall_h = static_cast<float>(std::max(24, spec.wall_height_px));
    const float pitch_factor = std::clamp(spec.roof_pitch_degrees / 35.0F, 0.35F, 1.75F);
    const float roof_h = spec.roof_style == BuildingRoofStyle::Flat
        ? 4.0F
        : static_cast<float>(std::max(8, spec.roof_height_px)) * pitch_factor;
    const float overhang = std::clamp(spec.roof_overhang, 0.0F, 0.24F);
    const float roof_half_w = half_w + overhang;
    const float roof_half_d = half_d + overhang;

    const std::array<Point3, 4> eaves = {
        Point3{-roof_half_w, -roof_half_d, wall_h},
        Point3{ roof_half_w, -roof_half_d, wall_h},
        Point3{ roof_half_w,  roof_half_d, wall_h},
        Point3{-roof_half_w,  roof_half_d, wall_h},
    };

    int near_index = 0;
    float near_y = -1.0e9F;
    for (int i = 0; i < 4; ++i) {
        const float y = static_cast<float>(projectPoint(eaves[i], view, canvas).y());
        if (y > near_y) {
            near_y = y;
            near_index = i;
        }
    }
    const std::array<int, 2> visible_edges = {(near_index + 3) % 4, near_index};

    std::vector<RoofFace> faces;
    std::vector<std::pair<QPointF, QPointF>> cap_lines;

    auto pushVisibleEdgeFacesToApex = [&](const Point3 apex) {
        for (const int edge : visible_edges) {
            const int next = (edge + 1) % 4;
            faces.push_back({{
                projectPoint(eaves[edge], view, canvas),
                projectPoint(eaves[next], view, canvas),
                projectPoint(apex, view, canvas),
            }, edge});
        }
        cap_lines.push_back({projectPoint(apex, view, canvas), projectPoint(eaves[near_index], view, canvas)});
    };

    if (spec.roof_style == BuildingRoofStyle::Flat) {
        QPolygonF top;
        for (const Point3& p : eaves) top << projectPoint({p.x, p.y, wall_h + 2.0F}, view, canvas);
        faces.push_back({top, 0});
    } else if (spec.roof_style == BuildingRoofStyle::Pyramid) {
        pushVisibleEdgeFacesToApex({0.0F, 0.0F, wall_h + roof_h});
    } else if (spec.roof_style == BuildingRoofStyle::Shed) {
        const std::array<Point3, 4> shed = {
            Point3{-roof_half_w, -roof_half_d, wall_h + roof_h},
            Point3{ roof_half_w, -roof_half_d, wall_h + roof_h},
            Point3{ roof_half_w,  roof_half_d, wall_h + roof_h * 0.10F},
            Point3{-roof_half_w,  roof_half_d, wall_h + roof_h * 0.10F},
        };
        QPolygonF plane;
        for (const Point3& p : shed) plane << projectPoint(p, view, canvas);
        faces.push_back({plane, 0});
        cap_lines.push_back({projectPoint(shed[0], view, canvas), projectPoint(shed[1], view, canvas)});
    } else if (spec.roof_style == BuildingRoofStyle::Mansard) {
        constexpr float inset_factor = 0.62F;
        const float break_z = wall_h + roof_h * 0.58F;
        const std::array<Point3, 4> inner = {
            Point3{-roof_half_w * inset_factor, -roof_half_d * inset_factor, break_z},
            Point3{ roof_half_w * inset_factor, -roof_half_d * inset_factor, break_z},
            Point3{ roof_half_w * inset_factor,  roof_half_d * inset_factor, break_z},
            Point3{-roof_half_w * inset_factor,  roof_half_d * inset_factor, break_z},
        };
        for (const int edge : visible_edges) {
            const int next = (edge + 1) % 4;
            faces.push_back({{
                projectPoint(eaves[edge], view, canvas),
                projectPoint(eaves[next], view, canvas),
                projectPoint(inner[next], view, canvas),
                projectPoint(inner[edge], view, canvas),
            }, edge});
            cap_lines.push_back({projectPoint(inner[edge], view, canvas), projectPoint(inner[next], view, canvas)});
        }

        const bool along_x = spec.footprint_width_tiles >= spec.footprint_depth_tiles;
        Point3 ridge0{};
        Point3 ridge1{};
        if (along_x) {
            const float ridge_x = roof_half_w * inset_factor * 0.58F;
            ridge0 = {-ridge_x, 0.0F, wall_h + roof_h};
            ridge1 = { ridge_x, 0.0F, wall_h + roof_h};
        } else {
            const float ridge_y = roof_half_d * inset_factor * 0.58F;
            ridge0 = {0.0F, -ridge_y, wall_h + roof_h};
            ridge1 = {0.0F,  ridge_y, wall_h + roof_h};
        }
        for (const int edge : visible_edges) {
            const int next = (edge + 1) % 4;
            QPolygonF upper;
            if (along_x) {
                if (edge == 0) upper = {projectPoint(inner[0], view, canvas), projectPoint(inner[1], view, canvas), projectPoint(ridge1, view, canvas), projectPoint(ridge0, view, canvas)};
                else if (edge == 2) upper = {projectPoint(inner[2], view, canvas), projectPoint(inner[3], view, canvas), projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)};
                else if (edge == 1) upper = {projectPoint(inner[1], view, canvas), projectPoint(inner[2], view, canvas), projectPoint(ridge1, view, canvas)};
                else upper = {projectPoint(inner[3], view, canvas), projectPoint(inner[0], view, canvas), projectPoint(ridge0, view, canvas)};
            } else {
                if (edge == 1) upper = {projectPoint(inner[1], view, canvas), projectPoint(inner[2], view, canvas), projectPoint(ridge1, view, canvas), projectPoint(ridge0, view, canvas)};
                else if (edge == 3) upper = {projectPoint(inner[3], view, canvas), projectPoint(inner[0], view, canvas), projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)};
                else if (edge == 0) upper = {projectPoint(inner[0], view, canvas), projectPoint(inner[1], view, canvas), projectPoint(ridge0, view, canvas)};
                else upper = {projectPoint(inner[2], view, canvas), projectPoint(inner[3], view, canvas), projectPoint(ridge1, view, canvas)};
            }
            faces.push_back({upper, edge + 10});
        }
        cap_lines.push_back({projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)});
    } else {
        const bool along_x = spec.footprint_width_tiles >= spec.footprint_depth_tiles;
        Point3 ridge0{};
        Point3 ridge1{};
        if (spec.roof_style == BuildingRoofStyle::Hip) {
            if (along_x) {
                const float ridge_x = std::max(0.0F, roof_half_w - roof_half_d * 0.78F);
                ridge0 = {-ridge_x, 0.0F, wall_h + roof_h};
                ridge1 = { ridge_x, 0.0F, wall_h + roof_h};
            } else {
                const float ridge_y = std::max(0.0F, roof_half_d - roof_half_w * 0.78F);
                ridge0 = {0.0F, -ridge_y, wall_h + roof_h};
                ridge1 = {0.0F,  ridge_y, wall_h + roof_h};
            }
        } else {
            if (along_x) {
                ridge0 = {-roof_half_w, 0.0F, wall_h + roof_h};
                ridge1 = { roof_half_w, 0.0F, wall_h + roof_h};
            } else {
                ridge0 = {0.0F, -roof_half_d, wall_h + roof_h};
                ridge1 = {0.0F,  roof_half_d, wall_h + roof_h};
            }
        }

        for (const int edge : visible_edges) {
            QPolygonF poly;
            if (along_x) {
                if (edge == 0) poly = {projectPoint(eaves[0], view, canvas), projectPoint(eaves[1], view, canvas), projectPoint(ridge1, view, canvas), projectPoint(ridge0, view, canvas)};
                else if (edge == 2) poly = {projectPoint(eaves[2], view, canvas), projectPoint(eaves[3], view, canvas), projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)};
                else if (edge == 1) poly = {projectPoint(eaves[1], view, canvas), projectPoint(eaves[2], view, canvas), projectPoint(ridge1, view, canvas)};
                else poly = {projectPoint(eaves[3], view, canvas), projectPoint(eaves[0], view, canvas), projectPoint(ridge0, view, canvas)};
            } else {
                if (edge == 1) poly = {projectPoint(eaves[1], view, canvas), projectPoint(eaves[2], view, canvas), projectPoint(ridge1, view, canvas), projectPoint(ridge0, view, canvas)};
                else if (edge == 3) poly = {projectPoint(eaves[3], view, canvas), projectPoint(eaves[0], view, canvas), projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)};
                else if (edge == 0) poly = {projectPoint(eaves[0], view, canvas), projectPoint(eaves[1], view, canvas), projectPoint(ridge0, view, canvas)};
                else poly = {projectPoint(eaves[2], view, canvas), projectPoint(eaves[3], view, canvas), projectPoint(ridge1, view, canvas)};
            }
            faces.push_back({poly, edge});
        }
        cap_lines.push_back({projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)});
        if (spec.roof_style == BuildingRoofStyle::Hip) {
            cap_lines.push_back({projectPoint(ridge0, view, canvas), projectPoint(eaves[(along_x ? 3 : 0)], view, canvas)});
            cap_lines.push_back({projectPoint(ridge1, view, canvas), projectPoint(eaves[(along_x ? 1 : 2)], view, canvas)});
        }
    }

    std::sort(faces.begin(), faces.end(), [](const RoofFace& lhs, const RoofFace& rhs) {
        return averageY(lhs.polygon) < averageY(rhs.polygon);
    });
    for (const RoofFace& face : faces) drawFace(painter, spec, face, canvas);

    for (const int edge : visible_edges) {
        const int next = (edge + 1) % 4;
        drawFascia(painter, spec, eaves[edge], eaves[next], wall_h, view, canvas);
    }
    for (const auto& line : cap_lines) drawCapLine(painter, spec, line.first, line.second, 3.0);

    if (spec.roof_chimney) {
        // Reuse the canonical chimney recipe by compositing only its roof module
        // from a transparent helper render. Keeping the module source canonical
        // prevents a second chimney implementation in the roof editor.
        BuildingComposerSpec helper = spec;
        helper.wall_color.setAlpha(0);
        helper.roof_color.setAlpha(0);
        helper.trim_color.setAlpha(0);
        helper.windows = false;
        helper.south_door = false;
        helper.south_awning = false;
        helper.south_sign = false;
        helper.cast_shadow = false;
        helper.roof_style = BuildingRoofStyle::Flat;
        helper.roof_material = BuildingRoofMaterial::Solid;
        const QImage helper_image = BuildingComposer::renderView(helper, view, canvas);
        painter.drawImage(0, 0, helper_image);
    }

    painter.end();
    return image;
}

} // namespace

QImage BuildingRoofEditorRenderer::renderView(const BuildingComposerSpec& spec,
                                              const BuildingView view,
                                              const QSize canvas) {
    return renderAdvancedRoof(spec, view, canvas);
}

QImage BuildingRoofEditorRenderer::renderSpriteSheet(const BuildingComposerSpec& spec,
                                                     const QSize cell) {
    QImage sheet(cell.width() * 4, cell.height(), QImage::Format_ARGB32_Premultiplied);
    sheet.fill(Qt::transparent);
    QPainter painter(&sheet);
    for (int i = 0; i < static_cast<int>(kViews.size()); ++i) {
        painter.drawImage(i * cell.width(), 0, renderView(spec, kViews[i], cell));
    }
    painter.end();
    return sheet;
}

QImage BuildingRoofEditorRenderer::renderReviewSheet(const BuildingComposerSpec& spec,
                                                     const QSize cell) {
    constexpr int kHeader = 34;
    QImage sheet(cell.width() * 4, cell.height() + kHeader, QImage::Format_ARGB32_Premultiplied);
    sheet.fill(QColor("#172025"));
    QPainter painter(&sheet);
    painter.setRenderHint(QPainter::Antialiasing, true);
    QFont font(QStringLiteral("Arial"));
    font.setBold(true);
    font.setPointSize(9);
    painter.setFont(font);

    for (int i = 0; i < static_cast<int>(kViews.size()); ++i) {
        const int left = i * cell.width();
        painter.fillRect(QRect(left, 0, cell.width(), kHeader), QColor("#243238"));
        painter.setPen(QColor("#dce7ea"));
        painter.drawText(QRect(left, 0, cell.width(), kHeader), Qt::AlignCenter,
                         BuildingComposer::viewName(kViews[i]));
        painter.drawImage(QPoint(left, kHeader), renderView(spec, kViews[i], cell));
        if (i > 0) {
            painter.setPen(QPen(QColor(58, 71, 76), 1.0));
            painter.drawLine(left, 0, left, sheet.height());
        }
    }
    painter.end();
    return sheet;
}

QJsonObject BuildingRoofEditorRenderer::roofEditorManifest(const BuildingComposerSpec& spec) {
    return QJsonObject{
        {"version", "roof_editor_1"},
        {"profile", BuildingComposer::roofName(spec.roof_style)},
        {"pitchDegrees", static_cast<double>(std::clamp(spec.roof_pitch_degrees, 12.0F, 60.0F))},
        {"overhang", static_cast<double>(std::clamp(spec.roof_overhang, 0.0F, 0.24F))},
        {"fasciaEnabled", spec.roof_fascia_enabled},
        {"fasciaThicknessPx", static_cast<double>(std::clamp(spec.roof_fascia_thickness_px, 0.5F, 6.0F))},
        {"ridgeEnabled", spec.roof_ridge_enabled},
        {"ridgeScale", static_cast<double>(std::clamp(spec.roof_ridge_scale, 0.5F, 1.8F))},
        {"singleParametricDefinition", true},
    };
}

} // namespace ch::studio
