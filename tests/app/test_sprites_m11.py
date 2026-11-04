"""M11 creature art: the M6 invariants re-expressed for the family/plan generator, plus the M11 rules
(family and plan fixed for life, constant palette, accumulating accessories, family eggs, draw budget)."""
import time
from dataclasses import replace

import numpy as np
import pygame
import pytest

from engrama.app.art import sprites, vpet
from engrama.app.art.sprites import ANIMS, SIZES, Look, frames
from engrama.app.art.vpet import anim as vanim
from engrama.app.art.vpet import gen as vgen
from engrama.app.art.vpet.core import BODY, Builder
from engrama.app.art.vpet.families import FAMILY_FN
from engrama.app.art.vpet.genes import genes, persona
from engrama.app.desktop import COLORKEY
from engrama.kernel.genome import Genome
from engrama.vocab import BRANCHES

STAGES = ("baby", "child", "adult", "perfect", "final")
M7_ANIMS = ("jump", "dance", "yawn", "dig")
PAIRS = [(st, br) for st, brs in BRANCHES.items() for br in brs]
FULL = ("curioso", "explorador", "sabio", "mestre")


@pytest.fixture(autouse=True, scope="module")
def _pg():
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    yield


def look(seed: int, **kw) -> Look:
    return replace(Look.from_dict(Genome.from_seed(seed).to_dict()), **kw)


BASE = look(5)


def raw(s):
    return pygame.image.tobytes(s, "RGBA")


def area(s):
    return int((pygame.surfarray.array_alpha(s) > 0).sum())


def mean_value(s):
    a = pygame.surfarray.array3d(s).reshape(-1, 3)
    al = pygame.surfarray.array_alpha(s).reshape(-1)
    return float(a[al > 0].max(axis=1).mean())


def seed_of(family, plan):
    return next(s for s in range(1, 3000) if vpet.family_of(s) == family and vpet.plan_of(s) == plan)


# ---- M6 invariants -------------------------------------------------------------------------------------------


def test_sizes():
    assert SIZES == {"egg": 16, "baby": 24, "child": 32, "adult": 40, "perfect": 44, "final": 48}
    for a in ("evolve", "old", "dead"):
        assert a in ANIMS


@pytest.mark.parametrize("family", vpet.FAMILIES)
def test_every_family_plan_stage_and_anim_draws(family):
    for plan in range(3):
        seed = seed_of(family, plan)
        for stage in STAGES:
            sp = vgen.sprite(seed, stage, lineage=FULL, family=family, plan=plan)
            assert (sp.family, sp.plan) == (family, plan)
            n = SIZES[stage]
            for an in ANIMS + M7_ANIMS:
                fr = vanim.frame_arrays(sp, an)
                assert 2 <= len(fr) <= 4
                for a in fr:
                    assert a.shape == (n, n, 4)
                    assert int((a[:, :, 3] > 0).sum()) > n * 2, (family, plan, stage, an)


@pytest.mark.parametrize("stage,branch", PAIRS)
def test_each_branch_draws(stage, branch):
    lk = replace(BASE, branch=branch, lineage=("brincalhao",))
    for an in ANIMS:
        fr = frames(lk, stage, an)
        assert 2 <= len(fr) <= 4
        for f in fr:
            assert f.get_size() == (SIZES[stage],) * 2
            assert area(f) > 0


def test_stages_without_branch_all_anims():
    for st in SIZES:
        for an in ANIMS:
            assert 2 <= len(frames(BASE, st, an)) <= 4


@pytest.mark.parametrize("stage", ["child", "adult", "perfect", "final"])
def test_branches_differ(stage):
    imgs = {br: raw(frames(replace(BASE, branch=br), stage, "idle")[0]) for br in BRANCHES[stage]}
    imgs["base"] = raw(frames(BASE, stage, "idle")[0])
    assert len(set(imgs.values())) == len(imgs)


def red_pixels(s):
    a = pygame.surfarray.array3d(s).reshape(-1, 3).astype(int)
    al = pygame.surfarray.array_alpha(s).reshape(-1)
    return int(((a[:, 0] > 200) & (a[:, 1] < 70) & (a[:, 2] < 80) & (al > 0)).sum())


def test_neglect_branch_has_red_eyes_and_keeps_the_palette():
    comp = frames(replace(BASE, branch="companheiro"), "adult", "idle")[0]
    somb = frames(replace(BASE, branch="sombrio"), "adult", "idle")[0]
    assert red_pixels(somb) > red_pixels(comp)
    body = tuple(int(c) for c in genes(BASE.seed, BASE.palette[1])["pal"][BODY][1])
    for s in (comp, somb):
        cols = {tuple(c) for c in pygame.surfarray.array3d(s).reshape(-1, 3)}
        assert body in cols


