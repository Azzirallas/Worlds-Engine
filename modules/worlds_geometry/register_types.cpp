// Registers the opt-in, read-only mesh audit scripting interface.
#include "register_types.h"
#include "worlds_mesh_topology.h"

#include "core/object/class_db.h"

void initialize_worlds_geometry_module(ModuleInitializationLevel p_level) {
    if (p_level == MODULE_INITIALIZATION_LEVEL_SCENE) {
        GDREGISTER_CLASS(WorldsMeshTopology);
    }
}

void uninitialize_worlds_geometry_module(ModuleInitializationLevel p_level) {
    (void)p_level; // There is no singleton or global allocation to dispose.
}
