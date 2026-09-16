#include "building_composer.h"

#include "src/ch_core/contracts.h"

#include <QFont>
#include <QJsonArray>
#include <QPainter>
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

Point3 lerpPoint(const Point3 a, const Point3 b, const float t, const float z) {
    return {
        a.x + (b.x - a.x) * t,
        a.y + (b.y - a.y) * t,
        z,
    };
}

QPolygonF faceQuad(const Point3 a, const Point3 b, const float z0, const float z1,
                   const BuildingView view, const QSize canvas) {
    return {
        projectPoint({a.x, a.y, z0}, view, canvas),
        projectPoint({b.x, b.y, z0}, view, canvas),
        projectPoint({b.x, b.y, z1}, view, canvas),
        projectPoint({a.x, a.y, z1}, view, canvas),
    };
}

float averageY(const QPolygonF& polygon) {
    float total = 0.0F;
    for (const QPointF& point : polygon) total += static_cast<float>(point.y());
    return polygon.isEmpty() ? 0.0F : total / static_cast<float>(polygon.size());
}

void drawOutlinedPolygon(QPainter& painter, const QPolygonF& polygon, const QColor fill,
                         const QColor outline = QColor(45, 49, 51, 220)) {
    painter.setPen(QPen(outline, 1.25));
    painter.setBrush(fill);
    painter.drawPolygon(polygon);
}

void drawFaceDetail(QPainter& painter, const Point3 a, const Point3 b, const float t0, const float t1,
                    const float z0, const float z1, const BuildingView view, const QSize canvas,
                    const QColor fill, const QColor outline) {
    const QPolygonF polygon = {
        projectPoint(lerpPoint(a, b, t0, z0), view, canvas),
        projectPoint(lerpPoint(a, b, t1, z0), view, canvas),
        projectPoint(lerpPoint(a, b, t1, z1), view, canvas),
        projectPoint(lerpPoint(a, b, t0, z1), view, canvas),
    };
    drawOutlinedPolygon(painter, polygon, fill, outline);
}

float doorCenter(const BuildingDoorPosition position) {
    switch (position) {
        case BuildingDoorPosition::Left: return 0.24F;
        case BuildingDoorPosition::Center: return 0.50F;
        case BuildingDoorPosition::Right: return 0.76F;
    }
    return 0.50F;
}

void drawWindows(QPainter& painter, const BuildingComposerSpec& spec,
                 const Point3 a, const Point3 b, const int edge,
                 const float wall_h, const BuildingView view, const QSize canvas) {
    if (!spec.windows) return;

    const float window_z0 = wall_h * 0.38F;
    const float window_z1 = wall_h * 0.68F;
    const QColor outline = scaledColor(spec.trim_color, 0.72F);
    const bool entrance_edge = spec.south_door && edge == 2;

    auto window = [&](const float t0, const float t1) {
        drawFaceDetail(painter, a, b, t0, t1, window_z0, window_z1,
                       view, canvas, spec.glass_color, outline);
    };

    if (entrance_edge) {
        switch (spec.window_pattern) {
            case BuildingWindowPattern::Single:
                if (spec.door_position == BuildingDoorPosition::Left) window(0.58F, 0.82F);
                else if (spec.door_position == BuildingDoorPosition::Right) window(0.18F, 0.42F);
                else window(0.12F, 0.32F);
                break;
            case BuildingWindowPattern::Pair:
                window(0.08F, 0.25F);
                window(0.75F, 0.92F);
                break;
            case BuildingWindowPattern::Strip:
                window(0.06F, 0.18F);
                window(0.23F, 0.35F);
                window(0.65F, 0.77F);
                window(0.82F, 0.94F);
                break;
        }
        return;
    }

    switch (spec.window_pattern) {
        case BuildingWindowPattern::Single:
            window(0.36F, 0.64F);
            break;
        case BuildingWindowPattern::Pair:
            window(0.16F, 0.34F);
            window(0.66F, 0.84F);
            break;
        case BuildingWindowPattern::Strip:
            window(0.08F, 0.22F);
            window(0.29F, 0.43F);
            window(0.57F, 0.71F);
            window(0.78F, 0.92F);
            break;
    }
}

