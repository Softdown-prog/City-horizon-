#pragma once

#include <cstddef>
#include <functional>
#include <optional>
#include <unordered_map>
#include <utility>

namespace ch {

// Shared, ownership-neutral cache primitive for runtime resources.
//
// ResourceCache deliberately does not know how a resource is created or
// destroyed. Callers keep ownership rules appropriate to the resource type
// (SDL textures, decoded data, audio, etc.) while reusing one lookup/load-on-
// miss contract and one set of cache telemetry.
template <typename Key, typename Value, typename Hash = std::hash<Key>, typename KeyEqual = std::equal_to<Key>>
class ResourceCache {
public:
    using Storage = std::unordered_map<Key, Value, Hash, KeyEqual>;
    using iterator = typename Storage::iterator;
    using const_iterator = typename Storage::const_iterator;

    struct Stats {
        std::size_t lookups = 0;
        std::size_t hits = 0;
        std::size_t misses = 0;
        std::size_t insertions = 0;
        std::size_t load_attempts = 0;
        std::size_t load_failures = 0;
    };

    [[nodiscard]] iterator find(const Key& key) {
        ++stats_.lookups;
        iterator found = storage_.find(key);
        if (found == storage_.end()) {
            ++stats_.misses;
        } else {
            ++stats_.hits;
        }
        return found;
    }

    [[nodiscard]] const_iterator find(const Key& key) const {
        ++stats_.lookups;
        const_iterator found = storage_.find(key);
        if (found == storage_.end()) {
            ++stats_.misses;
        } else {
            ++stats_.hits;
        }
        return found;
    }

    // Lookup without changing telemetry. Useful for diagnostics and shutdown.
    [[nodiscard]] iterator peek(const Key& key) { return storage_.find(key); }
    [[nodiscard]] const_iterator peek(const Key& key) const { return storage_.find(key); }

    template <typename... Args>
    std::pair<iterator, bool> emplace(Args&&... args) {
        auto result = storage_.emplace(std::forward<Args>(args)...);
        if (result.second) ++stats_.insertions;
        return result;
    }

    // Loader contract: std::optional<Value> loader(). A miss invokes it once;
    // successful results are inserted and reused by later callers.
    template <typename Loader>
    [[nodiscard]] Value* get_or_load(const Key& key, Loader&& loader) {
        iterator existing = find(key);
        if (existing != storage_.end()) return &existing->second;

        ++stats_.load_attempts;
        std::optional<Value> loaded = std::invoke(std::forward<Loader>(loader));
        if (!loaded.has_value()) {
            ++stats_.load_failures;
            return nullptr;
        }

        auto [inserted, was_inserted] = storage_.emplace(key, std::move(*loaded));
        if (was_inserted) ++stats_.insertions;
        return &inserted->second;
    }

    [[nodiscard]] bool contains(const Key& key) const { return storage_.contains(key); }
    [[nodiscard]] std::size_t size() const noexcept { return storage_.size(); }
    [[nodiscard]] bool empty() const noexcept { return storage_.empty(); }

    std::size_t erase(const Key& key) { return storage_.erase(key); }
    void clear() noexcept { storage_.clear(); }

    [[nodiscard]] iterator begin() noexcept { return storage_.begin(); }
    [[nodiscard]] iterator end() noexcept { return storage_.end(); }
    [[nodiscard]] const_iterator begin() const noexcept { return storage_.begin(); }
    [[nodiscard]] const_iterator end() const noexcept { return storage_.end(); }
    [[nodiscard]] const_iterator cbegin() const noexcept { return storage_.cbegin(); }
    [[nodiscard]] const_iterator cend() const noexcept { return storage_.cend(); }

    [[nodiscard]] const Stats& stats() const noexcept { return stats_; }
    void reset_stats() noexcept { stats_ = {}; }

private:
    Storage storage_;
    mutable Stats stats_{};
};

}  // namespace ch
