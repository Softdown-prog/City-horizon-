#pragma once

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

class DeveloperConsoleRegistry {
public:
    using Arguments = std::vector<std::string>;
    using Handler = std::function<DeveloperConsoleResult(const Arguments&)>;

    [[nodiscard]] bool register_command(std::string name, Handler handler) {
        if (name.empty() || !handler || commands_.contains(name)) return false;
        commands_.emplace(std::move(name), std::move(handler));
        return true;
    }

    [[nodiscard]] bool contains(const std::string_view name) const {
        return commands_.find(std::string(name)) != commands_.end();
    }

    [[nodiscard]] DeveloperConsoleResult execute(const std::string_view line) const {
        const Arguments tokens = tokenize(line);
        if (tokens.empty()) return {false, "empty command"};
        const auto found = commands_.find(tokens.front());
        if (found == commands_.end()) return {false, "unknown command: " + tokens.front()};
        Arguments args(tokens.begin() + 1, tokens.end());
        return found->second(args);
    }

    [[nodiscard]] std::vector<std::string> command_names() const {
        std::vector<std::string> names;
        names.reserve(commands_.size());
        for (const auto& [name, handler] : commands_) {
            (void)handler;
            names.push_back(name);
        }
        return names;
    }

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
    std::unordered_map<std::string, Handler> commands_;
};
