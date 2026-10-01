#include "rail_path_builder.h"

#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

namespace {

struct NamedGeometry {
    std::string name;
    RailGeometry geometry;
};

void write_mesh(std::ofstream& out, const char* name, const RailMesh& mesh) {
    out << "MESH " << name << " " << mesh.vertices.size() << " " << mesh.indices.size() << "\n";
    out << std::fixed << std::setprecision(6);
    for (const RailMeshVertex& v : mesh.vertices) {
        out << "V " << v.position.x << " " << v.position.y << " " << v.position.z << "\n";
    }
    for (std::size_t i = 0; i + 2 < mesh.indices.size(); i += 3) {
        out << "T " << mesh.indices[i] << " " << mesh.indices[i + 1] << " " << mesh.indices[i + 2] << "\n";
    }
}

bool append_geometry(std::vector<NamedGeometry>& items, const std::string& name, const RailPathBuildResult& path, const RailProfile& profile) {
    if (!path.ok()) return false;
    RailBuildResult built = RailMeshBuilder::build(path.segment, profile);
    if (!built.ok()) return false;
    items.push_back({name, std::move(built.geometry)});
    return true;
}

} // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: rail_visual_proof_export <output.txt>\n";
        return 2;
    }

    const RailProfile profile{};
    std::vector<NamedGeometry> items;

    const auto straight_a = RailPathBuilder::straight({-7.0F, -3.0F, 0.0F}, 0.0F, 6.0F, 32, profile);
    if (!append_geometry(items, "straight_a", straight_a, profile)) return 3;

    const auto curve = RailPathBuilder::quarter_curve(straight_a.segment.end, 0.0F, 4.0F, RailTurnDirection::left, 48, profile);
    if (!append_geometry(items, "curve", curve, profile)) return 4;

    constexpr float kHalfPi = 1.57079632679489661923F;
    const auto straight_b = RailPathBuilder::straight(curve.segment.end, kHalfPi, 4.5F, 32, profile);
    if (!append_geometry(items, "straight_b", straight_b, profile)) return 5;

    const RailWorldPoint3 turnout_start{4.0F, 5.5F, 0.0F};
    const auto lead = RailPathBuilder::straight({4.0F, 1.5F, 0.0F}, kHalfPi, 4.0F, 32, profile);
    if (!append_geometry(items, "turnout_lead", lead, profile)) return 6;

    const auto turnout = RailPathBuilder::turnout(turnout_start, kHalfPi, 7.0F, 0.2617993877991494F, RailTurnDirection::right, 48, profile);
    if (!turnout.ok()) return 7;

    RailBuildResult through = RailMeshBuilder::build(turnout.through, profile);
    RailBuildResult diverging = RailMeshBuilder::build(turnout.diverging, profile);
    if (!through.ok() || !diverging.ok()) return 8;
    items.push_back({"turnout_through", std::move(through.geometry)});
    items.push_back({"turnout_diverging", std::move(diverging.geometry)});

    std::ofstream out(argv[1], std::ios::trunc);
    if (!out) return 9;
    out << "CH_RAIL_VISUAL_PROOF_V1\n";
    for (const NamedGeometry& item : items) {
        out << "GEOMETRY " << item.name << "\n";
        write_mesh(out, "ballast", item.geometry.ballast);
        write_mesh(out, "sleepers", item.geometry.sleepers);
        write_mesh(out, "left_rail", item.geometry.left_rail);
        write_mesh(out, "right_rail", item.geometry.right_rail);
        out << "END_GEOMETRY\n";
    }
    return 0;
}
