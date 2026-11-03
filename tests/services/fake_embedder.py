"""Deterministic stand-in for the Ollama embedding model (M9). No test talks to a real model.

Each concept has a coordinate; PT and EN words of a concept load the same coordinate, so
"cachorro", "bichinho" and "dog" land close together while "trabalho" lands far away.
Other words add small hashed coordinates, so the vectors are not identical for different texts.
"""
from __future__ import annotations

import re
import threading
import time
import zlib

import numpy as np

from engrama.services.memory.topics import plain_text

CONCEPTS: dict[str, tuple[str, ...]] = {
    "pet": ("cachorro", "cao", "bichinho", "gato", "dog", "puppy", "pet", "biscoito"),
    "work": ("trabalho", "emprego", "chefe", "demitiu", "work", "job", "boss", "fired"),
    "sad": ("triste", "tristeza", "chorando", "sad", "cry", "crying", "sadness"),
    "game": ("jogo", "jogos", "game", "games", "videogame", "hollow", "knight"),
    "music": ("musica", "banda", "music", "song", "band"),
    "weather": ("chuva", "clima", "rain", "weather", "sol"),
    "school": ("escola", "aula", "estudo", "school", "class", "study"),
    "food": ("comida", "fome", "lanche", "food", "hungry", "meal"),
    "sleep": ("sono", "dormir", "cansado", "sleep", "tired"),
    "programming": ("programacao", "programar", "codigo", "coding", "programming", "code"),
    "city": ("cidade", "curitiba", "recife", "city"),
    "dream": ("sonho", "sonhos", "dream", "dreams"),
}
_CONCEPT_INDEX = {w: i for i, words in enumerate(CONCEPTS.values()) for w in words}
_HASH_WEIGHT = 0.3


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", plain_text(text))


class FakeEmbedder:
    """Same surface as the M9 Embedder: refresh/warm/unload/query/documents, plus test knobs."""

    def __init__(self, model: str = "embeddinggemma", status: str = "ready", dim: int = 32) -> None:
        self.model = model
        self.status = status
        self.dim = dim
        self.calls: list[tuple[str, int, str]] = []
        self.delay = 0.0
        self.fail = False

    # ---- helpers -------------------------------------------------------
    def _record(self, method: str, n: int) -> None:
        self.calls.append((method, n, threading.current_thread().name))

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float64)
        span = self.dim - len(CONCEPTS)
        for tok in _tokens(text):
            idx = _CONCEPT_INDEX.get(tok)
            if idx is not None:
                v[idx] += 1.0
            else:
                v[len(CONCEPTS) + zlib.crc32(tok.encode("utf-8")) % span] += _HASH_WEIGHT
        n = float(np.linalg.norm(v))
        if n == 0.0:
            # Text with nothing recognisable: a fixed "noise" vector, unrelated to every concept.
            v = np.full(self.dim, 1.0)
            n = float(np.linalg.norm(v))
        return v / n

    def _sleep(self) -> None:
        if self.delay:
            time.sleep(self.delay)

    # ---- Embedder surface ---------------------------------------------
    def refresh(self) -> str:
        self._record("refresh", 0)
        return self.status

    def warm(self) -> bool:
        self._record("warm", 0)
        if self.status == "cold":
            self.status = "ready"
        return self.status == "ready"

    def unload(self) -> None:
        self._record("unload", 0)
        if self.status == "ready":
            self.status = "cold"

    def query(self, text: str) -> np.ndarray | None:
        if self.status != "ready":
            return None
        self._record("query", 1)
        self._sleep()
        if self.fail:
            raise RuntimeError("fake embedder failure")
        return self._vec(text)

    def documents(self, texts: list[str]) -> list[np.ndarray] | None:
        if self.status != "ready":
            return None
        self._record("documents", len(texts))
        self._sleep()
        if self.fail:
            raise RuntimeError("fake embedder failure")
        return [self._vec(t) for t in texts]
