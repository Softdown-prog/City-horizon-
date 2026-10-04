#include "src/coaster_sdl_renderer.h"

#include <SDL3/SDL.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <limits>
#include <string>
#include <vector>

namespace {

constexpr int kWidth = 1280;
constexpr int kHeight = 720;
constexpr float kMargin = 72.0F;
constexpr double kPi = 3.14159265358979323846;

struct Cursor {
    double x = 12.0;
    double y = 0.0;
    double z = 0.0;
    double heading = 0.0;
};

void push_unique(std::vector<ch::coaster::RoutePoint>& points,
                 const double x,
                 const double y,
                 const double z,
                 const ch::coaster::DriveMode mode = ch::coaster::DriveMode::Free,
                 const double speed = -1.0) {
    if (!points.empty()) {
        const auto& p = points.back();
        const double dx = x - p.x;
        const double dy = y - p.y;
        const double dz = z - p.z;
        if (dx * dx + dy * dy + dz * dz < 1.0e-10) return;
    }
    points.push_back({x, y, z, mode, speed});
}

void append_straight(std::vector<ch::coaster::RoutePoint>& points,
                     Cursor& cursor,
                     const double length,
                     const double rise,
                     const ch::coaster::DriveMode mode = ch::coaster::DriveMode::Free,
                     const double speed = -1.0) {
    const int samples = std::max(2, static_cast<int>(std::ceil(length / 0.5)));
    const double sx = cursor.x;
    const double sy = cursor.y;
    const double sz = cursor.z;
    const double fx = std::cos(cursor.heading);
    const double fy = std::sin(cursor.heading);
    for (int i = 1; i <= samples; ++i) {
        const double t = static_cast<double>(i) / static_cast<double>(samples);
        push_unique(points,
                    sx + fx * length * t,
                    sy + fy * length * t,
                    sz + rise * t,
                    mode,
                    speed);
    }
    cursor.x = sx + fx * length;
    cursor.y = sy + fy * length;
    cursor.z = sz + rise;
}

void append_quarter_curve(std::vector<ch::coaster::RoutePoint>& points,
                          Cursor& cursor,
                          const double radius,
                          const bool left,
                          const ch::coaster::DriveMode mode = ch::coaster::DriveMode::Free,
                          const double speed = -1.0) {
    const double sign = left ? 1.0 : -1.0;
    const double lx = -std::sin(cursor.heading);
    const double ly = std::cos(cursor.heading);
    const double cx = cursor.x + lx * radius * sign;
    const double cy = cursor.y + ly * radius * sign;
    const double rx = cursor.x - cx;
    const double ry = cursor.y - cy;
    constexpr int samples = 40;
    for (int i = 1; i <= samples; ++i) {
        const double a = sign * (kPi * 0.5) *
                         (static_cast<double>(i) / static_cast<double>(samples));
        const double c = std::cos(a);
        const double s = std::sin(a);
        push_unique(points,
                    cx + rx * c - ry * s,
                    cy + rx * s + ry * c,
                    cursor.z,
                    mode,
                    speed);
    }
    const double a = sign * (kPi * 0.5);
    const double c = std::cos(a);
    const double s = std::sin(a);
    cursor.x = cx + rx * c - ry * s;
    cursor.y = cy + rx * s + ry * c;
    cursor.heading += a;
}

bool build_switchback_route(ch::coaster::CenterlineRoute& route) {
    using ch::coaster::DriveMode;
    Cursor c;
    std::vector<ch::coaster::RoutePoint> points;
    points.reserve(800U);
    push_unique(points, c.x, c.y, c.z, DriveMode::Station, 4.5);

    append_straight(points, c, 20.0, 0.0, DriveMode::Station, 4.5);
    append_quarter_curve(points, c, 10.0, true);
    append_straight(points, c, 20.0, 10.0, DriveMode::Lift, 6.0);
    append_quarter_curve(points, c, 10.0, false);
    append_straight(points, c, 20.0, -10.0);
    append_quarter_curve(points, c, 10.0, true);
    append_straight(points, c, 20.0, 6.0);
    append_quarter_curve(points, c, 10.0, true);
    append_straight(points, c, 20.0, 0.0);
    append_quarter_curve(points, c, 10.0, true);
    append_straight(points, c, 20.0, 6.0);
    append_quarter_curve(points, c, 10.0, false);
    append_straight(points, c, 20.0, -8.0);
    append_quarter_curve(points, c, 10.0, true);
    append_straight(points, c, 20.0, -4.0, DriveMode::Brake, 7.0);
    append_quarter_curve(points, c, 10.0, true, DriveMode::Brake, 5.5);

    const double dx = c.x - 12.0;
    const double dy = c.y;
    const double dz = c.z;
    const double closure = std::sqrt(dx * dx + dy * dy + dz * dz);
    if (closure > 0.02) {
        std::fprintf(stderr, "Switchback route did not close: %.6f m\n", closure);
        return false;
    }
    if (points.size() >= 2U) {
        const auto& first = points.front();
        const auto& last = points.back();
        const double ex = last.x - first.x;
        const double ey = last.y - first.y;
        const double ez = last.z - first.z;
        if (ex * ex + ey * ey + ez * ez < 1.0e-12) points.pop_back();
    }
    return route.rebuild(std::move(points), true);
}

struct Bounds {
    float min_x = std::numeric_limits<float>::max();
    float min_y = std::numeric_limits<float>::max();
    float max_x = std::numeric_limits<float>::lowest();
    float max_y = std::numeric_limits<float>::lowest();