void drawSouthModules(QPainter& painter, const BuildingComposerSpec& spec,
                      const Point3 a, const Point3 b, const float wall_h,
                      const BuildingView view, const QSize canvas) {
    if (!spec.south_door) return;

    const float center = doorCenter(spec.door_position);
    const float half = 0.12F;
    const float t0 = std::clamp(center - half, 0.05F, 0.80F);
    const float t1 = std::clamp(center + half, 0.20F, 0.95F);

    drawFaceDetail(painter, a, b, t0, t1, 1.0F, wall_h * 0.56F,
                   view, canvas, spec.door_color, scaledColor(spec.trim_color, 0.68F));

    if (spec.south_sign) {
        const float sign_half = 0.15F;
        drawFaceDetail(painter, a, b,
                       std::clamp(center - sign_half, 0.04F, 0.76F),
                       std::clamp(center + sign_half, 0.24F, 0.96F),
                       wall_h * 0.70F, wall_h * 0.83F,
                       view, canvas, spec.accent_color, scaledColor(spec.trim_color, 0.62F));
    }

    if (spec.south_awning) {
        const float awning_half = 0.18F;
        const Point3 inner0 = lerpPoint(a, b, std::clamp(center - awning_half, 0.03F, 0.70F), wall_h * 0.66F);
        const Point3 inner1 = lerpPoint(a, b, std::clamp(center + awning_half, 0.30F, 0.97F), wall_h * 0.66F);
        const Point3 outer0{inner0.x, inner0.y + 0.28F, wall_h * 0.59F};
        const Point3 outer1{inner1.x, inner1.y + 0.28F, wall_h * 0.59F};

        const QPolygonF canopy = {
            projectPoint(inner0, view, canvas),
            projectPoint(inner1, view, canvas),
            projectPoint(outer1, view, canvas),
            projectPoint(outer0, view, canvas),
        };
        drawOutlinedPolygon(painter, canopy, spec.accent_color, scaledColor(spec.trim_color, 0.62F));
    }
}

void drawChimney(QPainter& painter, const BuildingComposerSpec& spec,
                 const float half_w, const float half_d, const float wall_h, const float roof_h,
                 const BuildingView view, const QSize canvas) {
    if (!spec.roof_chimney) return;

    const float cx = -half_w * 0.30F;
    const float cy = -half_d * 0.18F;
    constexpr float size = 0.16F;
    const float z0 = wall_h + roof_h * 0.48F;
    const float z1 = z0 + 24.0F;

    const std::array<Point3, 4> corners = {
        Point3{cx - size, cy - size, z0},
        Point3{cx + size, cy - size, z0},
        Point3{cx + size, cy + size, z0},
        Point3{cx - size, cy + size, z0},
    };

    int near_index = 0;
    float near_y = -1.0e9F;
    for (int i = 0; i < 4; ++i) {
        const float y = static_cast<float>(projectPoint(corners[i], view, canvas).y());
        if (y > near_y) {
            near_y = y;
            near_index = i;
        }
    }

    const std::array<int, 2> edges = {(near_index + 3) % 4, near_index};
    for (const int edge : edges) {
        const int next = (edge + 1) % 4;
        const QPolygonF face = faceQuad(corners[edge], corners[next], z0, z1, view, canvas);
        const float factor = face.boundingRect().center().x() < canvas.width() * 0.5F ? 0.78F : 0.92F;
        drawOutlinedPolygon(painter, face, scaledColor(spec.door_color, factor));
    }

    QPolygonF cap;
    for (const Point3& corner : corners) cap << projectPoint({corner.x, corner.y, z1}, view, canvas);
    drawOutlinedPolygon(painter, cap, scaledColor(spec.door_color, 1.08F));
}

} // namespace

QString BuildingComposer::viewName(const BuildingView view) {
    switch (view) {
        case BuildingView::South: return "SOUTH";
        case BuildingView::East: return "EAST";
        case BuildingView::West: return "WEST";
        case BuildingView::North: return "NORTH";
    }
    return "UNKNOWN";
}

