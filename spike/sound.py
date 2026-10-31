"""Procedural chiptune growls (numpy square/noise) played via pygame.sndarray. Silent if audio fails."""
import numpy as np
import pygame

RATE = 22050


class Sound:
    def __init__(self, seed):
        self.ok = False
        self.sounds = {}
        try:
            pygame.mixer.init(frequency=RATE, size=-16, channels=1, buffer=512)
            self.channels = pygame.mixer.get_init()[2]
            self.base = 220 + (seed % 200)  # pitch from creature seed
            self.sounds = {
                "hatch": self._mk(self._growl(0.5, self.base * 0.7, self.base * 1.6, 0.25)),
                "speak": self._mk(self._growl(0.18, self.base * 1.1, self.base * 0.8, 0.15)),
                "ask": self._mk(np.concatenate([self._growl(0.1, self.base * 1.3, self.base * 1.5, 0.05),
                                                self._growl(0.14, self.base * 1.6, self.base * 1.2, 0.05)])),
                "bleh": self._mk(self._growl(0.3, self.base * 0.6, self.base * 0.35, 0.3)),
            }
            self.ok = True
        except Exception as e:  # no audio device etc.
            print("audio off:", e)

    def _growl(self, dur, f0, f1, noise):
        n = int(RATE * dur)
        t = np.arange(n) / RATE
        f = np.linspace(f0, f1, n)
        phase = np.cumsum(f) / RATE
        sq = np.sign(np.sin(2 * np.pi * phase))
        wob = np.sign(np.sin(2 * np.pi * 28 * t))  # growl-ish amplitude chop
        w = sq * (0.75 + 0.25 * wob) + noise * np.random.uniform(-1, 1, n) * 3
        env = np.minimum(1, np.minimum(t / 0.01, (dur - t) / (dur * 0.5)))
        return w * env

    def _mk(self, w):
        a = (np.clip(w, -1, 1) * 0.28 * 32767).astype(np.int16)  # moderate volume
        if self.channels > 1:
            a = np.ascontiguousarray(np.repeat(a[:, None], self.channels, axis=1))
        return pygame.sndarray.make_sound(a)

    def play(self, name):
        if self.ok and name in self.sounds:
            try:
                self.sounds[name].play()
            except Exception:
                pass
