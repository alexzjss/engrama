"""Golden hashes for the procedural creatures and eggs (M12 T0).

Every frame array that the app can draw for a sample of seeds (one seed per family x body plan), every creature
stage, every animation the app uses, for the base lineage and for a full neglect lineage, plus the family egg.
The SHA-256 of each (bytes, shape, dtype) is stored in tests/fixtures/m12_sprite_hashes.json. Any refactor that
changes a single pixel or the RNG order fails here.

Regenerate (only when a change of drawing is intended): ENGRAMA_REGEN_GOLDEN=1 pytest tests/app/test_sprite_golden.py
"""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest

from engrama.app.art import sprites, vpet
from engrama.app.art.sprites import Look
from engrama.kernel.genome import Genome

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "m12_sprite_hashes.json"

# one seed per (family, plan) combination (8 families x 3 plans = 24); seeds 1..24 alone miss several combos
SEEDS = (1, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 18, 24, 26, 31, 35, 49, 51, 57, 77, 84, 109)
CREATURE_STAGES = tuple(s for s in sprites.SIZES if s != "egg")
ANIMS = tuple(sprites.ANIMS)
NEGLECT = ("sombra", ("arisco", "sombrio"))   # child arisco -> adult sombrio -> final sombra
VARIANTS = {"base": ("base", ()), "neglect": NEGLECT}
EGG_DX = (0, 1, -1)


def _look(seed: int) -> Look:
    lk = Look.from_dict(Genome.from_seed(seed).to_dict())
    assert lk.seed == seed
    return lk


def _digest(frames) -> str:
    h = hashlib.sha256()
    for a in frames:
        a = np.ascontiguousarray(a)
        h.update(f"{a.shape}|{a.dtype.str}|".encode())
        h.update(a.tobytes())
    return h.hexdigest()


def _compute() -> dict[str, str]:
    out: dict[str, str] = {}
    for seed in SEEDS:
        lk = _look(seed)
        for stage in CREATURE_STAGES:
            for vname, (branch, lineage) in VARIANTS.items():
                for anim in ANIMS:
                    frames = vpet.creature_frames(lk, stage, anim, branch, lineage)
                    out[f"{seed}|{stage}|{anim}|{vname}"] = _digest(frames)
        for dx in EGG_DX:
            out[f"{seed}|egg|dx{dx}"] = _digest([vpet.egg_array(lk, dx)])
    return out


def test_seeds_cover_every_family_and_plan():
    combos = {(vpet.family_of(s), vpet.plan_of(s)) for s in SEEDS}
    assert combos == {(f, p) for f in vpet.FAMILIES for p in range(3)}


@pytest.mark.slow
def test_sprite_golden_hashes():
    current = _compute()
    if os.environ.get("ENGRAMA_REGEN_GOLDEN") == "1":
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 1, "seeds": list(SEEDS), "hashes": current}
        FIXTURE.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        pytest.skip(f"golden regenerated: {FIXTURE}")
    stored = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert stored["seeds"] == list(SEEDS)
    expected = stored["hashes"]
    missing = sorted(set(expected) - set(current))
    extra = sorted(set(current) - set(expected))
    assert not missing and not extra, f"keys differ: missing={missing[:5]} extra={extra[:5]}"
    changed = sorted(k for k in expected if expected[k] != current[k])
    assert not changed, f"{len(changed)} golden hashes changed, e.g. {changed[:10]}"
