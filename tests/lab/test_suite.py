import json
from pathlib import Path
import pytest
from engrama.lab.cli import main
from engrama.lab.suite import (MD_METRICS, PRESETS, RoutineUser, RunSpec, run_one, run_suite, specs_from,
                               summarize, to_markdown)

ROOT = Path(__file__).resolve().parents[2]
DEF = ROOT / "engrama" / "recipes" / "default-v1.toml"
MIN = ROOT / "engrama" / "recipes" / "minimal-v1.toml"
FIXTURE = ROOT / "tests" / "fixtures" / "m6_sim_1d_seed1_attentive.json"


def _strip(runs):
    return [{k: v for k, v in r.items() if k != "module_ms"} for r in runs]


def test_baseline_matches_sim():
    got = json.loads(json.dumps(run_one(RunSpec(DEF, "attentive", 1, 1.0))["metrics"]))
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert {k: got[k] for k in fixture} == fixture


def test_routine_user_matches_m2_copy():
    from tests.test_m2_acceptance import _RoutineUser
    a, b = RoutineUser(60.0), _RoutineUser(60.0)
    for i in range(2 * 1440):
        t = 8 * 3600 + i * 60.0
        ea, eb = a.events(t, 60.0, {}), b.events(t, 60.0, {})
        assert [(o.t, o.kind, o.data) for o in ea] == [(o.t, o.kind, o.data) for o in eb]
    assert a.state_dict() == {}


@pytest.mark.slow
def test_jobs_do_not_change_results():
    specs = [RunSpec(r, "attentive", s, 1.0) for r in (DEF, MIN) for s in (1, 2)]
    seq, par = run_suite(specs, jobs=1), run_suite(specs, jobs=2)
    assert _strip(seq) == _strip(par)
    assert json.dumps(_strip(seq)) == json.dumps(_strip(par))
    assert all(r["module_ms"] for r in par)


def test_deterministic_rerun():
    s = RunSpec(MIN, "routine", 1, 0.5)
    assert _strip([run_one(s)]) == _strip([run_one(s)])


def test_rebirth_runs_and_routine_metrics():
    r = run_one(RunSpec(MIN, "neglectful", 1, 8.0, dt=300.0))
    assert r["metrics"]["lives"]["generations_finished"] >= 1
    assert set(r["metrics"]) >= {"return_per_day", "decision_entropy", "switch_rate", "pred_brier",
                                 "need_satisfaction", "world_error_mean", "lab_metrics"}


def _run(recipe, profile, seed, **m):
    return {"recipe": recipe, "profile": profile, "seed": seed, "days": 1.0, "metrics": m, "module_ms": {"a": 1.0}}


def test_summarize_paired_diff_and_consistent_sign():
    runs = [_run("default-v1", "attentive", s, x=v, nest={"y": 1.0}) for s, v in ((1, 1.0), (2, 2.0), (3, 3.0))]
    runs += [_run("exp", "attentive", s, x=v, nest={"y": 1.0}) for s, v in ((1, 1.5), (2, 2.5), (3, 2.0))]
    runs += [_run("mix", "attentive", s, x=v, nest={"y": 1.0}) for s, v in ((1, 2.0), (2, 1.0), (3, 4.0))]
    sm = summarize(runs)
    b = sm["by_recipe"]["default-v1"]["attentive"]["x"]
    assert b["mean"] == pytest.approx(2.0) and b["n"] == 3 and b["sd"] == pytest.approx(1.0) and b["values"] == [1.0, 2.0, 3.0]
    assert "nest/y" in sm["by_recipe"]["exp"]["attentive"]
    e = sm["vs_baseline"]["exp"]["attentive"]["x"]
    assert e["diff"] == pytest.approx((0.5 + 0.5 - 1.0) / 3) and e["consistent_sign"] is False
    m = sm["vs_baseline"]["mix"]["attentive"]["x"]
    assert m["diff"] == pytest.approx((1 - 1 + 1) / 3) and m["consistent_sign"] is False
    runs2 = runs[:3] + [_run("up", "attentive", s, x=v) for s, v in ((1, 1.1), (2, 2.1), (3, 3.1))]
    u = summarize(runs2)["vs_baseline"]["up"]["attentive"]["x"]
    assert u["diff"] == pytest.approx(0.1) and u["consistent_sign"] is True
    assert "default-v1" not in sm["vs_baseline"]


def test_markdown_has_one_table_per_profile():
    runs = [_run(r, p, s, wellbeing=float(s) + (r == "exp"), need_satisfaction=0.5)
            for r in ("default-v1", "exp") for p in ("attentive", "absent") for s in (1, 2)]
    md = to_markdown(summarize(runs))
    assert md.count("### ") == 2 and "### attentive" in md and "### absent" in md
    assert "| exp |" in md and "*" in md and "±" in md
    assert MD_METRICS[0] in md


def test_specs_from_routine_days_and_preset():
    sp = specs_from({"recipes": [MIN], "profiles": ["attentive", "routine"], "seeds": [1, 2], "days": 7})
    assert len(sp) == 4 and {s.days for s in sp if s.profile == "routine"} == {4.0}
    assert {s.days for s in sp if s.profile == "attentive"} == {7.0}
    full = specs_from("m10")
    assert len(PRESETS["m10"]["recipes"]) == 8 and len(full) == 8 * 4 * 3


def test_cli_suite_small(tmp_path, capsys):
    out, md = tmp_path / "x.json", tmp_path / "x.md"
    assert main(["suite", "--recipes", "default-v1", "minimal-v1", "--profiles", "attentive", "--seeds", "1",
                 "--days", "0.5", "--out", str(out), "--md", str(md)]) == 0
    d = json.loads(out.read_text())
    assert [r["recipe"] for r in d["runs"]] == ["default-v1", "minimal-v1"]
    assert "minimal-v1" in d["summary"]["vs_baseline"]
    assert "### attentive" in md.read_text()
    assert capsys.readouterr().out == ""


def test_sim_and_compare_output_unchanged(capsys):
    assert main(["sim", "--recipe", str(DEF), "--days", "1", "--seed", "1", "--profile", "attentive"]) == 0
    assert json.loads(capsys.readouterr().out) == json.loads(FIXTURE.read_text(encoding="utf-8"))
