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


class Scene:
    def __init__(self, size: tuple[int, int]) -> None:
        self.size = size  # low-res size
        self.creature_rect = pygame.Rect(0, 0, 0, 0)  # low-res coordinates, from the last draw
        self.is_egg = True
        self._bg: pygame.Surface | None = None

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
            if snap.asleep:
                anim = "sleep"
            fr = sprites.frames(look, stage, anim)
            img = fr[int(now * 4) % len(fr)]
            moving = snap.action in ("wander", "explore") and not snap.asleep
            pos_x = int(w / 2 + (math.sin(now * 0.6) * w * 0.3 if moving else math.sin(now * 0.1) * 6))
        r = img.get_rect(midbottom=(pos_x, ground))
        asking = snap.action == "ask_attention" and not self.is_egg
        if asking:
            r.y -= int(abs(math.sin(now * 5)) * 3)
        if snap.action == "hide" and not self.is_egg:
            surface.blit(img, r, pygame.Rect(0, 0, r.w, r.h * 2 // 3))
            surface.fill((50, 100, 60), (r.x - 2, r.y + r.h // 3, r.w + 4, r.h))
            surface.fill((70, 130, 70), (r.x, r.y + r.h // 3, r.w, 2))
        else:
            surface.blit(img, r)
        self.creature_rect = r
        if asking and int(now * 2) % 2 == 0:
            bx, by = r.midtop[0], r.y - 8
            surface.fill((250, 240, 120), (bx - 1, by - 5, 3, 5))
            surface.fill((250, 240, 120), (bx - 1, by + 1, 3, 2))
