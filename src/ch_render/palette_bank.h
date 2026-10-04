#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace ch {

struct Rgba8 {
    std::uint8_t r = 0;
    std::uint8_t g = 0;
    std::uint8_t b = 0;
    std::uint8_t a = 255;

    friend bool operator==(const Rgba8&, const Rgba8&) = default;
};

struct PaletteRange {
    std::size_t first = 0;
    std::size_t count = 0;
};

class PaletteBank {
public:
    PaletteBank() = default;
    explicit PaletteBank(std::vector<Rgba8> entries) : entries_(std::move(entries)) {}

    [[nodiscard]] std::size_t size() const noexcept { return entries_.size(); }

    [[nodiscard]] const Rgba8* color(std::size_t index) const noexcept {
        return index < entries_.size() ? &entries_[index] : nullptr;
    }

    [[nodiscard]] bool define_range(std::string name, PaletteRange range) {
        if (name.empty() || range.count == 0 || range.first > entries_.size() ||
            range.count > entries_.size() - range.first) {
            return false;
        }
        ranges_[std::move(name)] = range;
        return true;
    }

    [[nodiscard]] std::optional<PaletteRange> range(std::string_view name) const {
        const auto found = ranges_.find(std::string(name));
        return found == ranges_.end() ? std::nullopt : std::optional(found->second);
    }

    [[nodiscard]] bool replace_range(std::string_view name, const std::vector<Rgba8>& colors) {
        const auto selected = range(name);
        if (!selected || selected->count != colors.size()) return false;
        std::copy(colors.begin(), colors.end(), entries_.begin() + static_cast<std::ptrdiff_t>(selected->first));
        return true;
    }

    [[nodiscard]] bool cycle_range(std::string_view name, int steps = 1) {
        const auto selected = range(name);
        if (!selected || selected->count < 2) return false;

        const int count = static_cast<int>(selected->count);
        int normalized = steps % count;
        if (normalized < 0) normalized += count;
        if (normalized == 0) return true;

        auto begin = entries_.begin() + static_cast<std::ptrdiff_t>(selected->first);
        auto end = begin + static_cast<std::ptrdiff_t>(selected->count);
        std::rotate(begin, end - normalized, end);
        return true;
    }

private:
    std::vector<Rgba8> entries_;
    std::unordered_map<std::string, PaletteRange> ranges_;
};

}  // namespace ch
