"""Headless real-time benchmark of the default recipe: peak RSS, mean CPU %, per-module mean_ms (JSON)."""
from __future__ import annotations
import argparse
import json
import os
import subprocess
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


def bench_app(seconds: float, data_dir: Path, sample_s: float = 0.5) -> dict:
    """Run the whole app (`python -m engrama --no-llm`, dummy SDL) in a child process; sample its RSS/CPU."""
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", PYTHONPATH=str(ROOT))
    child = subprocess.Popen([sys.executable, "-m", "engrama", "--no-llm", "--data-dir", str(data_dir)],
                             cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    root = psutil.Process(child.pid)

    def tree() -> list[psutil.Process]:   # a venv launcher stub may sit in front of the real interpreter
        try:
            return [root] + root.children(recursive=True)
        except psutil.Error:
            return [root]

    def usage() -> tuple[float, int]:
        cpu, rss = 0.0, 0
        for p in tree():
            try:
                cpu += sum(p.cpu_times()[:2])
                rss += p.memory_info().rss
            except psutil.Error:
                pass
        return cpu, rss

    time.sleep(2.0)   # let imports and start-up settle, then measure the steady state
    psutil.cpu_percent(None)
    (cpu0, peak), wall0 = usage(), time.perf_counter()
    while time.perf_counter() - wall0 < seconds and child.poll() is None:
        peak = max(peak, usage()[1])
        time.sleep(sample_s)
    wall = time.perf_counter() - wall0
    cpu = (usage()[0] - cpu0) / wall * 100.0
    system_load = psutil.cpu_percent(None)
    alive = child.poll() is None
    child.terminate()
    try:
        child.wait(5)
    except subprocess.TimeoutExpired:
        child.kill()
    return {"mode": "app", "seconds": round(wall, 1), "alive": alive,
            "peak_rss_mb": round(peak / 2**20, 1), "mean_cpu_percent": round(cpu, 2),
            "system_cpu_percent": system_load, "cpu_count": psutil.cpu_count(),
            "loaded": system_load > 50.0}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--recipe", type=Path, default=ROOT / "recipes" / "default-v1.toml")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--profile", default="attentive", choices=sorted(PROFILES))
    ap.add_argument("--app", action="store_true", help="bench the whole app process (dummy SDL, --no-llm)")
    ap.add_argument("--data-dir", type=Path, default=ROOT / ".pytest_tmp" / "bench_app")
    a = ap.parse_args(argv)
    if a.app:
        a.data_dir.mkdir(parents=True, exist_ok=True)
        print(json.dumps(bench_app(a.seconds, a.data_dir), indent=2))
        return 0
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
