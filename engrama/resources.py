"""Package resources (recipes, i18n tables): one lookup that works installed, editable and frozen (PyInstaller)."""
from __future__ import annotations
import sys
from importlib import resources
from pathlib import Path


def _pkg_dir(*parts: str) -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        p = Path(meipass, "engrama", *parts)
        if p.is_dir():
            return p
    return Path(str(resources.files("engrama").joinpath(*parts)))


def recipes_dir() -> Path:
    return _pkg_dir("recipes")


def i18n_dir() -> Path:
    return _pkg_dir("app", "i18n")


def assets_dir() -> Path:
    return _pkg_dir("app", "assets")
