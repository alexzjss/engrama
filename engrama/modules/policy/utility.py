"""UtilityPolicy: hand-written utility scores per action."""
from __future__ import annotations
from engrama.mind.contracts import Module, Blackboard, Proposal
from engrama.mind.helpers import read_traits
from engrama.vocab import NEED_KEYS


class UtilityPolicy(Module):
    reads = ("drives", "affect.pad", "traits", "body.stage")
    writes = ()
    rate_hz = 1.0

    def propose(self, bb: Blackboard) -> list[Proposal]:
        dv = bb.get("drives")
        d = {k: float(dv[i]) for i, k in enumerate(NEED_KEYS)} if dv is not None else {k: 0.0 for k in NEED_KEYS}
        pad = bb.get("affect.pad")
        P, A = (float(pad[0]), float(pad[1])) if pad is not None else (0.0, 0.0)
        tr = read_traits(bb)
        terms: dict[str, list[tuple[float, str]]] = {
            "sleep": [(d["sono"] * 1.5, "sono alto")],
            "play_alone": [(d["tedio"] * (0.6 + tr["criatividade"]), "tédio + criatividade")],
            "ask_attention": [((d["carinho"] + 0.5 * d["apoio"]) * (0.4 + tr["sociabilidade"]),
                               "carinho + sociabilidade")],
            "explore": [(d["curiosidade"] * (0.5 + tr["curiosidade"]), "curiosidade alta")],
            "show_something": [(0.3 * (1.0 if P > 0 else 0.0) * tr["sociabilidade"], "feliz + sociável"),
                               (0.2 * d["curiosidade"], "curiosidade")],
            "wander": [(0.25, "base"), (0.2 * A, "excitação")],
            "idle": [(0.2, "base"), (0.3 * (1 - A) / 2, "calma")],
            "hide": [(1.0, "esconder")],
        }
        out = []
        for a in bb.available_actions:
            t = terms.get(a)
            if not t:
                continue
            top = max(t, key=lambda x: x[0])
            out.append(Proposal(a, float(sum(s for s, _ in t)), top[1]))
        return out
