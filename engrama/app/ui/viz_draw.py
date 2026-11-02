"""Renderers for module `Viz` specs. Small font, numbers allowed (this is the dev/mind view). Never raises."""
from __future__ import annotations
import collections
import math
from typing import Any, Callable

import pygame

from engrama.app.snapshot import Viz

BG = (24, 26, 32)
FG = (205, 210, 220)
DIM = (110, 116, 130)
ACCENT = (240, 200, 90)
GOOD = (110, 200, 140)
BAD = (220, 100, 100)
BORDER = (60, 64, 76)
_HIST = 60

_fonts: dict[int, Any] = {}
_text_hook: Callable[[str], None] | None = None   # tests set this to capture drawn text


def font(size: int = 11):
    f = _fonts.get(size)
    if f is None:
        if not pygame.font.get_init():
            pygame.font.init()
        try:
            f = pygame.font.SysFont("consolas,dejavusansmono,arial", size)
        except Exception:
            f = pygame.font.Font(None, size + 4)
        _fonts[size] = f
    return f


def draw_text(surface, text: str, pos, color=FG, size: int = 11, clip: pygame.Rect | None = None) -> int:
    """The single text-drawing entry point. Returns the rendered height."""
    text = str(text)
    if _text_hook is not None:
        _text_hook(text)
    try:
        img = font(size).render(text, True, color)
    except Exception:
        return size
    if clip is not None:
        old = surface.get_clip()
        surface.set_clip(clip.clip(old) if old else clip)
        surface.blit(img, pos)
        surface.set_clip(old)
    else:
        surface.blit(img, pos)
    return img.get_height()


class VizState:
    """Per-view history for vector rasters, keyed by title."""
    def __init__(self) -> None:
        self.rows: dict[str, collections.deque] = {}

    def push(self, key: str, row: list[float]) -> list[list[float]]:
        d = self.rows.get(key)
        if d is None or (d and len(d[0]) != len(row)):
            d = self.rows[key] = collections.deque(maxlen=_HIST)
        d.append(row)
        return list(d)


def _finite(x) -> bool:
    if isinstance(x, bool):
        return True
    return isinstance(x, (int, float)) and math.isfinite(x)


def _matrix(data) -> list[list[float]] | None:
    if not isinstance(data, (list, tuple)) or not data:
        return None
    rows = []
    for r in data:
        if not isinstance(r, (list, tuple)) or not r or not all(_finite(v) for v in r):
            return None
        rows.append([float(v) for v in r])
    w = len(rows[0])
    return rows if all(len(r) == w for r in rows) else None


def _vector(data) -> list[float] | None:
    if isinstance(data, (list, tuple)) and data and all(_finite(v) for v in data):
        return [float(v) for v in data]
    return None


def _placeholder(surface, rect, viz) -> None:
    pygame.draw.rect(surface, BORDER, rect, 1)
    draw_text(surface, getattr(viz, "title", "?"), (rect.x + 4, rect.y + 2), DIM, clip=rect)


def _title(surface, rect, viz) -> pygame.Rect:
    draw_text(surface, viz.title, (rect.x + 2, rect.y), DIM, clip=rect)
    return pygame.Rect(rect.x, rect.y + 14, rect.w, max(1, rect.h - 14))


def _grid(surface, body, rows, color_fn) -> None:
    h, w = len(rows), len(rows[0])
    cw, ch = body.w / w, body.h / h
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            c = color_fn(v)
            if c is None:
                continue
            x0, y0 = body.x + int(j * cw), body.y + int(i * ch)
            surface.fill(c, (x0, y0, max(1, int((j + 1) * cw) - int(j * cw)),
                             max(1, int((i + 1) * ch) - int(i * ch))))


def _raster(surface, rect, viz, state) -> bool:
    data = viz.data
    rows = _matrix(data)
    if rows is None:
        vec = _vector(data)
        if vec is None:
            return False
        hist = (state or VizState()).push(viz.title, [1.0 if v else 0.0 for v in vec])
        rows = [list(c) for c in zip(*hist)]   # neurons are rows, time scrolls left to right
    body = _title(surface, rect, viz)
    pygame.draw.rect(surface, (14, 15, 20), body)
    _grid(surface, body, rows, lambda v: ACCENT if v else None)
    return True


def _heatmap(surface, rect, viz, state) -> bool:
    rows = _matrix(viz.data)
    if rows is None:
        return False
    lo = min(min(r) for r in rows)
    hi = max(max(r) for r in rows)
    span = hi - lo
    body = _title(surface, rect, viz)

    def col(v):
        x = 0.5 if span <= 0 else (v - lo) / span
        return (int(30 + 215 * x), int(50 + 140 * x), int(140 - 110 * x))
    _grid(surface, body, rows, col)
    draw_text(surface, f"{lo:.2f}..{hi:.2f}", (rect.right - 80, rect.y), DIM, clip=rect)
    return True


