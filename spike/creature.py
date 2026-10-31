"""Creature state: needs (0-100 'urges'; higher = more wanting), traits, movement."""
import math
import random

NEEDS = ["fome", "sono", "tedio", "carinho", "curiosidade"]
LABELS = {"fome": "FOME", "sono": "SONO", "tedio": "TEDIO", "carinho": "CARINHO", "curiosidade": "CURIOS"}
DEFAULT_TRAITS = {"curiosidade": 50, "sociabilidade": 40, "paciencia": 70, "independencia": 30, "criatividade": 50}
TRAIT_PT = {"curiosidade": "curiosidade", "sociabilidade": "sociabilidade", "paciencia": "paciência",
            "independencia": "independência", "criatividade": "criatividade"}
# urge growth per second (fast on purpose, so a spike session shows things happening)
RATE = {"fome": 0.5, "sono": 0.3, "tedio": 0.7, "carinho": 0.5, "curiosidade": 0.45}
WORLD_W, WORLD_H = 96, 68
SPEED = {"idle": 0, "wander": 9, "play_alone": 14, "sleep": 0, "ask_attention": 7, "explore": 18}


class Creature:
    def __init__(self, seed=None):
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.traits = dict(DEFAULT_TRAITS)
        self.needs = {"fome": 20.0, "sono": 10.0, "tedio": 20.0, "carinho": 30.0, "curiosidade": 30.0}
        self.stage = "egg"
        self.egg_t = 0.0
        self.egg_clicks = 0
        self.x, self.y, self.tx, self.ty = 48.0, 46.0, 48.0, 46.0
        self.behavior = "idle"
        self.sleeping = False
        self.ask_t = None
        self.hop = 0.0
        self.prefs = None  # food -> liking score in [-1, 1]; set up by foods.init_prefs

    def tick_needs(self, dt):
        if self.stage == "egg":
            return
        mult = {k: 1.0 for k in NEEDS}
        if self.sleeping:
            mult.update(fome=0.3, tedio=0.2, carinho=0.5, curiosidade=0.2)
        for k in NEEDS:
            self.needs[k] += RATE[k] * mult[k] * dt
        if self.sleeping:
            self.needs["sono"] -= 3.0 * dt
        if self.behavior == "play_alone":
            self.needs["tedio"] -= 1.6 * dt
        if self.behavior == "explore":
            self.needs["curiosidade"] -= 1.6 * dt
        for k in NEEDS:
            self.needs[k] = max(0.0, min(100.0, self.needs[k]))
        if self.sleeping and self.needs["sono"] <= 5:
            self.sleeping = False

    def change(self, **d):
        for k, v in d.items():
            self.needs[k] = max(0.0, min(100.0, self.needs[k] + v))

    def new_target(self, far=False):
        self.tx = random.uniform(10, WORLD_W - 10)
        self.ty = random.uniform(34, WORLD_H - 8)

    def move(self, dt, behavior):
        sp = SPEED.get(behavior, 0)
        self.hop = 0.0
        if self.sleeping or sp == 0:
            return
        if behavior == "ask_attention":
            self.tx, self.ty = 48 + 10 * math.sin(self.x / 9), 50
        dx, dy = self.tx - self.x, self.ty - self.y
        d = math.hypot(dx, dy)
        if d < 1.5:
            if behavior != "ask_attention":
                self.new_target()
        else:
            step = min(sp * dt, d)
            self.x += dx / d * step
            self.y += dy / d * step
        if behavior in ("play_alone", "ask_attention"):
            self.hop = abs(math.sin(self.x * 0.5 + self.y)) * (4 if behavior == "play_alone" else 2.5)
