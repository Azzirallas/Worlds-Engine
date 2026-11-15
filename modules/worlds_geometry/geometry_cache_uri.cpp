// Conservative script-provided cache URI validation before Godot globalizes it.
#include "geometry_cache_uri.h"

namespace worlds_geometry {
bool valid_geometry_cache_uri(const std::string &uri) {
    constexpr char prefix[] = "user://worlds_geometry_cache/";
    constexpr char suffix[] = ".wgc1";
    const std::string root(prefix);
    const std::string extension(suffix);
    if (uri.size() <= root.size() + extension.size() || uri.size() > 240 ||
            uri.compare(0, root.size(), root) != 0 ||
            uri.compare(uri.size() - extension.size(), extension.size(), extension) != 0) {
        return false;
    }
    // Dots are forbidden except for the final extension, so traversal is impossible.
    const std::size_t end = uri.size() - extension.size();
    bool previous_was_slash = true;
    for (std::size_t i = root.size(); i < end; ++i) {
        const char c = uri[i];
        if (c == '/') {
            if (previous_was_slash) { return false; }
            previous_was_slash = true;
            continue;
        }
        if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') ||
                (c >= 'a' && c <= 'z') || c == '_' || c == '-')) {
            return false;
        }
        previous_was_slash = false;
    }
    return !previous_was_slash;
}
} // namespace worlds_geometry
