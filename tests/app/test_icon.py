"""App icon (M15 T5): the packaged PNG/ICO exist and are well formed, the generator is deterministic, and a
missing icon file never stops the window."""
import os
import struct
import subprocess
import sys
from pathlib import Path

import pygame

from engrama import resources

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "engrama" / "app" / "assets"
GENERATOR = ROOT / "tools" / "make_icon.py"


def test_assets_exist():
    assert (ASSETS / "icon-256.png").is_file()
    assert (ASSETS / "icon.ico").is_file()
    assert resources.assets_dir() == ASSETS


def test_png_is_256_square_with_transparent_background_and_content():
    img = pygame.image.load(str(ASSETS / "icon-256.png"))
    assert img.get_size() == (256, 256)
    assert img.get_at((0, 0)).a == 0 and img.get_at((255, 255)).a == 0
    opaque = sum(1 for x in range(256) for y in range(256) if img.get_at((x, y)).a == 255)
    assert opaque > 1000


def test_ico_header_declares_the_four_sizes():
    data = (ASSETS / "icon.ico").read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind, count) == (0, 1, 4)
    sizes = set()
    for i in range(count):
        w, h, _colors, _res, _planes, bpp, size, offset = struct.unpack("<BBBBHHII", data[6 + 16 * i:22 + 16 * i])
        sizes.add(w or 256)
        assert w == h or (w == 0 and h == 0)
        assert bpp == 32 and offset + size <= len(data)
        assert data[offset:offset + 8] == b"\x89PNG\r\n\x1a\n"
    assert sizes == {16, 32, 48, 256}


def test_generator_is_deterministic(tmp_path):
    env = dict(os.environ, SDL_VIDEODRIVER="dummy")
    outs = []
    for name in ("a", "b"):
        out = tmp_path / name
        subprocess.run([sys.executable, str(GENERATOR), str(out)], check=True, env=env, cwd=ROOT,
                       capture_output=True, timeout=240)
        outs.append(out)
    for fname in ("icon-256.png", "icon.ico"):
        assert (outs[0] / fname).read_bytes() == (outs[1] / fname).read_bytes()
    # the committed files are what the generator makes today
    assert (outs[0] / "icon.ico").read_bytes() == (ASSETS / "icon.ico").read_bytes()


def test_missing_icon_never_crashes_the_window(monkeypatch, tmp_path):
    from engrama.app.ui import window
    monkeypatch.setattr(window, "assets_dir", lambda: tmp_path / "nope")
    window._set_app_icon()     # no exception
