"""Simulated users: Poisson behaviour driven by a Profile."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from engrama import balance as B
from engrama.kernel.sensors import Obs
from engrama.vocab import FOOD_IDS


@dataclass(frozen=True)
class Profile:
    name: str
    active_hours: tuple[int, int]
    answer_prob: float
    pet_per_h: float
    feed_when_fome: float
    msgs_per_h: float
    msg_valence: float
    apps: tuple[str, ...]
    fullscreen_per_day: float


PROFILES: dict[str, Profile] = {p.name: p for p in (
    Profile("attentive", (8, 22), 0.8, 3.0, 0.6, 1.0, 0.5, ("editor", "browser", "terminal"), 1.0),
    Profile("absent", (18, 21), 0.1, 0.2, 0.9, 0.05, 0.0, ("browser",), 0.5),
    Profile("night_owl", (20, 4), 0.5, 1.5, 0.7, 0.5, 0.3, ("editor", "terminal", "chat"), 1.0),
    Profile("gamer", (14, 2), 0.3, 0.5, 0.8, 0.2, 0.1, ("game", "chat", "browser"), 4.0),
)}

_EGG_CLICKS_PER_H = 30.0
_APP_FOCUS_PER_H = 2.0


class SimUser:
    def __init__(self, profile: Profile, rng: np.random.Generator) -> None:
        self.profile, self.rng = profile, rng
        self._active = False  # matches the kernel default
        self._ask_decided = float("-inf")
        self._answer_at: float | None = None
        self._fs_off: float | None = None

    def _is_active(self, t: float) -> bool:
        h = (t / B.HOUR) % 24.0
        a, b = self.profile.active_hours
        return a <= h < b if a < b else (h >= a or h < b)

    def _poisson(self, per_h: float, dt: float) -> int:
        return int(self.rng.poisson(per_h * dt / B.HOUR)) if per_h > 0 else 0

    def events(self, t: float, dt: float, creature: dict) -> list[Obs]:
        p, rng = self.profile, self.rng
        out: list[Obs] = []
        active = self._is_active(t)
        if active != self._active:
            out.append(Obs(t, "user_active" if active else "user_idle"))
            self._active = active
        if self._fs_off is not None and t >= self._fs_off:
            out.append(Obs(t, "fullscreen_off")); self._fs_off = None
        if self._answer_at is not None and t >= self._answer_at:
            out.append(Obs(min(t, self._answer_at + B.ASK_ANSWER_WINDOW * 0.5), "answered"))
            self._answer_at = None
        if creature.get("action") == "ask_attention" and t - self._ask_decided >= B.ASK_ANSWER_WINDOW:
            self._ask_decided = t
            if active and rng.random() < p.answer_prob:
                self._answer_at = t + float(rng.uniform(5.0, B.ASK_ANSWER_WINDOW * 0.4))
        if not active:
            return out
        if creature.get("stage") == "egg":
            out.extend(Obs(t, "click") for _ in range(self._poisson(_EGG_CLICKS_PER_H, dt)))
        out.extend(Obs(t, "pet") for _ in range(self._poisson(p.pet_per_h, dt)))
        for _ in range(self._poisson(p.msgs_per_h, dt)):
            v = float(np.clip(rng.normal(p.msg_valence, 0.3), -1.0, 1.0))
            out.append(Obs(t, "message", {"valence": v}))
        if creature.get("needs", {}).get("fome", 0.0) >= p.feed_when_fome * 100.0:
            out.append(Obs(t, "food", {"food": FOOD_IDS[int(rng.integers(len(FOOD_IDS)))]}))
        for _ in range(self._poisson(_APP_FOCUS_PER_H, dt)):
            app = p.apps[int(rng.integers(len(p.apps)))]
            out.append(Obs(t, "app_focus", {"app": app, "category": app}))
        if self._fs_off is None and self._poisson(p.fullscreen_per_day / 24.0, dt):
            out.append(Obs(t, "fullscreen_on"))
            self._fs_off = t + float(rng.uniform(600.0, 3600.0))
        return out

    def state_dict(self) -> dict:
        return {"profile": self.profile.name, "rng": self.rng.bit_generator.state, "active": self._active,
                "ask_decided": None if self._ask_decided == float("-inf") else self._ask_decided,
                "answer_at": self._answer_at, "fs_off": self._fs_off}

    @classmethod
    def from_state_dict(cls, d: dict) -> "SimUser":
        from engrama.services.persistence import rng_from_state
        u = cls(PROFILES[d["profile"]], rng_from_state(d["rng"]))
        u._active = d["active"]
        u._ask_decided = float("-inf") if d["ask_decided"] is None else float(d["ask_decided"])
        u._answer_at, u._fs_off = d["answer_at"], d["fs_off"]
        return u
