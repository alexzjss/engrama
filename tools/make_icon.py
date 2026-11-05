"""App icon from the creature sprite (M15): python tools/make_icon.py [outdir]

Renders a fixed seed's baby sprite (the app's own procedural art, through engrama.app.art.sprites.frames),
puts it on a 256x256 transparent canvas with an integer nearest-neighbour scale, and writes:
  icon-256.png  the canvas itself
  icon.ico      multi-size ICO (16, 32, 48, 256); the PNG entries are the canvas, smoothscaled for the small sizes
Default outdir: engrama/app/assets. Deterministic: same code and pygame build give the same bytes.
Needs only pygame-ce (and numpy through the app); no Pillow.
"""
from __future__ import annotations

import io
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from engrama.app.art import sprites  # noqa: E402
from engrama.kernel.genome import Genome  # noqa: E402

SEED = 6          # a baby with a clear silhouette at 16 px (checked by eye against seeds 3, 7, 12)
STAGE = "baby"    # 24 px sprite; the egg (16 px) is too close to a plain blob at icon size
CANVAS = 256
MARGIN = 8        # 24 px * 10 = 240 px, so the scale is an exact integer (no uneven pixel columns)
ICO_SIZES = (16, 32, 48, 256)
DEFAULT_OUT = ROOT / "engrama" / "app" / "assets"


def render_canvas() -> pygame.Surface:
    pygame.display.set_mode((1, 1))
    look = sprites.Look.from_dict(Genome.from_seed(SEED).to_dict())
    sprite = sprites.frames(look, STAGE, "idle")[0]
    k = (CANVAS - 2 * MARGIN) // sprite.get_width()
    big = pygame.transform.scale(sprite, (sprite.get_width() * k, sprite.get_height() * k))
    canvas = pygame.Surface((CANVAS, CANVAS), pygame.SRCALPHA)
    canvas.fill((0, 0, 0, 0))
    canvas.blit(big, big.get_rect(center=(CANVAS // 2, CANVAS // 2)))
    return canvas


def png_bytes(surf: pygame.Surface) -> bytes:
    buf = io.BytesIO()
    pygame.image.save(surf, buf, "icon.png")
    return buf.getvalue()


def ico_bytes(canvas: pygame.Surface) -> bytes:
    entries = []
    for size in ICO_SIZES:
        s = canvas if size == CANVAS else pygame.transform.smoothscale(canvas, (size, size))
        entries.append((size, png_bytes(s)))
    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    directory = b""
    body = b""
    for size, data in entries:
        dim = 0 if size >= 256 else size      # 0 means 256 in the ICO directory
        directory += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        body += data
        offset += len(data)
    return header + directory + body


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    canvas = render_canvas()
    (out / "icon-256.png").write_bytes(png_bytes(canvas))
    (out / "icon.ico").write_bytes(ico_bytes(canvas))
    print(f"wrote {out / 'icon-256.png'} and {out / 'icon.ico'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
