import json
from engrama.config import Config


def test_config_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    cfg = Config.load(p)
    assert p.exists()
    assert cfg.recipe == "default-v1" and cfg.permissions["time"] is True
    assert not hasattr(cfg, "model") and not hasattr(cfg, "keep_alive")
    cfg.recipe = "other"
    cfg.save(p)
    assert Config.load(p) == cfg
    raw = json.loads(p.read_text(encoding="utf-8"))
    raw["bogus"] = 1
    p.write_text(json.dumps(raw), encoding="utf-8")
    assert Config.load(p) == cfg
