"""README showcase images (deterministic): python -m spike.vpet2.showcase [outdir]

Writes lineages.png, families.png and anims.png (default outdir: docs/images).
Nearest-neighbour upscaled; the sprites are the M11 prototype art, not yet in the app.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

from .gen import STAGES
from .genes import FAMILIES, FAMILY_PT, family_of
from .gen import idle, sprite
from .anim import frame_arrays
from .sheets import BG, demo_lineage, egg, label, surf

LINEAGE_SEEDS = (3, 6, 7, 12, 14, 16)
# one adult per family, picked by eye from the review sheets
FAMILY_SEEDS = {f: next(s for s in range(1, 400) if family_of(s) == f) for f in FAMILIES}
ANIM_SEED = 7
SHOW_ANIMS = ("idle", "happy", "eat", "sleep", "sad")


def lineages(path, seeds=LINEAGE_SEEDS, sc=4):
    font = pygame.font.Font(None, 22)
    cell = 48 * sc + 10
    sheet = pygame.Surface((cell * 6, (cell + 26) * len(seeds)))
    sheet.fill(BG)
    for row, seed in enumerate(seeds):
        lin = demo_lineage(seed)
        y0 = row * (cell + 26)
        label(sheet, font, FAMILY_PT[family_of(seed)], 8, y0 + 12, (160, 160, 185))
        sheet.blit(egg(seed, sc), ((cell - 16 * sc) // 2, y0 + 26 + cell - 6 - 16 * sc))
        for col, st in enumerate(STAGES, start=1):
            im = surf(idle(seed, st, lineage=lin), sc)
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
        sheet.blit(surf(idle(seed, "adult", lineage=demo_lineage(seed)[:1]), sc), (x + 8, y + 22))
    pygame.image.save(sheet, path)


def anims(path, seed=ANIM_SEED, sc=5):
    font = pygame.font.Font(None, 22)
    sp = sprite(seed, "adult", lineage=demo_lineage(seed))
    cell = sp.n * sc + 8
    rows = [(a, frame_arrays(sp, a)) for a in SHOW_ANIMS]
    nf = max(len(f) for _, f in rows)
    sheet = pygame.Surface((70 + cell * nf, cell * len(rows)))
    sheet.fill(BG)
    for r, (name, fr) in enumerate(rows):
        label(sheet, font, name, 6, r * cell + cell // 2)
        for c, a in enumerate(fr):
            sheet.blit(surf(a, sc), (70 + c * cell + 4, r * cell + 4))
    pygame.image.save(sheet, path)


if __name__ == "__main__":
    pygame.init()
    out = sys.argv[1] if len(sys.argv) > 1 else "docs/images"
    os.makedirs(out, exist_ok=True)
    for fn in (lineages, families, anims):
        fn(os.path.join(out, fn.__name__ + ".png"))
