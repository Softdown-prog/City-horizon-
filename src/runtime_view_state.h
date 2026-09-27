#pragma once

#include "src/ch_core/projection.h"

namespace ch::runtime_view {

// Read-only bridge for small runtime tools that live outside main.cpp. The
// projection layer already receives the canonical camera on every frame, so it
// records the latest view here instead of duplicating camera math in UI tools.
struct ViewSnapshot {
    CameraState camera{};
    float viewport_width = 0.0F;
    float viewport_height = 0.0F;
    bool valid = false;
};

[[nodiscard]] inline ViewSnapshot& mutable_snapshot() {
    static ViewSnapshot snapshot;
    return snapshot;
}

inline void capture(const CameraState& camera, const float viewport_width,
                    const float viewport_height) {
    ViewSnapshot& snapshot = mutable_snapshot();
    const bool valid = viewport_width > 0.0F && viewport_height > 0.0F && camera.zoom > 0.0F;

    // world_to_screen_point() is one of the hottest renderer paths and calls
    // this bridge for every projected vertex/anchor. During a frame almost all
    // of those calls carry the exact same camera and viewport. Avoid rewriting
    // the shared snapshot thousands of times while preserving the existing
    // contract for tools that read runtime_view::snapshot().
    if (snapshot.valid == valid &&
        snapshot.viewport_width == viewport_width &&
        snapshot.viewport_height == viewport_height &&
        snapshot.camera.pan_x == camera.pan_x &&
        snapshot.camera.pan_y == camera.pan_y &&
        snapshot.camera.zoom == camera.zoom &&
        snapshot.camera.rotation == camera.rotation) {
        return;
    }

    snapshot.camera = camera;
    snapshot.viewport_width = viewport_width;
    snapshot.viewport_height = viewport_height;
    snapshot.valid = valid;
}

[[nodiscard]] inline const ViewSnapshot& snapshot() {
    return mutable_snapshot();
}

}  // namespace ch::runtime_view
