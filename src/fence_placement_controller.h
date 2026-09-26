#pragma once

#include "fence_system.h"

#include <optional>
#include <vector>

// Runtime interaction layer for the classic tycoon-style fence tool.
// It deliberately keeps drawing/UI concerns out of FenceManager: this class
// owns the transient drag route and resolves the visual state that every
// affected node would have if the preview were committed.
struct FencePlacementPreviewNode {
    FenceVertex vertex{};
    FenceVisualState visual{};
    bool already_placed = false;
};

class FencePlacementController {
public:
    explicit FencePlacementController(FenceManager& fences);

    void begin_drag(FenceVertex start,
                    FenceRotation orientation_hint = FenceRotation::south);
    void update_drag(FenceVertex current);
    void cancel_drag();

    [[nodiscard]] bool dragging() const;
    [[nodiscard]] std::optional<FenceVertex> drag_start() const;
    [[nodiscard]] std::optional<FenceVertex> drag_current() const;
    [[nodiscard]] const std::vector<FenceVertex>& preview_route() const;

    // Returns both new route nodes and any already-placed neighbouring nodes
    // whose shape/rotation would change because of the preview. This is what
    // lets the player see end -> straight -> corner -> tee -> cross updates
    // before releasing the mouse button.
    [[nodiscard]] std::vector<FencePlacementPreviewNode> preview_nodes() const;

    // Commits only missing nodes; existing connected fence remains untouched
    // apart from the topology refresh performed by FenceManager.
    int commit_drag();

    // Gates are a deliberate secondary operation on a straight run. The gate
    // keeps the same automatic orientation selected from its neighbours.
    [[nodiscard]] bool place_open_gate(FenceVertex vertex);

private:
    [[nodiscard]] bool preview_contains(FenceVertex vertex) const;
    [[nodiscard]] bool virtual_has_fence(FenceVertex vertex) const;
    [[nodiscard]] FenceConnection virtual_connections(FenceVertex vertex) const;
    void rebuild_preview_route();

    FenceManager& fences_;
    bool dragging_ = false;
    FenceRotation orientation_hint_ = FenceRotation::south;
    std::optional<FenceVertex> start_;
    std::optional<FenceVertex> current_;
    std::vector<FenceVertex> preview_route_;
};
