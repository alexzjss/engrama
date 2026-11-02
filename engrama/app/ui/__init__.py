"""Terrarium UI: pygame window, scene, HUD and panels. Reads Snapshots, posts events; never touches the kernel or mind."""
from .window import Window, register_panel, PANELS
from . import menus
from .memories import MemoriesPanel
from .permissions import FirstUsePanel, PermissionsPanel

# window.py registers placeholders for these names; replace them with the real panels.
register_panel("models", menus.ModelsPanel)
register_panel("settings", menus.SettingsPanel)
register_panel("memories", MemoriesPanel)
register_panel("permissions", PermissionsPanel)
register_panel("first_use", FirstUsePanel)

__all__ = ["Window", "register_panel", "PANELS"]
