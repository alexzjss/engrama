"""Action catalog and availability rules."""
from dataclasses import dataclass, field

from engrama.vocab import ACTIONS, STAGES


@dataclass(frozen=True)
class ActionSpec:
    name: str
    duration_s: float            # 0 = open-ended (sleep runs until rested or woken)
    min_stage: str
    effects_per_h: dict[str, float] = field(default_factory=dict)


ACTION_SPECS: dict[str, ActionSpec] = {s.name: s for s in (
    ActionSpec("idle", 5.0, "egg"),
    ActionSpec("wander", 20.0, "baby", {"tedio": -20.0, "curiosidade": -10.0}),
    ActionSpec("play_alone", 60.0, "baby", {"tedio": -90.0}),
    ActionSpec("sleep", 0.0, "baby"),
    ActionSpec("ask_attention", 30.0, "baby"),
    ActionSpec("explore", 45.0, "baby", {"curiosidade": -60.0, "tedio": -10.0}),
    ActionSpec("show_something", 20.0, "child", {"carinho": -10.0}),
    ActionSpec("hide", 60.0, "baby"),
)}

assert tuple(ACTION_SPECS) == ACTIONS

WAKE_SONO = 20.0


def available(stage: str, asleep: bool, fullscreen: bool) -> tuple[str, ...]:
    if stage == "egg":
        return ("idle",)
    if fullscreen:
        return ("hide",)
    if asleep:
        return ("sleep",)
    idx = STAGES.index(stage)
    return tuple(a for a, s in ACTION_SPECS.items()
                 if a != "hide" and STAGES.index(s.min_stage) <= idx)
