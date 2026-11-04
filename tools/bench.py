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


def _thread_ticks(pids: list[int]) -> dict[tuple[int, int], tuple[str, int]]:
    """{(pid, tid): (comm, utime+stime ticks)} from /proc/<pid>/task/*/stat (Linux; empty elsewhere)."""
    out: dict[tuple[int, int], tuple[str, int]] = {}
    for pid in pids:
        try:
            tids = os.listdir(f"/proc/{pid}/task")
        except OSError:
            continue
        for tid in tids:
            try:
                raw = Path(f"/proc/{pid}/task/{tid}/stat").read_text()
                comm = raw[raw.index("(") + 1:raw.rindex(")")]
                f = raw[raw.rindex(")") + 2:].split()
                out[(pid, int(tid))] = (comm, int(f[11]) + int(f[12]))
            except (OSError, ValueError, IndexError):
                continue
    return out


def _resolve_recipe(arg: str) -> Path:
    p = Path(arg)
    if p.exists():
        return p
    return ROOT / "recipes" / (p.name if p.suffix == ".toml" else p.name + ".toml")


def bench_app(seconds: float, data_dir: Path, sample_s: float = 0.5, fake_perception: bool = False,
              first_use: bool = False, threads: bool = False, recipe: str | None = None) -> dict:
    """Run the whole app (`python -m engrama --no-llm`, dummy SDL) in a child process; sample its RSS/CPU.

    By default the first-use screen is already answered (steady state: it is shown once in a user's life);
    `first_use=True` keeps the old behaviour (fresh data dir). `threads=True` adds per-thread CPU % (Linux)."""
    cmd = [sys.executable, "-m", "engrama", "--no-llm", "--data-dir", str(data_dir)]
    if recipe is not None:
        cmd += ["--recipe", recipe]
    if not fake_perception and not first_use:
        from engrama.config import Config
        cfg = Config(data_dir=data_dir)
        cfg.perception_asked = True
        cfg.permissions = {k: False for k in cfg.permissions}
        cfg.save(data_dir / "config.json")
    if fake_perception:   # all sources allowed, scripted machine, short interval: worst case for the service
        from engrama.config import Config
        cfg = Config(data_dir=data_dir)
        cfg.perception_asked, cfg.perception_interval_s = True, 15.0
        cfg.permissions = {k: True for k in cfg.permissions}
        cfg.save(data_dir / "config.json")
        cmd.append("--fake-perception")
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", PYTHONPATH=str(ROOT))
    child = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    pids = [p.pid for p in tree()]
    t0 = _thread_ticks(pids) if threads else {}
    (cpu0, peak), wall0 = usage(), time.perf_counter()
    while time.perf_counter() - wall0 < seconds and child.poll() is None:
        peak = max(peak, usage()[1])
        time.sleep(sample_s)
    wall = time.perf_counter() - wall0
    cpu = (usage()[0] - cpu0) / wall * 100.0
    per_thread: dict[str, float] = {}
    if threads:
        hz = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
        for (pid, tid), (comm, ticks) in _thread_ticks(pids).items():
            pct = round((ticks - t0.get((pid, tid), (comm, 0))[1]) / hz / wall * 100.0, 2)
            per_thread[comm if comm not in per_thread else f"{comm}-{tid}"] = pct
    system_load = psutil.cpu_percent(None)
    alive = child.poll() is None
    child.terminate()
    try:
        child.wait(5)
    except subprocess.TimeoutExpired:
        child.kill()
    res = {"mode": "app", "fake_perception": fake_perception, "first_use": first_use, "seconds": round(wall, 1),
           "alive": alive, "peak_rss_mb": round(peak / 2**20, 1), "mean_cpu_percent": round(cpu, 2),
           "system_cpu_percent": system_load, "cpu_count": psutil.cpu_count(), "loaded": system_load > 50.0}
    if threads:
        res["threads"] = per_thread
    return res


