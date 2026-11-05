import json
import locale
import os
import sys

from engrama.resources import i18n_dir

_DIR = i18n_dir()
_LANGS = ("pt", "en")
_FALLBACK = "en"
_TABLES: dict[str, dict[str, str]] = {}


def _ui_locale_name(env=None, platform=None) -> str:
    plat = sys.platform if platform is None else platform
    if plat == "win32":
        try:
            import ctypes

            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return locale.windows_locale.get(lcid, "")
        except Exception:
            return locale.getlocale()[0] or ""
    # M8: POSIX — first non-empty of LANGUAGE (first item), LC_ALL, LC_MESSAGES, LANG
    env = os.environ if env is None else env
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        raw = env.get(var, "")
        if var == "LANGUAGE":
            raw = raw.split(":")[0]
        raw = raw.strip()
        if raw:
            return "" if raw.split(".")[0] in ("C", "POSIX") else raw
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
