"""Genes and archetype choice. Everything here is a pure function of (seed, stage, lineage); no Genome fields added."""
import colorsys
import hashlib
import random
import zlib

from engrama.vocab import BRANCHES

from .archetypes import ARCHS, BABIES
from .core import PX

STAGE_IDX = {"baby": 0, "child": 1, "adult": 2, "perfect": 3, "final": 4}
STAGE_ORDER = ("baby", "child", "adult", "perfect", "final")

# baby kind -> children it can grow into
CHILD_FROM_BABY = {"blob": ("slime", "plant", "ghost", "stack"), "chick": ("bird", "beast", "dragon"),
                   "ghostlet": ("ghost", "bug", "robot"), "fishling": ("fish", "serpent", "dragon"),
                   "bud": ("plant", "bug", "beast"), "spark": ("beast", "robot", "dragon", "bird")}

# branch id -> archetype weight multipliers (applied to the stage it was chosen at and every later one)
BIAS = {
    "brincalhao": dict(slime=2, beast=2, bird=2, stack=1.5),
    "curioso": dict(bug=2, ghost=2, fish=1.5, plant=1.5),
    "sonhador": dict(ghost=3, fish=2, plant=2, winged=1.5),
    "arisco": dict(bug=2, serpent=2, ghost=1.5, dragon=1.5),
    "companheiro": dict(beast=3, winged=3, bird=2, plant=2, slime=2, stack=1, knight=1),
    "explorador": dict(bird=3, beast=2, winged=2, bug=2, fish=1.5, dragon=1.5),
    "artista": dict(bird=3, plant=2, ghost=2, fish=2, winged=1),
    "tecnico": dict(robot=4, golem=2, bug=2, knight=2, dragon=1),
    "sombrio": dict(winged=3, dragon=3, ghost=2, golem=2, bug=2, serpent=2, beast=1),
    "guardiao": dict(knight=4, golem=3, beast=2, dragon=1.5),
    "sabio": dict(ghost=2.5, bird=2.5, plant=2, winged=2, fish=1.5),
    "virtuoso": dict(bird=3, winged=2, knight=1.5, fish=1.5, ghost=1.5),
    "aventureiro": dict(dragon=2.5, beast=2.5, winged=2, bird=2, serpent=1.5),
    "rebelde": dict(dragon=3, winged=3, golem=2, serpent=2, bug=2),
    "lendario": dict(winged=3, dragon=3, knight=3, bird=2, beast=1, serpent=1),
    "mestre": dict(knight=3, robot=3, golem=2, dragon=2, winged=1.5),
    "eco": dict(ghost=4, fish=2, winged=2, bird=1.5),
    "sombra": dict(winged=3, ghost=3, dragon=2.5, serpent=2.5, golem=1.5),
}
# branch id -> palette/face style (see core.mkpal); ids without art of their own share a style but get a hue nudge
STYLE = {
    "brincalhao": "companheiro", "curioso": "base", "sonhador": "artista", "arisco": "sombrio",
    "companheiro": "companheiro", "explorador": "explorador", "artista": "artista", "tecnico": "tecnico",
    "sombrio": "sombrio", "guardiao": "companheiro", "sabio": "artista", "virtuoso": "artista",
    "aventureiro": "explorador", "rebelde": "sombrio", "lendario": "lendario", "mestre": "tecnico",
    "eco": "artista", "sombra": "sombrio",
}


# mean fraction of the canvas an (archetype, pose) fills once fitted (measured offline); keeps higher stages bigger
FILL = {
    "slime": (.41, .39, .43, .40), "dragon": (.53, .45, .36, .58), "beast": (.49, .51, .40, .44),
    "bird": (.50, .40, .49, .28), "bug": (.51, .52, .39, .44), "plant": (.50, .55, .46, .50),
    "ghost": (.54, .43, .56, .50), "fish": (.47, .45, .53, .30), "knight": (.45, .38, .46, .50),
    "robot": (.48, .47, .47, .47), "golem": (.53, .50, .55, .45), "winged": (.56, .58, .49, .32),
    "stack": (.44, .53, .53, .47), "serpent": (.55, .33, .48, .33),
}
GROWTH = {"adult": 1.15, "perfect": 1.12, "final": 1.12}   # required occupied-area ratio over the previous stage


