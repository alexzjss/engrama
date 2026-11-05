import json
import sys

import pytest
from pathlib import Path
from engrama.config import Config


def test_config_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    cfg = Config.load(p)
    assert p.exists()
    assert cfg.recipe == "default-v1" and cfg.permissions["time"] is False
    cfg.recipe = "other"
    cfg.save(p)
    assert Config.load(p) == cfg
    raw = json.loads(p.read_text(encoding="utf-8"))
    raw["bogus"] = 1
    p.write_text(json.dumps(raw), encoding="utf-8")
    assert Config.load(p) == cfg


def test_old_config_without_llm_fields_loads_defaults(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"recipe": "old", "time_scale": 2.0}), encoding="utf-8")
    cfg = Config.load(p)
    assert cfg.recipe == "old" and cfg.time_scale == 2.0
    assert cfg.model == "qwen3:1.7b" and cfg.keep_alive_s == 600.0
    assert cfg.recommended_models == ("qwen3:1.7b", "qwen3:0.6b", "gemma3:1b", "llama3.2:1b")
    assert cfg.ollama_url == "http://127.0.0.1:11434"
    cfg.save(p)
    assert Config.load(p) == cfg


def test_config_m5_defaults_and_old_config(tmp_path):
    cfg = Config.load(tmp_path / "new.json")
    assert not any(cfg.permissions.values()) and cfg.perception_asked is False
    assert cfg.eyes_closed is False and cfg.perception_interval_s == 30.0
    assert cfg.perception_blocklist == [] and cfg.eyes_hotkey == "ctrl+alt+e"
    p = tmp_path / "old.json"
    p.write_text(json.dumps({"permissions": {"idle": True}}), encoding="utf-8")
    old = Config.load(p)
    assert old.permissions["idle"] is True and old.permissions["time"] is False
    assert old.perception_asked is False and old.eyes_hotkey == "ctrl+alt+e"


@pytest.mark.skipif(sys.platform == "win32", reason="simula Linux: caminhos POSIX")
def test_config_linux_defaults_no_drive_letter(tmp_path, monkeypatch):
    from engrama import config as config_mod

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(config_mod.shutil, "which", lambda name: "/usr/bin/ollama")
    p = tmp_path / "config.json"
    cfg = Config.load(p)
    assert str(cfg.ollama_exe) == "/usr/bin/ollama"
    assert cfg.ollama_home is None and cfg.ollama_models is None
    assert "E:" not in p.read_text(encoding="utf-8")


def test_config_windows_defaults_have_no_fixed_drive(monkeypatch):
    from engrama import config as config_mod
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(config_mod.shutil, "which", lambda name: None)   # shutil.which is POSIX-only here
    cfg = Config()
    assert cfg.ollama_home is None and cfg.ollama_models is None
    assert "E:" not in str(cfg.ollama_exe)


def test_windows_ollama_discovery_order():
    from engrama.config import default_ollama_exe
    env = {"LOCALAPPDATA": r"C:\L", "ProgramFiles": r"C:\PF"}
    local, pf = Path(env["LOCALAPPDATA"]) / "Programs" / "Ollama" / "ollama.exe", \
        Path(env["ProgramFiles"]) / "Ollama" / "ollama.exe"
    # PATH first
    assert default_ollama_exe("win32", env, lambda p: True, lambda n: r"C:\bin\ollama.exe") == Path(r"C:\bin\ollama.exe")
    # then the official installer folder, then Program Files
    assert default_ollama_exe("win32", env, lambda p: True, lambda n: None) == local
    assert default_ollama_exe("win32", env, lambda p: p == pf, lambda n: None) == pf
    # nothing found: a non-existent, non-crashing value (the UI reports "Ollama not found")
    nothing = default_ollama_exe("win32", env, lambda p: False, lambda n: None)
    assert nothing == local and not nothing.exists()
    assert default_ollama_exe("win32", {}, lambda p: False, lambda n: None) == Path("ollama.exe")


