#include "fence_runtime_adapter.h"
#include "park_fence_renderer.h"

#include <QDir>
#include <QGuiApplication>
#include <QImage>

#include <array>
#include <iostream>
#include <string_view>
#include <vector>

namespace {

struct RuntimeCase {
    const char* name;
    std::vector<FenceVertex> vertices;
    bool gate_center = false;
};

bool saveRuntimeCase(const QString& output_dir,
                     const ch::studio::ParkFenceSpec& spec,
                     const RuntimeCase& runtime_case) {
    FenceManager fences(0, 8);
    for (const FenceVertex vertex : runtime_case.vertices) {
        if (!fences.place_node(vertex.x, vertex.y)) {
            std::cerr << "failed to place runtime fence vertex for " << runtime_case.name << '\n';
            return false;
        }
    }
    if (runtime_case.gate_center && !fences.set_gate(4, 4, true)) {
        std::cerr << "failed to mark runtime fence gate for " << runtime_case.name << '\n';
        return false;
    }

    const FenceVisualState state = fences.visual_state(4, 4);
    const ch::studio::FenceRenderSelection selection =
        ch::studio::FenceRuntimeAdapter::select(state);
    const QImage image = ch::studio::ParkFenceRenderer::renderPiece(
        spec, selection.piece, selection.rotation);
    const QString path = QDir(output_dir).filePath(
        QStringLiteral("park_fence_runtime_%1.png").arg(QString::fromLatin1(runtime_case.name)));
    if (!image.save(path)) {
        std::cerr << "failed to save " << path.toStdString() << '\n';
        return false;
    }
    return true;
}

} // namespace

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

    // These cases are resolved by the real runtime FenceManager. They prove
    // that MapForge consumes the same topology contract used by gameplay rather
    // than keeping a second N/E/S/W resolver in the editor.
    const std::array<RuntimeCase, 7> runtime_cases = {{
        {"end", {{4, 4}, {4, 5}}}, false},
        {"straight", {{4, 3}, {4, 4}, {4, 5}}}, false},
        {"corner", {{4, 4}, {5, 4}, {4, 5}}}, false},
        {"tee", {{3, 4}, {4, 4}, {5, 4}, {4, 5}}}, false},
        {"cross", {{4, 3}, {3, 4}, {4, 4}, {5, 4}, {4, 5}}}, false},
        {"gate", {{4, 3}, {4, 4}, {4, 5}}, true},
        {"drag_corner", {{2, 2}, {3, 2}, {4, 2}, {4, 3}, {4, 4}}}, false},
    }};
    for (const RuntimeCase& runtime_case : runtime_cases) {
        if (!saveRuntimeCase(output_dir, spec, runtime_case)) {
            return 4;
        }
    }

    // Exercise the actual tycoon drag helper too: X first, then Y. The bend at
    // (4,2) must resolve to Corner without the preview choosing a piece itself.
    FenceManager drag_fences(0, 8);
    const std::vector<FenceVertex> drag_path = drag_fences.line_between({2, 2}, {4, 4});
    if (drag_fences.place_run(drag_path) != static_cast<int>(drag_path.size())) {
        std::cerr << "runtime fence drag helper did not place the complete path\n";
        return 5;
    }
    if (drag_fences.visual_state(4, 2).type != FenceVisualType::corner) {
        std::cerr << "runtime fence drag bend did not resolve to a corner\n";
        return 6;
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
