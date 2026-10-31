from engrama.kernel.foods import FOODS
from engrama.vocab import FOOD_IDS


def test_foods_min_stage():
    assert len(FOODS) == 10
    assert FOODS["ram"].min_stage == "child" and FOODS["ram"].digital
    assert FOODS["ram"].effects == {"fome": -15, "sono": -10}
    assert all(f.min_stage == "baby" for f in FOODS.values() if f.digital and f.id != "ram")
    assert all(f.min_stage for f in FOODS.values())


def test_food_ids_match_vocab():
    assert tuple(FOODS) == FOOD_IDS