def test_missing_ollama_is_reported_unavailable(tmp_path):
    from engrama.config import default_ollama_exe
    from engrama.services.language.server import OllamaServer
    exe = default_ollama_exe("win32", {"LOCALAPPDATA": str(tmp_path)}, lambda p: False, lambda n: None)
    srv = OllamaServer(Config(data_dir=tmp_path, ollama_exe=exe), ping=lambda *a: False)
    assert srv.available() is False and srv.start() is False


def test_saved_e_drive_config_loads_unchanged_on_windows(tmp_path, monkeypatch):
    from engrama import config as config_mod
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(config_mod.shutil, "which", lambda name: None)
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"ollama_exe": r"E:\Ollama\ollama.exe", "ollama_home": r"E:\Ollama\home",
                             "ollama_models": r"E:\Ollama\models"}), encoding="utf-8")
    cfg = Config.load(p)
    assert cfg.ollama_exe == Path(r"E:\Ollama\ollama.exe")
    assert cfg.ollama_home == Path(r"E:\Ollama\home") and cfg.ollama_models == Path(r"E:\Ollama\models")


@pytest.mark.skipif(sys.platform == "win32", reason="simula Linux: caminhos POSIX")
def test_windows_config_loaded_on_linux_falls_back(tmp_path, monkeypatch):
    from engrama import config as config_mod

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(config_mod.shutil, "which", lambda name: None)
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"ollama_exe": r"E:\Ollama\ollama.exe", "ollama_home": r"E:\Ollama\home",
                             "ollama_models": "E:/Ollama/models", "recipe": "x"}), encoding="utf-8")
    cfg = Config.load(p)
    assert str(cfg.ollama_exe) == "/usr/local/bin/ollama"
    assert cfg.ollama_home is None and cfg.ollama_models is None
    assert cfg.recipe == "x"


@pytest.mark.skipif(sys.platform == "win32", reason="simula Linux: caminhos POSIX")
def test_linux_custom_ollama_path_is_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"ollama_exe": "/opt/ollama/bin/ollama", "ollama_home": "/srv/ollama"}),
                 encoding="utf-8")
    cfg = Config.load(p)
    assert str(cfg.ollama_exe) == "/opt/ollama/bin/ollama"
    assert cfg.ollama_home == Path("/srv/ollama")


def test_windows_config_kept_on_windows(tmp_path, monkeypatch):
    from engrama import config as config_mod
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(config_mod.shutil, "which", lambda name: None)
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"ollama_home": r"D:\Ollama\home"}), encoding="utf-8")
    assert Config.load(p).ollama_home == Path(r"D:\Ollama\home")


def test_null_paths_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    cfg = Config(ollama_home=None, ollama_models=None)
    cfg.save(p)
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["ollama_home"] is None and raw["ollama_models"] is None
    assert Config.load(p) == cfg


def test_config_embed_defaults_roundtrip(tmp_path):
    cfg = Config.load(tmp_path / "new.json")
    assert cfg.embed_model == "embeddinggemma" and cfg.semantic_recall is True
    assert cfg.recommended_embed_models == ("embeddinggemma", "nomic-embed-text", "bge-m3")
    p = tmp_path / "config.json"
    cfg.embed_model = "nomic-embed-text"
    cfg.semantic_recall = False
    cfg.save(p)
    back = Config.load(p)
    assert back == cfg
    assert back.recommended_embed_models == cfg.recommended_embed_models
    assert isinstance(back.recommended_embed_models, tuple)


def test_m8_config_without_embed_fields_loads_defaults(tmp_path):
    p = tmp_path / "m8.json"
    p.write_text(json.dumps({"display_mode": "overlay", "model": "qwen3:1.7b"}), encoding="utf-8")
    cfg = Config.load(p)
    assert cfg.display_mode == "overlay"
    assert cfg.embed_model == "embeddinggemma" and cfg.semantic_recall is True
    assert cfg.recommended_embed_models == ("embeddinggemma", "nomic-embed-text", "bge-m3")