QString BuildingComposer::roofName(const BuildingRoofStyle style) {
    switch (style) {
        case BuildingRoofStyle::Gable: return "gable";
        case BuildingRoofStyle::Pyramid: return "pyramid";
        case BuildingRoofStyle::Flat: return "flat";
    }
    return "unknown";
}

QString BuildingComposer::doorPositionName(const BuildingDoorPosition position) {
    switch (position) {
        case BuildingDoorPosition::Left: return "left";
        case BuildingDoorPosition::Center: return "center";
        case BuildingDoorPosition::Right: return "right";
    }
    return "center";
}

QString BuildingComposer::windowPatternName(const BuildingWindowPattern pattern) {
    switch (pattern) {
        case BuildingWindowPattern::Single: return "single";
        case BuildingWindowPattern::Pair: return "pair";
        case BuildingWindowPattern::Strip: return "strip";
    }
    return "pair";
}

QImage BuildingComposer::renderView(const BuildingComposerSpec& spec, const BuildingView view,
                                    const QSize canvas) {
    QImage image(canvas, QImage::Format_ARGB32_Premultiplied);
    image.fill(Qt::transparent);

    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);

    const float half_w = std::max(1, spec.footprint_width_tiles) * 0.5F;
    const float half_d = std::max(1, spec.footprint_depth_tiles) * 0.5F;
    const float wall_h = static_cast<float>(std::max(24, spec.wall_height_px));
    const float roof_h = static_cast<float>(std::max(8, spec.roof_height_px));

    const std::array<Point3, 4> corners = {
        Point3{-half_w, -half_d, 0.0F},
        Point3{half_w, -half_d, 0.0F},
        Point3{half_w, half_d, 0.0F},
        Point3{-half_w, half_d, 0.0F},
    };

    std::array<QPointF, 4> ground{};
    std::array<QPointF, 4> top{};
    int near_index = 0;
    float near_y = -1.0e9F;
    for (int i = 0; i < 4; ++i) {
        ground[i] = projectPoint(corners[i], view, canvas);
        top[i] = projectPoint({corners[i].x, corners[i].y, wall_h}, view, canvas);
        if (ground[i].y() > near_y) {
            near_y = static_cast<float>(ground[i].y());
            near_index = i;
        }
    }

    if (spec.cast_shadow) {
        QPolygonF shadow;
        for (const Point3 corner : corners) {
            shadow << projectPoint({corner.x * 1.08F, corner.y * 1.08F, -4.0F}, view, canvas);
        }
        painter.setPen(Qt::NoPen);
        painter.setBrush(QColor(0, 0, 0, 46));
        painter.drawPolygon(shadow);
    }

    const std::array<int, 2> visible_edges = {
        (near_index + 3) % 4,
        near_index,
    };

    struct FaceDraw {
        int edge = 0;
        QPolygonF polygon;
    };
    std::vector<FaceDraw> wall_faces;
    wall_faces.reserve(2);
    for (const int edge : visible_edges) {
        const int next = (edge + 1) % 4;
        wall_faces.push_back({edge, faceQuad(corners[edge], corners[next], 0.0F, wall_h, view, canvas)});
    }
    std::sort(wall_faces.begin(), wall_faces.end(), [](const FaceDraw& lhs, const FaceDraw& rhs) {
        return averageY(lhs.polygon) < averageY(rhs.polygon);
    });

    for (const FaceDraw& face : wall_faces) {
        const float center_x = static_cast<float>(face.polygon.boundingRect().center().x());
        const float factor = center_x < canvas.width() * 0.5F ? 0.84F : 1.0F;
        drawOutlinedPolygon(painter, face.polygon, scaledColor(spec.wall_color, factor));
    }

    for (const int edge : visible_edges) {
        const int next = (edge + 1) % 4;
        const Point3 a = corners[edge];
        const Point3 b = corners[next];

        drawWindows(painter, spec, a, b, edge, wall_h, view, canvas);
        if (edge == 2) {
            drawSouthModules(painter, spec, a, b, wall_h, view, canvas);
        }
    }

    struct RoofDraw {
        QPolygonF polygon;
        QColor color;
    };
    std::vector<RoofDraw> roof_faces;

    if (spec.roof_style == BuildingRoofStyle::Flat) {
        QPolygonF roof;
        for (const QPointF point : top) roof << point;
        roof_faces.push_back({roof, spec.roof_color});
    } else if (spec.roof_style == BuildingRoofStyle::Pyramid) {
        const Point3 apex{0.0F, 0.0F, wall_h + roof_h};
        for (const int edge : visible_edges) {
            const int next = (edge + 1) % 4;
            QPolygonF poly = {
                top[edge],
                top[next],
                projectPoint(apex, view, canvas),
            };
            const float factor = poly.boundingRect().center().x() < canvas.width() * 0.5F ? 0.86F : 1.06F;
            roof_faces.push_back({poly, scaledColor(spec.roof_color, factor)});
        }
    } else {
        const bool ridge_along_x = spec.footprint_width_tiles >= spec.footprint_depth_tiles;
        Point3 ridge0;
        Point3 ridge1;
        if (ridge_along_x) {
            ridge0 = {-half_w, 0.0F, wall_h + roof_h};
            ridge1 = {half_w, 0.0F, wall_h + roof_h};
        } else {
            ridge0 = {0.0F, -half_d, wall_h + roof_h};
            ridge1 = {0.0F, half_d, wall_h + roof_h};
        }

        for (const int edge : visible_edges) {
            QPolygonF poly;
            if (ridge_along_x) {
                if (edge == 0) {
                    poly = {top[0], top[1], projectPoint(ridge1, view, canvas), projectPoint(ridge0, view, canvas)};
                } else if (edge == 2) {
                    poly = {top[2], top[3], projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)};
                } else if (edge == 1) {
                    poly = {top[1], top[2], projectPoint(ridge1, view, canvas)};
                } else {
                    poly = {top[3], top[0], projectPoint(ridge0, view, canvas)};
                }
            } else {
                if (edge == 1) {
                    poly = {top[1], top[2], projectPoint(ridge1, view, canvas), projectPoint(ridge0, view, canvas)};
                } else if (edge == 3) {
                    poly = {top[3], top[0], projectPoint(ridge0, view, canvas), projectPoint(ridge1, view, canvas)};
                } else if (edge == 0) {
                    poly = {top[0], top[1], projectPoint(ridge0, view, canvas)};
                } else {
                    poly = {top[2], top[3], projectPoint(ridge1, view, canvas)};
                }
            }
            const float factor = poly.boundingRect().center().x() < canvas.width() * 0.5F ? 0.86F : 1.06F;
            roof_faces.push_back({poly, scaledColor(spec.roof_color, factor)});
        }
    }

    std::sort(roof_faces.begin(), roof_faces.end(), [](const RoofDraw& lhs, const RoofDraw& rhs) {
        return averageY(lhs.polygon) < averageY(rhs.polygon);
    });
    for (const RoofDraw& roof : roof_faces) {
        drawOutlinedPolygon(painter, roof.polygon, roof.color, QColor(52, 45, 43, 225));
    }

    painter.setPen(QPen(spec.trim_color, 1.6));
    for (const int edge : visible_edges) {
        const int next = (edge + 1) % 4;
        painter.drawLine(top[edge], top[next]);
    }

    drawChimney(painter, spec, half_w, half_d, wall_h, roof_h, view, canvas);

    painter.end();
    return image;
}

