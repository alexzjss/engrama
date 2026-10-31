"""Utility-based behavior selection + epsilon-greedy bandit bias."""
import random
import numpy as np

BEHAVIORS = ["idle", "wander", "play_alone", "sleep", "ask_attention", "explore"]


class Bandit:
    def __init__(self, q=None, eps=0.1, alpha=0.25):
        self.q = q or {b: 0.0 for b in BEHAVIORS}
        self.eps, self.alpha = eps, alpha

    def update(self, b, r):
        self.q[b] += self.alpha * (r - self.q[b])


def utilities(c, group_rate, arousal, bandit):
    n = {k: v / 100 for k, v in c.needs.items()}
    t = {k: v / 100 for k, v in c.traits.items()}
    r = np.clip(np.asarray(group_rate) / 40.0, 0, 1)  # SNN output, normalized
    u = {
        "idle": 0.25 + 0.35 * t["paciencia"] - 0.2 * max(n.values()),
        "wander": 0.20 + 0.35 * t["independencia"] + 0.2 * n["tedio"],
        "play_alone": n["tedio"] * (0.45 + 0.55 * (t["criatividade"] + t["independencia"]) / 2),
        "sleep": 1.4 * n["sono"] ** 3,
        "ask_attention": (0.7 * n["carinho"] + 0.4 * n["tedio"] + 0.4 * n["fome"]) * (0.25 + 0.9 * t["sociabilidade"]) * (1.15 - 0.6 * t["paciencia"]),
        "explore": n["curiosidade"] * (0.35 + 0.9 * t["curiosidade"]),
    }
    mood = arousal - 0.3  # arousal modulates active vs passive behaviors
    for i, b in enumerate(BEHAVIORS):
        u[b] += 0.6 * r[i] + 0.5 * bandit.q[b]
        if b in ("wander", "explore", "play_alone"):
            u[b] += 0.3 * mood
        elif b in ("idle", "sleep"):
            u[b] -= 0.2 * mood
    return u


def choose(c, group_rate, arousal, bandit):
    u = utilities(c, group_rate, arousal, bandit)
    if random.random() < bandit.eps:
        return random.choice(BEHAVIORS), u
    return max(u, key=lambda b: u[b] + random.gauss(0, 0.05)), u
