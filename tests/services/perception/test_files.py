import os

from engrama.services.perception import files
from engrama.services.perception.files import FILE_READ_CAP, read_dropped


class Block:
    def is_blocked(self, process, title):
        return "bradesco" in title.lower()


def test_text_capped(tmp_path):
    p = tmp_path / "big.py"
    p.write_text("x = 'ação'\n" * 5000, encoding="utf-8")
    assert p.stat().st_size > 50_000 - 1
    g = read_dropped(str(p))
    assert g.kind == "codigo" and g.name == "big.py"
    assert len(g.text.encode()) <= FILE_READ_CAP == files.FILE_READ_CAP
    assert g.size_word == "médio"


def test_folder_first_level_only(tmp_path):
    d = tmp_path / "proj"
    (d / "sub").mkdir(parents=True)
    (d / "sub" / "deep.txt").write_text("x")
    for i in range(15):
        (d / f"f{i:02d}.txt").write_text("x")
    g = read_dropped(str(d))
    assert g.kind == "pasta" and g.text is None
    assert len(g.entries) <= 20 and list(g.entries) == sorted(g.entries)
    assert "deep.txt" not in g.entries and "sub" in g.entries and len(g.entries) == 16


def test_image_metadata_only(tmp_path):
    p = tmp_path / "foto.png"
    p.write_bytes(b"\x89PNG" + b"a" * 100)
    g = read_dropped(str(p))
    assert g.kind == "imagem" and g.text is None and g.entries == () and g.size_word == "pequeno"


def test_blocked_name_refused(tmp_path):
    p = tmp_path / "extrato_bradesco.txt"
    p.write_text("saldo")
    assert read_dropped(str(p), Block()) is None
    assert read_dropped(str(p)) is not None


def test_binary_disguised_as_txt(tmp_path):
    p = tmp_path / "fake.txt"
    p.write_bytes(bytes(range(128, 256)) * 40)
    g = read_dropped(str(p))
    assert g.kind == "binario" and g.text is None


def test_unreadable_and_lnk_return_none(tmp_path, monkeypatch):
    lnk = tmp_path / "atalho.lnk"
    lnk.write_text("x")
    assert read_dropped(str(lnk)) is None
    assert read_dropped(str(tmp_path / "nao_existe.txt")) is None
    p = tmp_path / "a.txt"
    p.write_text("oi")
    real = open

    def deny(f, *a, **k):
        if os.fspath(f) == str(p):
            raise PermissionError
        return real(f, *a, **k)
    monkeypatch.setattr("builtins.open", deny)
    assert read_dropped(str(p)) is None


def test_folder_capped_at_20(tmp_path):
    d = tmp_path / "many"
    d.mkdir()
    for i in range(30):
        (d / f"f{i:02d}.txt").write_text("x")
    assert len(read_dropped(str(d)).entries) == 20
