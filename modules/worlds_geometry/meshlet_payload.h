// Offline meshlet payload compaction; preserves audited triangle and vertex references.
#pragma once

#include "meshlet_builder.h"

namespace worlds_geometry {
// Remove unreferenced vertex and triangle storage while preserving meshlet ordering.
// Requires prior independent coverage certification; never repairs an invalid partition.
// On failure the input is left unchanged.
bool compact_meshlet_payload(MeshletBuild &build);
} // namespace worlds_geometry
