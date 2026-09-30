#define main procedural_road_preview_interactive_main
#include "procedural_road_preview_main.cpp"
#undef main

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    if (argc < 2) {
        std::cerr << "Usage: MapForge2ProceduralRoadPngProof <output.png>\n";
        return 2;
    }

    const std::filesystem::path output = argv[1];

    // CI proof must exercise the supported City Horizon road policy: ground-only.
    // Keep every spline handle at z=0 so an old elevated/viaduct demo can never
    // masquerade as the current MapForge road proof again.
    RoadSplineSegment segment = default_segment();
    segment.start.z = 0.0F;
    segment.control_a.z = 0.0F;
    segment.control_b.z = 0.0F;
    segment.end.z = 0.0F;

    QImage image(kPreviewWidth, kPreviewHeight, QImage::Format_ARGB32_Premultiplied);
    QPainter painter(&image);
    render_scene(painter, segment, ProceduralRoadClass::local,
                 default_camera(), -1, kPreviewWidth, kPreviewHeight);
    painter.end();

    const std::filesystem::path parent = output.parent_path();
    if (!parent.empty()) std::filesystem::create_directories(parent);
    if (!image.save(QString::fromStdString(output.string()), "PNG")) {
        std::cerr << "Failed to write ground-only procedural road preview: " << output.string() << '\n';
        return 1;
    }

    std::cout << "Wrote ground-only procedural road preview: " << output.string() << '\n';
    return 0;
}
