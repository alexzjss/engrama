"""Behaviour variants: purely visual flavours the UI picks when a kernel action starts."""
from __future__ import annotations
import random
import zlib
from dataclasses import dataclass

STAGE_ORDER = ("egg", "baby", "child", "adult", "perfect", "final")

VARIANT_RULES: dict[str, dict] = {
    "jump": {"actions": ("play_alone", "idle"), "min_stage": "baby", "mode": "any"},
    "dance": {"actions": ("play_alone",), "min_stage": "child", "mode": "any"},
    "yawn": {"actions": ("idle",), "min_stage": "baby", "mode": "any"},
    "nap_clock": {"actions": ("sleep",), "min_stage": "child", "mode": "overlay"},
    "chase": {"actions": ("play_alone", "explore"), "min_stage": "child", "mode": "overlay"},
    "look_cursor": {"actions": ("idle", "wander", "explore", "play_alone", "show_something", "ask_attention",
                                "hide"), "min_stage": "baby", "mode": "overlay"},
    "peek": {"actions": ("explore",), "min_stage": "adult", "mode": "overlay"},
    "dig": {"actions": ("explore",), "min_stage": "child", "mode": "terrarium"},
    "found": {"actions": ("show_something",), "min_stage": "adult", "mode": "any"},
}


@dataclass(frozen=True)
class VariantCtx:
    stage: str
    pad: tuple[float, float, float]
    needs: dict[str, float]
    overlay: bool
    cursor_near: bool = False
    theme: str = ""
    peek_ok: bool = False
    asleep: bool = False


def _condition(name: str, ctx: VariantCtx) -> bool:
    happy = ctx.pad[0] > 0.3
    if name == "jump":
        return happy
    if name == "dance":
        return happy or ctx.theme == "musica"
    if name == "yawn":
        return ctx.needs.get("sono", 0.0) > 60
    if name in ("chase", "look_cursor"):
        return ctx.cursor_near
    if name == "peek":
        return ctx.peek_ok
    return True


def pick_variant(action: str, ctx: VariantCtx, seed: int, n: int) -> str:
    if ctx.stage not in STAGE_ORDER or ctx.stage == "egg":
        return ""
    if ctx.asleep and action != "sleep":
        return ""
    rank = STAGE_ORDER.index(ctx.stage)
    elig = []
    for name, rule in VARIANT_RULES.items():
        if action not in rule["actions"] or rank < STAGE_ORDER.index(rule["min_stage"]):
            continue
        if rule["mode"] == "overlay" and not ctx.overlay:
            continue
        if rule["mode"] == "terrarium" and ctx.overlay:
            continue
        if ctx.asleep and name != "nap_clock":
            continue
        if _condition(name, ctx):
            elig.append(name)
    if not elig:
        return ""
    # stable across processes: crc32 of text, never hash() of a str
    rng = random.Random(zlib.crc32(f"{int(seed)}|{action}|{int(n)}".encode()))
    i = rng.randrange(len(elig) + 1)   # last slot = no variant (weight 1)
    return elig[i] if i < len(elig) else ""
