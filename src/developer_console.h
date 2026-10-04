#pragma once

#include <algorithm>
#include <cctype>
#include <functional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

inline constexpr const char* kDeveloperConsoleContract = "CH_DEVELOPER_CONSOLE_V1";

struct DeveloperConsoleResult {
    bool success = false;
    std::string output;
};

struct DeveloperConsoleCommandInfo {
    std::string name;
    std::string usage;
    std::string description;
    bool read_only = true;
};

class DeveloperConsoleRegistry {
public:
    using Arguments = std::vector<std::string>;
    using Handler = std::function<DeveloperConsoleResult(const Arguments&)>;

    [[nodiscard]] bool register_command(std::string name, Handler handler) {
        return register_command({name, name, {}, true}, std::move(handler));
    }

    [[nodiscard]] bool register_command(DeveloperConsoleCommandInfo info, Handler handler) {
        if (info.name.empty() || !handler || commands_.contains(info.name)) return false;
        if (info.usage.empty()) info.usage = info.name;
        const std::string key = info.name;
        commands_.emplace(key, Entry{std::move(info), std::move(handler)});
        return true;
    }

    [[nodiscard]] bool contains(const std::string_view name) const {
        return commands_.find(std::string(name)) != commands_.end();
    }

    [[nodiscard]] DeveloperConsoleResult execute(const std::string_view line) {
        const Arguments tokens = tokenize(line);
        if (tokens.empty()) return record_result(std::string(line), {false, "empty command"});
        const auto found = commands_.find(tokens.front());
        if (found == commands_.end()) {
            return record_result(std::string(line), {false, "unknown command: " + tokens.front()});
        }
        Arguments args(tokens.begin() + 1, tokens.end());
        return record_result(std::string(line), found->second.handler(args));
    }

    [[nodiscard]] std::vector<std::string> command_names() const {
        std::vector<std::string> names;
        names.reserve(commands_.size());
        for (const auto& [name, entry] : commands_) {
            (void)entry;
            names.push_back(name);
        }
        std::sort(names.begin(), names.end());
        return names;
    }

    [[nodiscard]] std::vector<DeveloperConsoleCommandInfo> command_info() const {
        std::vector<DeveloperConsoleCommandInfo> info;
        info.reserve(commands_.size());
        for (const auto& [name, entry] : commands_) {
            (void)name;
            info.push_back(entry.info);
        }
        std::sort(info.begin(), info.end(), [](const auto& left, const auto& right) {
            return left.name < right.name;
        });
        return info;
    }

    [[nodiscard]] DeveloperConsoleResult help(const std::string_view name = {}) const {
        if (!name.empty()) {
            const auto found = commands_.find(std::string(name));
            if (found == commands_.end()) return {false, "unknown command: " + std::string(name)};
            const DeveloperConsoleCommandInfo& info = found->second.info;
            std::string output = info.usage;
            if (!info.description.empty()) output += " - " + info.description;
            output += info.read_only ? " [read-only]" : " [mutating]";
            return {true, std::move(output)};
        }

        std::string output;
        for (const DeveloperConsoleCommandInfo& info : command_info()) {
            if (!output.empty()) output += '\n';
            output += info.usage;
            if (!info.description.empty()) output += " - " + info.description;
        }
        return {true, std::move(output)};
    }

    [[nodiscard]] const std::vector<std::string>& history() const noexcept { return history_; }
    void clear_history() { history_.clear(); }

    [[nodiscard]] static Arguments tokenize(const std::string_view line) {
        Arguments tokens;
        std::string current;
        bool quoted = false;
        bool escaped = false;
        for (const char c : line) {
            if (escaped) {
                current.push_back(c);
                escaped = false;
                continue;
            }
            if (c == '\\') {
                escaped = true;
                continue;
            }
            if (c == '"') {
                quoted = !quoted;
                continue;
            }
            if (!quoted && std::isspace(static_cast<unsigned char>(c))) {
                if (!current.empty()) {
                    tokens.push_back(std::move(current));
                    current.clear();
                }
                continue;
            }
            current.push_back(c);
        }
        if (escaped) current.push_back('\\');
        if (!current.empty()) tokens.push_back(std::move(current));
        return tokens;
    }

private:
    struct Entry {
        DeveloperConsoleCommandInfo info;
        Handler handler;
    };

    [[nodiscard]] DeveloperConsoleResult record_result(std::string line, DeveloperConsoleResult result) {
        if (!line.empty()) history_.push_back(std::move(line));
        return result;
    }

    std::unordered_map<std::string, Entry> commands_;
    std::vector<std::string> history_;
};
