"""Automatic rest triggers: fullscreen app, a heavy PC, low free RAM, long user idleness, or a manual override."""
from __future__ import annotations
import math
from typing import Callable
from engrama import balance as B


def system_ram_free_mb() -> float:
    try:
        import psutil
        return psutil.virtual_memory().available / 2 ** 20
    except Exception:
        return math.inf


class RestPolicy:
    def __init__(self, now_fn: Callable[[], float], ram_free_mb_fn: Callable[[], float] = system_ram_free_mb) -> None:
        self._now = now_fn
        self._ram = ram_free_mb_fn
        self.manual = False

    def update(self, fullscreen: bool, last_input_wall: float, heavy_pc: bool = False) -> str | None:
        """Reason the creature should rest right now, or None. Manual wins; rest ends when triggers clear."""
        if self.manual:
            return "manual"
        if fullscreen:
            return "fullscreen"
        if heavy_pc:
            return "heavy_pc"
        try:
            ram = float(self._ram())
        except Exception:
            ram = math.inf
        if ram < B.REST_RAM_FREE_MB:
            return "low_ram"
        if self._now() - last_input_wall >= B.REST_IDLE_S:
            return "idle"
        return None
