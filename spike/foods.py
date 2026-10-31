"""Foods: tiny procedural pixel icons, hunger/side effects, and per-creature taste preferences."""
import random

import pygame

# char -> color for the 8x8 icon art ('.' = transparent)
PAL = {"r": (200, 60, 60), "R": (140, 30, 40), "o": (230, 150, 60), "y": (240, 220, 90), "g": (90, 190, 90),
       "G": (40, 120, 70), "b": (90, 150, 240), "B": (40, 70, 160), "w": (245, 245, 245), "k": (40, 36, 50),
       "n": (150, 100, 60), "N": (95, 60, 40), "p": (230, 140, 190), "s": (170, 175, 195), "c": (120, 230, 240)}

# id: (nome, kind, fome reduction, side effects (need deltas), 8x8 art)
FOODS = {
    "carne": ("carne", "real", 40, {"carinho": -3}, [
        "........", "..NNNN..", ".NrrrrN.", ".NrRrrN.", ".NrrrRN.", "..NrrN..", "...ww...", "...w...."]),
    "fruta": ("fruta", "real", 28, {"sono": -4, "curiosidade": -2}, [
        "....g...", "...gG...", "..rrrr..", ".rrwrrr.", ".rrrrrr.", ".rrrrRr.", "..rrrR..", "........"]),
    "peixe": ("peixe", "real", 36, {"curiosidade": -3}, [
        "........", "..bbb..b", ".bwkbbbb", "bbbbbbbB", ".bbbbbbb", "..bbb..b", "........", "........"]),
    "bolinho": ("bolinho", "real", 30, {"carinho": -6, "tedio": -3}, [
        "........", "...pp...", "..pppp..", ".pwpwpp.", "..oooo..", ".oooooo.", ".oyoyoo.", "..oooo.."]),
    "pacote": ("pacote de dados", "digital", 26, {"curiosidade": -8, "tedio": -4}, [
        "..cccc..", ".cbbbbc.", "cb0101bc", "cb1010bc", "cb0101bc", "cbbbbbbc", ".cbbbbc.", "..cccc.."]),
    "cookie": ("cookie de navegador", "digital", 22, {"carinho": -4, "curiosidade": +4}, [
        "........", "..nnnn..", ".nNnnNn.", "nnnNnnnn", "nNnnnnNn", "nnnNnnnn", ".nnnNnn.", "..nnnn.."]),
    "bug": ("bug frito", "digital", 24, {"curiosidade": -12, "tedio": -10, "sono": +4}, [
        "g..kk..g", ".g.kk.g.", "..kooK..", "gkoookKg", "..kooK..", ".gkoKg..", "g..kk..g", "........"]),
    "cache": ("cache quentinho", "digital", 24, {"sono": +12, "carinho": -6}, [
        "..r..r..", "...r.r..", "........", ".ssssss.", "sooooooS", "soyyyyoS", "sooooooS", ".SSSSSS."]),
    "byte": ("byte crocante", "digital", 20, {"tedio": -6, "curiosidade": -4}, [
        "........", ".yyyyyy.", "yykkykky", "yykyykky", "yykkykky", "yyykkyyy", ".yyyyyy.", "........"]),
}
ORDER = list(FOODS)
LIKE_T = 0.35  # score above = likes, below -LIKE_T = dislikes

_icons = {}


def icon(fid, scale=1):
    key = (fid, scale)
    if key not in _icons:
        s = pygame.Surface((8, 8), pygame.SRCALPHA)
        for y, row in enumerate(FOODS[fid][4]):
            for x, ch in enumerate(row[:8]):
                col = PAL.get(ch) or ((90, 220, 120) if ch == "1" else (40, 120, 90) if ch == "0" else None)
                if col:
                    s.set_at((x, y), col)
        _icons[key] = pygame.transform.scale(s, (8 * scale, 8 * scale)) if scale != 1 else s
    return _icons[key]


def init_prefs(seed, traits):
    """Deterministic taste from seed + traits: curious creatures lean digital, patient/sociable ones like real food."""
    digi = (traits["curiosidade"] - 50) / 100 * 0.6 + (traits["criatividade"] - 50) / 100 * 0.3
    real = (traits["paciencia"] - 50) / 100 * 0.3 + (traits["sociabilidade"] - 50) / 100 * 0.3
    p = {}
    for fid in ORDER:
        r = random.Random(f"{seed}:{fid}")
        bias = digi if FOODS[fid][1] == "digital" else real
        p[fid] = round(max(-1.0, min(1.0, r.uniform(-0.7, 0.7) + bias)), 3)
    return p


def verdict(score):
    return "like" if score > LIKE_T else "dislike" if score < -LIKE_T else "meh"


def update_pref(prefs, fid, rng=random):
    """Eating shifts the taste a bit: slight familiarity bonus plus noise."""
    prefs[fid] = round(max(-1.0, min(1.0, prefs[fid] + 0.02 + rng.uniform(-0.08, 0.08))), 3)


def taste_summary(prefs):
    ranked = sorted(prefs, key=prefs.get, reverse=True)
    fav = [FOODS[f][0] for f in ranked[:2] if prefs[f] > LIKE_T]
    bad = [FOODS[f][0] for f in ranked[::-1][:2] if prefs[f] < -LIKE_T]
    return fav, bad