def test_unknown_branch_falls_back():
    a = frames(replace(BASE, branch="futuro_x", lineage=("zzz",)), "adult", "idle")
    b = frames(BASE, "adult", "idle")
    assert [raw(x) for x in a] == [raw(x) for x in b]
    # a branch of a later stage does not apply either
    assert raw(frames(replace(BASE, branch="lendario"), "adult", "idle")[0]) == raw(b[0])


def test_look_from_old_dict():
    lk = Look.from_dict({"seed": 3, "body": 1})
    assert lk.branch == "base" and lk.lineage == ()
    lk = Look.from_dict({"branch": "artista", "lineage": ["curioso", "artista"]})
    assert lk.branch == "artista" and lk.lineage == ("curioso", "artista")
    assert Look.from_dict({"lineage": 5}).lineage == ()


def test_old_save_genome_renders_every_stage():
    d = Genome.from_seed(11).to_dict()
    d.pop("branch", None)
    lk = Look.from_dict(d)
    for st in SIZES:
        assert area(frames(lk, st, "idle")[0]) > 0


def test_cache_key_has_seed_stage_lineage_anim():
    sprites._cache.clear()
    frames(replace(BASE, branch="artista", lineage=("curioso",)), "adult", "walk")
    (key,) = list(sprites._cache)
    assert BASE.seed in key and "adult" in key and "walk" in key and ("curioso", "artista") in key


def test_cache_bounded():
    sprites._cache.clear()
    for s in range(sprites._CACHE_MAX + 20):
        frames(replace(BASE, seed=s), "baby", "idle")
    assert len(sprites._cache) <= sprites._CACHE_MAX <= 400
    assert len(vpet._SPRITES) <= vpet._SPRITES_MAX


def test_deterministic_and_later_branches_never_apply():
    lin = ("curioso", "tecnico", "virtuoso", "mestre")
    for seed in (2, 9, 31):
        for st in STAGES:
            a = vgen.sprite(seed, st, lineage=lin, hue_rgb=(200, 80, 90)).body
            b = vgen.sprite(seed, st, lineage=lin, hue_rgb=(200, 80, 90)).body
            assert (a == b).all()
        adult = vgen.sprite(seed, "adult", lineage=lin[:2]).body
        assert (adult == vgen.sprite(seed, "adult", lineage=lin).body).all()


def test_evolve_brightens_and_dead_fades():
    ev = [mean_value(f) for f in frames(BASE, "adult", "evolve")]
    assert ev == sorted(ev) and ev[-1] > ev[0]
    d = frames(BASE, "adult", "dead")
    assert pygame.surfarray.array_alpha(d[1]).max() < pygame.surfarray.array_alpha(d[0]).max()


def test_anim_frames_differ():
    for an in ("walk", "eat", "sleep", "happy", "sad", "sick", "old"):
        fr = frames(BASE, "adult", an)
        assert len({raw(f) for f in fr}) >= 2, an
    assert raw(frames(BASE, "adult", "sick")[0]) != raw(frames(BASE, "adult", "idle")[0])


def test_eyes_visible_in_every_idle():
    for seed in range(1, 41):
        lk = look(seed)
        for stage in STAGES:
            sp = vpet.build_sprite(lk, stage)
            idle = vpet.creature_frames(lk, stage, "idle")[0]
            diff = np.abs(idle[:, :, :3].astype(int) - sp.body[:, :, :3].astype(int)).sum(axis=2) > 90
            assert int((diff & (sp.body[:, :, 3] > 0)).sum()) >= 4, (seed, stage)
            f = sp.face
            left_end, right_start = f["ex0"] + f["w"] - 1, f["axis"] - (f["ex0"] + f["w"] - 1)
            assert 0 <= f["ex0"] and left_end + 2 <= right_start and f["axis"] - f["ex0"] < sp.n, (seed, stage)


def test_higher_stages_are_bigger():
    for seed in range(1, 41):
        lk = look(seed)
        a = {st: area(frames(lk, st, "idle")[0]) for st in STAGES}
        assert a["final"] > a["adult"], seed
        assert a["adult"] > a["child"] * 1.1, seed
        assert a["child"] > a["baby"] * 1.1, seed
        assert a["perfect"] > a["adult"] * .9, seed


def test_creature_stays_inside_canvas_with_room_to_hop():
    for seed in range(1, 41):
        for stage in STAGES:
            sp = vpet.build_sprite(look(seed), stage, lineage=FULL)
            ys, xs = np.nonzero(sp.body[:, :, 3] > 0)
            assert ys.max() == sp.n - 1 and ys.min() >= 1 and xs.min() >= 0 and xs.max() <= sp.n - 1, (seed, stage)