QImage BuildingComposer::renderSpriteSheet(const BuildingComposerSpec& spec, const QSize cell) {
    QImage sheet(cell.width() * 4, cell.height(), QImage::Format_ARGB32_Premultiplied);
    sheet.fill(Qt::transparent);
    QPainter painter(&sheet);
    for (int i = 0; i < static_cast<int>(kViews.size()); ++i) {
        painter.drawImage(i * cell.width(), 0, renderView(spec, kViews[i], cell));
    }
    painter.end();
    return sheet;
}

QImage BuildingComposer::renderReviewSheet(const BuildingComposerSpec& spec, const QSize cell) {
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
        painter.drawText(QRect(left, 0, cell.width(), kHeader), Qt::AlignCenter, viewName(kViews[i]));

        const QPointF center(left + cell.width() * 0.5F, kHeader + cell.height() - 42.0F);
        QPolygonF guide = {
            QPointF(center.x(), center.y() - ch::contracts::kTileHeight * 0.5F),
            QPointF(center.x() + ch::contracts::kTileWidth * 0.5F, center.y()),
            QPointF(center.x(), center.y() + ch::contracts::kTileHeight * 0.5F),
            QPointF(center.x() - ch::contracts::kTileWidth * 0.5F, center.y()),
        };
        painter.setPen(QPen(QColor(84, 113, 122, 130), 1.0));
        painter.setBrush(QColor(67, 96, 75, 55));
        painter.drawPolygon(guide);
        painter.drawImage(QPoint(left, kHeader), renderView(spec, kViews[i], cell));

        if (i > 0) {
            painter.setPen(QPen(QColor(58, 71, 76), 1.0));
            painter.drawLine(left, 0, left, sheet.height());
        }
    }
    painter.end();
    return sheet;
}

