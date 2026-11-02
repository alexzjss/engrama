import os, sys, random, time
os.environ["SDL_VIDEODRIVER"] = "dummy"
import numpy as np, pygame
from core import gdict, SIZES
from arch2 import draw, ARCHS, CHILD_OK, BABIES

pygame.init()
OUTDIR = os.path.dirname(os.path.abspath(__file__))
SC = 3
CELL = 48 * SC + 8

CHILD_FROM_BABY = {"blob": ["slime", "plant", "ghost", "stack"], "chick": ["bird", "beast", "dragon"],
                   "ghostlet": ["ghost", "bug", "robot"], "fishling": ["fish", "serpent", "dragon"],
                   "bud": ["plant", "bug", "beast"], "spark": ["beast", "robot", "dragon", "bird"]}
BIAS = {"companheiro": dict(beast=3, winged=3, bird=2, plant=2, slime=2, stack=1, knight=1),
        "sombrio": dict(winged=3, dragon=3, ghost=2, golem=2, bug=2, serpent=2, beast=1),
        "lendario": dict(winged=3, dragon=3, knight=3, bird=2, beast=1, serpent=1),
        "artista": dict(bird=3, plant=2, ghost=2, fish=2, winged=1),
        "tecnico": dict(robot=4, golem=2, bug=2, knight=2, dragon=1),
        "base": {}}


def surf(arr):
    N = arr.shape[0]
    s = pygame.image.frombuffer(arr.tobytes(), (N, N), "RGBA")
    return s


def plan(seed, branch):
    r = random.Random(seed * 7 + 3)
    baby = BABIES[seed % len(BABIES)]
    child = r.choice(CHILD_FROM_BABY[baby]); line = [(baby, "baby"), (child, "child")]
    prev = child; out = []
    for stage in ("adult", "perfect", "final"):
        w = {a: (3 if a == prev else 1) * BIAS[branch].get(a, 1) for a in ARCHS}
        if stage == "adult": w[prev] *= 1  # allow same line
        keys = list(w); ws = [w[k] for k in keys]
        nxt = r.choices(keys, ws)[0]
        # force visible change at evolution
        if nxt == prev and r.random() < .6:
            ws2 = [w[k] if k != prev else 0 for k in keys]; nxt = r.choices(keys, ws2)[0]
        out.append(nxt); prev = nxt
    return baby, child, out


def sprite(seed, t, arch, branch, baby=None, pose=None):
    g = gdict(seed, branch)
    br = branch if t >= 2 else "base"
    return draw(g, t, arch, br, baby_kind=baby, pose=pose)


def seed_for(pose, start=1):
    sd = start
    while gdict(sd)['pose'] != pose: sd += 1
    return sd


def blit_cell(canvas, arr, cx, by):
    s = pygame.transform.scale(surf(arr), (arr.shape[1] * SC, arr.shape[0] * SC))
    canvas.blit(s, (cx - s.get_width() // 2, by - s.get_height()))


def make_sheet(path):
    ents = []
    rr = random.Random(5)
    brs = ["base", "companheiro", "sombrio", "lendario", "artista", "tecnico"]
    for i, b in enumerate(BABIES): ents.append((10 + i, 0, None, "base", b))
    for i, a in enumerate(CHILD_OK[:10]): ents.append((seed_for(i % 4, 100 + i * 7), 1, a, "base", None))
    for i, a in enumerate(ARCHS): ents.append((seed_for((i + i // 4) % 4, 300 + i * 11), 2, a, brs[i % 6], None))
    for i, a in enumerate(["dragon", "knight", "winged", "beast", "robot", "bird", "golem", "bug", "serpent"]):
        ents.append((seed_for((i * 3 + 1) % 4, 500 + i * 13), 3, a, brs[(i + 2) % 6], None))
    for i, a in enumerate(["winged", "dragon", "knight", "golem", "bird", "beast", "robot", "slime", "ghost"]):
        ents.append((seed_for((i * 5 + 2) % 4, 700 + i * 17), 4, a, brs[(i + 3) % 6], None))
    cols = 8; rows = (len(ents) + cols - 1) // cols
    W = cols * CELL; H = rows * CELL
    cv = pygame.Surface((W, H)); cv.fill((255, 255, 255))
    t0 = time.perf_counter(); n = 0
    for i, (sd, t, a, b, bk) in enumerate(ents):
        arr = sprite(sd, t, a, b, bk); n += 1
        cx = (i % cols) * CELL + CELL // 2; by = (i // cols) * CELL + CELL - 4
        blit_cell(cv, arr, cx, by)
    print("sheet: %d sprites, %.1f ms avg" % (n, (time.perf_counter() - t0) / n * 1000))
    pygame.image.save(cv, path)


def make_lines(path):
    seeds = [(3, "companheiro"), (11, "sombrio"), (6, "lendario"), (14, "tecnico")]
    cv = pygame.Surface((5 * CELL, 4 * CELL)); cv.fill((255, 255, 255))
    for row, (sd, br) in enumerate(seeds):
        baby, child, rest = plan(sd, br)
        seq = [(baby, 0, baby), (child, 1, None)] + [(a, 2 + i, None) for i, a in enumerate(rest)]
        for col, (a, t, bk) in enumerate(seq):
            arr = sprite(sd, t, a, br, bk)
            blit_cell(cv, arr, col * CELL + CELL // 2, row * CELL + CELL - 4)
        print(sd, br, [s[0] for s in seq])
    pygame.image.save(cv, path)


def make_poses(path):
    archs = ["dragon", "beast", "robot", "bird"]
    cv = pygame.Surface((6 * CELL, 4 * CELL)); cv.fill((255, 255, 255))
    for r, a in enumerate(archs):
        seeds = []; st = 900 + r * 50
        for want in (0, 1, 2, 3, 1, 2):
            sd = seed_for(want, st); seeds.append(sd); st = sd + 1
        for col, sd in enumerate(seeds):
            arr = sprite(sd, 2, a, "base")
            blit_cell(cv, arr, col * CELL + CELL // 2, r * CELL + CELL - 4)
    pygame.image.save(cv, path)


if __name__ == "__main__":
    make_sheet(os.path.join(OUTDIR, "vpet_sheet.png"))
    make_lines(os.path.join(OUTDIR, "vpet_lines.png"))
    make_poses(os.path.join(OUTDIR, "vpet_poses.png"))