def test_no_pixel_uses_the_overlay_colour_key():
    for seed in range(1, 61):
        lk = look(seed, branch="sombra", lineage=("arisco", "sombrio", "rebelde"))
        for st in SIZES:
            for f in frames(lk, st, "idle") + frames(lk, st, "happy"):
                a = pygame.surfarray.array3d(f).reshape(-1, 3)
                al = pygame.surfarray.array_alpha(f).reshape(-1)
                assert not ((a == COLORKEY).all(axis=1) & (al > 0)).any(), (seed, st)


def test_sprite_cost_is_small():
    t0 = time.perf_counter()
    n = 0
    for seed in range(100, 130):
        for stage in STAGES:
            frames(look(seed), stage, "idle")
            n += 1
    assert (time.perf_counter() - t0) / n < 0.03


# ---- M11 rules -----------------------------------------------------------------------------------------------


def test_family_and_plan_fixed_across_stages_and_lineages():
    for seed in range(1, 60):
        seen = {(vgen.sprite(seed, st, lineage=lin).family, vgen.sprite(seed, st, lineage=lin).plan)
                for st in ("baby", "adult", "final") for lin in ((), FULL, ("arisco", "sombrio", "rebelde", "sombra"))}
        assert seen == {(vpet.family_of(seed), vpet.plan_of(seed))}, seed


def test_every_family_and_plan_occurs():
    combos = {(vpet.family_of(s), vpet.plan_of(s)) for s in range(1, 600)}
    assert combos == {(f, p) for f in vpet.FAMILIES for p in range(3)}
    adults = {vpet.family_of(s) for s in range(1, 41)}
    assert len(adults) == 8


def body_colours(s):
    a = pygame.surfarray.array3d(s).reshape(-1, 3)
    al = pygame.surfarray.array_alpha(s).reshape(-1)
    return {tuple(int(x) for x in c) for c in a[al > 0]}


def test_palette_constant_across_stages():
    for seed in range(1, 25):
        lk = look(seed, branch="mestre", lineage=FULL[:3])
        base = tuple(int(c) for c in genes(seed, lk.palette[1])["pal"][BODY][1])
        for st in ("egg",) + STAGES:
            assert base in body_colours(frames(lk, st, "idle")[0]), (seed, st)


def test_egg_takes_the_family_colour_pull():
    for seed in range(1, 30):
        lk = look(seed)
        g = genes(seed, lk.palette[1])
        egg = body_colours(frames(lk, "egg", "idle")[0])
        assert tuple(int(c) for c in g["pal"][BODY][1]) in egg
    # planta pulls toward green: its eggs are greener than their raw genome colour
    greener = 0
    plants = [s for s in range(1, 200) if vpet.family_of(s) == "planta"][:10]
    for seed in plants:
        lk = look(seed)
        c = genes(seed, lk.palette[1])["pal"][BODY][1]
        raw_c = lk.palette[1]
        greener += int(c[1]) - max(int(c[0]), int(c[2])) >= raw_c[1] - max(raw_c[0], raw_c[2])
    assert greener >= 8


def test_egg_crack_levels_and_family_motif():
    lk = look(9)
    shots = [sprites.make_egg_crack(lk, lv) for lv in range(4)]
    assert len({raw(s) for s in shots}) == 4
    motifs = {raw(frames(look(seed_of(f, 0)), "egg", "idle")[0]) for f in vpet.FAMILIES}
    assert len(motifs) == 8


def built(seed, stage, lineage):
    g = genes(seed)
    t = STAGES.index(stage)
    b = Builder()
    d = FAMILY_FN[g["family"]](b, g, persona(seed, lineage), t)
    return vgen.accessories(b, d, lineage, t), d


def test_accessories_accumulate_up_to_three():
    for seed in range(1, 80):
        worn, d = built(seed, "final", FULL)
        assert 1 <= len(worn) <= min(vgen.MAX_ACC, d.acc_max)
        assert worn[0][0] == "mestre"                     # the latest branch always shows
        assert len({slot for _, slot in worn}) == len(worn)
        assert not {slot for _, slot in worn} & set(d.no_slots)
    # an earlier branch's accessory is still there two stages later
    kept = sum(any(b == "curioso" for b, _ in built(s, "perfect", FULL[:3])[0]) for s in range(1, 80))
    assert kept >= 40
    a = frames(look(3, branch="sabio", lineage=("curioso", "explorador")), "perfect", "idle")[0]
    b = frames(look(3, branch="sabio", lineage=("brincalhao", "explorador")), "perfect", "idle")[0]
    assert raw(a) != raw(b)


def test_draw_budget():
    times = []
    for seed in range(1, 41):
        for st in ("adult", "final"):
            t0 = time.perf_counter()
            vgen.sprite(seed, st, lineage=FULL)
            times.append(time.perf_counter() - t0)
    times.sort()
    assert times[len(times) // 2] < 0.010          # median under 10 ms (measured ~5 ms; CI machines vary)
    assert times[-1] < 0.040
