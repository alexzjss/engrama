"""python -m engrama.lab <command>"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from engrama.lab.explog import read_log
from engrama.lab.metrics import compute_metrics
from engrama.lab.runtime import run_days


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
    r = sub.add_parser("report", help="print metrics of a logged run")
    r.add_argument("--log", type=Path, required=True)
    r.add_argument("--run", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "sim":
        m = run_days(a.recipe, a.days, a.profile, a.seed, a.dt, a.log, a.save)
    else:
        m = compute_metrics(read_log(a.log, a.run))
    print(json.dumps(m, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
