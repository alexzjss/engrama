"""Personality traits with a capped daily drift."""
from engrama.core import balance as B

TRAIT_KEYS = ("curiosidade", "sociabilidade", "paciencia", "independencia", "criatividade")
INITIAL_TRAITS = {"curiosidade": 50.0, "sociabilidade": 40.0, "paciencia": 70.0, "independencia": 30.0, "criatividade": 50.0}

ADJECTIVES = {
    "pt": {
        "curiosidade": ("curiosa", "pouco curiosa"),
        "sociabilidade": ("sociável", "reservada"),
        "paciencia": ("paciente", "impaciente"),
        "independencia": ("independente", "dependente"),
        "criatividade": ("criativa", "pouco criativa"),
    },
    "en": {
        "curiosidade": ("curious", "incurious"),
        "sociabilidade": ("sociable", "reserved"),
        "paciencia": ("patient", "impatient"),
        "independencia": ("independent", "clingy"),
        "criatividade": ("creative", "unimaginative"),
    },
}
ADJECTIVE_MIN_DEVIATION = 15.0


class Traits:
    def __init__(self, values: dict[str, float] | None = None, drift_log: dict | None = None):
        self.values: dict[str, float] = dict(INITIAL_TRAITS)
        if values:
            self.values.update({k: float(v) for k, v in values.items() if k in self.values})
        # per trait: [day_index, cumulative drift that day]
        self._drift: dict[str, list[float]] = {k: list(v) for k, v in (drift_log or {}).items()}

    def drift(self, key: str, amount: float, day_index: int) -> None:
        day, used = self._drift.get(key, [day_index, 0.0])
        if day != day_index:
            day, used = day_index, 0.0
        cap = B.TRAIT_MAX_DRIFT_PER_DAY
        # the cap bounds the total movement (either direction) per sim-day
        mag = min(abs(amount), max(0.0, cap - used))
        allowed = mag if amount >= 0 else -mag
        self._drift[key] = [day, used + mag]
        self.values[key] = max(0.0, min(100.0, self.values[key] + allowed))

    def norm(self, key: str) -> float:
        return self.values[key] / 100.0

    def adjectives(self, lang: str) -> list[str]:
        table = ADJECTIVES.get(lang, ADJECTIVES["en"])
        ranked = sorted(self.values, key=lambda k: abs(self.values[k] - 50), reverse=True)
        out = []
        for k in ranked:
            dev = self.values[k] - 50
            if abs(dev) < ADJECTIVE_MIN_DEVIATION or len(out) == 2:
                break
            out.append(table[k][0] if dev > 0 else table[k][1])
        return out

    def to_dict(self) -> dict:
        return {"values": dict(self.values), "drift": {k: list(v) for k, v in self._drift.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> "Traits":
        return cls(d.get("values"), d.get("drift"))
