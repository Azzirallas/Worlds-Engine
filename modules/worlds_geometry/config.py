"""Experimental geometry diagnostics are explicitly opt-in."""


def is_enabled():
    """Keep normal Godot builds unaffected until native integration is tested."""
    return False


def can_build(env, platform):
    """Require 3D mesh types and the existing meshoptimizer module."""
    if env["disable_3d"]:
        return False
    env.module_add_dependencies("worlds_geometry", ["meshoptimizer"])
    return True


def configure(env):
    """No custom environment modifications are needed."""
    pass


def get_doc_classes():
    """Expose the optional editor/script API reference."""
    return ["WorldsMeshTopology"]


def get_doc_path():
    """Find the module's class reference near its source code."""
    return "doc_classes"