def _series(surface, rect, viz, state) -> bool:
    d = viz.data
    if not isinstance(d, dict):
        return False
    names, rows = d.get("names"), _matrix(d.get("rows"))
    if not isinstance(names, (list, tuple)) or rows is None or len(names) != len(rows[0]):
        return False
    body = _title(surface, rect, viz)
    flat = [v for r in rows for v in r]
    lo, hi = min(flat), max(flat)
    span = (hi - lo) or 1.0
    pal = [ACCENT, GOOD, BAD, (120, 170, 240), (200, 130, 220)]
    n = len(rows)
    for k, name in enumerate(names):
        pts = [(body.x + int(i * (body.w - 1) / max(1, n - 1)),
                body.bottom - 1 - int((rows[i][k] - lo) / span * max(1, body.h - 2))) for i in range(n)]
        c = pal[k % len(pal)]
        if len(pts) > 1:
            pygame.draw.lines(surface, c, False, pts, 1)
        else:
            surface.set_at(pts[0], c)
        draw_text(surface, str(name), (rect.right - 70, rect.y + 14 + 11 * k), c, size=10, clip=rect)
    return True


def _bars(surface, rect, viz, state) -> bool:
    d = viz.data
    if not isinstance(d, dict) or not d or not all(_finite(v) for v in d.values()):
        return False
    body = _title(surface, rect, viz)
    vals = {str(k): float(v) for k, v in d.items()}
    top = max(1.0, max(abs(v) for v in vals.values()))
    neg = min(vals.values()) < 0
    rh = max(8, min(14, body.h // len(vals)))
    labw = min(70, body.w // 3)
    avail = max(4, body.w - labw - 30)
    mid = body.x + labw + (avail // 2 if neg else 0)
    half = max(1, avail // 2 if neg else avail)
    for i, (k, v) in enumerate(vals.items()):
        y = body.y + i * rh
        if y + rh > body.bottom + rh // 2:
            break
        draw_text(surface, k, (body.x + 2, y), FG, size=10, clip=pygame.Rect(body.x, y, labw, rh))
        wpx = int(abs(v) / top * half)
        x0 = mid if v >= 0 else mid - wpx
        pygame.draw.rect(surface, GOOD if v >= 0 else BAD, (x0, y + 1, max(1, wpx), max(1, rh - 3)))
        draw_text(surface, f"{v:.2f}", (mid + (wpx if v >= 0 else 2) + 2, y), DIM, size=10, clip=body)
    return True


def _pad3d(surface, rect, viz, state) -> bool:
    d = viz.data
    if not isinstance(d, dict):
        return False
    pad = _vector(d.get("pad"))
    if pad is None or len(pad) != 3:
        return False
    body = _title(surface, rect, viz)
    side = min(body.w, body.h - 12)
    if side < 8:
        return False
    box = pygame.Rect(body.x + (body.w - side) // 2, body.y, side, side)
    pygame.draw.rect(surface, BORDER, box, 1)
    pygame.draw.line(surface, BORDER, (box.centerx, box.y), (box.centerx, box.bottom))
    pygame.draw.line(surface, BORDER, (box.x, box.centery), (box.right, box.centery))
    p, a, dom = (max(-1.0, min(1.0, v)) for v in pad)
    cx = box.centerx + int(p * (side / 2 - 6))
    cy = box.centery - int(a * (side / 2 - 6))
    pygame.draw.circle(surface, ACCENT, (cx, cy), int(3 + (dom + 1) * 3))
    draw_text(surface, f"{d.get('label', '')}  P{p:+.2f} A{a:+.2f} D{dom:+.2f}",
              (body.x + 2, box.bottom), FG, size=10, clip=body)
    return True


def _table(surface, rect, viz, state) -> bool:
    d = viz.data
    if not isinstance(d, (list, tuple)) or not d:
        return False
    body = _title(surface, rect, viz)
    for i, r in enumerate(d):
        y = body.y + i * 12
        if y > body.bottom - 8:
            break
        cells = r if isinstance(r, (list, tuple)) else [r]
        txt = "  ".join(f"{c:.2f}" if isinstance(c, float) else str(c) for c in cells)
        draw_text(surface, txt, (body.x + 2, y), FG, size=10, clip=body)
    return True


_RENDERERS = {"raster": _raster, "heatmap": _heatmap, "series": _series, "bars": _bars,
              "pad3d": _pad3d, "table": _table}


def draw_viz(surface, rect, viz: Viz, state: VizState | None = None) -> None:
    """Draw one Viz into rect. Unknown kind or invalid data -> placeholder with the title. Never raises."""
    try:
        rect = pygame.Rect(rect)
        if rect.w < 4 or rect.h < 4:
            return
        old = surface.get_clip()
        surface.set_clip(rect.clip(old))
        try:
            fn = _RENDERERS.get(getattr(viz, "kind", None))
            if fn is None or not fn(surface, rect, viz, state):
                _placeholder(surface, rect, viz)
        finally:
            surface.set_clip(old)
    except Exception:
        try:
            _placeholder(surface, pygame.Rect(rect), viz)
        except Exception:
            pass
