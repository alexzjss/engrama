"""Food catalog."""
from dataclasses import dataclass, field

from engrama.vocab import FOOD_IDS


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

assert tuple(FOODS) == FOOD_IDS