def bench_overlay(seconds: float, data_dir: Path, sample_s: float = 0.5) -> dict:
    """Overlay mode in this process (dummy SDL, FakeDesktop, a fake cursor wandering the screen): RSS and CPU."""
    # Force, don't setdefault: a session that already exports SDL_VIDEODRIVER=wayland (Hyprland) would
    # otherwise open a real window and segfault in pygame.display.get_wm_info(). FakeDesktop needs no window.
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    import math
    import pygame
    from engrama.app.desktop import FakeDesktop
    from engrama.app.host import Host
    from engrama.app.ui.window import Window
    from engrama.config import Config

    data_dir.mkdir(parents=True, exist_ok=True)
    cfg = Config(data_dir=data_dir)
    host = Host(cfg, data_dir, ROOT / "recipes" / "default-v1.toml", seed=1)
    desk = FakeDesktop(work=(0, 0, 1920, 1040), cur=(900, 500))
    window = Window(host.snapshot, host.post)
    window.desktop = desk
    window.config = cfg
    window.save_config = lambda: None
    host.start()
    ok = window.set_mode("overlay")
    window.focused = False   # the real overlay never takes focus
    proc = psutil.Process()
    time.sleep(1.0)
    cpu0, wall0 = sum(proc.cpu_times()[:2]), time.perf_counter()
    peak = proc.memory_info().rss
    clock, nxt = pygame.time.Clock(), 0.0
    while time.perf_counter() - wall0 < seconds:
        el = time.perf_counter() - wall0
        desk.cur = (int(960 + 800 * math.sin(el / 3.0)), int(500 + 300 * math.sin(el / 5.0)))   # fake cursor
        for e in pygame.event.get():
            if e.type != pygame.WINDOWFOCUSGAINED:   # the dummy driver "focuses" the window; the real overlay never has focus
                window.handle_event(e)
        window.frame()
        if el >= nxt:
            peak = max(peak, proc.memory_info().rss)
            nxt = el + sample_s
        clock.tick(window.target_fps)
    wall = time.perf_counter() - wall0
    cpu = (sum(proc.cpu_times()[:2]) - cpu0) / wall * 100.0
    mode = window.mode
    host.stop()
    pygame.display.quit()
    return {"mode": "overlay", "overlay_active": ok and mode == "overlay", "focused": window.focused, "seconds": round(wall, 1),
            "peak_rss_mb": round(peak / 2**20, 1), "mean_cpu_percent": round(cpu, 2),
            "cpu_count": psutil.cpu_count()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--recipe", default=None, help="recipe name or path (headless default: default-v1; with --app: passed on)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--profile", default="attentive", choices=sorted(PROFILES))
    ap.add_argument("--app", action="store_true", help="bench the whole app process (dummy SDL, --no-llm)")
    ap.add_argument("--overlay", action="store_true", help="bench overlay mode in-process (FakeDesktop + fake cursor)")
    ap.add_argument("--fake-perception", action="store_true", help="with --app: scripted perception sources, all allowed")
    ap.add_argument("--first-use", action="store_true", help="with --app: fresh data dir, first-use screen open")
    ap.add_argument("--threads", action="store_true", help="with --app: per-thread CPU %% (Linux)")
    ap.add_argument("--data-dir", type=Path, default=ROOT / ".pytest_tmp" / "bench_app")
    a = ap.parse_args(argv)
    if a.overlay:
        import shutil
        d = a.data_dir.with_name("bench_overlay")
        shutil.rmtree(d, ignore_errors=True)
        print(json.dumps(bench_overlay(a.seconds, d), indent=2))
        return 0
    if a.app:
        a.data_dir.mkdir(parents=True, exist_ok=True)
        print(json.dumps(bench_app(a.seconds, a.data_dir, fake_perception=a.fake_perception,
                                     first_use=a.first_use, threads=a.threads,
                                     recipe=a.recipe), indent=2))
        return 0
    rec_path = _resolve_recipe(a.recipe or "default-v1")
    rt = Runtime(load_recipe(rec_path), a.seed)
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
        "recipe": rec_path.stem, "seconds": round(wall, 1), "ticks": ticks,
        "peak_rss_mb": round(peak / 2**20, 1), "mean_cpu_percent": round(cpu, 2),
        "modules_mean_ms": {s.name: round(s.mean_ms, 4) for s in rt.scheduler.status()},
        "disabled": [s.name for s in rt.scheduler.status() if not s.enabled],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
