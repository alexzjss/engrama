"""Short, privacy-safe themes extracted from window titles. Raw titles are never kept."""
from __future__ import annotations

import re
from typing import Callable

from .categories import normalize_process

_BAD = re.compile(r"[@\\/:]|\d")
_SEP = re.compile(r"\s+[-|–—]\s+")
_GENERIC = {"steam", "epic games launcher", "launcher", "menu", "friends list", "home", "sign in"}
_MUSIC_PLAYERS = {"spotify", "foobar2000", "musicbee", "itunes", "rhythmbox", "elisa", "strawberry",
                  "audacious", "lollypop", "amberol"}
_LANGS = {"py": "python", "pyw": "python", "js": "javascript", "ts": "typescript", "tsx": "typescript",
          "jsx": "javascript", "rs": "rust", "java": "java", "cs": "csharp", "cpp": "cpp", "c": "c",
          "h": "c", "go": "go", "rb": "ruby", "php": "php", "kt": "kotlin", "lua": "lua",
          "gd": "gdscript", "html": "html", "css": "css", "sh": "shell", "swift": "swift"}
_EXT = re.compile(r"\.([A-Za-z]{1,5})\b")


def _clean(text: str) -> str | None:
    t = " ".join((text or "").lower().split())
    if not t or _BAD.search(t) or len(t.split()) > 4 or t in _GENERIC:
        return None
    return t


def extract_theme(process: str, title: str, category: str) -> str | None:
    title = (title or "").strip()
    if not title:
        return None
    if category == "jogo":
        return _clean(_SEP.split(title)[0])
    if category == "musica":
        if normalize_process(process) not in _MUSIC_PLAYERS:
            return None
        parts = _SEP.split(title, maxsplit=1)
        return _clean(parts[0]) if len(parts) == 2 else None
    if category == "programacao":
        for ext in _EXT.findall(title):
            lang = _LANGS.get(ext.lower())
            if lang:
                return f"código {lang}"
        return None
    return None


def make_theme_sink(memory, now_fn: Callable[[], float]) -> Callable[[str, str, str], None]:
    def sink(process: str, title: str, category: str) -> None:
        theme = extract_theme(process, title, category)
        if theme:
            memory.bump_perceived(theme, now_fn())
    return sink
