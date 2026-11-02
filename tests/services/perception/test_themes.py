import sqlite3

import pytest

from engrama.services.memory.store import MemoryStore
from engrama.services.perception.themes import extract_theme, make_theme_sink


@pytest.mark.parametrize("args,out", [
    (("hollow_knight.exe", "Hollow Knight", "jogo"), "hollow knight"),
    (("code.exe", "main.py - engrama - Visual Studio Code", "programacao"), "código python"),
    (("chrome.exe", "Gmail - joao@x.com", "navegador"), None),
    (("spotify.exe", "Daft Punk - Around the World", "musica"), "daft punk"),
    (("x.exe", "fatura 2026.pdf", "programa"), None),
    (("hollow_knight.exe", "C:\\jogos\\x", "jogo"), None),
])
def test_theme_extraction_cases(args, out):
    assert extract_theme(*args) == out


def test_raw_title_never_stored(tmp_path):
    mem = MemoryStore(tmp_path / "m.sqlite")
    make_theme_sink(mem, lambda: 1000.0)("hollow_knight.exe", "Hollow Knight - Steam 2026", "jogo")
    assert mem.top_topics(1)[0][0] == "hollow knight"
    mem.close()
    db = sqlite3.connect(str(tmp_path / "m.sqlite"))
    dump = "\n".join(db.iterdump()).lower()
    db.close()
    assert "steam" not in dump and "2026" not in dump
