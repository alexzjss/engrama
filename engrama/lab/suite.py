"""Experiment suite: recipes x profiles x seeds, with rebirth. Never edits the runtime: the loop repeats
the body of Runtime.run tick by tick and probes the blackboard in between."""
from __future__ import annotations
import multiprocessing
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from engrama import balance as B
from engrama.resources import recipes_dir
from engrama.kernel.sensors import Obs
from engrama.lab.expmetrics import Probe, experiment_metrics
from engrama.lab.metrics import compute_metrics
from engrama.lab.runtime import Runtime, _Collector
from engrama.lab.simuser import PROFILES, SimUser
from engrama.mind.recipe import load_recipe

RECIPES_DIR = recipes_dir()


class RoutineUser:
    """Scripted periodic user: the same schedule every day, no randomness (copy of the M2 R21 test user)."""
    _WINDOWS = ((9, 12, "message", 3), (14, 16, "pet", 4))   # (from h, to h, kind, every n ticks)

    def __init__(self, dt: float) -> None:
        self.dt = dt
        self._active = False

    def events(self, t, dt, creature):
        out = []
        h = (t / B.HOUR) % 24.0
        active = 8 <= h < 22
        if active != self._active:
            self._active = active
            out.append(Obs(t, "user_active" if active else "user_idle"))
        k = int(round(t / self.dt))
        for a, b, kind, n in self._WINDOWS:
            if a <= h < b and k % n == 0:
                out.append(Obs(t, kind, {"valence": 0.5} if kind == "message" else {}))
        return out

    def state_dict(self):
        return {}


@dataclass(frozen=True)
class RunSpec:
    recipe: Path
    profile: str
    seed: int
    days: float
    dt: float = 60.0


PRESETS: dict[str, dict] = {
    "m10": {"recipes": [RECIPES_DIR / f"{n}.toml" for n in (
                "default-v1", "ctrnn-v1", "shadow-ctrnn-v1", "curious-v1", "curious-lp-v1",
                "thompson-v1", "aif-v1", "aif-solo-v1")],
            "profiles": B.SUITE_PROFILES,
            "seeds": B.SUITE_SEEDS, "days": B.SUITE_DAYS, "routine_days": B.SUITE_ROUTINE_DAYS},
}


def resolve_recipe(p) -> Path:
    """A path, or a bare recipe name resolved against recipes/ ('thompson-v1' -> recipes/thompson-v1.toml)."""
    p = Path(p)
    if p.exists():
        return p
    q = RECIPES_DIR / (p.name if p.suffix == ".toml" else p.name + ".toml")
    return q if q.exists() else p


def specs_from(preset_or_args) -> list[RunSpec]:
    """A preset name, or a dict with recipes/profiles/seeds/days (+ optional routine_days, dt, preset).
    Missing keys fall back to the preset (default 'm10'). 'routine' runs use routine_days."""
    if isinstance(preset_or_args, str):
        args = {"preset": preset_or_args}
    else:
        args = dict(preset_or_args)
    base = PRESETS[args.get("preset") or "m10"]
    recipes = [resolve_recipe(r) for r in (args.get("recipes") or base["recipes"])]
    profiles = tuple(args.get("profiles") or base["profiles"])
    seeds = tuple(args.get("seeds") or base["seeds"])
    days = float(args.get("days") if args.get("days") is not None else base["days"])
    rdays = args.get("routine_days")
    rdays = float(rdays) if rdays is not None else min(float(base["routine_days"]), days)
    dt = float(args.get("dt") or 60.0)
    return [RunSpec(r, p, int(s), rdays if p == "routine" else days, dt)
            for r in recipes for p in profiles for s in seeds]


def run_one(spec: RunSpec) -> dict:
    recipe = load_recipe(Path(spec.recipe))
    col = _Collector()
    rt = Runtime(recipe, spec.seed, col)
    user = (RoutineUser(spec.dt) if spec.profile == "routine"
            else SimUser(PROFILES[spec.profile], np.random.default_rng([spec.seed, 1])))
    rt.user = user
    start = rt.kernel.t
    end = start + spec.days * 24 * B.HOUR
    probe = Probe(start, spec.days)
    reborn = False
    while rt.kernel.t < end - 1e-9:
        step = min(spec.dt, end - rt.kernel.t)
        evs = user.events(rt.kernel.t, step, rt.creature())
        rt.tick(step, evs)
        probe.after_tick(rt, reborn)
        reborn = False
        if rt.kernel.dead:
            probe.before_rebirth(rt)
            rt.lives.append(rt.rebirth())
            reborn = True
    lives = rt.lives + [rt.life_summary()]
    metrics = {**compute_metrics(col.rows, lives), **experiment_metrics(col.rows, spec.days),
               **probe.result(rt)}
    return {"recipe": recipe.name, "profile": spec.profile, "seed": spec.seed, "days": spec.days,
            "metrics": metrics,
            "module_ms": {s.name: float(s.mean_ms) for s in rt.scheduler.status()}}


