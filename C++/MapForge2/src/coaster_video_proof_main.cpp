// Compatibility launcher for the established CH MapForge coaster video workflow.
// The workflow historically passes only <output-dir> <atlas>.  Keep that stable,
// but route the capture through CH_MAPFORGE_COASTER_PROJECT_V1 instead of the
// retired private canonical-layout proof.
#define main mapforge_coaster_project_main
#include "coaster_project_video_main.cpp"
#undef main

int main(int argc, char** argv) {
    if (argc == 3) {
        char projectPath[] = "C++/MapForge2/projects/coaster_flame_01.mapforge.json";
        char* forwarded[] = {argv[0], argv[1], argv[2], projectPath, nullptr};
        return mapforge_coaster_project_main(4, forwarded);
    }
    return mapforge_coaster_project_main(argc, argv);
}
