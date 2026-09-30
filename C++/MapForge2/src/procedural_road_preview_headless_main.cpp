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
    if (!render_png(output)) {
        std::cerr << "Failed to write procedural road preview: " << output.string() << '\n';
        return 1;
    }
    std::cout << "Wrote procedural road preview: " << output.string() << '\n';
    return 0;
}
