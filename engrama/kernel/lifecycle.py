"""Life stages, the care-driven stage machine and health."""
from dataclasses import asdict, dataclass

from engrama.balance import CARE_EMA_SECONDS, CARE_MIN_TO_EVOLVE, STAGE_MIN_SECONDS
from engrama.vocab import STAGES


@dataclass
class StageMachine:
    stage: str = "egg"
    age: float = 0.0
    stage_age: float = 0.0
    care_quality: float = 1.0

    @property
    def stage_index(self) -> int:
        return STAGES.index(self.stage)

    def update(self, dt: float, needs_mean: float) -> str | None:
        self.age += dt
        self.stage_age += dt
        target = 1.0 - needs_mean / 100.0
        self.care_quality += (target - self.care_quality) * min(1.0, dt / CARE_EMA_SECONDS)
        if self.stage == "final":
            return None
        need = STAGE_MIN_SECONDS[self.stage]
        if (self.stage_age >= need and self.care_quality >= CARE_MIN_TO_EVOLVE) \
                or self.stage_age >= 1.5 * need:
            return self._advance()
        return None

    def hatch_now(self) -> None:
        if self.stage == "egg":
            self._advance()

    def _advance(self) -> str:
        self.stage = STAGES[STAGES.index(self.stage) + 1]
        self.stage_age = 0.0
        return self.stage

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StageMachine":
        return cls(stage=d["stage"], age=float(d["age"]),
                   stage_age=float(d["stage_age"]), care_quality=float(d["care_quality"]))


@dataclass
class Health:
    sick: bool = False

    def update(self, dt: float, needs_mean: float) -> None:
        """No-op stub in M1; M6 implements sickness."""

    def to_dict(self) -> dict:
        return {"sick": self.sick}

    @classmethod
    def from_dict(cls, d: dict) -> "Health":
        return cls(sick=bool(d.get("sick", False)))
