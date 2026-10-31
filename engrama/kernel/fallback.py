"""Deterministic action used when the mind proposes nothing usable."""


def fallback_action(needs: dict[str, float], available: tuple[str, ...]) -> str:
    if needs.get("sono", 0.0) >= 80 and "sleep" in available:
        return "sleep"
    if needs.get("tedio", 0.0) >= 60 and "play_alone" in available:
        return "play_alone"
    for a in ("idle", "hide"):
        if a in available:
            return a
    return available[0]
