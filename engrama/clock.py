import time
from typing import Callable


class SimClock:
    def __init__(self, time_scale: float = 1.0, now_fn: Callable[[], float] = time.time):
        self.time_scale = time_scale
        self._now = now_fn
        self._last = now_fn()
        self.sim_time = 0.0

    def set_scale(self, s: float) -> None:
        self.time_scale = s

    def advance(self) -> float:
        now = self._now()
        real_dt = now - self._last
        self._last = now
        dt = min(max(real_dt, 0.0) * self.time_scale, 5 * self.time_scale)
        self.sim_time += dt
        return dt
