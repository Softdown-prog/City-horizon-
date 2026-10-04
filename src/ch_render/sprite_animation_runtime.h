#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace ch {

enum class SpriteDirection : std::uint8_t {
    South = 0,
    East = 1,
    West = 2,
    North = 3
};

struct SpriteRect {
    int x = 0;
    int y = 0;
    int width = 0;
    int height = 0;

    [[nodiscard]] bool valid() const noexcept { return width > 0 && height > 0; }
};

struct SpriteFrame {
    std::string asset_path;
    SpriteRect source_rect{};
    int draw_offset_x = 0;
    int draw_offset_y = 0;
    int anchor_x = 0;
    int anchor_y = 0;
    std::uint32_t duration_ms = 100;

    [[nodiscard]] bool valid() const noexcept {
        return !asset_path.empty() && source_rect.valid() && duration_ms > 0;
    }
};

struct SpriteTrack {
    std::vector<SpriteFrame> frames;
    bool loop = true;

    [[nodiscard]] bool valid() const noexcept {
        if (frames.empty()) return false;
        for (const SpriteFrame& frame : frames) {
            if (!frame.valid()) return false;
        }
        return true;
    }
};

struct DirectionAlias {
    SpriteDirection source = SpriteDirection::South;
    bool mirror_x = false;
};

struct ResolvedSpriteTrack {
    const SpriteTrack* track = nullptr;
    SpriteDirection authored_direction = SpriteDirection::South;
    bool mirror_x = false;

    [[nodiscard]] explicit operator bool() const noexcept { return track != nullptr; }
};

class SpriteAnimationClip {
public:
    std::string id;

    [[nodiscard]] bool set_track(SpriteDirection direction, SpriteTrack track) {
        if (!track.valid()) return false;
        tracks_[index(direction)] = std::move(track);
        aliases_[index(direction)].reset();
        return true;
    }

    [[nodiscard]] bool set_alias(SpriteDirection requested, DirectionAlias alias) {
        if (requested == alias.source) return false;
        aliases_[index(requested)] = alias;
        return true;
    }

    [[nodiscard]] ResolvedSpriteTrack resolve(SpriteDirection requested) const noexcept {
        const std::size_t requested_index = index(requested);
        if (tracks_[requested_index]) {
            return {&*tracks_[requested_index], requested, false};
        }
        if (!aliases_[requested_index]) return {};
        const DirectionAlias alias = *aliases_[requested_index];
        const auto& source = tracks_[index(alias.source)];
        if (!source) return {};
        return {&*source, alias.source, alias.mirror_x};
    }

private:
    static constexpr std::size_t index(SpriteDirection direction) noexcept {
        return static_cast<std::size_t>(direction);
    }

    std::array<std::optional<SpriteTrack>, 4> tracks_{};
    std::array<std::optional<DirectionAlias>, 4> aliases_{};
};

class SpriteAnimationPlayer {
public:
    void bind(const SpriteAnimationClip* clip) noexcept {
        if (clip_ == clip) return;
        clip_ = clip;
        reset();
    }

    void set_direction(SpriteDirection direction) noexcept {
        if (direction_ == direction) return;
        direction_ = direction;
        reset();
    }

    void reset() noexcept {
        frame_index_ = 0;
        elapsed_in_frame_ms_ = 0;
    }

    void advance(std::uint32_t delta_ms) noexcept {
        const ResolvedSpriteTrack resolved = resolved_track();
        if (!resolved || resolved.track->frames.empty() || delta_ms == 0) return;

        const SpriteTrack& track = *resolved.track;
        std::uint64_t effective_delta = delta_ms;
        if (track.loop) {
            std::uint64_t cycle_ms = 0;
            for (const SpriteFrame& frame : track.frames) cycle_ms += frame.duration_ms;
            if (cycle_ms > 0) effective_delta %= cycle_ms;
        }
        elapsed_in_frame_ms_ += effective_delta;

        while (true) {
            const SpriteFrame& frame = track.frames[frame_index_];
            if (elapsed_in_frame_ms_ < frame.duration_ms) break;
            elapsed_in_frame_ms_ -= frame.duration_ms;

            if (frame_index_ + 1 < track.frames.size()) {
                ++frame_index_;
                continue;
            }
            if (track.loop) {
                frame_index_ = 0;
                continue;
            }
            frame_index_ = track.frames.size() - 1;
            elapsed_in_frame_ms_ = 0;
            break;
        }
    }

    [[nodiscard]] const SpriteFrame* current_frame() const noexcept {
        const ResolvedSpriteTrack resolved = resolved_track();
        if (!resolved || resolved.track->frames.empty()) return nullptr;
        const std::size_t safe_index = frame_index_ < resolved.track->frames.size() ? frame_index_ : 0;
        return &resolved.track->frames[safe_index];
    }

    [[nodiscard]] bool mirror_x() const noexcept {
        return resolved_track().mirror_x;
    }

    [[nodiscard]] std::size_t frame_index() const noexcept { return frame_index_; }

private:
    [[nodiscard]] ResolvedSpriteTrack resolved_track() const noexcept {
        return clip_ == nullptr ? ResolvedSpriteTrack{} : clip_->resolve(direction_);
    }

    const SpriteAnimationClip* clip_ = nullptr;
    SpriteDirection direction_ = SpriteDirection::South;
    std::size_t frame_index_ = 0;
    std::uint64_t elapsed_in_frame_ms_ = 0;
};

}  // namespace ch
