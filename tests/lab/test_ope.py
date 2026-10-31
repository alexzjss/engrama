import pytest
from engrama.lab.explog import TickRow
from engrama.lab.ope import ips_estimate


def _rows(n=20):
    return [TickRow(60.0 * i, 60.0, "idle" if i % 2 else "wander", 0.5,
                    {"user_response": float(i % 3 == 0)}, [], [], [], {}) for i in range(n)]


def test_ips_equals_logged_when_target_equals_behavior():
    rows = _rows()
    out = ips_estimate(rows, lambda r: {r.action: r.prob})
    assert out["n"] == len(rows) - 1
    assert out["value"] == pytest.approx(out["logged_value"])
    assert out["ess"] == pytest.approx(out["n"])


def test_ips_clip():
    rows = _rows()
    big = ips_estimate(rows, lambda r: {r.action: 50.0}, clip=3.0)
    ref = ips_estimate(rows, lambda r: {r.action: 1.5}, clip=3.0)   # ratio 3.0 exactly
    assert big["value"] == pytest.approx(3.0 * big["logged_value"])
    assert big["value"] == pytest.approx(ref["value"])


def test_ips_counts_only_decision_ticks(tmp_path):
    from pathlib import Path
    from engrama.lab.explog import read_log
    from engrama.lab.runtime import run_days
    recipe = Path(__file__).resolve().parents[2] / "recipes" / "minimal-v1.toml"
    log = tmp_path / "l.db"
    run_days(recipe, 0.05, "attentive", 1, 2.0, log)
    rows = list(read_log(log))
    decisions = sum(1 for r in rows[:-1] if r.decided)
    assert 0 < decisions < len(rows) - 1
    out = ips_estimate(rows, lambda r: {r.action: r.prob})
    assert out["n"] == decisions
