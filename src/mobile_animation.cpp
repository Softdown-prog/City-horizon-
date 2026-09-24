#include "mobile_animation.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <optional>
#include <sstream>
#include <unordered_set>

namespace {

[[nodiscard]] std::string read_file(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    std::ostringstream output;
    output << input.rdbuf();
    return output.str();
}

[[nodiscard]] std::optional<std::size_t> value_position(const std::string_view json, const std::string_view key) {
    const auto found = json.find('"' + std::string(key) + '"');
    if (found == std::string_view::npos) return std::nullopt;
    const auto colon = json.find(':', found);
    if (colon == std::string_view::npos) return std::nullopt;
    auto position = colon + 1;
    while (position < json.size() && std::isspace(static_cast<unsigned char>(json[position]))) ++position;
    return position;
}

[[nodiscard]] std::optional<std::string> string_value(const std::string_view json, const std::string_view key) {
    const auto position = value_position(json, key);
    if (!position || *position >= json.size() || json[*position] != '"') return std::nullopt;
    const auto end = json.find('"', *position + 1);
    return end == std::string_view::npos ? std::nullopt : std::optional(std::string(json.substr(*position + 1, end - *position - 1)));
}

[[nodiscard]] std::optional<float> float_value(const std::string_view json, const std::string_view key) {
    const auto position = value_position(json, key);
    if (!position) return std::nullopt;
    try { return std::stof(std::string(json.substr(*position))); } catch (...) { return std::nullopt; }
}

[[nodiscard]] std::optional<bool> bool_value(const std::string_view json, const std::string_view key) {
    const auto position = value_position(json, key);
    if (!position) return std::nullopt;
    if (json.substr(*position, 4) == "true") return true;
    if (json.substr(*position, 5) == "false") return false;
    return std::nullopt;
}

[[nodiscard]] std::optional<std::string_view> array_body(const std::string_view json, const std::string_view key) {
    const auto position = value_position(json, key);
    if (!position || *position >= json.size() || json[*position] != '[') return std::nullopt;
    int depth = 0;
    bool quoted = false;
    for (std::size_t index = *position; index < json.size(); ++index) {
        if (json[index] == '"' && (index == 0 || json[index - 1] != '\\')) quoted = !quoted;
        if (quoted) continue;
        if (json[index] == '[') ++depth;
        if (json[index] == ']' && --depth == 0) return json.substr(*position + 1, index - *position - 1);
    }
    return std::nullopt;
}

[[nodiscard]] std::vector<std::string_view> object_values(const std::string_view body) {
    std::vector<std::string_view> values;
    int depth = 0;
    bool quoted = false;
    std::size_t start = 0;
    for (std::size_t index = 0; index < body.size(); ++index) {
        if (body[index] == '"' && (index == 0 || body[index - 1] != '\\')) quoted = !quoted;
        if (quoted) continue;
        if (body[index] == '{' && depth++ == 0) start = index;
        if (body[index] == '}' && --depth == 0) values.push_back(body.substr(start, index - start + 1));
    }
    return values;
}

[[nodiscard]] std::vector<std::string> string_values(const std::string_view body) {
    std::vector<std::string> values;
    for (std::size_t index = 0; index < body.size();) {
        const auto begin = body.find('"', index);
        if (begin == std::string_view::npos) break;
        const auto end = body.find('"', begin + 1);
        if (end == std::string_view::npos) break;
        values.emplace_back(body.substr(begin + 1, end - begin - 1));
        index = end + 1;
    }
    return values;
}

[[nodiscard]] std::optional<MobileEntityDirection> direction_from_string(const std::string_view direction) {
    if (direction == "north") return MobileEntityDirection::north;
    if (direction == "east") return MobileEntityDirection::east;
    if (direction == "south") return MobileEntityDirection::south;
    if (direction == "west") return MobileEntityDirection::west;
    return std::nullopt;
}

}  // namespace

bool MobileAnimationCatalog::load_from_directory(const std::filesystem::path& directory) {
    sets_.clear();
    return append_from_directory(directory);
}

bool MobileAnimationCatalog::append_from_directory(const std::filesystem::path& directory) {
    bool added = false;
    std::error_code error;
    for (const auto& entry : std::filesystem::recursive_directory_iterator(directory, error)) {
        if (error || !entry.is_regular_file() || entry.path().extension() != ".json") continue;
        const std::string json = read_file(entry.path());
        MobileAnimationSet set;
        set.id = string_value(json, "id").value_or("");
        const auto clips = array_body(json, "clips");
        if (set.id.empty() || !clips) continue;
        for (const std::string_view object : object_values(*clips)) {
            MobileAnimationClip clip;
            clip.id = string_value(object, "id").value_or("");
            clip.state = string_value(object, "state").value_or("");
            const auto direction = direction_from_string(string_value(object, "direction").value_or(""));
            const auto frames = array_body(object, "frames");
            if (!direction || !frames || clip.id.empty() || clip.state.empty()) continue;
            clip.direction = *direction;
            clip.frames = string_values(*frames);
            clip.frames_per_second = std::max(0.0F, float_value(object, "fps").value_or(1.0F));
            clip.loop = bool_value(object, "loop").value_or(true);
            if (!clip.frames.empty()) set.clips.push_back(std::move(clip));
        }
        if (const auto fallbacks = array_body(json, "fallbacks")) {
            for (const std::string_view object : object_values(*fallbacks)) {
                MobileAnimationFallback fallback;
                fallback.state = string_value(object, "state").value_or("");
                fallback.fallback_state = string_value(object, "fallback").value_or("");
                if (!fallback.state.empty() && !fallback.fallback_state.empty()) set.fallbacks.push_back(std::move(fallback));
            }
        }
        if (!set.clips.empty() && find_set(set.id) == nullptr) {
            sets_.push_back(std::move(set));
            added = true;
        }
    }
    return added;
}

