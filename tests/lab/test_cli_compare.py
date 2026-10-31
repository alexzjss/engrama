import json
from pathlib import Path
from engrama.lab.cli import main

RECIPE = str(Path(__file__).resolve().parents[2] / "recipes" / "minimal-v1.toml")


def test_cli_compare_outputs_diff(capsys, tmp_path):
    b = tmp_path / "b.toml"
    b.write_text(Path(RECIPE).read_text().replace("temperature = 0.5", "temperature = 2.0"))
    assert main(["compare", "--a", RECIPE, "--b", str(b), "--days", "0.5", "--seed", "1"]) == 0
    m = json.loads(capsys.readouterr().out)
    assert set(m) == {"a", "b", "diff"}
    assert m["diff"]["wellbeing"] == m["b"]["wellbeing"] - m["a"]["wellbeing"]
    assert m["diff"]["behavior_entropy"] != 0


def test_cli_replay_summary(capsys, tmp_path):
    log = tmp_path / "l.db"
    assert main(["sim", "--recipe", RECIPE, "--days", "0.3", "--log", str(log)]) == 0
    capsys.readouterr()
    assert main(["replay", "--log", str(log), "--module", "drives.needs", "--param", "x=1.5"]) == 0
    s = json.loads(capsys.readouterr().out)
    assert set(s["drives"]) == {"mean", "min", "max"}
