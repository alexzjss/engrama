"""Low-resolution terrarium scene and the animated creature."""
from __future__ import annotations
import math
import time
import pygame
from engrama import balance
from engrama.app.art import emotes, home, sprites, terrain, vpet
from engrama.app.art.items import found_item
from engrama.app.art.sprites import Look
from engrama.app.snapshot import Snapshot

ANIM_FOR = {"idle": "idle", "wander": "walk", "explore": "walk", "sleep": "sleep", "play_alone": "happy",
            "show_something": "happy", "ask_attention": "happy", "hide": "idle"}

# variant -> animation name (new ones live in vpet.anim.ANIM_FRAMES; the rest reuse existing poses)
VARIANT_ANIM = {"jump": "jump", "dance": "dance", "yawn": "yawn", "dig": "dig", "found": "happy",
                "nap_clock": "sleep", "chase": "walk", "look_cursor": "idle", "peek": "idle"}
_NEW_ANIMS = frozenset(("jump", "dance", "yawn", "dig"))
_vframes: dict[tuple, list] = {}

EVOLVE_SECONDS = 3.0
FAREWELL_FADE_START = 3.0   # seconds of the dead animation at full opacity
FAREWELL_FADE_END = 7.0     # after this only the outline remains
FAREWELL_BUBBLE_AT = 1.0    # when the farewell text may appear


def _anim_frames(look: Look, stage: str, anim: str) -> list:
    """Frames for any anim, including the M7 ones that `sprites.frames` does not list (creatures only, never eggs)."""
    if anim not in _NEW_ANIMS:
        return sprites.frames(look, stage, anim)
    lineage = vpet.known_lineage(getattr(look, "lineage", ()) or ())
    key = (look.seed, look.body, look.eyes, look.ears, look.tail, look.pattern, tuple(look.palette[1]), stage, anim,
           getattr(look, "branch", "base") or "base", lineage)
    hit = _vframes.get(key)
    if hit is None:
        branch = getattr(look, "branch", "base") or "base"
        hit = [sprites._surface(a) for a in vpet.creature_frames(look, stage, anim, branch, lineage)]
        _vframes[key] = hit
        while len(_vframes) > 64:
            _vframes.pop(next(iter(_vframes)))
    return hit


def local_hour() -> float:
    """The wall clock as a fractional hour of the day: the terrarium follows the real day and night."""
    t = time.localtime()
    return t.tm_hour + t.tm_min / 60.0


