"""python -m engrama.lab <command>"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import numpy as np
from engrama.lab.explog import read_log, run_identity
from engrama.lab.metrics import compute_metrics
from engrama.lab.replay import replay_module
from engrama.lab.runtime import run_days
from engrama.mind.recipe import ModuleSpec


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _parse(v: str):
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    for f in (int, float):
        try:
            return f(v)
        except ValueError:
            pass
    return v


def _replay_summary(a) -> dict:
    params = {}
    for kv in a.param:
        k, _, v = kv.partition("=")
        params[k] = _parse(v)
    out = replay_module(a.log, ModuleSpec(a.module, a.module, params), a.seed, a.run)
    summary: dict = {"ticks": len(out["t"])}
    for ch, vals in out.items():
        if ch in ("t", "proposals_top"):
            continue
        arr = np.asarray([v for v in vals if v is not None], dtype=float)
        summary[ch] = ({"mean": float(arr.mean()), "min": float(arr.min()), "max": float(arr.max())}
                       if arr.size else {"mean": None, "min": None, "max": None})
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="engrama.lab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sim", help="run a simulated creature and print metrics")
    s.add_argument("--recipe", type=Path, default=Path("recipes/default-v1.toml"))
    s.add_argument("--days", type=float, default=1.0)
    s.add_argument("--profile", default="attentive")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--dt", type=float, default=60.0)
    s.add_argument("--log", type=Path, default=None)
    s.add_argument("--save", type=Path, default=None)
    s.add_argument("--enforce-budgets", action="store_true",
                   help="demote slow modules by wall-clock time (not deterministic; off for lab runs)")
    r = sub.add_parser("report", help="print metrics of a logged run")
    r.add_argument("--log", type=Path, required=True)
    r.add_argument("--run", default=None)
    c = sub.add_parser("compare", help="run two recipes with the same seed/profile and diff the metrics")
    c.add_argument("--a", type=Path, required=True)
    c.add_argument("--b", type=Path, required=True)
    c.add_argument("--days", type=float, default=1.0)
    c.add_argument("--profile", default="attentive")
    c.add_argument("--seed", type=int, default=1)
    c.add_argument("--dt", type=float, default=60.0)
    p = sub.add_parser("replay", help="replay a logged run through one module")
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--module", required=True)
    p.add_argument("--param", action="append", default=[], metavar="K=V")
    p.add_argument("--run", default=None)
    p.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    if a.cmd == "sim":
        m = run_days(a.recipe, a.days, a.profile, a.seed, a.dt, a.log, a.save, a.enforce_budgets)
    elif a.cmd == "compare":
        ma = run_days(a.a, a.days, a.profile, a.seed, a.dt, None)
        mb = run_days(a.b, a.days, a.profile, a.seed, a.dt, None)
        m = {"a": ma, "b": mb,
             "diff": {k: mb[k] - v for k, v in ma.items() if _num(v) and k in mb and _num(mb[k])}}
    elif a.cmd == "replay":
        m = _replay_summary(a)
    else:
        m = {**compute_metrics(read_log(a.log, a.run)), **run_identity(a.log, a.run)}
    print(json.dumps(m, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
