"""README showcase images (deterministic): python -m spike.vpet2.showcase [outdir]

Writes lineages.png, families.png and anims.png (default outdir: docs/images), through the app's public sprite
API (engrama.app.art.sprites.frames), nearest-neighbour upscaled.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

from engrama.app.art import sprites
from engrama.app.art.vpet import FAMILIES, FAMILY_PT, STAGES, family_of
from engrama.kernel.genome import Genome

from .sheets import BG, demo_lineage, label, plan_seeds

LINEAGE_SEEDS = (3, 6, 7, 12, 14, 16)
SHOW_PLAN = dict(draco=2, fera=1, ave=1, inseto=1, planta=1, espirito=2, aquatico=1, maquina=1)
FAMILY_SEEDS = {f: plan_seeds(f)[SHOW_PLAN[f]] for f in FAMILIES}
ANIM_SEED = 7
SHOW_ANIMS = ("idle", "happy", "eat", "sleep", "sad")


def look(seed, lineage=()):
    d = Genome.from_seed(seed).to_dict()
    if lineage:
        d["branch"], d["lineage"] = lineage[-1], list(lineage[:-1])
    return sprites.Look.from_dict(d)


def big(s, sc):
    return pygame.transform.scale(s, (s.get_width() * sc, s.get_height() * sc))


def lineages(path, seeds=LINEAGE_SEEDS, sc=4):
    font = pygame.font.Font(None, 22)
    cell = 48 * sc + 10
    sheet = pygame.Surface((cell * 6, (cell + 26) * len(seeds)))
    sheet.fill(BG)
    for row, seed in enumerate(seeds):
        lk = look(seed, demo_lineage(seed))
        y0 = row * (cell + 26)
        label(sheet, font, FAMILY_PT[family_of(seed)], 8, y0 + 12, (160, 160, 185))
        for col, st in enumerate(("egg",) + STAGES):
            im = big(sprites.frames(lk, st, "idle")[0], sc)
            sheet.blit(im, (col * cell + (cell - im.get_width()) // 2, y0 + 26 + cell - 6 - im.get_height()))
    pygame.image.save(sheet, path)


def families(path, sc=5, cols=4):
    font = pygame.font.Font(None, 24)
    cell = 40 * sc + 16
    rows = (len(FAMILIES) + cols - 1) // cols
    sheet = pygame.Surface((cell * cols, (cell + 22) * rows))
    sheet.fill(BG)
    for i, fam in enumerate(FAMILIES):
        seed = FAMILY_SEEDS[fam]
        x, y = (i % cols) * cell, (i // cols) * (cell + 22)
        label(sheet, font, FAMILY_PT[fam], x + 10, y + 4, (190, 190, 210))
        sheet.blit(big(sprites.frames(look(seed, demo_lineage(seed)[:2]), "adult", "idle")[0], sc), (x + 8, y + 22))
    pygame.image.save(sheet, path)


def anims(path, seed=ANIM_SEED, sc=5):
    font = pygame.font.Font(None, 22)
    lk = look(seed, demo_lineage(seed)[:2])
    cell = 40 * sc + 8
    rows = [(a, sprites.frames(lk, "adult", a)) for a in SHOW_ANIMS]
    nf = max(len(f) for _, f in rows)
    sheet = pygame.Surface((70 + cell * nf, cell * len(rows)))
    sheet.fill(BG)
    for r, (name, fr) in enumerate(rows):
        label(sheet, font, name, 6, r * cell + cell // 2)
        for c, s in enumerate(fr):
            sheet.blit(big(s, sc), (70 + c * cell + 4, r * cell + 4))
    pygame.image.save(sheet, path)


if __name__ == "__main__":
    pygame.init()
    out = sys.argv[1] if len(sys.argv) > 1 else "docs/images"
    os.makedirs(out, exist_ok=True)
    for fn in (lineages, families, anims):
        fn(os.path.join(out, fn.__name__ + ".png"))
