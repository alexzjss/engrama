"""Life stages, the care-driven stage machine and health."""
import math
from dataclasses import asdict, dataclass

from engrama import balance as B
from engrama.balance import CARE_EMA_SECONDS, CARE_MIN_TO_EVOLVE, STAGE_MIN_SECONDS
from engrama.vocab import STAGES


@dataclass
class StageMachine:
    stage: str = "egg"
    age: float = 0.0
    stage_age: float = 0.0
    care_quality: float = 1.0
    stage_care_sum: float = 0.0      # integral of care_quality over the current stage (s)
    stage_care_t: float = 0.0
    life_care_sum: float = 0.0
    life_care_t: float = 0.0
    finished_care_mean: float = 1.0  # stage_care_mean of the stage that just ended
    final_age: float = 0.0           # lifetime spent in the final stage (offline counts)
    old: bool = False
    old_online_s: float = 0.0        # online time spent old (offline never counts)

    @property
    def stage_index(self) -> int:
        return STAGES.index(self.stage)

    @property
    def stage_care_mean(self) -> float:
        return self.stage_care_sum / self.stage_care_t if self.stage_care_t > 0 else self.care_quality

    @property
    def life_care_mean(self) -> float:
        return self.life_care_sum / self.life_care_t if self.life_care_t > 0 else self.care_quality

    def update(self, dt: float, needs_mean: float, online: bool = True) -> str | None:
        self.age += dt
        self.stage_age += dt
        target = 1.0 - needs_mean / 100.0
        self.care_quality += (target - self.care_quality) * min(1.0, dt / CARE_EMA_SECONDS)
        if self.stage != "egg":
            self.stage_care_sum += self.care_quality * dt
            self.stage_care_t += dt
            self.life_care_sum += self.care_quality * dt
            self.life_care_t += dt
        if self.stage == "final":
            self.final_age += dt
            if self.final_age >= B.FINAL_LIFESPAN_S:
                self.old = True
            if self.old and online:
                self.old_online_s += dt
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
        self.finished_care_mean = self.stage_care_mean
        self.stage_care_sum = self.stage_care_t = 0.0
        self.stage = STAGES[STAGES.index(self.stage) + 1]
        self.stage_age = 0.0
        return self.stage

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StageMachine":
        cq = float(d["care_quality"])
        return cls(stage=d["stage"], age=float(d["age"]),
                   stage_age=float(d["stage_age"]), care_quality=cq,
                   stage_care_sum=float(d.get("stage_care_sum", 0.0)),
                   stage_care_t=float(d.get("stage_care_t", 0.0)),
                   life_care_sum=float(d.get("life_care_sum", 0.0)),
                   life_care_t=float(d.get("life_care_t", 0.0)),
                   finished_care_mean=float(d.get("finished_care_mean", cq)),
                   final_age=float(d.get("final_age", 0.0)),
                   old=bool(d.get("old", False)),
                   old_online_s=float(d.get("old_online_s", 0.0)))


@dataclass
class Health:
    sick: bool = False
    kind: str = ""                  # "", "neglect", "cold"
    severity: float = 0.0
    neglect_s: float = 0.0          # accumulated time with needs mean above NEGLECT_NEED_MEAN
    grave_s: float = 0.0
    cold_left_s: float = 0.0
    last_medicine_t: float = -math.inf
    cold_count: int = 0             # colds caught so far (lab metrics)
    sick_total_s: float = 0.0       # total online time spent sick (lab metrics)

    @property
    def grave(self) -> bool:
        return self.sick and self.severity >= B.GRAVE_SEVERITY

    def _cure(self) -> None:
        self.sick, self.kind, self.severity = False, "", 0.0
        self.grave_s = self.cold_left_s = self.neglect_s = 0.0

    def update(self, dt: float, needs_mean: float, rng, online: bool = True) -> bool:
        """Advance health by dt online seconds; True when neglect has become fatal."""
        if not online or dt <= 0:
            return False
        if needs_mean > B.NEGLECT_NEED_MEAN:
            self.neglect_s += dt
        else:
            self.neglect_s = 0.0
        if self.sick:
            self.sick_total_s += dt
        else:
            if self.neglect_s >= B.NEGLECT_SICK_AFTER_S:
                self.sick, self.kind, self.severity = True, "neglect", B.SICK_SEVERITY_START
            elif rng.random() < 1.0 - math.exp(-B.COLD_PER_ONLINE_H * dt / B.HOUR):
                self.sick, self.kind = True, "cold"
                self.severity = float(rng.uniform(0.1, B.COLD_MAX_SEVERITY))
                self.cold_left_s = float(rng.uniform(B.COLD_MIN_S, B.COLD_MAX_S))
                self.cold_count += 1
            return False
        if self.kind == "cold":
            if self.neglect_s >= B.NEGLECT_SICK_AFTER_S:
                self.kind, self.severity = "neglect", max(self.severity, B.SICK_SEVERITY_START)
                self.cold_left_s = 0.0
            else:
                self.cold_left_s -= dt
                if self.cold_left_s <= 0:
                    self._cure()
                return False
        if needs_mean > B.NEGLECT_NEED_MEAN:
            self.severity = min(1.0, self.severity + B.SICK_SEVERITY_UP_PER_H * dt / B.HOUR)
        elif needs_mean < B.CARE_RECOVER_NEED_MEAN:
            self.severity -= B.SICK_SEVERITY_DOWN_PER_H * dt / B.HOUR
            if self.severity <= 0:
                self._cure()
                return False
        if self.severity >= B.GRAVE_SEVERITY:
            self.grave_s += dt
            return self.grave_s >= B.GRAVE_DEATH_AFTER_S
        self.grave_s = 0.0
        return False

    def give_medicine(self, t: float) -> bool:
        """True when the medicine took effect (sick and off cooldown)."""
        if not self.sick or t - self.last_medicine_t < B.MEDICINE_COOLDOWN_S:
            return False
        self.last_medicine_t = t
        if self.kind == "cold":
            self._cure()
        else:
            self.severity -= B.MEDICINE_NEGLECT_RELIEF
            if self.severity <= 0:
                self._cure()
            elif self.severity < B.GRAVE_SEVERITY:
                self.grave_s = 0.0
        return True

    def to_dict(self) -> dict:
        return {"sick": self.sick, "kind": self.kind, "severity": self.severity,
                "neglect_s": self.neglect_s, "grave_s": self.grave_s,
                "cold_left_s": self.cold_left_s,
                "last_medicine_t": None if self.last_medicine_t == -math.inf else self.last_medicine_t,
                "cold_count": self.cold_count, "sick_total_s": self.sick_total_s}

    @classmethod
    def from_dict(cls, d: dict) -> "Health":
        lm = d.get("last_medicine_t")
        return cls(sick=bool(d.get("sick", False)), kind=str(d.get("kind", "")),
                   severity=float(d.get("severity", 0.0)), neglect_s=float(d.get("neglect_s", 0.0)),
                   grave_s=float(d.get("grave_s", 0.0)), cold_left_s=float(d.get("cold_left_s", 0.0)),
                   last_medicine_t=-math.inf if lm is None else float(lm),
                   cold_count=int(d.get("cold_count", 0)), sick_total_s=float(d.get("sick_total_s", 0.0)))
