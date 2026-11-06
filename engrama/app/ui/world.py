"""The desktop as a world (M17): walkable surfaces from window geometry, and the creature that walks on them.

Pure geometry, no pygame: rectangles in, positions out, so every rule is testable with fake windows.
Screen coordinates (y grows down). A surface is a horizontal ledge the creature's FEET stand on.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

Rect = tuple[int, int, int, int]

GRAVITY = 1400.0          # px/s^2
MAX_FALL = 1600.0         # px/s
JUMP_UP = 1000            # highest ledge it can hop up to (px): a cartoon pet, a screen is the limit
JUMP_DX = 260             # farthest ledge it can hop to sideways (px)
JUMP_TIME = 0.5           # s, plus a little per 100 px of height
EDGE_MIN = 90             # shortest visible top-edge worth standing on (px)
TOL = 3.0                 # feet within this of a ledge count as standing on it


@dataclass(frozen=True)
class Surface:
    x0: float
    x1: float
    y: float
    kind: str = "edge"    # "strip" (the taskbar band) | "edge" (top of a window)


def visible_edges(windows: list[Rect], area: Rect, headroom: int, min_len: int = EDGE_MIN) -> list[Surface]:
    """Top edges of the windows (topmost first) that nothing in front covers.

    A window above covers a point of the edge when it contains that point; its own edge is what remains after
    subtracting the spans of every window earlier in the list whose vertical range includes the edge row. Edges
    without `headroom` pixels of screen above them (a maximised window) or outside the work area are dropped.
    """
    ax, ay, aw, ah = area
    out: list[Surface] = []
    for i, (x, y, w, h) in enumerate(windows):
        if y < ay + headroom or y > ay + ah - 8 or w <= 0:
            continue
        spans = [(float(max(x, ax)), float(min(x + w, ax + aw)))]
        for (ox, oy, ow, oh) in windows[:i]:
            if oy <= y < oy + oh:
                cut0, cut1 = ox, ox + ow
                nxt = []
                for a, b in spans:
                    if cut1 <= a or cut0 >= b:
                        nxt.append((a, b))
                        continue
                    if cut0 > a:
                        nxt.append((a, float(cut0)))
                    if cut1 < b:
                        nxt.append((float(cut1), b))
                spans = nxt
                if not spans:
                    break
        for a, b in spans:
            if b - a >= min_len:
                out.append(Surface(a + 4, b - 4, float(y), "edge"))
    return out


def edge_surfaces_for(windows: list[Rect], area: Rect, sprite_px: int) -> list[Surface]:
    """Ledges for a creature `sprite_px` tall: top edges with room for its body above them."""
    return visible_edges(windows, area, headroom=int(sprite_px), min_len=max(EDGE_MIN, int(sprite_px)))


def temper_of(branch: str, traits: dict[str, float] | None) -> str:
    """How it reacts to the cursor: 'skittish' (flees), 'playful' (follows), 'curious' (looks) or 'calm'."""
    t = traits or {}
    b = (branch or "").lower()
    if b in ("arisco", "sombrio", "rebelde", "sombra") or (t.get("independencia", 0) > 65 and t.get("sociabilidade", 50) < 35):
        return "skittish"
    if b in ("brincalhao", "companheiro", "aventureiro") or t.get("sociabilidade", 0) > 65:
        return "playful"
    if b in ("curioso", "explorador", "sabio") or t.get("curiosidade", 0) > 65:
        return "curious"
    return "calm"


class Walker:
    """Where the creature stands: on a surface, falling to one, or hopping to one."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random(0)
        self.x = 0.0
        self.y = 0.0                 # feet
        self.state = "walk"          # "walk" | "fall" | "jump"
        self.vy = 0.0
        self.goal: Surface | None = None
        self._jump: tuple[float, float, float, float, float] | None = None   # x0, y0, x1, y1, elapsed
        self._jump_to: Surface | None = None
        self._jump_len = JUMP_TIME

    # ---------------------------------------------------------------- queries
    def support(self, surfaces: list[Surface]) -> Surface | None:
        """The ledge under the feet right now (None while in the air or when the ground vanished)."""
        best = None
        for s in surfaces:
            if abs(s.y - self.y) <= TOL and (s.kind == "strip" or s.x0 <= self.x <= s.x1):
                if best is None or s.kind == "strip":
                    best = s
        return best

    @property
    def airborne(self) -> bool:
        return self.state != "walk"

    def place(self, x: float, y: float) -> None:
        self.x, self.y, self.state, self.vy, self.goal, self._jump = float(x), float(y), "walk", 0.0, None, None

    # ---------------------------------------------------------------- goals
    def choose_goal(self, surfaces: list[Surface], prefer: Surface | None = None) -> Surface | None:
        """Pick a ledge to go to (hop up, or walk off to a lower one). None when there is nowhere else."""
        here = self.support(surfaces)
        options = [s for s in surfaces if s is not here and not (here and _same(s, here))]
        if not options:
            return None
        if prefer is not None and not (here and _same(prefer, here)) and self.rng.random() < 0.6:
            self.goal = prefer
            return prefer
        self.goal = self.rng.choice(options)
        return self.goal

    def clear_goal(self) -> None:
        self.goal = None

    # ---------------------------------------------------------------- stepping
    def edge_target(self, here: Surface) -> float | None:
        """Where to walk on `here` to head for the goal: the launch point of a hop, or past the edge to drop off."""
        g = self.goal
        if g is None or _same(g, here):
            return None
        if g.y < here.y:   # up: stand as close as possible to the ledge, in x
            return min(max(self.x, g.x0), g.x1) if not (g.x0 <= self.x <= g.x1) else self.x
        # down (or level): leave through the side nearest to the goal
        mid = (g.x0 + g.x1) / 2
        if mid < here.x0:
            left = True
        elif mid > here.x1:
            left = False
        else:
            left = self.x - here.x0 <= here.x1 - self.x     # the nearest end, so it never dithers midway
        return here.x0 - 6.0 if left else here.x1 + 6.0

    def update(self, dt: float, surfaces: list[Surface], target_x: float | None, speed: float) -> bool:
        """Advance one tick; returns True while the creature is moving (walking, falling or hopping)."""
        dt = max(0.0, min(0.25, dt))
        if self.state == "jump":
            return self._step_jump(dt, surfaces)
        if self.state == "fall":
            return self._step_fall(dt, surfaces)
        here = self.support(surfaces)
        if here is None:
            self.state, self.vy = "fall", 0.0
            return self._step_fall(dt, surfaces)
        if self.goal is not None and (_same(self.goal, here) or not any(_same(self.goal, s) for s in surfaces)):
            self.goal = None       # arrived, or the ledge went away (window closed or moved)
        tx = target_x
        if self.goal is not None:
            et = self.edge_target(here)
            if et is not None:
                tx = et
                g = self.goal
                if g.y < here.y and self._can_hop(here, g):
                    self._start_hop(g)
                    return True
                if g.y < here.y and not self._reachable_up(here, g):
                    self.goal = None   # too high or too far: give up
                    tx = target_x
        moved = False
        if tx is not None:
            d = tx - self.x
            step = speed * dt
            if abs(d) <= step:
                self.x, moved = tx, abs(d) > 1e-6
            else:
                self.x += step if d > 0 else -step
                moved = True
        return moved

    # ---------------------------------------------------------------- hopping and falling
    def _reachable_up(self, here: Surface, g: Surface) -> bool:
        return here.y - g.y <= JUMP_UP and _gap(here, g) <= JUMP_DX * 3

    def _can_hop(self, here: Surface, g: Surface) -> bool:
        gap = 0.0 if g.x0 <= self.x <= g.x1 else min(abs(self.x - g.x0), abs(self.x - g.x1))
        return here.y - g.y <= JUMP_UP and gap <= JUMP_DX

    def _start_hop(self, g: Surface) -> None:
        lx = min(max(self.x, g.x0 + 4), g.x1 - 4) if g.x1 - g.x0 > 8 else (g.x0 + g.x1) / 2
        self._jump = (self.x, self.y, lx, g.y, 0.0)
        self._jump_len = JUMP_TIME + max(0.0, self.y - g.y) * 0.0006
        self._jump_to = g
        self.state = "jump"

    def _step_jump(self, dt: float, surfaces: list[Surface]) -> bool:
        assert self._jump is not None
        x0, y0, x1, y1, el = self._jump
        el += dt
        k = min(1.0, el / self._jump_len)
        self.x = x0 + (x1 - x0) * k
        arc = 70.0 + max(0.0, y0 - y1) * 0.25
        self.y = y0 + (y1 - y0) * k - 4 * arc * k * (1 - k)
        self._jump = (x0, y0, x1, y1, el)
        if k >= 1.0:
            self.x, self.y = x1, y1
            self._jump = None
            self.state, self.vy = "walk", 0.0
            if self.support(surfaces) is None:   # the target ledge vanished mid-air
                self.state = "fall"
            elif self.goal is not None and _same(self.goal, self._jump_to or self.goal):
                self.goal = None
        return True

    def _step_fall(self, dt: float, surfaces: list[Surface]) -> bool:
        self.vy = min(MAX_FALL, self.vy + GRAVITY * dt)
        ny = self.y + self.vy * dt
        landing = None
        for s in surfaces:
            if (s.kind == "strip" or s.x0 - 2 <= self.x <= s.x1 + 2) and self.y - TOL <= s.y <= ny + TOL:
                if landing is None or s.y < landing.y:
                    landing = s
        if landing is not None:
            self.y, self.vy, self.state = landing.y, 0.0, "walk"
            if landing.kind != "strip":
                self.x = min(max(self.x, landing.x0), landing.x1)
        else:
            self.y = ny
        return True


def _same(a: Surface, b: Surface) -> bool:
    return abs(a.y - b.y) <= TOL and a.x0 < b.x1 and b.x0 < a.x1


def _gap(a: Surface, b: Surface) -> float:
    if a.x0 < b.x1 and b.x0 < a.x1:
        return 0.0
    return min(abs(a.x0 - b.x1), abs(b.x0 - a.x1))


def flee_target(x: float, cursor_x: float, surface: Surface) -> float:
    """Run to the far end of the ledge, away from the cursor."""
    return surface.x1 if x >= cursor_x else surface.x0


def distance(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)
