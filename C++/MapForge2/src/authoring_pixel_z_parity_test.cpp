#include "authoring_projection.h"
#include "src/ch_core/contracts.h"

#include <QPointF>
#include <QSizeF>

#include <array>
#include <cmath>
#include <cstdlib>
#include <iostream>

namespace {

struct Sample {
    float x;
    float y;
    float z_pixels;
};

QPointF legacyProject(float x, float y, float z_pixels, int turns,
                      const QSizeF& viewport, const QPointF& origin) {
    float rx = x;
    float ry = y;
    switch (turns & 3) {
        case 1: rx = -y; ry = x; break;
        case 2: rx = -x; ry = -y; break;
        case 3: rx = y; ry = -x; break;
        default: break;
    }

    const float half_w = static_cast<float>(ch::contracts::kTileWidth) * 0.5F;
    const float half_h = static_cast<float>(ch::contracts::kTileHeight) * 0.5F;
    return {
        origin.x() + (rx - ry) * half_w,
        origin.y() + (rx + ry) * half_h - z_pixels,
    };
}

bool nearlyEqual(qreal a, qreal b) {
    return std::abs(a - b) <= 0.0001;
}

} // namespace

int main() {
    const QSizeF viewport(420.0, 420.0);
    const QPointF origin(210.0, 378.0);
    constexpr std::array<Sample, 8> samples = {{
        {0.0F, 0.0F, 0.0F},
        {1.0F, 0.0F, 0.0F},
        {0.0F, 1.0F, 0.0F},
        {-1.25F, 0.75F, 0.0F},
        {1.5F, -0.5F, 24.0F},
        {-0.25F, -1.75F, 82.0F},
        {0.33F, 0.66F, 128.0F},
        {-2.0F, 1.0F, -4.0F},
    }};

    for (int turns = 0; turns < 4; ++turns) {
        for (const Sample& sample : samples) {
            const QPointF expected = legacyProject(
                sample.x, sample.y, sample.z_pixels, turns, viewport, origin);
            const QPointF actual = ch::studio::projectAuthoringPixelElevation(
                sample.x, sample.y, sample.z_pixels, turns, viewport, origin);
            if (!nearlyEqual(expected.x(), actual.x()) ||
                !nearlyEqual(expected.y(), actual.y())) {
                std::cerr << "FAIL CH_MAPFORGE_PIXEL_Z_PARITY_V1 turns=" << turns
                          << " sample=(" << sample.x << ',' << sample.y << ','
                          << sample.z_pixels << ") expected=(" << expected.x() << ','
                          << expected.y() << ") actual=(" << actual.x() << ','
                          << actual.y() << ")\n";
                return EXIT_FAILURE;
            }
        }
    }

    std::cout << "PASS CH_MAPFORGE_PIXEL_Z_PARITY_V1\n";
    std::cout << "pixel elevation remains authored in output pixels\n";
    return EXIT_SUCCESS;
}
