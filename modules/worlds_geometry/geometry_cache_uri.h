// Portable validation for opt-in Godot WGC1 cache paths; no filesystem access.
#pragma once

#include <string>

namespace worlds_geometry {
// Accept only ASCII safe relative names under the dedicated user:// cache directory.
bool valid_geometry_cache_uri(const std::string &uri);
} // namespace worlds_geometry
