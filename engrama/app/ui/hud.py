"""HUD and the single text-drawing entry point. All UI text goes through `draw_text`, so tests can capture it."""
from __future__ import annotations
from typing import Callable
import pygame
from engrama.app import i18n
from engrama.app.snapshot import Snapshot

NEED_THRESHOLD = 0.6
MAX_NEED_ICONS = 3
_fonts: dict[int, pygame.font.Font] = {}
_hooks: list[Callable[[str], None]] = []
_rendered: dict[tuple, pygame.Surface] = {}
MAX_RENDERED = 256


def add_text_hook(fn: Callable[[str], None]) -> None:
    """Register fn(text) to be called for every string drawn (used by tests to audit visible text)."""
    _hooks.append(fn)


def remove_text_hook(fn: Callable[[str], None]) -> None:
    if fn in _hooks:
        _hooks.remove(fn)


def font(size: int) -> pygame.font.Font:
    if not pygame.font.get_init():
        pygame.font.init()
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size)
    return _fonts[size]


def draw_text(surface: pygame.Surface, text: str, pos: tuple[int, int], color=(235, 235, 240), size: int = 20,
              anchor: str = "topleft") -> pygame.Rect:
    for h in list(_hooks):
        try:
            h(text)
        except Exception:
            pass
    key = (text, tuple(color), size)
    img = _rendered.get(key)
    if img is None:   # antialiased rendering is the costliest part of a frame; most strings repeat every frame
        if len(_rendered) >= MAX_RENDERED:
            _rendered.clear()
        img = _rendered[key] = font(size).render(text, True, color)
    r = img.get_rect(**{anchor: pos})
    surface.blit(img, r)
    return r


def wrap(text: str, size: int, max_w: int) -> list[str]:
    """Greedy word wrap of `text` at `size` into lines no wider than max_w (a single long word is kept whole)."""
    f = font(size)
    lines: list[str] = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            trial = f"{cur} {word}".strip()
            if cur and f.size(trial)[0] > max_w:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        lines.append(cur)
    return lines


def fit(text: str, size: int, max_w: int) -> str:
    """`text` cut with an ellipsis so it is never wider than max_w at `size`."""
    f = font(size)
    if f.size(text)[0] <= max_w:
        return text
    while text and f.size(text + "…")[0] > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


NEED_COLORS = {"fome": (230, 140, 70), "sono": (110, 120, 220), "tedio": (150, 150, 160),
               "carinho": (240, 130, 170), "curiosidade": (110, 210, 200), "apoio": (170, 210, 110)}


# 7x7 glyphs drawn inside each need circle (a letter says little; these read at a glance)
NEED_GLYPHS = {
    "fome": ("..###..", ".#####.", ".#####.", "..###..", "...#...", "...#...", "..###.."),
    "sono": ("..###..", ".##....", "##.....", "##.....", "##.....", ".##....", "..###.."),
    "tedio": ("..###..", ".#...#.", "#.#.#.#", "#..#..#", "#.#.#.#", ".#...#.", "..###.."),
    "carinho": (".##.##.", "#######", "#######", "#######", ".#####.", "..###..", "...#..."),
    "curiosidade": (".####..", "#...##.", "....##.", "..###..", "..##...", ".......", "..##..."),
    "apoio": ("#######", "#.....#", "#.#.#.#", "#.....#", "####.##", "...##..", "...#..."),
}
_NEED_R = 12
_glyphs: dict[str, pygame.Surface] = {}


def need_glyph(name: str) -> pygame.Surface | None:
    rows = NEED_GLYPHS.get(name)
    if rows is None:
        return None
    img = _glyphs.get(name)
    if img is None:
        small = pygame.Surface((7, 7), pygame.SRCALPHA)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    small.set_at((x, y), (34, 30, 46))
        img = _glyphs[name] = pygame.transform.scale(small, (14, 14))
    return img


def mood_kind(snap: Snapshot) -> str:
    v = snap.pad[0] if snap.pad else 0.0
    return "happy" if v > 0.2 else "sad" if v < -0.2 else "neutral"


def _mood_icon(surface, cx, cy, kind):
    col = {"happy": (250, 220, 90), "sad": (120, 150, 230), "neutral": (200, 200, 205)}[kind]
    dark = (40, 36, 50)
    pygame.draw.circle(surface, col, (cx, cy), 12)
    pygame.draw.circle(surface, dark, (cx - 4, cy - 3), 2)
    pygame.draw.circle(surface, dark, (cx + 4, cy - 3), 2)
    if kind == "happy":
        pygame.draw.arc(surface, dark, (cx - 6, cy - 4, 12, 10), 3.5, 5.9, 2)
    elif kind == "sad":
        pygame.draw.arc(surface, dark, (cx - 6, cy + 2, 12, 10), 0.4, 2.8, 2)
    else:
        pygame.draw.line(surface, dark, (cx - 4, cy + 5), (cx + 4, cy + 5), 2)


