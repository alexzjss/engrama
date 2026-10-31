import json

import pytest

from engrama import i18n


REQUIRED_KEYS = [
    *[f"need.{k}" for k in ("fome", "sono", "tedio", "carinho", "curiosidade", "apoio")],
    *[f"stage.{s}" for s in ("egg", "baby", "child", "adult", "perfect", "final")],
    *[f"action.{a}" for a in ("feed", "play", "sleep", "rest", "chat_hint")],
    *[
        f"menu.{k}"
        for k in (
            "food.title",
            "models.title",
            "models.other",
            "models.installed",
            "models.active",
            "models.offline",
            "models.pulling",
            "settings.title",
            "settings.lang",
            "settings.dev",
        )
    ],
    *[f"llm.{k}" for k in ("offline", "loading", "ready", "not_found")],
    *[f"model.note.{m}" for m in ("qwen3_1_7b", "gemma3_1b", "qwen2_5_1_5b", "llama3_2_1b", "qwen3_4b")],
    *[f"food.{f}" for f in ("carne", "fruta", "peixe", "bolinho", "pacote", "cookie", "bug", "cache", "byte", "ram")],
    "snn.title",
    "rest.on",
    "rest.off",
    "babble.bleh",
    "babble.missed_you",
    "babble.brain_loading",
]


@pytest.fixture(autouse=True)
def _restore_lang():
    before = i18n.get_lang()
    yield
    i18n.set_lang(before)


def _load(lang: str) -> dict:
    return json.loads((i18n._DIR / f"{lang}.json").read_text(encoding="utf-8"))


def test_all_keys_in_both_languages():
    pt, en = _load("pt"), _load("en")
    assert set(pt) == set(en)
    assert set(REQUIRED_KEYS) <= set(pt)


def test_exact_values_from_brief():
    i18n.set_lang("pt")
    assert i18n.t("model.note.qwen3_1_7b") == "recomendado: bom PT/EN, ~1,4 GB"
    assert i18n.t("babble.missed_you") == "demorou... gru?"
    assert i18n.t("babble.brain_loading") == "zzz... (cérebro carregando)"
    assert i18n.t("food.ram") == "raminho de RAM"
    i18n.set_lang("en")
    assert i18n.t("model.note.qwen3_1_7b") == "recommended: good PT/EN, ~1.4 GB"
    assert i18n.t("babble.missed_you") == "you took long... gru?"
    assert i18n.t("babble.brain_loading") == "zzz... (brain loading)"
    assert i18n.t("food.cookie") == "browser cookie"


def test_set_and_get_lang():
    i18n.set_lang("pt")
    assert i18n.get_lang() == "pt"
    i18n.set_lang("en")
    assert i18n.get_lang() == "en"


def test_set_lang_rejects_unknown():
    with pytest.raises(ValueError):
        i18n.set_lang("fr")


def test_system_lang_pt(monkeypatch):
    monkeypatch.setattr(i18n, "_ui_locale_name", lambda: "pt_BR")
    assert i18n.system_lang() == "pt"


def test_system_lang_defaults_to_en(monkeypatch):
    monkeypatch.setattr(i18n, "_ui_locale_name", lambda: "de_DE")
    assert i18n.system_lang() == "en"
    monkeypatch.setattr(i18n, "_ui_locale_name", lambda: "")
    assert i18n.system_lang() == "en"


def test_fallback_to_en_then_key(monkeypatch):
    pt = dict(_load("pt"))
    del pt["stage.egg"]
    monkeypatch.setitem(i18n._TABLES, "pt", pt)
    i18n.set_lang("pt")
    assert i18n.t("stage.egg") == "Egg"
    assert i18n.t("no.such.key") == "no.such.key"


def test_format_kwargs(monkeypatch):
    monkeypatch.setitem(i18n._TABLES, "en", {"x.count": "{n} items for {who}"})
    i18n.set_lang("en")
    assert i18n.t("x.count", n=3, who="Engrama") == "3 items for Engrama"


def test_no_format_args_leaves_braces_alone(monkeypatch):
    monkeypatch.setitem(i18n._TABLES, "en", {"x.raw": "{literal}"})
    i18n.set_lang("en")
    assert i18n.t("x.raw") == "{literal}"
