"""Review sheets: python -m spike.vpet2.sheets [outdir]"""
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import numpy as np
import pygame

from engrama.app.art.sprites import ANIMS
from .anim import frame_arrays
from .gen import STAGES, SIZES, sprite, idle
from .genes import FAMILIES, FAMILY_PT, TRAITS, family_of, rng

BG = (40, 38, 54)
OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "/home/alex/Documentos/codes/engrama/art-review"


def surf(a, sc):
    n = a.shape[0]
    s = pygame.image.frombuffer(np.ascontiguousarray(a).tobytes(), (n, n), "RGBA")
    return pygame.transform.scale(s, (n * sc, n * sc))


def demo_lineage(seed):
    from engrama.vocab import BRANCHES
    r = rng(seed, "demo-lineage")
    return tuple(r.choice(BRANCHES[st]) for st in ("child", "adult", "perfect", "final"))


def label(sheet, font, text, x, y, col=(220, 220, 235)):
    sheet.blit(font.render(text, True, col), (x, y))


def egg(seed, sc):
    from engrama.app.art import sprites
    from engrama.kernel.genome import Genome
    s = sprites.frames(sprites.Look.from_dict(Genome.from_seed(seed).to_dict()), "egg", "idle")[0]
    return pygame.transform.scale(s, (16 * sc, 16 * sc))


def lineages(path, seeds=range(1, 17), sc=4):
    font = pygame.font.Font(None, 22)
    cell = 48 * sc + 10
    lw = 150
    sheet = pygame.Surface((lw + cell * 6, cell * len(seeds)))
    sheet.fill(BG)
    for row, seed in enumerate(seeds):
        lin = demo_lineage(seed)
        label(sheet, font, f"#{seed} {FAMILY_PT[family_of(seed)]}", 6, row * cell + 8)
        for k, b in enumerate(lin):
            label(sheet, font, b, 10, row * cell + 30 + k * 18, (160, 160, 185))
        sheet.blit(egg(seed, sc), (lw + (cell - 16 * sc) // 2, row * cell + cell - 6 - 16 * sc))
        for col, st in enumerate(STAGES):
            a = idle(seed, st, lineage=lin)
            im = surf(a, sc)
            sheet.blit(im, (lw + (col + 1) * cell + (cell - im.get_width()) // 2, row * cell + cell - 6 - im.get_height()))
    pygame.image.save(sheet, path)


def families(path, sc=6, per=4):
    font = pygame.font.Font(None, 26)
    cell = 40 * sc + 12
    lw = 120
    sheet = pygame.Surface((lw + cell * per, cell * len(FAMILIES)))
    sheet.fill(BG)
    for row, fam in enumerate(FAMILIES):
        seeds = [s for s in range(1, 400) if family_of(s) == fam][:per]
        label(sheet, font, FAMILY_PT[fam], 8, row * cell + cell // 2)
        for col, seed in enumerate(seeds):
            im = surf(idle(seed, "adult", lineage=demo_lineage(seed)[:1]), sc)
            sheet.blit(im, (lw + col * cell + 6, row * cell + 6))
    pygame.image.save(sheet, path)


def personality(path, sc=5):
    font = pygame.font.Font(None, 22)
    seeds = [next(s for s in range(1, 400) if family_of(s) == f) for f in ("draco", "fera", "ave", "maquina")]
    cases = [("neutro", None, ()), ]
    for k in TRAITS:
        tr = {kk: .5 for kk in TRAITS}; tr[k] = 1.0
        cases.append((k[:7] + "+", tr, ()))
    for bset in (("brincalhao",), ("curioso",), ("sonhador",), ("arisco",), ("brincalhao", "companheiro"), ("curioso", "explorador"), ("sonhador", "artista"),
                 ("curioso", "tecnico"), ("arisco", "sombrio"),
                 ("brincalhao", "companheiro", "guardiao"), ("curioso", "explorador", "sabio"),
                 ("sonhador", "artista", "virtuoso"), ("x", "y", "aventureiro"), ("arisco", "sombrio", "rebelde"),
                 ("x", "y", "z", "lendario"), ("x", "y", "z", "mestre"), ("x", "y", "z", "eco"),
                 ("x", "y", "z", "sombra")):
        cases.append((bset[-1], None, bset))
    cell = 48 * sc + 8
    cols = 10
    rows_per = (len(cases) + cols - 1) // cols
    rh = cell + 22
    sheet = pygame.Surface((cell * cols, rh * rows_per * len(seeds) + 30 * len(seeds)))
    sheet.fill(BG)
    for row, seed in enumerate(seeds):
        oy = row * (rh * rows_per + 30)
        label(sheet, font, f"#{seed} {FAMILY_PT[family_of(seed)]}", 4, oy + 6, (255, 230, 150))
        for i, (name, tr, lin) in enumerate(cases):
            st = ("child", "adult", "perfect", "final")[len(lin) - 1] if lin else "adult"
            im = surf(idle(seed, st, lineage=lin, traits=tr), sc)
            x, y = (i % cols) * cell, oy + 30 + (i // cols) * rh
            label(sheet, font, f"{name} ({st[:3]})", x + 4, y + 2)
            sheet.blit(im, (x + (cell - im.get_width()) // 2, y + 22 + cell - 4 - im.get_height()))
    pygame.image.save(sheet, path)


def anims(path, seed=None, sc=5, stage="adult"):
    font = pygame.font.Font(None, 22)
    seed = seed or next(s for s in range(1, 400) if family_of(s) == "fera")
    sp = sprite(seed, stage, lineage=demo_lineage(seed))
    cell = sp.n * sc + 8
    rows = [(a, frame_arrays(sp, a)) for a in ANIMS]
    sheet = pygame.Surface((90 + cell * 4, cell * len(rows)))
    sheet.fill(BG)
    for r, (name, fr) in enumerate(rows):
        label(sheet, font, name, 6, r * cell + cell // 2)
        for c, a in enumerate(fr):
            sheet.blit(surf(a, sc), (90 + c * cell + 4, r * cell + 4))
    pygame.image.save(sheet, path)


def bench():
    t0 = time.perf_counter(); n = 0
    for seed in range(1, 41):
        for st in STAGES:
            sprite(seed, st, lineage=demo_lineage(seed)); n += 1
    return (time.perf_counter() - t0) / n * 1000


if __name__ == "__main__":
    pygame.init()
    os.makedirs(OUT_DIR, exist_ok=True)
    which = sys.argv[2:] or ["lineages", "families", "personality", "anims"]
    for w in which:
        globals()[w](os.path.join(OUT_DIR, w + ".png"))
    print("ms/sprite %.2f" % bench())
