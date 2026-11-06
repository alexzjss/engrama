from pathlib import Path

import pytest

from engrama.app import cli
from engrama.paths import (has_save, legacy_save_dir, migrate_data_dir, resolve_data_dir)


def _pkg(tmp_path, git=True, pyproject=True):
    repo = tmp_path / "repo"
    (repo / "engrama").mkdir(parents=True)
    if git:
        (repo / ".git").mkdir()
    if pyproject:
        (repo / "pyproject.toml").write_text("x")
    return repo / "engrama"


def test_cli_arg_wins(tmp_path):
    pkg = _pkg(tmp_path)
    assert resolve_data_dir("/a", {"ENGRAMA_DATA_DIR": "/b"}, "linux", tmp_path, pkg) == Path("/a")


def test_env_beats_dev_and_os(tmp_path):
    pkg = _pkg(tmp_path)
    assert resolve_data_dir(None, {"ENGRAMA_DATA_DIR": "/b"}, "linux", tmp_path, pkg) == Path("/b")


def test_dev_checkout(tmp_path):
    pkg = _pkg(tmp_path)
    assert resolve_data_dir(None, {}, "linux", tmp_path / "h", pkg) == pkg.parent / "data"


@pytest.mark.parametrize("git,pyproject", [(False, True), (True, False), (False, False)])
def test_not_dev_without_both_markers(tmp_path, git, pyproject):
    pkg = _pkg(tmp_path, git, pyproject)
    home = tmp_path / "h"
    assert resolve_data_dir(None, {}, "linux", home, pkg) == home / ".local" / "share" / "engrama"


def test_linux_xdg_and_fallback(tmp_path):
    pkg = _pkg(tmp_path, git=False)
    assert resolve_data_dir(None, {"XDG_DATA_HOME": "/x"}, "linux", tmp_path, pkg) == Path("/x/engrama")
    assert resolve_data_dir(None, {}, "linux", tmp_path, pkg) == tmp_path / ".local/share/engrama"


def test_windows_appdata_and_fallback(tmp_path):
    pkg = _pkg(tmp_path, git=False)
    assert resolve_data_dir(None, {"APPDATA": "/ad"}, "win32", tmp_path, pkg) == Path("/ad") / "Engrama"
    assert resolve_data_dir(None, {}, "win32", tmp_path, pkg) == tmp_path / "AppData" / "Roaming" / "Engrama"


def test_macos(tmp_path):
    pkg = _pkg(tmp_path, git=False)
    assert resolve_data_dir(None, {}, "darwin", tmp_path, pkg) == tmp_path / "Library/Application Support/Engrama"


def _make_save(d):
    (d / "save").mkdir(parents=True)
    (d / "save" / "meta.json").write_text("{}")
    (d / "memory.sqlite").write_text("m")
    (d / "engrama.lock").write_text("123")


def test_migrate_copies_and_keeps_source(tmp_path):
    src, dst = tmp_path / "old", tmp_path / "new"
    _make_save(src)
    assert migrate_data_dir(src, dst) == "ok"
    assert (dst / "save" / "meta.json").exists() and (dst / "memory.sqlite").read_text() == "m"
    assert not (dst / "engrama.lock").exists()
    assert (src / "save" / "meta.json").exists()   # copied, not moved


def test_migrate_refuses_when_destination_has_save(tmp_path):
    src, dst = tmp_path / "old", tmp_path / "new"
    _make_save(src)
    _make_save(dst)
    (dst / "memory.sqlite").write_text("mine")
    assert migrate_data_dir(src, dst) == "has_save"
    assert (dst / "memory.sqlite").read_text() == "mine"


def test_migrate_refuses_when_host_json_present(tmp_path):
    src, dst = tmp_path / "old", tmp_path / "new"
    _make_save(src)
    dst.mkdir()
    (dst / "host.json").write_text("{}")
    assert has_save(dst) and migrate_data_dir(src, dst) == "has_save"


def test_migrate_missing_source(tmp_path):
    assert migrate_data_dir(tmp_path / "nope", tmp_path / "new") == "missing"
    assert not (tmp_path / "new").exists()


def test_legacy_save_dir(tmp_path):
    pkg = _pkg(tmp_path)
    assert legacy_save_dir(pkg) is None
    _make_save(pkg.parent / "data")
    assert legacy_save_dir(pkg) == pkg.parent / "data"


def test_cli_migrate_from(tmp_path, capsys):
    src, dst = tmp_path / "old", tmp_path / "new"
    _make_save(src)
    assert cli.main(["--migrate-from", str(src), "--data-dir", str(dst)]) == 0
    assert (dst / "save" / "meta.json").exists()
    assert "Copiado" in capsys.readouterr().out
    assert cli.main(["--migrate-from", str(src), "--data-dir", str(dst)]) == 2
    err = capsys.readouterr().err
    assert "já tem um save" in err and "already has a save" in err
    assert cli.main(["--migrate-from", str(tmp_path / "x"), "--data-dir", str(tmp_path / "n2")]) == 2
    err = capsys.readouterr().err
    assert "não encontrada" in err and "not found" in err
