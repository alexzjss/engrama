"""Genes, family, persona and palette: pure functions of the seed (+ lineage for the lived persona)."""
import colorsys
import hashlib
import random

from .core import palette, _toward, ACC, MARK

FAMILIES = ("draco", "fera", "ave", "inseto", "planta", "espirito", "aquatico", "maquina")
FAMILY_PT = {"draco": "dragão", "fera": "fera", "ave": "ave", "inseto": "inseto", "planta": "planta",
             "espirito": "espírito", "aquatico": "aquático", "maquina": "máquina"}
TRAITS = ("curiosidade", "sociabilidade", "paciencia", "independencia", "criatividade")

# lived persona: each branch in the lineage pushes the traits it rewards (mirrors kernel/branches.py scores)
BRANCH_PUSH = {
    "brincalhao": dict(sociabilidade=.3), "curioso": dict(curiosidade=.3),
    "sonhador": dict(criatividade=.2, paciencia=.2), "arisco": dict(independencia=.3, sociabilidade=-.2),
    "companheiro": dict(sociabilidade=.25), "explorador": dict(curiosidade=.2, independencia=.2),
    "artista": dict(criatividade=.3), "tecnico": dict(curiosidade=.15, paciencia=.15),
    "sombrio": dict(independencia=.3, sociabilidade=-.2),
    "guardiao": dict(paciencia=.25, sociabilidade=.1), "sabio": dict(paciencia=.2, curiosidade=.2),
    "virtuoso": dict(criatividade=.3), "aventureiro": dict(independencia=.25, curiosidade=.1),
    "rebelde": dict(independencia=.35, paciencia=-.2),
    "lendario": dict(curiosidade=.1, sociabilidade=.1, paciencia=.1, independencia=.1, criatividade=.1),
    "mestre": dict(paciencia=.2, independencia=.1), "eco": dict(criatividade=.2, sociabilidade=.1),
    "sombra": dict(independencia=.3, sociabilidade=-.3),
}
NEGLECT = frozenset({"arisco", "sombrio", "rebelde", "sombra"})


def rng(seed, tag):
    h = hashlib.sha256(f"vpet2:{seed}:{tag}".encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def family_of(seed: int) -> str:
    return FAMILIES[rng(seed, "family").randrange(len(FAMILIES))]


def temperament(seed: int) -> dict:
    """Innate persona (0..1 per trait) from the seed; the baby/child look and the palette use this."""
    r = rng(seed, "temper")
    return {k: min(1, max(0, .5 + r.uniform(-.22, .22))) for k in TRAITS}


def persona(seed: int, lineage=(), traits=None) -> dict:
    """Lived persona. `traits` (0..1 or 0..100, kernel TRAIT_KEYS) wins if given; else temperament + lineage pushes."""
    if traits:
        out = {}
        for k in TRAITS:
            v = float(traits.get(k, 50 if max(traits.values(), default=0) > 1 else .5))
            out[k] = min(1, max(0, v / 100 if v > 1 else v))
        return out
    p = temperament(seed)
    for b in lineage or ():
        for k, d in BRANCH_PUSH.get(b, {}).items():
            p[k] = min(1, max(0, p[k] + d))
    return p


def _genome_hue(seed):
    try:
        from engrama.kernel.genome import Genome
        c = Genome.from_seed(seed).palette[1]
        return colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)
    except Exception:
        r = random.Random(seed)
        return r.random(), .6, .9


FAM_COL = {  # family -> (target hue or None, pull, sat mul, val mul)
    "draco": (None, 0, 1.0, 1.0), "fera": (.08, .25, .95, 1.0), "ave": (None, 0, 1.05, 1.0),
    "inseto": (None, 0, 1.0, .96), "planta": (.29, .8, 1.0, .95), "espirito": (.68, .25, .55, 1.0),
    "aquatico": (.53, .35, 1.0, 1.0), "maquina": (.58, .2, .45, .94),
}


def genes(seed: int, hue_rgb=None) -> dict:
    """All visual genes. `hue_rgb` = the genome's main colour (Look.palette[1]) if known."""
    fam = family_of(seed)
    r = rng(seed, "genes")
    if hue_rgb is not None:
        h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in hue_rgb))
    else:
        h, s, v = _genome_hue(seed)
    th, pull, sm, vm = FAM_COL[fam]
    if th is not None:
        h = _toward(h, th, pull)
    tp = temperament(seed)
    # temperament nudges: social -> warmer, independent -> cooler & more saturated, patient -> softer
    h = _toward(h, .06, .10 * max(0, tp["sociabilidade"] - .5) * 2)
    h = _toward(h, .62, .10 * max(0, tp["independencia"] - .5) * 2)
    sat = min(.92, max(.42, (s * .5 + .36) * sm + .25 * (tp["independencia"] - .5) - .2 * (tp["paciencia"] - .5)))
    val = min(.97, max(.78, (v * .4 + .58) * vm))
    mode = r.choice(("comp", "comp", "triad", "split"))
    off = {"comp": .5, "triad": 1 / 3, "split": .42}[mode] * (1 if r.random() < .5 else -1)
    off *= 1 + .25 * (tp["criatividade"] - .5)
    acc_h = (h + off) % 1
    if fam == "planta":           # flowers: warm accents read best on green
        acc_h = r.choice((.97, .9, .08, .13, .78))
    g = dict(seed=seed, family=fam, hue=h, sat=sat, val=val, acc_hue=acc_h,
             eye=r.choice(("gem", "gem", "sclera")),
             mark=r.choice(("none", "stripes", "spots", "mask", "cap", "socks")),
             mark_mat=r.choice((MARK, MARK, ACC)),
             mouth=r.choice(("smile", "smile", "fang", "cat")),
             belly=r.random() < .8,
             f1=r.randrange(4), f2=r.randrange(4), f3=r.randrange(4), f4=r.randrange(4),
             side=1 if r.random() < .5 else -1,
             hy=r.uniform(.86, .96), bodyk=r.uniform(.92, 1.1), limbk=r.uniform(.9, 1.12),
             plan=rng(seed, "plan").randrange(3), eye_pick=r.random())
    g["pal"] = palette(h, sat, val, acc_h)
    return g