    void include(const ch::ScreenPoint p) {
        min_x = std::min(min_x, p.x);
        min_y = std::min(min_y, p.y);
        max_x = std::max(max_x, p.x);
        max_y = std::max(max_y, p.y);
    }
};

Bounds projected_bounds(const ch::coaster::CoasterTrackGeometry& geometry,
                        const ch::CameraState& camera) {
    Bounds bounds;
    const auto include_world = [&](const ch::coaster::CoasterTrackPoint3& p) {
        const ch::WorldPoint3 world = ch::coaster::coaster_track_world_point(p);
        bounds.include(ch::world_to_screen_point(
            world, camera, static_cast<float>(kWidth), static_cast<float>(kHeight)));
    };
    for (const auto& frame : geometry.frames) {
        include_world(frame.left_rail);
        include_world(frame.right_rail);
        include_world(frame.spine);
    }
    for (const auto& support : geometry.supports) {
        include_world(support.top);
        include_world(support.bottom);
    }
    return bounds;
}

ch::CameraState fitted_camera(const ch::coaster::CoasterTrackGeometry& geometry) {
    ch::CameraState camera;
    camera.rotation = ch::CameraRotation::r0;
    camera.zoom = 1.0F;
    camera.pan_x = 0.0F;
    camera.pan_y = 0.0F;

    Bounds initial = projected_bounds(geometry, camera);
    const float width = std::max(1.0F, initial.max_x - initial.min_x);
    const float height = std::max(1.0F, initial.max_y - initial.min_y);
    camera.zoom = std::clamp(
        std::min((static_cast<float>(kWidth) - 2.0F * kMargin) / width,
                 (static_cast<float>(kHeight) - 2.0F * kMargin) / height),
        0.20F,
        2.50F);

    Bounds scaled = projected_bounds(geometry, camera);
    const float center_x = (scaled.min_x + scaled.max_x) * 0.5F;
    const float center_y = (scaled.min_y + scaled.max_y) * 0.5F;
    camera.pan_x += static_cast<float>(kWidth) * 0.5F - center_x;
    camera.pan_y += static_cast<float>(kHeight) * 0.5F - center_y;
    return camera;
}

void draw_grid(SDL_Renderer* renderer, const ch::CameraState& camera) {
    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
    SDL_SetRenderDrawColor(renderer, 235, 245, 235, 26);
    constexpr int tiles = 32;
    for (int x = 0; x <= tiles; ++x) {
        const ch::ScreenPoint a = ch::world_to_screen_point(
            static_cast<float>(x), 0.0F, camera,
            static_cast<float>(kWidth), static_cast<float>(kHeight));
        const ch::ScreenPoint b = ch::world_to_screen_point(
            static_cast<float>(x), static_cast<float>(tiles), camera,
            static_cast<float>(kWidth), static_cast<float>(kHeight));
        SDL_RenderLine(renderer, a.x, a.y, b.x, b.y);
    }
    for (int y = 0; y <= tiles; ++y) {
        const ch::ScreenPoint a = ch::world_to_screen_point(
            0.0F, static_cast<float>(y), camera,
            static_cast<float>(kWidth), static_cast<float>(kHeight));
        const ch::ScreenPoint b = ch::world_to_screen_point(
            static_cast<float>(tiles), static_cast<float>(y), camera,
            static_cast<float>(kWidth), static_cast<float>(kHeight));
        SDL_RenderLine(renderer, a.x, a.y, b.x, b.y);
    }
}

bool write_metadata(const std::filesystem::path& path,
                    const ch::coaster::CenterlineRoute& route,
                    const ch::coaster::CoasterTrackGeometry& geometry,
                    const ch::CameraState& camera) {
    std::ofstream out(path);
    if (!out) return false;
    out << "{\n"
        << "  \"contract\": \"CH_COASTER_SDL_VISUAL_PROOF_V1\",\n"
        << "  \"trackGeometryContract\": \"" << ch::coaster::kCoasterTrackGeometryContract << "\",\n"
        << "  \"trackPresentationContract\": \"" << ch::coaster::kCoasterTrackPresentationContract << "\",\n"
        << "  \"worldScaleContract\": \"" << ch::coaster::kCoasterWorldScaleContract << "\",\n"
        << "  \"projectId\": \"coaster.flame.switchback.02\",\n"
        << "  \"tileMeters\": 3.0,\n"
        << "  \"routeLengthMeters\": " << route.length_m() << ",\n"
        << "  \"frames\": " << geometry.frames.size() << ",\n"
        << "  \"ties\": " << geometry.ties.size() << ",\n"
        << "  \"supportMembers\": " << geometry.supports.size() << ",\n"
        << "  \"cameraZoom\": " << camera.zoom << ",\n"
        << "  \"width\": " << kWidth << ",\n"
        << "  \"height\": " << kHeight << "\n"
        << "}\n";
    return true;
}

}  // namespace

