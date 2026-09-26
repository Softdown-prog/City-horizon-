#include "park_fence_renderer.h"

#include <QDir>
#include <QGuiApplication>
#include <QImage>

#include <array>
#include <iostream>

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);

    const QString output_dir = argc > 1
        ? QString::fromLocal8Bit(argv[1])
        : QDir::currentPath();
    QDir().mkpath(output_dir);

    const ch::studio::ParkFenceSpec spec;
    struct ExportItem {
        const char* name;
        ch::studio::ParkFencePiece piece;
        ch::studio::ParkFenceRotation rotation;
    };

    constexpr std::array<ExportItem, 24> exports = {{
        {"park_fence_straight_south.png", ch::studio::ParkFencePiece::Straight, ch::studio::ParkFenceRotation::South},
        {"park_fence_straight_east.png", ch::studio::ParkFencePiece::Straight, ch::studio::ParkFenceRotation::East},
        {"park_fence_straight_west.png", ch::studio::ParkFencePiece::Straight, ch::studio::ParkFenceRotation::West},
        {"park_fence_straight_north.png", ch::studio::ParkFencePiece::Straight, ch::studio::ParkFenceRotation::North},

        {"park_fence_corner_south.png", ch::studio::ParkFencePiece::Corner, ch::studio::ParkFenceRotation::South},
        {"park_fence_corner_east.png", ch::studio::ParkFencePiece::Corner, ch::studio::ParkFenceRotation::East},
        {"park_fence_corner_west.png", ch::studio::ParkFencePiece::Corner, ch::studio::ParkFenceRotation::West},
        {"park_fence_corner_north.png", ch::studio::ParkFencePiece::Corner, ch::studio::ParkFenceRotation::North},

        {"park_fence_end_south.png", ch::studio::ParkFencePiece::End, ch::studio::ParkFenceRotation::South},
        {"park_fence_end_east.png", ch::studio::ParkFencePiece::End, ch::studio::ParkFenceRotation::East},
        {"park_fence_end_west.png", ch::studio::ParkFencePiece::End, ch::studio::ParkFenceRotation::West},
        {"park_fence_end_north.png", ch::studio::ParkFencePiece::End, ch::studio::ParkFenceRotation::North},

        {"park_fence_gate_open_south.png", ch::studio::ParkFencePiece::Gate, ch::studio::ParkFenceRotation::South},
        {"park_fence_gate_open_east.png", ch::studio::ParkFencePiece::Gate, ch::studio::ParkFenceRotation::East},
        {"park_fence_gate_open_west.png", ch::studio::ParkFencePiece::Gate, ch::studio::ParkFenceRotation::West},
        {"park_fence_gate_open_north.png", ch::studio::ParkFencePiece::Gate, ch::studio::ParkFenceRotation::North},

        {"park_fence_tee_south.png", ch::studio::ParkFencePiece::Tee, ch::studio::ParkFenceRotation::South},
        {"park_fence_tee_east.png", ch::studio::ParkFencePiece::Tee, ch::studio::ParkFenceRotation::East},
        {"park_fence_tee_west.png", ch::studio::ParkFencePiece::Tee, ch::studio::ParkFenceRotation::West},
        {"park_fence_tee_north.png", ch::studio::ParkFencePiece::Tee, ch::studio::ParkFenceRotation::North},

        {"park_fence_cross_south.png", ch::studio::ParkFencePiece::Cross, ch::studio::ParkFenceRotation::South},
        {"park_fence_cross_east.png", ch::studio::ParkFencePiece::Cross, ch::studio::ParkFenceRotation::East},
        {"park_fence_cross_west.png", ch::studio::ParkFencePiece::Cross, ch::studio::ParkFenceRotation::West},
        {"park_fence_cross_north.png", ch::studio::ParkFencePiece::Cross, ch::studio::ParkFenceRotation::North},
    }};

    for (const auto& item : exports) {
        const QImage image = ch::studio::ParkFenceRenderer::renderPiece(spec, item.piece, item.rotation);
        const QString path = QDir(output_dir).filePath(QString::fromLatin1(item.name));
        if (!image.save(path)) {
            std::cerr << "failed to save " << path.toStdString() << '\n';
            return 2;
        }
    }

    const QImage review = ch::studio::ParkFenceRenderer::renderReviewSheet(spec);
    const QString review_path = QDir(output_dir).filePath("park_fence_review.png");
    if (!review.save(review_path)) {
        std::cerr << "failed to save " << review_path.toStdString() << '\n';
        return 3;
    }

    std::cout << review_path.toStdString() << '\n';
    return 0;
}
