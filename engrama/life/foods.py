"""Foods and per-creature tastes."""
import random
from dataclasses import dataclass, field

from engrama.life.traits import Traits

LIKE_T = 0.35  # score above = likes, below -LIKE_T = dislikes
REFUSE_CHANCE = 0.6


@dataclass(frozen=True)
class Food:
    id: str
    name_pt: str
    name_en: str
    digital: bool
    effects: dict[str, float] = field(default_factory=dict)
    min_stage: str = "baby"


def _f(id, pt, en, digital, fome, fx, min_stage="baby") -> Food:
    return Food(id, pt, en, digital, {"fome": -fome, **fx}, min_stage)


FOODS: dict[str, Food] = {f.id: f for f in (
    _f("carne", "carne", "meat", False, 40, {"carinho": -3}),
    _f("fruta", "fruta", "fruit", False, 28, {"sono": -4, "curiosidade": -2}),
    _f("peixe", "peixe", "fish", False, 36, {"curiosidade": -3}),
    _f("bolinho", "bolinho", "little cake", False, 30, {"carinho": -6, "tedio": -3}),
    _f("pacote", "pacote de dados", "data packet", True, 26, {"curiosidade": -8, "tedio": -4}),
    _f("cookie", "cookie de navegador", "browser cookie", True, 22, {"carinho": -4, "curiosidade": 4}),
    _f("bug", "bug frito", "fried bug", True, 24, {"curiosidade": -12, "tedio": -10, "sono": 4}),
    _f("cache", "cache quentinho", "warm cache", True, 24, {"sono": 12, "carinho": -6}),
    _f("byte", "byte crocante", "crunchy byte", True, 20, {"tedio": -6, "curiosidade": -4}),
    _f("ram", "raminho de RAM", "little RAM stick", True, 15, {"sono": -10}, "child"),
)}


def verdict(score: float) -> str:
    return "like" if score > LIKE_T else "dislike" if score < -LIKE_T else "meh"


class Tastes:
    def __init__(self, seed: int, traits: Traits, scores: dict[str, float] | None = None):
        self.seed = seed
        if scores is not None:
            self.scores = dict(scores)
            return
        t = traits.values
        digi = (t["curiosidade"] - 50) / 100 * 0.6 + (t["criatividade"] - 50) / 100 * 0.3
        real = (t["paciencia"] - 50) / 100 * 0.3 + (t["sociabilidade"] - 50) / 100 * 0.3
        self.scores = {}
        for fid, food in FOODS.items():
            r = random.Random(f"{seed}:{fid}")
            bias = digi if food.digital else real
            self.scores[fid] = round(max(-1.0, min(1.0, r.uniform(-0.7, 0.7) + bias)), 3)

    def eat(self, food_id: str, rng: random.Random) -> tuple[bool, dict[str, float]]:
        v = verdict(self.scores[food_id])
        if v == "dislike" and rng.random() < REFUSE_CHANCE:
            self._shift(food_id, -0.03, rng)  # refusing sours the taste a bit
            return False, {}
        delta = dict(FOODS[food_id].effects)
        if v == "dislike":
            delta["fome"] *= 0.5
        elif v == "like":
            delta["carinho"] = delta.get("carinho", 0.0) - 10
            delta["tedio"] = delta.get("tedio", 0.0) - 5
        self._shift(food_id, 0.0, rng)
        return True, delta

    def _shift(self, food_id: str, extra: float, rng: random.Random) -> None:
        # slight familiarity bonus plus noise
        s = self.scores[food_id] + 0.02 + rng.uniform(-0.08, 0.08) + extra
        self.scores[food_id] = round(max(-1.0, min(1.0, s)), 3)

    def favorites(self, n: int = 2) -> list[str]:
        ranked = sorted(self.scores, key=self.scores.get, reverse=True)
        return [f for f in ranked[:n] if self.scores[f] > LIKE_T]

    def disliked(self, n: int = 2) -> list[str]:
        ranked = sorted(self.scores, key=self.scores.get)
        return [f for f in ranked[:n] if self.scores[f] < -LIKE_T]

    def to_dict(self) -> dict:
        return {"seed": self.seed, "scores": dict(self.scores)}

    @classmethod
    def from_dict(cls, d: dict, traits: Traits) -> "Tastes":
        return cls(d["seed"], traits, d["scores"])
