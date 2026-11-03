import json
from pathlib import Path

from engrama import balance, vocab
from engrama.app.snapshot import Snapshot
from engrama.config import Config

I18N = Path(__file__).resolve().parents[1] / "engrama" / "app" / "i18n"


def _catalog(lang: str) -> dict:
    return json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))


def test_m7_vocab_tuples():
    assert vocab.DIGITAL_IDS == ("ram", "defrag", "update", "cache", "cooler")
    assert vocab.VARIANTS == ("jump", "dance", "yawn", "nap_clock", "chase", "look_cursor", "peek", "dig", "found")
    assert vocab.DISPLAY_MODES == ("terrarium", "overlay")


def test_m7_balance_constants():
    assert balance.DIGITAL_REQUEST_MIN_GAP_S == 2 * balance.HOUR
    assert balance.DIGITAL_REQUEST_TTL_S == 30 * 60
    assert balance.DIGITAL_REQUEST_P == 0.35
    assert balance.CURSOR_POLL_HZ == 10
    assert balance.CURSOR_NEAR_PX == 150
    assert balance.OVERLAY_WALK_PX_S == 40


def test_config_display_mode_default_and_load(tmp_path):
    assert Config().display_mode == "terrarium"

    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    assert Config.load(path).display_mode == "terrarium"

    path.write_text(json.dumps({"display_mode": "xyz"}), encoding="utf-8")
    assert Config.load(path).display_mode == "terrarium"

    path.write_text(json.dumps({"display_mode": "overlay"}), encoding="utf-8")
    assert Config.load(path).display_mode == "overlay"


def test_config_display_mode_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    Config(display_mode="overlay").save(path)
    assert Config.load(path).display_mode == "overlay"


def test_snapshot_m7_defaults():
    snap = Snapshot()
    assert snap.fullscreen is False
    assert snap.theme == ""
    assert snap.digital_request == ""


def test_m7_i18n_keys_present_in_both_languages():
    keys = [f"digital.{d}" for d in vocab.DIGITAL_IDS]
    keys += [f"digital.ask.{d}" for d in vocab.DIGITAL_IDS]
    keys += ["ui.menu.digital", "ui.menu.overlay", "ui.overlay.unavailable", "ui.overlay.back", "ui.overlay.talk"]
    for lang in ("pt", "en"):
        cat = _catalog(lang)
        for key in keys:
            assert key in cat, (lang, key)
            assert cat[key].strip(), (lang, key)
            assert not any(ch.isdigit() for ch in cat[key]), (lang, key, cat[key])


def test_m7_i18n_key_sets_match():
    pt, en = _catalog("pt"), _catalog("en")
    new = [k for k in pt if k.startswith(("digital.", "ui.menu.digital", "ui.menu.overlay", "ui.overlay."))]
    assert new
    for k in new:
        assert k in en, k
