import json
from pathlib import Path
from engrama.lab.cli import main

RECIPE = str(Path(__file__).resolve().parents[2] / "recipes" / "minimal-v1.toml")


def test_cli_sim_smoke(capsys, tmp_path):
    assert main(["sim", "--recipe", RECIPE, "--days", "1", "--profile", "attentive", "--seed", "1",
                 "--dt", "60", "--log", str(tmp_path / "l.db"), "--save", str(tmp_path / "s")]) == 0
    m = json.loads(capsys.readouterr().out)
    assert "wellbeing" in m and m["ticks"] > 1000
    assert (tmp_path / "s" / "kernel.json").exists()
    assert main(["report", "--log", str(tmp_path / "l.db")]) == 0
    assert json.loads(capsys.readouterr().out) == m


def test_cli_sim_without_log(capsys):
    assert main(["sim", "--recipe", RECIPE, "--days", "0.2"]) == 0
    assert "wellbeing" in json.loads(capsys.readouterr().out)
