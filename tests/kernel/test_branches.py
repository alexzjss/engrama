import itertools

import pytest

from engrama.kernel.branches import (
    BRANCH_NAMES,
    BranchContext,
    branch_name,
    derive_seed,
    pick_branch,
)
from engrama.vocab import BRANCHES, INTEREST_KEYS, NEGLECT_BRANCHES, TRAIT_KEYS

MID = tuple(0.5 for _ in TRAIT_KEYS)
NO_INT = {k: 0.0 for k in INTEREST_KEYS}


def ctx(stage="adult", care=0.8, stage_care=0.8, life=0.8, traits=MID, interests=None, lineage=()):
    return BranchContext(stage, care, stage_care, life, tuple(traits), dict(interests or NO_INT), tuple(lineage))


def traits_with(**kw):
    t = {k: 0.5 for k in TRAIT_KEYS}
    t.update(kw)
    return tuple(t[k] for k in TRAIT_KEYS)


def interest(**kw):
    d = dict(NO_INT)
    d.update(kw)
    return d


@pytest.mark.parametrize("stage", list(BRANCHES))
def test_neglect_wins_when_care_low(stage):
    got = pick_branch(ctx(stage=stage, stage_care=0.2, life=0.9, traits=traits_with(sociabilidade=1.0)), 1)
    assert got in NEGLECT_BRANCHES and got in BRANCHES[stage]


def test_redemption_leaves_neglect():
    c = ctx(stage="perfect", stage_care=0.85, lineage=("arisco", "sombrio"))
    assert pick_branch(c, 1) not in NEGLECT_BRANCHES
    c2 = ctx(stage="perfect", stage_care=0.3, lineage=("arisco", "sombrio"))
    assert pick_branch(c2, 1) == "rebelde"


def test_social_child_is_playful():
    c = ctx(stage="child", traits=traits_with(sociabilidade=0.95))
    assert pick_branch(c, 1) == "brincalhao"


def test_art_interest_pulls_artist():
    assert pick_branch(ctx(interests=interest(arte=0.8, social=0.2)), 1) == "artista"


def test_tech_interest_pulls_tinkerer():
    assert pick_branch(ctx(interests=interest(tecnologia=0.8, trabalho=0.2)), 1) == "tecnico"


def test_games_interest_pulls_adventurer():
    c = ctx(stage="perfect", interests=interest(jogos=1.0))
    assert pick_branch(c, 1) == "aventureiro"


def test_legendary_needs_life_care():
    hi = ctx(stage="final", life=0.9, stage_care=0.9)
    lo = ctx(stage="final", life=0.7, stage_care=0.9)
    assert pick_branch(hi, 1) == "lendario"
    assert pick_branch(lo, 1) != "lendario"


def test_deterministic_and_seed_breaks_ties():
    # symmetric final context: mestre and eco tie at zero signal
    c = ctx(stage="final", life=0.5, stage_care=0.9, traits=MID)
    assert pick_branch(c, 7) == pick_branch(c, 7)
    results = {pick_branch(c, s) for s in range(200)}
    assert len(results) >= 2
    assert results <= {"mestre", "eco"}


def _candidates(stage):
    lineages = [(), ("arisco",), ("sombrio",), ("artista",), ("companheiro",),
                ("brincalhao",), ("sonhador",), ("curioso",), ("explorador",)]
    for stage_care, life, lineage in itertools.product((0.2, 0.6, 0.9), (0.5, 0.9), lineages):
        bases = [MID, tuple(1.0 for _ in TRAIT_KEYS)]
        bases += [tuple(1.0 if j == i else 0.3 for j in range(len(TRAIT_KEYS))) for i in range(len(TRAIT_KEYS))]
        for t in bases:
            yield ctx(stage, 0.8, stage_care, life, t, NO_INT, lineage)
            for k in INTEREST_KEYS:
                yield ctx(stage, 0.8, stage_care, life, t, interest(**{k: 1.0}), lineage)


@pytest.mark.parametrize("stage", list(BRANCHES))
def test_every_branch_reachable(stage):
    found = {pick_branch(c, s) for c in _candidates(stage) for s in (1, 2, 3)}
    assert found == set(BRANCHES[stage])


def test_names_pt_en_complete():
    all_ids = {b for bs in BRANCHES.values() for b in bs}
    assert all_ids <= set(BRANCH_NAMES) and "base" in BRANCH_NAMES
    for b, (pt, en) in BRANCH_NAMES.items():
        assert pt and en
        assert branch_name(b, "pt") == pt and branch_name(b, "en") == en
    assert branch_name("desconhecido", "pt") == BRANCH_NAMES["base"][0]


def test_derive_seed_stable():
    assert derive_seed(1, 2) == derive_seed(1, 2)
    assert derive_seed(1, 2) == EXPECTED
    assert 0 <= derive_seed(1, 2) < 2**31
    assert derive_seed(1, 3) != derive_seed(1, 2)


EXPECTED = 1696718611
