"""Terrarium UI: pygame window, scene, HUD and panels. Reads Snapshots, posts events; never touches the kernel or mind."""
from .window import Window, register_panel, PANELS

__all__ = ["Window", "register_panel", "PANELS"]
