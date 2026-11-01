"""Kernel-side observation shape and the world state it updates."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Obs:
    t: float
    kind: str
    data: dict = field(default_factory=dict)


@dataclass
class WorldState:
    user_active: bool = False
    fullscreen: bool = False
    last_app: str = ""
    seen_apps: set[str] = field(default_factory=set)

    def apply(self, obs: Obs) -> bool:
        """Update from one event; True when it reveals a new app category."""
        k = obs.kind
        if k == "user_active":
            self.user_active = True
        elif k == "user_idle":
            self.user_active = False
        elif k == "fullscreen_on":
            self.fullscreen = True
        elif k == "fullscreen_off":
            self.fullscreen = False
        elif k == "app_focus":
            app = str(obs.data.get("app", ""))
            cat = str(obs.data.get("category", app))
            self.last_app = app
            if cat and cat not in self.seen_apps:
                self.seen_apps.add(cat)
                return True
        return False

    def to_dict(self) -> dict:
        return {"user_active": self.user_active, "fullscreen": self.fullscreen,
                "last_app": self.last_app, "seen_apps": sorted(self.seen_apps)}

    @classmethod
    def from_dict(cls, d: dict) -> "WorldState":
        return cls(bool(d["user_active"]), bool(d["fullscreen"]), d["last_app"], set(d["seen_apps"]))