class Scene:
    def __init__(self, size: tuple[int, int]) -> None:
        self.size = size  # low-res size
        self.creature_rect = pygame.Rect(0, 0, 0, 0)  # low-res coordinates, from the last draw
        self.is_egg = True
        self.moving = False   # the last draw displaced the creature (walking, jumping, bouncing) or animates fast
        self._bg: pygame.Surface | None = None
        self._bg_key: tuple | None = None
        self._shadow = (60, 100, 70)
        self.hour_fn = local_hour                     # tests and the screenshot tool pin the hour here
        self._burst: tuple[str, float] | None = None  # (emote kind, start) of a one-off burst (hearts on a pet)
        self._dead_t0: float | None = None
        self._age = 0.0
        self._outlines: dict[int, list] = {}

    def _background(self, seed: int = 0) -> pygame.Surface:
        hour = float(self.hour_fn())
        key = (self.size, int(hour * 4), seed)   # one backdrop per quarter of an hour
        if self._bg is None or key != self._bg_key:
            self._bg, self._shadow = terrain.backdrop(self.size, int(hour * 4) / 4.0, seed)
            self._bg_key = key
        return self._bg

    def burst(self, kind: str, now: float) -> None:
        self._burst = (kind, now)

    def draw(self, surface: pygame.Surface, snap: Snapshot, now: float, eating: bool = False,
             variant: str = "", background: bool = True, item: str = "", flip: bool = False,
             pos_x: int | None = None, ground: int | None = None) -> None:
        w, h = self.size
        look = sprites.look_of(snap.look)
        stage = snap.stage if snap.stage in sprites.SIZES else "baby"
        if ground is None:
            ground = int(h * 0.80)
        things = home.items_for(stage) if background and not snap.dead else ()
        if background:
            surface.blit(self._background(look.seed % 97), (0, 0))
            for kind in things:
                img = home.item(kind, look.palette)
                fx, up = home.SPOTS[kind]
                surface.blit(img, img.get_rect(midbottom=(int(w * fx), ground - up + (2 if kind == "nest" else 0))))
        self.is_egg = stage == "egg"
        x_override = pos_x
        self.moving = False
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
            plain = not (snap.old or snap.sick or snap.asleep or evolving or snap.dead or eating)
            if variant in VARIANT_ANIM and plain:
                anim = VARIANT_ANIM[variant]
                rate = 5.0 if variant in ("jump", "dance", "dig") else rate
            fr = _anim_frames(look, stage, anim)
            img = fr[int(now * rate) % len(fr)]
            if snap.eyes_closed and not snap.asleep and not evolving and not snap.dead:
                img = sprites.frames(look, stage, "sleep")[0]   # user asked for closed eyes: first sleep frame has them shut
            moving = snap.action in ("wander", "explore") and not snap.asleep
            pos_x = int(w / 2 + (math.sin(now * 0.6) * w * 0.3 if moving else math.sin(now * 0.1) * 6))
            if snap.asleep and "bed" in things:   # she has a bed: that is where she sleeps
                pos_x, ground = int(w * home.SPOTS["bed"][0]), ground - home.SPOTS["bed"][1] - 3
            self.moving = (moving or evolving or eating or snap.dead or snap.action == "ask_attention"
                           or (plain and variant in ("jump", "dance", "dig", "chase")))
        if x_override is not None:   # overlay: the caller owns the horizontal position
            pos_x = int(x_override)
        if flip:
            img = pygame.transform.flip(img, True, False)
        if not snap.dead:
            self._dead_t0 = None
            self._age = 0.0
        r = img.get_rect(midbottom=(pos_x, ground))
        asking = snap.action == "ask_attention" and not self.is_egg
        if background and not self.is_egg and snap.action != "hide":
            sw = max(6, r.w * 2 // 3)
            pygame.draw.ellipse(surface, self._shadow, (r.centerx - sw // 2, ground - 2, sw, 4))
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
        if not self.is_egg and not snap.dead and not (snap.old or snap.sick or snap.asleep):
            if variant == "dig":
                self._draw_dirt(surface, r, now)
            elif variant == "found" and item:
                it = found_item(item)
                surface.blit(it, (r.right - 2, r.bottom - 10 - int(abs(math.sin(now * 3)) * 2)))
        if background and not snap.dead:
            if self._burst is not None:
                if emotes.draw_burst(surface, self._burst[0], r, now - self._burst[1]):
                    self.moving = True
                else:
                    self._burst = None
            elif not self.is_egg and not asking:
                emotes.draw_ambient(surface, emotes.ambient_kind(snap.asleep, snap.pad, snap.sick), r, now)
        if asking and int(now * 2) % 2 == 0:
            bx, by = r.midtop[0], r.y - 8
            surface.fill((250, 240, 120), (bx - 1, by - 5, 3, 5))
            surface.fill((250, 240, 120), (bx - 1, by + 1, 3, 2))

    @staticmethod
    def _draw_dirt(surface: pygame.Surface, r: pygame.Rect, now: float) -> None:
        """A mound of turned earth beside the creature plus a few flying clods."""
        gx, gy = r.right - 4, r.bottom
        surface.fill((92, 62, 40), (gx, gy - 3, 8, 3))
        surface.fill((122, 86, 56), (gx + 1, gy - 4, 6, 1))
        surface.fill((70, 46, 30), (gx - 1, gy - 1, 10, 1))
        for i in range(3):
            ph = (now * 2.5 + i * 0.33) % 1.0
            surface.fill((122, 86, 56), (gx + 2 + i * 2 - int(ph * 3), gy - 4 - int(math.sin(ph * math.pi) * 6), 1, 1))

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
