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
    snapshot.camera = camera;
    snapshot.viewport_width = viewport_width;
    snapshot.viewport_height = viewport_height;
    snapshot.valid = viewport_width > 0.0F && viewport_height > 0.0F && camera.zoom > 0.0F;
}

[[nodiscard]] inline const ViewSnapshot& snapshot() {
    return mutable_snapshot();
}

}  // namespace ch::runtime_view
