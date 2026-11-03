"""Embedding model state and validation (M9). Never pulls a model; never raises to the caller."""
from __future__ import annotations

import math
import time
from typing import Callable

import numpy as np

from engrama.services.memory import (EMBED_BATCH_TIMEOUT_S, EMBED_CHECK_S, EMBED_DIM_MAX,
                                     EMBED_MAX_CHARS, EMBED_QUERY_TIMEOUT_S, EMBED_RETRY_S)

STATES = ("off", "missing", "cold", "ready", "failed")

# family -> (query prefix, document prefix)
PREFIXES: dict[str, tuple[str, str]] = {
    "embeddinggemma": ("task: search result | query: ", "title: none | text: "),
    "nomic-embed-text": ("search_query: ", "search_document: "),
    "bge-m3": ("", ""),
}


def family(model: str) -> str:
    return model.strip().split(":", 1)[0]


def installed(model: str, tags: set[str]) -> bool:
    model = model.strip()
    if not model:
        return False
    if ":" in model:
        return model in tags
    return model in tags or f"{model}:latest" in tags


class Embedder:
    def __init__(self, client, cfg, now: Callable[[], float] = time.monotonic) -> None:
        self.client = client
        self.cfg = cfg
        self._now = now
        self.dim: int | None = None
        self.dim_changed = False
        self._status = "cold"
        self._failed_until = 0.0
        self._last_model: str | None = None
        self._checked_at: float | None = None
        self._installed: bool | None = None

    @property
    def model(self) -> str:
        if not getattr(self.cfg, "semantic_recall", True):
            return ""
        return (self.cfg.embed_model or "").strip()

    @property
    def status(self) -> str:
        model = self.model
        if model != self._last_model:  # model changed (or first look): forget everything known
            self._last_model = model
            self._status = "cold"
            self._failed_until = 0.0
            self._checked_at = None
            self._installed = None
            self.dim = None
        if not model:
            return "off"
        if self._status == "failed" and self._now() >= self._failed_until:
            self._status = "cold"
        return self._status

    def _fail(self, offline: bool = False) -> None:
        self._status = "failed"
        self._failed_until = self._now() + EMBED_RETRY_S
        if offline:
            self._checked_at = None
            self._installed = None

    def refresh(self) -> str:
        st = self.status
        if st in ("off", "failed"):
            return st
        now = self._now()
        if self._checked_at is None or now - self._checked_at >= EMBED_CHECK_S:
            try:
                tags = self.client.tags()
            except Exception:
                tags = None
            if tags is not None:
                self._checked_at = now
                self._installed = installed(self.model, tags)
        if self._installed is False:
            self._status = "missing"
        elif self._installed and self._status == "missing":
            self._status = "cold"
        return self.status

    def _call(self, texts: list[str], prefix: str, timeout: float) -> list[np.ndarray] | None:
        from engrama.services.language.client import LLMOffline
        cut = [prefix + t[:EMBED_MAX_CHARS] for t in texts]
        try:
            raw = self.client.embed(self.model, cut, timeout)
            vecs = self._validate(raw, len(texts))
        except LLMOffline:
            self._fail(offline=True)
            return None
        except Exception:
            self._fail()
            return None
        if vecs is None:
            self._fail()
            return None
        dim = int(vecs[0].shape[0])
        if self.dim is not None and dim != self.dim:
            self.dim_changed = True
        self.dim = dim
        self._status = "ready"
        return vecs

    @staticmethod
    def _validate(raw, n: int) -> list[np.ndarray] | None:
        if not isinstance(raw, (list, tuple)) or len(raw) != n or n == 0:
            return None
        out: list[np.ndarray] = []
        for row in raw:
            if not isinstance(row, (list, tuple, np.ndarray)):
                return None
            if not 1 <= len(row) <= EMBED_DIM_MAX:
                return None
            try:
                v = np.asarray(row, dtype=np.float64)
            except (TypeError, ValueError):
                return None
            if v.ndim != 1 or (out and v.shape != out[0].shape) or not np.all(np.isfinite(v)):
                return None
            norm = float(np.linalg.norm(v))
            if not math.isfinite(norm) or norm <= 0.0:
                return None
            out.append((v / norm).astype(np.float32))
        return out

    def warm(self) -> bool:
        if self.refresh() in ("off", "missing", "failed"):
            return False
        return self._call([" "], "", EMBED_BATCH_TIMEOUT_S) is not None

    def unload(self) -> None:
        if self.status == "off":
            return
        try:
            self.client.unload_embed(self.model)
        except Exception:
            pass
        if self._status == "ready":
            self._status = "cold"

    def _prefix(self, i: int) -> str:
        return PREFIXES.get(family(self.model), ("", ""))[i]

    def query(self, text: str) -> np.ndarray | None:
        if self.status != "ready":
            return None
        vecs = self._call([text], self._prefix(0), EMBED_QUERY_TIMEOUT_S)
        return vecs[0] if vecs else None

    def documents(self, texts: list[str]) -> list[np.ndarray] | None:
        if self.status != "ready" or not texts:
            return None
        return self._call(texts, self._prefix(1), EMBED_BATCH_TIMEOUT_S)