class Hud:
    def __init__(self) -> None:
        self.name = ""                          # the name the user gave the creature ("" = show the branch only)
        self.hover: tuple[int, int] | None = None
        self._spots: list[tuple[pygame.Rect, str]] = []   # (hit rect, tooltip text) of the last draw

    def _tip(self) -> str:
        if self.hover is None:
            return ""
        return next((text for r, text in self._spots if r.collidepoint(self.hover)), "")

    def key(self, snap: Snapshot, dev: bool = False) -> tuple:
        """Everything `draw` paints, as a comparable value: equal keys mean an identical HUD."""
        urgent = tuple(k for _v, k in sorted(((v, k) for k, v in snap.needs.items() if v > NEED_THRESHOLD),
                                             reverse=True)[:MAX_NEED_ICONS])
        k = (mood_kind(snap), urgent, snap.resting, snap.stage, snap.dead, snap.branch_name, snap.branch, snap.grave,
             snap.sick, snap.old, i18n.get_lang(), dev, self.name, self._tip())
        if dev:
            k += (tuple(snap.needs.items()), snap.action, round(snap.t))
        return k

    def draw(self, surface: pygame.Surface, snap: Snapshot, dev: bool = False) -> None:
        w = surface.get_width()
        kind = mood_kind(snap)
        _mood_icon(surface, 22, 22, kind)
        self._spots = [(pygame.Rect(8, 8, 28, 28), i18n.t(f"ui.mood.{kind}"))]
        urgent = sorted(((v, k) for k, v in snap.needs.items() if v > NEED_THRESHOLD), reverse=True)[:MAX_NEED_ICONS]
        x = 52
        for _v, k in urgent:
            pygame.draw.circle(surface, (30, 26, 40), (x, 22), _NEED_R + 1)
            pygame.draw.circle(surface, NEED_COLORS.get(k, (200, 200, 200)), (x, 22), _NEED_R)
            g = need_glyph(k)
            if g is not None:
                surface.blit(g, g.get_rect(center=(x, 22)))
            else:
                draw_text(surface, i18n.t(f"need.{k}")[:1].upper(), (x, 22), (30, 26, 40), 18, "center")
            self._spots.append((pygame.Rect(x - _NEED_R, 22 - _NEED_R, 2 * _NEED_R, 2 * _NEED_R), i18n.t(f"need.{k}")))
            x += 2 * _NEED_R + 6
        tip = self._tip()
        if tip:
            box = pygame.Rect(8, 40, font(18).size(tip)[0] + 14, 22)
            pygame.draw.rect(surface, (24, 22, 34), box, border_radius=6)
            pygame.draw.rect(surface, (120, 110, 170), box, 1, border_radius=6)
            draw_text(surface, tip, box.center, (235, 235, 245), 18, "center")
        top = 10
        if self.name and not snap.dead:
            draw_text(surface, fit(self.name, 24, w // 3), (w - 10, top), (245, 245, 250), 24, "topright")
            top += 22
        if snap.stage != "egg" and not snap.dead:
            branch = snap.branch_name or i18n.t(f"branch.{snap.branch or 'base'}")
            line = f"{i18n.t(f'stage.{snap.stage}')} · {branch}" if self.name else branch
            draw_text(surface, line, (w - 10, top), (200, 200, 215), 18, "topright")
            top += 18
        if snap.resting:
            draw_text(surface, "z z  " + i18n.t("ui.rest.on"), (w - 10, top + 2), (170, 180, 240), 20, "topright")
        if snap.stage != "egg" and not snap.dead:
            y = 44
            if snap.grave:   # urgent: the creature asks for help
                draw_text(surface, i18n.t("ui.life.grave"), (w // 2, y), (250, 120, 110), 22, "midtop")
            elif snap.sick:
                draw_text(surface, i18n.t("ui.life.sick"), (w // 2, y), (170, 220, 120), 20, "midtop")
            if snap.old:
                draw_text(surface, i18n.t("ui.life.old"), (w // 2, y + 22), (190, 190, 205), 18, "midtop")
        if snap.stage == "egg":
            draw_text(surface, i18n.t("ui.egg.hint"), (w // 2, 44), (225, 225, 235), 20, "midtop")
        if dev:
            y = 44
            for k, v in snap.needs.items():
                draw_text(surface, f"{k} {v:.2f}", (8, y), (255, 240, 160), 16)
                y += 14
            draw_text(surface, f"{snap.stage} {snap.action} t={snap.t:.0f}", (8, y), (255, 240, 160), 16)
