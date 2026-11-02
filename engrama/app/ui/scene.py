"""Low-resolution terrarium scene and the animated creature."""
from __future__ import annotations
import math
import pygame
from engrama import balance
from engrama.app.art import sprites
from engrama.app.art.sprites import Look
from engrama.app.snapshot import Snapshot

ANIM_FOR = {"idle": "idle", "wander": "walk", "explore": "walk", "sleep": "sleep", "play_alone": "happy",
            "show_something": "happy", "ask_attention": "happy", "hide": "idle"}

EVOLVE_SECONDS = 3.0
FAREWELL_FADE_START = 3.0   # seconds of the dead animation at full opacity
FAREWELL_FADE_END = 7.0     # after this only the outline remains
FAREWELL_BUBBLE_AT = 1.0    # when the farewell text may appear


class Scene:
    def __init__(self, size: tuple[int, int]) -> None:
        self.size = size  # low-res size
        self.creature_rect = pygame.Rect(0, 0, 0, 0)  # low-res coordinates, from the last draw
        self.is_egg = True
        self._bg: pygame.Surface | None = None
        self._dead_t0: float | None = None
        self._age = 0.0
        self._outlines: dict[int, list] = {}

    def _background(self) -> pygame.Surface:
        if self._bg is None:
            w, h = self.size
            s = pygame.Surface((w, h))
            horizon = int(h * 0.62)
            for y in range(horizon):
                k = y / horizon
                pygame.draw.line(s, (int(60 + 50 * k), int(80 + 70 * k), int(140 + 50 * k)), (0, y), (w, y))
            s.fill((88, 140, 84), (0, horizon, w, h - horizon))
            for y in range(horizon, h, 4):
                pygame.draw.line(s, (76, 126, 74), (0, y), (w, y))
            for x in range(3, w, 17):
                s.fill((120, 170, 100), (x, horizon + 3 + (x * 7) % max(1, h - horizon - 6), 2, 1))
            self._bg = s
        return self._bg

    def draw(self, surface: pygame.Surface, snap: Snapshot, now: float, eating: bool = False) -> None:
        surface.blit(self._background(), (0, 0))
        w, h = self.size
        look = Look.from_dict(snap.look)
        stage = snap.stage if snap.stage in sprites.SIZES else "baby"
        self.is_egg = stage == "egg"
        ground = int(h * 0.80)
        if self.is_egg:
            level = min(3, int(snap.egg_clicks * 4 / max(1, balance.EGG_HATCH_CLICKS)))
            if level == 0:
                fr = sprites.frames(look, "egg", "idle")
                img = fr[int(now * 3) % len(fr)]
            else:
                img = sprites.make_egg_crack(look, level)
            pos_x = w // 2
        else:
            anim = "eat" if eating else ANIM_FOR.get(snap.action, "idle")
            rate = 4.0
            if snap.old:
                anim, rate = "old", 2.0
            if snap.sick:
                anim, rate = "sick", 4.0
            if snap.asleep:
                anim, rate = "sleep", 4.0
            evolving = 0.0 <= snap.wall - snap.evolved_at < EVOLVE_SECONDS
            if evolving:
                anim, rate = "evolve", 4.0
            if snap.dead:
                anim, rate = "dead", 4.0
            fr = sprites.frames(look, stage, anim)
            img = fr[int(now * rate) % len(fr)]
            if snap.eyes_closed and not snap.asleep and not evolving and not snap.dead:
                img = sprites.frames(look, stage, "sleep")[0]   # user asked for closed eyes: first sleep frame has them shut
            moving = snap.action in ("wander", "explore") and not snap.asleep
            pos_x = int(w / 2 + (math.sin(now * 0.6) * w * 0.3 if moving else math.sin(now * 0.1) * 6))
        if not snap.dead:
            self._dead_t0 = None
            self._age = 0.0
        r = img.get_rect(midbottom=(pos_x, ground))
        asking = snap.action == "ask_attention" and not self.is_egg
        if asking:
            r.y -= int(abs(math.sin(now * 5)) * 3)
        if snap.action == "hide" and not self.is_egg and not snap.dead:
            surface.blit(img, r, pygame.Rect(0, 0, r.w, r.h * 2 // 3))
            surface.fill((50, 100, 60), (r.x - 2, r.y + r.h // 3, r.w + 4, r.h))
            surface.fill((70, 130, 70), (r.x, r.y + r.h // 3, r.w, 2))
        elif snap.dead and not self.is_egg:
            self._draw_farewell(surface, img, r, now)
        else:
            surface.blit(img, r)
        self.creature_rect = r
        if asking and int(now * 2) % 2 == 0:
            bx, by = r.midtop[0], r.y - 8
            surface.fill((250, 240, 120), (bx - 1, by - 5, 3, 5))
            surface.fill((250, 240, 120), (bx - 1, by + 1, 3, 2))

    # --- farewell: lying down (dead anim), fading, then only an outline
    @property
    def farewell_age(self) -> float:
        return self._age

    @property
    def farewell_done(self) -> bool:
        return self._age >= FAREWELL_FADE_END

    def _draw_farewell(self, surface: pygame.Surface, img: pygame.Surface, r: pygame.Rect, now: float) -> None:
        if self._dead_t0 is None:
            self._dead_t0 = now
        self._age = age = max(0.0, now - self._dead_t0)
        if age < FAREWELL_FADE_START:
            surface.blit(img, r)
            return
        if age < FAREWELL_FADE_END:
            k = (age - FAREWELL_FADE_START) / (FAREWELL_FADE_END - FAREWELL_FADE_START)
            ghost = img.copy()
            ghost.set_alpha(int(255 * (1.0 - k)))
            surface.blit(ghost, r)
        pts = self._outlines.get(id(img))
        if pts is None:
            pts = self._outlines[id(img)] = pygame.mask.from_surface(img).outline()
            if len(self._outlines) > 16:
                self._outlines.pop(next(iter(self._outlines)))
        if len(pts) > 2:
            pygame.draw.lines(surface, (205, 205, 220), True, [(x + r.x, y + r.y) for x, y in pts], 1)
