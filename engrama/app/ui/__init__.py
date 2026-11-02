"""Terrarium UI: pygame window, scene, HUD and panels. Reads Snapshots, posts events; never touches the kernel or mind."""
from .window import Window, register_panel, PANELS
from . import menus

# window.py registers placeholders for these names; replace them with the real panels.
register_panel("models", menus.ModelsPanel)
register_panel("settings", menus.SettingsPanel)

__all__ = ["Window", "register_panel", "PANELS"]