def _key(r: dict):
    return (r["recipe"], r["profile"], r["seed"])


def run_suite(specs: list[RunSpec], jobs: int = 1) -> list[dict]:
    specs = list(specs)
    if jobs > 1 and len(specs) > 1:
        with multiprocessing.get_context("spawn").Pool(min(jobs, len(specs))) as pool:
            runs = pool.map(run_one, specs, chunksize=1)
    else:
        runs = [run_one(s) for s in specs]
    return sorted(runs, key=_key)


def _flat(d: dict, prefix: str = "") -> dict[str, float]:
    out: dict[str, float] = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flat(v, f"{prefix}{k}/"))
        elif isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v):
            out[f"{prefix}{k}"] = float(v)
    return out


def summarize(runs: list[dict], baseline: str = "default-v1") -> dict:
    cells: dict[str, dict[str, dict[int, dict[str, float]]]] = {}
    for r in sorted(runs, key=_key):
        cells.setdefault(r["recipe"], {}).setdefault(r["profile"], {})[r["seed"]] = _flat(r["metrics"])
    by_recipe: dict = {}
    for rec, profs in cells.items():
        for prof, seeds in profs.items():
            names = sorted({m for v in seeds.values() for m in v})
            out = {}
            for m in names:
                vals = [seeds[s][m] for s in sorted(seeds) if m in seeds[s]]
                out[m] = {"mean": float(np.mean(vals)), "sd": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
                          "n": len(vals), "values": vals}
            by_recipe.setdefault(rec, {})[prof] = out
    vs: dict = {}
    for rec, profs in cells.items():
        if rec == baseline:
            continue
        for prof, seeds in profs.items():
            base = cells.get(baseline, {}).get(prof)
            if not base:
                continue
            common = sorted(set(seeds) & set(base))
            out = {}
            for m in sorted({m for s in common for m in seeds[s]}):
                diffs = [seeds[s][m] - base[s][m] for s in common if m in seeds[s] and m in base[s]]
                if not diffs:
                    continue
                out[m] = {"diff": float(np.mean(diffs)), "n": len(diffs),
                          "consistent_sign": all(d > 0 for d in diffs) or all(d < 0 for d in diffs)}
            vs.setdefault(rec, {})[prof] = out
    ms: dict = {}
    for r in runs:
        for mod, v in r.get("module_ms", {}).items():
            ms.setdefault(r["recipe"], {}).setdefault(mod, []).append(v)
    return {"baseline": baseline, "by_recipe": by_recipe, "vs_baseline": vs,
            "module_ms": {rec: {m: float(np.mean(v)) for m, v in sorted(d.items())} for rec, d in sorted(ms.items())}}


MD_METRICS: tuple[str, ...] = (
    "wellbeing", "need_satisfaction", "return_per_day", "behavior_entropy", "decision_entropy",
    "answered_rate", "ignored_rate", "novelty_per_day", "pred_brier/temporal.expectation",
    "world_error_mean/world.error", "lives/life_days_mean", "lives/generations_finished")


def _fmt(x: float) -> str:
    return f"{x:.4g}"


def to_markdown(summary: dict, metrics=MD_METRICS) -> str:
    base = summary.get("baseline", "")
    profiles = sorted({p for d in summary["by_recipe"].values() for p in d})
    lines = ["Cells: mean ± sd over seeds; for non-baseline recipes `Δ` is the mean paired difference to "
             f"`{base}`, marked `*` when the sign is the same in every seed.", ""]
    for prof in profiles:
        lines += [f"### {prof}", "", "| recipe | " + " | ".join(metrics) + " |",
                  "|---|" + "---|" * len(metrics)]
        for rec in sorted(summary["by_recipe"]):
            cell = summary["by_recipe"][rec].get(prof)
            if cell is None:
                continue
            row = []
            for m in metrics:
                s = cell.get(m)
                if s is None:
                    row.append("—"); continue
                txt = f"{_fmt(s['mean'])} ± {_fmt(s['sd'])}"
                d = summary["vs_baseline"].get(rec, {}).get(prof, {}).get(m)
                if d is not None:
                    txt += f" (Δ{d['diff']:+.3g}{'*' if d['consistent_sign'] else ''})"
                row.append(txt)
            lines.append(f"| {rec} | " + " | ".join(row) + " |")
        lines.append("")
    return "\n".join(lines)
