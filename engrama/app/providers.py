"""Adapters and small helpers the app wires into the UI and services (moved out of host.py, unchanged)."""
from __future__ import annotations
import time
from pathlib import Path
from typing import Callable

from engrama import balance as B
from engrama.app.snapshot import Snapshot
from engrama.services.generations import GenerationRecord, delete_generation_archive, load_generations


class _GenerationsProvider:
    """Adapter the Generations panel (F10) talks to: the registry file plus per-generation archive folders."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)

    def records(self) -> list[GenerationRecord]:
        return load_generations(self.data_dir / "generations.json")

    def delete_archive(self, n: int) -> None:
        delete_generation_archive(self.data_dir, n)


def _build_persona(snap: Snapshot, memory, name: str = ""):
    from engrama.services.language.persona import PersonaState
    needs = sorted(((v, n) for n, v in snap.needs.items() if v > 0.6), reverse=True)
    liking = sorted(snap.food_liking.items(), key=lambda kv: kv[1])
    try:
        memories = memory.recent(3)
    except Exception:
        memories = []
    return PersonaState(
        stage=snap.stage, needs_top=[n for _, n in needs], traits=dict(snap.traits), mood=snap.pad_label,
        curious=snap.surprise > B.SURPRISE_CURIOUS,
        favorites=[f for f, v in reversed(liking) if v > 0][:2],
        disliked=[f for f, v in liking if v < 0][:2],
        memories=list(memories), name=name)


class _MemoryProvider:
    """Adapter the Memories panel (F7) talks to: MemoryStore + WorkingMemory behind the duck-typed protocol."""

    def __init__(self, memory, working, language=None) -> None:
        self.memory, self.working, self.language = memory, working, language

    @staticmethod
    def _lang() -> str:
        from engrama.app import i18n
        return i18n.get_lang()

    def facts(self) -> list[tuple[str, str]]:
        return [(r["key"], r["value"]) for r in self.memory.fact_rows()]

    def topics(self) -> list[tuple[str, bool]]:
        cur = set(self.memory.current_topics(10 ** 6))
        return [(r["name"], r["name"] in cur) for r in self.memory.topic_rows()]

    def opinions(self) -> list[tuple[str, str]]:
        from engrama.services.memory.opinions import stance_word
        lang = self._lang()
        return [(r["topic"], r["phrase"] or stance_word(r["stance"], lang))
                for r in self.memory.opinion_rows() if r["confidence"] > 0]

    def reflections(self) -> list[str]:
        return list(self.memory.recent_reflections(5))

    def _embed_state(self) -> tuple[str, dict]:
        """(embedder status, vector counts). Reads only what is already known; never calls the embedder."""
        lang = self.language
        if lang is None:
            try:
                counts = self.memory.vector_counts()
            except Exception:
                counts = {}
            return "off", counts
        try:
            status = str(getattr(lang, "embed_status", "off") or "off")
        except Exception:
            status = "off"
        try:
            counts = dict(lang.embed_counts() or {})
        except Exception:
            counts = {}
        return status, counts

    SUMMARY_TTL_S = 2.0   # the Mind View asks every frame; the counts are COUNT(*) queries

    def _counts(self, status: str) -> dict:
        """Counts behind summary(), refreshed at most every SUMMARY_TTL_S (or when the embedder status changes
        or something is deleted through this adapter)."""
        now = time.monotonic()
        c = getattr(self, "_cache", None)
        if c is not None and c[2] == status and now - c[0] < self.SUMMARY_TTL_S:
            return c[1]
        refl = self.memory.recent_reflections(1)
        _, vcounts = self._embed_state()
        data = {"episodes": len(self.memory.recent(10 ** 6)), "facts": len(self.memory.fact_rows()),
                "topics": len(self.memory.topic_rows()),
                "opinions": len([r for r in self.memory.opinion_rows() if r["confidence"] > 0]),
                "last_reflection": refl[0] if refl else "",
                "vectors": int(vcounts.get("vectors", 0) or 0), "items": int(vcounts.get("items", 0) or 0)}
        self._cache = (now, data, status)
        return data

    def _invalidate(self) -> None:
        self._cache = None

    def summary(self) -> dict:
        lang = self.language
        try:
            status = str(getattr(lang, "embed_status", "off") or "off") if lang is not None else "off"
        except Exception:
            status = "off"
        data = dict(self._counts(status))
        vectors = data["vectors"]
        # "on" when the embedder is ready, or when vectors are stored and the embedder is not off
        data["semantic"] = "on" if (status == "ready" or (vectors > 0 and status != "off")) else "words"
        return data

    def _drop_working(self, needles: list[str]) -> None:
        from engrama.services.memory.topics import plain_text
        needles = [plain_text(n) for n in needles if n]
        keep = [m for m in self.working.messages()
                if not any(n and n in plain_text(m.get("content", "")) for n in needles)]
        self.working.clear()
        for m in keep:
            self.working.add(m["role"], m["content"])

    def delete_fact(self, key: str) -> None:
        value = next((v for k, v in self.facts() if k == key), "")
        self.memory.delete_fact(key)
        self._invalidate()
        self._drop_working([value, key.replace("_", " ")])

    def delete_topic(self, name: str) -> None:
        from engrama.services.memory.topics import SYNONYMS, normalize_topic
        key = normalize_topic(name)
        try:
            perceived = any(r["name"] == key and r.get("source") == "percepcao" for r in self.memory.topic_rows())
        except Exception:
            perceived = False
        self.memory.delete_topic(name)
        self._invalidate()
        if perceived:   # a deleted screen-derived theme stays silenced (and is listed in F8 to undo)
            self.memory.silence_theme(name)
        self._drop_working([key] + [k for k, v in SYNONYMS.items() if v == key])

    def forget_all(self) -> None:
        self.memory.forget_all_about_user()
        self._invalidate()
        self.working.clear()


class _PerceptionProvider:
    """Adapter the Permissions panel (F8) talks to."""

    def __init__(self, memory, hotkey_error: Callable[[], str]) -> None:
        self.memory, self._hk = memory, hotkey_error

    def silenced_themes(self) -> list[str]: return self.memory.silenced_themes()
    def unsilence_theme(self, name: str) -> None: self.memory.unsilence_theme(name)
    def clear_app_categories(self) -> None: self.memory.clear_app_categories()
    def hotkey_error(self) -> str: return self._hk() or ""


class _Activity:
    """Last allowed thing the user is doing (a theme, else a category), kept in memory only.

    Never holds a title or process: the service only emits categories/themes. A private app yields None."""

    def __init__(self, post: Callable[[str, dict | None], None], theme_sink: Callable[[str, str, str], None]) -> None:
        self._post, self._sink = post, theme_sink
        self._category: str | None = None
        self._theme: str | None = None

    def post(self, kind: str, data: dict | None = None) -> None:
        if kind == "app_focus":
            cat = (data or {}).get("category")
            if cat != self._category:
                self._category, self._theme = cat, None
        self._post(kind, data)

    def on_theme(self, process: str, title: str, category: str) -> None:
        from engrama.services.perception.themes import extract_theme
        self._sink(process, title, category)
        theme = extract_theme(process, title, category)
        if theme:
            self._theme = theme

    def current(self) -> str | None:
        from engrama.services.perception import PRIVATE
        if self._category is None or self._category == PRIVATE:
            return None
        return self._theme or self._category


def _memory_provider(memory, working, language=None) -> _MemoryProvider:
    return _MemoryProvider(memory, working, language)


class _NullServer:
    """Stands in for OllamaServer under --no-llm: never available, never spawns anything."""
    started_by_us = False

    def available(self) -> bool: return False
    def running(self) -> bool: return False
    def start(self) -> bool: return False
    def stop(self) -> None: pass