const MobileAnimationSet* MobileAnimationCatalog::find_set(const std::string_view id) const {
    for (const MobileAnimationSet& set : sets_) if (set.id == id) return &set;
    return nullptr;
}

const MobileAnimationClip* MobileAnimationCatalog::find_clip(const MobileAnimationSet& set, const std::string_view state,
                                                              const MobileEntityDirection direction) const {
    const auto found = std::find_if(set.clips.begin(), set.clips.end(), [&](const MobileAnimationClip& clip) {
        return clip.state == state && clip.direction == direction;
    });
    return found == set.clips.end() ? nullptr : &*found;
}

std::string_view MobileAnimationCatalog::fallback_for(const MobileAnimationSet& set, const std::string_view state) const {
    const auto found = std::find_if(set.fallbacks.begin(), set.fallbacks.end(), [&](const MobileAnimationFallback& fallback) {
        return fallback.state == state;
    });
    return found == set.fallbacks.end() ? std::string_view{} : std::string_view(found->fallback_state);
}

const MobileAnimationClip* MobileAnimationCatalog::resolve_clip(const std::string_view set_id, const std::string_view state,
                                                                 const MobileEntityDirection direction) const {
    const MobileAnimationSet* set = find_set(set_id);
    if (set == nullptr) return nullptr;
    std::string_view candidate = state;
    for (int attempt = 0; attempt < 8; ++attempt) {
        if (const MobileAnimationClip* clip = find_clip(*set, candidate, direction)) return clip;
        const std::string_view fallback = fallback_for(*set, candidate);
        if (fallback.empty() || fallback == candidate) break;
        candidate = fallback;
    }
    // Last-resort directional fallbacks keep a usable sprite on screen even
    // when an incomplete future set omitted a requested state.
    if (const MobileAnimationClip* idle = find_clip(*set, "idle", direction)) return idle;
    if (const MobileAnimationClip* south = find_clip(*set, state, MobileEntityDirection::south)) return south;
    return find_clip(*set, "idle", MobileEntityDirection::south);
}

const MobileAnimationClip* MobileAnimationCatalog::find_clip(const std::string_view set_id, const std::string_view clip_id) const {
    const MobileAnimationSet* set = find_set(set_id);
    if (set == nullptr) return nullptr;
    const auto found = std::find_if(set->clips.begin(), set->clips.end(), [&](const MobileAnimationClip& clip) { return clip.id == clip_id; });
    return found == set->clips.end() ? nullptr : &*found;
}

const std::string* MobileAnimationCatalog::current_frame(const MobileAnimationPlayer& player) const {
    const MobileAnimationClip* clip = find_clip(player.animation_set_id, player.clip_id);
    if (clip == nullptr || clip->frames.empty()) return nullptr;
    return &clip->frames[std::min(player.frame_index, clip->frames.size() - 1)];
}

std::vector<std::string> MobileAnimationCatalog::frame_assets() const {
    std::unordered_set<std::string> unique;
    for (const MobileAnimationSet& set : sets_) for (const MobileAnimationClip& clip : set.clips)
        unique.insert(clip.frames.begin(), clip.frames.end());
    return {unique.begin(), unique.end()};
}

void MobileAnimationCatalog::update_player(MobileAnimationPlayer& player, const std::string_view state,
                                           const MobileEntityDirection direction, const float frame_seconds) const {
    const MobileAnimationClip* desired = resolve_clip(player.animation_set_id, state, direction);
    if (desired == nullptr) { player.clip_id.clear(); player.frame_index = 0; player.accumulated_seconds = 0.0F; return; }
    if (player.clip_id != desired->id) {
        player.clip_id = desired->id;
        player.frame_index = 0;
        player.accumulated_seconds = 0.0F;
    }
    if (desired->frames.size() <= 1 || desired->frames_per_second <= 0.0F || frame_seconds <= 0.0F) return;
    player.accumulated_seconds += frame_seconds;
    const float effective_frames_per_second = desired->frames_per_second * std::max(0.0F, player.playback_rate);
    if (effective_frames_per_second <= 0.0F) return;
    const float frame_seconds_per_frame = 1.0F / effective_frames_per_second;
    while (player.accumulated_seconds >= frame_seconds_per_frame) {
        player.accumulated_seconds -= frame_seconds_per_frame;
        if (player.frame_index + 1 < desired->frames.size()) ++player.frame_index;
        else if (desired->loop) player.frame_index = 0;
        else { player.frame_index = desired->frames.size() - 1; player.accumulated_seconds = 0.0F; break; }
    }
}
