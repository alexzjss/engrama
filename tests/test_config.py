import json
from engrama.config import Config


def test_config_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    cfg = Config.load(p)
    assert p.exists()
    assert cfg.recipe == "default-v1" and cfg.permissions["time"] is True
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
