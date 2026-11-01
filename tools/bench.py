"""Headless real-time benchmark of the default recipe: peak RSS, mean CPU %, per-module mean_ms (JSON)."""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engrama.lab.runtime import Runtime  # noqa: E402
from engrama.lab.simuser import PROFILES, SimUser  # noqa: E402
from engrama.mind.recipe import load_recipe  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--recipe", type=Path, default=ROOT / "recipes" / "default-v1.toml")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--profile", default="attentive", choices=sorted(PROFILES))
    a = ap.parse_args(argv)
    rt = Runtime(load_recipe(a.recipe), a.seed)
    user = SimUser(PROFILES[a.profile], np.random.default_rng([a.seed, 1]))
    proc = psutil.Process()
    cpu0, wall0 = sum(proc.cpu_times()[:2]), time.perf_counter()
    peak = proc.memory_info().rss
    ticks, nxt = 0, time.perf_counter()
    while time.perf_counter() - wall0 < a.seconds:
        evs = user.events(rt.kernel.t, 1.0, rt.creature())
        rt.tick(1.0, evs)
        ticks += 1
        peak = max(peak, proc.memory_info().rss)
        nxt += 1.0
        time.sleep(max(0.0, nxt - time.perf_counter()))
    wall = time.perf_counter() - wall0
    cpu = (sum(proc.cpu_times()[:2]) - cpu0) / wall * 100.0
    print(json.dumps({
        "recipe": a.recipe.stem, "seconds": round(wall, 1), "ticks": ticks,
        "peak_rss_mb": round(peak / 2**20, 1), "mean_cpu_percent": round(cpu, 2),
        "modules_mean_ms": {s.name: round(s.mean_ms, 4) for s in rt.scheduler.status()},
        "disabled": [s.name for s in rt.scheduler.status() if not s.enabled],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
