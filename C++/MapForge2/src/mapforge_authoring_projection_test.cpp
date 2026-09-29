#include "authoring_projection.h"
#include "src/ch_core/contracts.h"

#include <QPointF>
#include <QSizeF>

#include <array>
#include <cmath>
#include <iostream>

namespace {

struct Point2 {
    float x = 0.0F;
    float y = 0.0F;
};

Point2 rotate_asset(const Point2 point, const int asset_quarter_turns) {
    switch (asset_quarter_turns) {
        case 1: return {-point.y, point.x};
        case 2: return {-point.x, -point.y};
        case 3: return {point.y, -point.x};
        default: return point;
    }
}

float point_error(const QPointF& left, const QPointF& right) {
    const float dx = static_cast<float>(left.x() - right.x());
    const float dy = static_cast<float>(left.y() - right.y());
    return std::sqrt(dx * dx + dy * dy);
}

QPointF legacy_authoring_projection(const Point2 point,
                                    const float elevation_pixels,
                                    const int asset_quarter_turns,
                                    const QPointF& origin) {
    const Point2 rotated = rotate_asset(point, asset_quarter_turns);
    return QPointF(
        origin.x() + (rotated.x - rotated.y) * (ch::contracts::kTileWidth * 0.5F),
        origin.y() + (rotated.x + rotated.y) * (ch::contracts::kTileHeight * 0.5F)
            - elevation_pixels);
}

} // namespace

int main() {
    constexpr float kTolerance = 0.0001F;
    const QPointF origin(137.25, 91.75);
    const QSizeF viewport(731.0, 509.0);
    const std::array<Point2, 5> points = {{
        {0.0F, 0.0F},
        {1.0F, 0.0F},
        {0.0F, 1.0F},
        {1.25F, -0.75F},
        {-2.50F, 3.125F},
    }};
    const std::array<float, 3> pixel_heights = {{0.0F, 13.0F, 82.0F}};

    if (ch::studio::authoringCameraRotation(0) != ch::CameraRotation::r0
        || ch::studio::authoringCameraRotation(1) != ch::CameraRotation::r270
        || ch::studio::authoringCameraRotation(2) != ch::CameraRotation::r180
        || ch::studio::authoringCameraRotation(3) != ch::CameraRotation::r90) {
        std::cerr << "asset-turn to camera-turn mapping drifted\n";
        return 1;
    }

    for (int turn = 0; turn < 4; ++turn) {
        for (const Point2 point : points) {
            for (const float z_pixels : pixel_heights) {
                const QPointF expected = legacy_authoring_projection(point, z_pixels, turn, origin);
                const QPointF projected = ch::studio::projectAuthoringPixelElevation(
                    point.x, point.y, z_pixels, turn, viewport, origin);
                if (point_error(expected, projected) > kTolerance) {
                    std::cerr << "authoring projection parity failed at turn " << turn
                              << " point (" << point.x << ", " << point.y << ")"
                              << " zpx=" << z_pixels << '\n';
                    return 2;
                }
            }
        }
    }

    const QPointF north = ch::studio::projectAuthoringGround(-0.5F, -0.5F, 0, viewport, origin);
    const QPointF east = ch::studio::projectAuthoringGround(0.5F, -0.5F, 0, viewport, origin);
    const QPointF south = ch::studio::projectAuthoringGround(0.5F, 0.5F, 0, viewport, origin);
    const QPointF west = ch::studio::projectAuthoringGround(-0.5F, 0.5F, 0, viewport, origin);
    const float diamond_width = static_cast<float>(east.x() - west.x());
    const float diamond_height = static_cast<float>(south.y() - north.y());
    if (std::abs(diamond_width - ch::contracts::kTileWidth) > kTolerance
        || std::abs(diamond_height - ch::contracts::kTileHeight) > kTolerance) {
        std::cerr << "authoring tile diamond no longer matches CH_CAMERA_V1\n";
        return 3;
    }

    std::cout << "PASS CH_MAPFORGE_AUTHORING_PROJECTION_V1\n";
    return 0;
}
