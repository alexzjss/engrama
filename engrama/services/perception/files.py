"""Reading of a file/folder the user dropped on the window (explicit show-a-file).

The content is returned in memory only; callers must never persist it.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

FILE_READ_CAP = 8192
MAX_ENTRIES = 20

TEXT_EXT = {".txt", ".md", ".rst", ".log", ".csv", ".tsv", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
            ".xml", ".html", ".htm", ".css", ".tex"}
CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".h", ".cpp", ".hpp", ".cs", ".go", ".rs", ".rb",
            ".php", ".sh", ".bat", ".ps1", ".sql", ".lua", ".kt", ".swift", ".gd"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".svg", ".tif", ".tiff"}


@dataclass(frozen=True)
class FileGlimpse:
    name: str
    kind: str          # texto | codigo | imagem | pasta | binario
    size_word: str     # pequeno | médio | grande
    text: str | None
    entries: tuple[str, ...]


def _size_word(n: int) -> str:
    return "pequeno" if n < 10_000 else "médio" if n < 1_000_000 else "grande"


def read_dropped(path: str, blocklist=None, cap: int = FILE_READ_CAP) -> FileGlimpse | None:
    try:
        path = os.fspath(path)
        name = os.path.basename(path.rstrip("/\\"))
        ext = os.path.splitext(name)[1].lower()
        if not name or ext == ".lnk":
            return None
        if blocklist is not None and blocklist.is_blocked(name, name):
            return None
        if os.path.isdir(path):
            with os.scandir(path) as it:
                entries = tuple(sorted(e.name for e in it))[:MAX_ENTRIES]
            return FileGlimpse(name, "pasta", "pequeno", None, entries)
        if not os.path.isfile(path):
            return None
        sw = _size_word(os.path.getsize(path))
        if ext in IMAGE_EXT:
            return FileGlimpse(name, "imagem", sw, None, ())
        kind = "texto" if ext in TEXT_EXT else "codigo" if ext in CODE_EXT else "binario"
        if kind == "binario":
            return FileGlimpse(name, kind, sw, None, ())
        with open(path, "rb") as f:
            data = f.read(max(0, cap))
        if b"\x00" in data:
            return FileGlimpse(name, "binario", sw, None, ())
        text = data.decode("utf-8", errors="replace")
        if text and text.count("�") / len(text) > 0.10:
            return FileGlimpse(name, "binario", sw, None, ())
        while len(text.encode("utf-8")) > cap:
            text = text[:-1]
        return FileGlimpse(name, kind, sw, text, ())
    except Exception:
        return None
