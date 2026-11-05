from pathlib import Path
import pytest
from engrama.lab.metrics import compute_metrics, life_metrics
from engrama.lab.runtime import run_days

RECIPE = Path(__file__).resolve().parents[2] / "engrama" / "recipes" / "minimal-v1.toml"


def _life(gen, days, cause, colds=0, sick=0.0, final=None, lineage=()):
    return {"generation": gen, "lineage": list(lineage), "days": days, "cause": cause, "colds": colds,
            "sick_hours": sick, "final_day": final, "seed": gen, "final_traits": []}


def test_metrics_per_generation():
    lives = [_life(1, 100.0, "old_age", 3, 20.0, 80.0, ("a", "b")),
             _life(2, 10.0, "neglect", 1, 30.0),
             _life(3, 2.0, "", 0, 0.0)]
    m = life_metrics(lives)
    assert [g["generation"] for g in m["per_generation"]] == [1, 2, 3]
    assert m["per_generation"][0]["lineage"] == ["a", "b"] and m["per_generation"][0]["final_day"] == 80.0
    assert m["generations_finished"] == 2 and m["life_days_mean"] == pytest.approx(55.0)
    assert m["colds_total"] == 4 and m["sick_hours_total"] == pytest.approx(50.0)
    assert m["deaths_by_cause"] == {"old_age": 1, "neglect": 1}
    assert "lives" not in compute_metrics([])
    assert compute_metrics([], lives)["lives"]["generations_finished"] == 2


def test_run_days_reports_lives():
    m = run_days(RECIPE, 0.5, "attentive", 1, 60.0, None)
    g = m["lives"]["per_generation"]
    assert len(g) == 1 and g[0]["generation"] == 1 and g[0]["cause"] == ""
    assert g[0]["days"] == pytest.approx(0.5, abs=0.01)
