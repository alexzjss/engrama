import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    platform: str            # "win32" | "linux" | outro sys.platform
    kind: str                # "x11" | "wayland" | "none"
    compositor: str          # "hyprland" | "sway" | "kde" | "gnome" | "other" | ""
    env: Mapping[str, str]


def _kind(env: Mapping[str, str], platform: str) -> str:
    if platform == "win32" or env.get("SDL_VIDEODRIVER") == "dummy":
        return "none"
    session_type = env.get("XDG_SESSION_TYPE", "")
    if session_type == "wayland" or (env.get("WAYLAND_DISPLAY") and session_type != "x11"):
        return "wayland"
    if env.get("DISPLAY"):
        return "x11"
    return "none"


def _compositor(env: Mapping[str, str]) -> str:
    if env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "hyprland"
    if env.get("SWAYSOCK"):
        return "sway"
    desktop = env.get("XDG_CURRENT_DESKTOP", "").upper()
    if "KDE" in desktop:
        return "kde"
    if "GNOME" in desktop:
        return "gnome"
    return "other"


def detect(env: Mapping[str, str] | None = None, platform: str | None = None) -> Session:
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    kind = _kind(env, platform)
    compositor = "" if kind == "none" else _compositor(env)
    return Session(platform=platform, kind=kind, compositor=compositor, env=env)
