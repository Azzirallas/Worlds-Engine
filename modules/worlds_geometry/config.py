"""Experimental geometry diagnostics are explicitly opt-in."""


def is_enabled():
    """Keep normal Godot builds unaffected until native integration is tested."""
    return False


def can_build(env, platform):
    """Indexed 3D mesh diagnostics need the engine's 3D types."""
    return not env["disable_3d"]


def configure(env):
    """No custom environment modifications are needed."""
    pass


def get_doc_classes():
    """Expose the optional editor/script API reference."""
    return ["WorldsMeshTopology"]


def get_doc_path():
    """Find the module's class reference near its source code."""
    return "doc_classes"
