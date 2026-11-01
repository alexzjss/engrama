import json
import locale
from pathlib import Path

_DIR = Path(__file__).parent
_LANGS = ("pt", "en")
_FALLBACK = "en"
_TABLES: dict[str, dict[str, str]] = {}


def _ui_locale_name() -> str:
    try:
        import ctypes

        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return locale.windows_locale.get(lcid, "")
    except Exception:
        return locale.getlocale()[0] or ""


def system_lang() -> str:
    return "pt" if _ui_locale_name().lower().startswith("pt") else "en"


_lang = system_lang()


def set_lang(lang: str) -> None:
    global _lang
    if lang not in _LANGS:
        raise ValueError(f"unsupported language: {lang}")
    _lang = lang


def get_lang() -> str:
    return _lang


def _table(lang: str) -> dict[str, str]:
    if lang not in _TABLES:
        _TABLES[lang] = json.loads((_DIR / f"{lang}.json").read_text(encoding="utf-8"))
    return _TABLES[lang]


def t(key: str, **fmt) -> str:
    text = _table(_lang).get(key)
    if text is None:
        text = _table(_FALLBACK).get(key, key)
    return text.format(**fmt) if fmt else text