QJsonObject BuildingComposer::manifest(const BuildingComposerSpec& spec, const QSize frame) {
    QJsonArray views;
    for (const BuildingView view : kViews) views.append(viewName(view));

    QJsonArray sockets;
    if (spec.south_door) {
        sockets.append(QJsonObject{
            {"id", "entrance_south"},
            {"kind", "entrance"},
            {"edge", "south"},
            {"position", doorPositionName(spec.door_position)},
        });
    }
    if (spec.south_awning) {
        sockets.append(QJsonObject{
            {"id", "awning_south"},
            {"kind", "awning"},
            {"edge", "south"},
            {"parent", "entrance_south"},
        });
    }
    if (spec.south_sign) {
        sockets.append(QJsonObject{
            {"id", "sign_south"},
            {"kind", "sign"},
            {"edge", "south"},
            {"parent", "entrance_south"},
        });
    }
    if (spec.roof_chimney) {
        sockets.append(QJsonObject{
            {"id", "chimney_roof"},
            {"kind", "chimney"},
            {"surface", "roof"},
        });
    }

    QJsonObject metadata{
        {"generator", "City Horizon Studio Building/Asset Composer"},
        {"contractVersion", "CH_BUILDING_COMPOSER_V0"},
        {"featureRevision", "socket_modules_1"},
        {"status", "PILOT"},
        {"sourceRepresentation", "parametric_vector_volume"},
        {"runtimeRepresentation", "PNG_RGBA_bitmap"},
    };

    QJsonObject geometry{
        {"footprintWidthTiles", spec.footprint_width_tiles},
        {"footprintDepthTiles", spec.footprint_depth_tiles},
        {"wallHeightPx", spec.wall_height_px},
        {"roofHeightPx", spec.roof_height_px},
        {"roofStyle", roofName(spec.roof_style)},
    };

    QJsonObject projection{
        {"gridContract", ch::contracts::kGridContract},
        {"projection", "isometric_2_to_1"},
        {"logicalTileWidth", ch::contracts::kTileWidth},
        {"logicalTileHeight", ch::contracts::kTileHeight},
        {"frameWidth", frame.width()},
        {"frameHeight", frame.height()},
        {"views", views},
        {"groundAnchorX", frame.width() / 2},
        {"groundAnchorY", frame.height() - 42},
    };

    QJsonObject palette{
        {"wall", spec.wall_color.name(QColor::HexRgb)},
        {"roof", spec.roof_color.name(QColor::HexRgb)},
        {"trim", spec.trim_color.name(QColor::HexRgb)},
        {"glass", spec.glass_color.name(QColor::HexRgb)},
        {"door", spec.door_color.name(QColor::HexRgb)},
        {"accent", spec.accent_color.name(QColor::HexRgb)},
    };

    QJsonObject features{
        {"windows", spec.windows},
        {"windowPattern", windowPatternName(spec.window_pattern)},
        {"southDoor", spec.south_door},
        {"doorPosition", doorPositionName(spec.door_position)},
        {"southAwning", spec.south_awning},
        {"southSign", spec.south_sign},
        {"roofChimney", spec.roof_chimney},
        {"castShadow", spec.cast_shadow},
    };

    return {
        {"metadata", metadata},
        {"geometry", geometry},
        {"projection", projection},
        {"palette", palette},
        {"features", features},
        {"sockets", sockets},
    };
}

} // namespace ch::studio
