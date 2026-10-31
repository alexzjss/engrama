"""Procedural chiptune growls (square + noise + pitch sweep) played through pygame.mixer. Silent if audio fails."""
import numpy as np
import pygame

KINDS = ("happy", "ask", "bleh", "hatch", "evolve", "talk")
VOLUME = 0.28


class Growler:
    def __init__(self, sample_rate: int = 22050):
        self.rate = sample_rate
        self.ok = False
        self.muted = False
        self._channels = 1
        self._cache: dict[tuple[int, str], pygame.mixer.Sound] = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=sample_rate, size=-16, channels=1, buffer=512)
            self._channels = pygame.mixer.get_init()[2]
            self.ok = True
        except Exception:
            self.ok = False

    def set_muted(self, muted: bool) -> None:
        self.muted = bool(muted)

    def growl(self, pitch: float, kind: str) -> None:
        if not self.ok or self.muted or kind not in KINDS:
            return
        try:
            key = (int(pitch), kind)
            if key not in self._cache:
                self._cache[key] = self._make(self._wave(float(pitch), kind))
            self._cache[key].play()
        except Exception:
            pass

    def _wave(self, p: float, kind: str) -> np.ndarray:
        g = self._tone
        if kind == "happy":
            return np.concatenate([g(0.08, p * 1.2, p * 1.6, 0.02), g(0.12, p * 1.5, p * 2.0, 0.02)])
        if kind == "ask":
            return np.concatenate([g(0.1, p * 1.3, p * 1.5, 0.05), g(0.14, p * 1.6, p * 1.2, 0.05)])
        if kind == "bleh":
            return g(0.3, p * 0.6, p * 0.35, 0.3)
        if kind == "hatch":
            return g(0.5, p * 0.7, p * 1.6, 0.25)
        if kind == "evolve":
            return np.concatenate([g(0.09, p * m, p * m * 1.05, 0.02) for m in (1.0, 1.25, 1.5, 2.0)])
        return g(0.18, p * 1.1, p * 0.8, 0.15)  # talk

    def _tone(self, dur: float, f0: float, f1: float, noise: float) -> np.ndarray:
        n = int(self.rate * dur)
        t = np.arange(n) / self.rate
        phase = np.cumsum(np.linspace(f0, f1, n)) / self.rate
        square = np.sign(np.sin(2 * np.pi * phase))
        chop = np.sign(np.sin(2 * np.pi * 28 * t))  # growl-ish amplitude chop
        rng = np.random.default_rng(int(f0 * 10) + n)
        wave = square * (0.75 + 0.25 * chop) + noise * rng.uniform(-1, 1, n) * 3
        env = np.minimum(1, np.minimum(t / 0.01, (dur - t) / (dur * 0.5)))
        return wave * env

    def _make(self, wave: np.ndarray) -> pygame.mixer.Sound:
        a = (np.clip(wave, -1, 1) * VOLUME * 32767).astype(np.int16)
        if self._channels > 1:
            a = np.ascontiguousarray(np.repeat(a[:, None], self._channels, axis=1))
        return pygame.sndarray.make_sound(a)
