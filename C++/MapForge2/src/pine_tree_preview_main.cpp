#include "pine_tree_renderer.h"

#include <QDir>
#include <QGuiApplication>
#include <QImage>

#include <iostream>

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);

    const QString output_dir = argc > 1
        ? QString::fromLocal8Bit(argv[1])
        : QDir::currentPath();
    QDir().mkpath(output_dir);

    const ch::studio::PineTreeSpec spec;

    const QImage tree = ch::studio::PineTreeRenderer::renderTree(spec);
    const QString tree_path = QDir(output_dir).filePath("pine_tree_rgba.png");
    if (!tree.save(tree_path)) {
        std::cerr << "failed to save " << tree_path.toStdString() << '\n';
        return 2;
    }

    const QImage review = ch::studio::PineTreeRenderer::renderReviewSheet(spec);
    const QString review_path = QDir(output_dir).filePath("pine_tree_review.png");
    if (!review.save(review_path)) {
        std::cerr << "failed to save " << review_path.toStdString() << '\n';
        return 3;
    }

    std::cout << review_path.toStdString() << '\n';
    return 0;
}