def pose_of(seed: int) -> int:
    return random.Random("h%d" % seed).randrange(4)


def _area(arch: str, pose: int, stage: str) -> float:
    return FILL[arch][pose] * PX[STAGE_IDX[stage]] ** 2


def branch_at(stage: str, branch: str, lineage) -> str:
    """The branch id that applies at `stage`: the latest one in lineage+[branch] belonging to that stage, else base."""
    pool = BRANCHES.get(stage, ())
    for b in reversed(tuple(lineage or ()) + ((branch,) if branch else ())):
        if b in pool:
            return b
    return "base"


def _rng(seed: int, tag: str) -> random.Random:
    h = hashlib.sha256(f"{seed}:{tag}".encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def baby_kind(seed: int) -> str:
    return BABIES[seed % len(BABIES)]


def archetype(seed: int, stage: str, lineage=(), branch: str = "base") -> str:
    """Archetype (or baby kind) of `stage` for a creature: pure function of (seed, stage, lineage[, branch])."""
    if stage in ("egg", "baby"):
        return baby_kind(seed)
    bk = baby_kind(seed)
    r = _rng(seed, "child")
    prev = r.choice(CHILD_FROM_BABY[bk])
    chosen = [branch_at("child", branch, lineage)]
    if stage == "child":
        return prev
    pose = pose_of(seed)
    prev_st = "child"
    for st in STAGE_ORDER[2:]:
        r = _rng(seed, st)
        chosen.append(branch_at(st, branch, lineage))
        w = {a: (3.0 if a == prev else 1.0) for a in ARCHS}
        for b in chosen:
            for a, m in BIAS.get(b, {}).items():
                w[a] *= m
        need = GROWTH[st] * _area(prev, pose, prev_st)
        for a in ARCHS:     # never let a thin shape make a higher stage look smaller than the one before
            if _area(a, pose, st) < need and a != prev:
                w[a] = 0.0
        keys = list(w)
        nxt = r.choices(keys, [w[k] for k in keys])[0]
        if nxt == prev and r.random() < .6:   # make evolution visible most of the time
            alt = [w[k] if k != prev else 0 for k in keys]
            if sum(alt) > 0:
                nxt = r.choices(keys, alt)[0]
        prev = nxt
        prev_st = st
        if st == stage:
            return prev
    return prev


def genes(look) -> dict:
    """Visual genes: five from the look (kernel genome), the rest derived from the seed."""
    seed = int(getattr(look, "seed", 0))
    r2 = random.Random("h%d" % seed)
    g = dict(seed=seed, body=int(getattr(look, "body", 0)) % 6, eyes=int(getattr(look, "eyes", 0)) % 4,
             ears=int(getattr(look, "ears", 0)) % 5, tail=int(getattr(look, "tail", 0)) % 4,
             pattern=int(getattr(look, "pattern", 0)) % 4)
    pal = getattr(look, "palette", None) or ((40, 30, 60), (240, 140, 120))
    try:
        c = pal[1]
        h, s, v = colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)
    except (TypeError, IndexError, ValueError):
        h, s, v = .02, .6, .9
    r = random.Random("g%d" % seed)
    g["hue"] = h
    g["sat"] = min(.95, max(.68, s + r.uniform(0, .25)))
    g["val"] = min(1.0, max(.86, v))
    g["pose"] = r2.randrange(4); g["hd"] = r2.randrange(4); g["mouth"] = r2.randrange(4)
    g["tex"] = r2.randrange(5); g["accy"] = r2.randrange(4); g["tri"] = r2.random() < .5
    return g


def branch_shift(bid: str) -> float:
    """Small deterministic hue nudge so branches sharing a style still differ."""
    if bid == "base":
        return 0.0
    return ((zlib.crc32(bid.encode()) % 1000) / 1000 - .5) * .12
