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

    constexpr std::array<ExportItem, 8> exports = {{
        {"park_fence_straight_south.png", ch::studio::ParkFencePiece::Straight, ch::studio::ParkFenceRotation::South},
        {"park_fence_straight_east.png", ch::studio::ParkFencePiece::Straight, ch::studio::ParkFenceRotation::East},
        {"park_fence_corner_south.png", ch::studio::ParkFencePiece::Corner, ch::studio::ParkFenceRotation::South},
        {"park_fence_corner_east.png", ch::studio::ParkFencePiece::Corner, ch::studio::ParkFenceRotation::East},
        {"park_fence_end_south.png", ch::studio::ParkFencePiece::End, ch::studio::ParkFenceRotation::South},
        {"park_fence_end_east.png", ch::studio::ParkFencePiece::End, ch::studio::ParkFenceRotation::East},
        {"park_fence_gate_south.png", ch::studio::ParkFencePiece::Gate, ch::studio::ParkFenceRotation::South},
        {"park_fence_gate_east.png", ch::studio::ParkFencePiece::Gate, ch::studio::ParkFenceRotation::East},
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