int main(int argc, char** argv) {
    const std::filesystem::path output_dir =
        argc >= 2 ? std::filesystem::path(argv[1])
                  : std::filesystem::path("out/coaster_sdl_visual_proof");
    std::filesystem::create_directories(output_dir);

    ch::coaster::CenterlineRoute route;
    if (!build_switchback_route(route)) return 2;

    const ch::coaster::CoasterTrackStyle style{};
    const ch::coaster::CoasterTrackGeometry geometry =
        ch::coaster::build_coaster_track_geometry(route, style, 0.0);
    if (!geometry.valid()) {
        std::fprintf(stderr, "CH_COASTER_TRACK_GEOMETRY_V1 output invalid\n");
        return 3;
    }

    const ch::CameraState camera = fitted_camera(geometry);

    if (!SDL_Init(SDL_INIT_VIDEO)) {
        std::fprintf(stderr, "SDL_Init failed: %s\n", SDL_GetError());
        return 4;
    }

    SDL_Surface* surface = SDL_CreateSurface(kWidth, kHeight, SDL_PIXELFORMAT_RGBA32);
    if (surface == nullptr) {
        std::fprintf(stderr, "SDL_CreateSurface failed: %s\n", SDL_GetError());
        SDL_Quit();
        return 5;
    }
    SDL_Renderer* renderer = SDL_CreateSoftwareRenderer(surface);
    if (renderer == nullptr) {
        std::fprintf(stderr, "SDL_CreateSoftwareRenderer failed: %s\n", SDL_GetError());
        SDL_DestroySurface(surface);
        SDL_Quit();
        return 6;
    }

    SDL_SetRenderDrawColor(renderer, 58, 112, 62, 255);
    SDL_RenderClear(renderer);
    draw_grid(renderer, camera);
    ch::coaster::render_coaster_track(
        renderer,
        geometry,
        camera,
        static_cast<float>(kWidth),
        static_cast<float>(kHeight));
    SDL_RenderPresent(renderer);

    const std::filesystem::path bmp_path =
        output_dir / "coaster_flame_switchback_02_runtime_track.bmp";
    if (!SDL_SaveBMP(surface, bmp_path.string().c_str())) {
        std::fprintf(stderr, "SDL_SaveBMP failed: %s\n", SDL_GetError());
        SDL_DestroyRenderer(renderer);
        SDL_DestroySurface(surface);
        SDL_Quit();
        return 7;
    }

    const std::filesystem::path meta_path = output_dir / "proof_meta.json";
    if (!write_metadata(meta_path, route, geometry, camera)) {
        std::fprintf(stderr, "Failed to write proof metadata\n");
        SDL_DestroyRenderer(renderer);
        SDL_DestroySurface(surface);
        SDL_Quit();
        return 8;
    }

    std::printf("CH_COASTER_SDL_VISUAL_PROOF_V1: OK\n");
    std::printf("%s + %s + %s\n",
                ch::coaster::kCoasterTrackGeometryContract,
                ch::coaster::kCoasterWorldScaleContract,
                ch::coaster::kCoasterTrackPresentationContract);
    std::printf("route=%.3f m frames=%zu ties=%zu supports=%zu zoom=%.4f\n",
                route.length_m(),
                geometry.frames.size(),
                geometry.ties.size(),
                geometry.supports.size(),
                camera.zoom);

    SDL_DestroyRenderer(renderer);
    SDL_DestroySurface(surface);
    SDL_Quit();
    return 0;
}
