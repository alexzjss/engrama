"""M15: a non-editable install carries recipes and i18n inside the package."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

PROBE = (
    "import engrama.resources as r\n"
    "print(r.__file__)\n"
    "print(len(list(r.recipes_dir().glob('*.toml'))))\n"
    "print(len(list(r.i18n_dir().glob('*.json'))))\n"
)


@pytest.mark.slow
def test_wheel_install_runs_from_other_cwd(tmp_path):
    uv = shutil.which("uv")
    if not uv:
        pytest.skip("uv not available")
    wheels = tmp_path / "wheels"
    leftovers = [d for d in (ROOT / "build", ROOT / "engrama.egg-info") if not d.exists()]
    try:
        subprocess.run([uv, "build", "--wheel", "--out-dir", str(wheels), str(ROOT)], check=True, capture_output=True,
                       timeout=300)
    except (subprocess.SubprocessError, OSError) as e:
        pytest.skip(f"cannot build wheel: {e}")
    finally:
        for d in leftovers:  # the in-tree build leaves these behind
            shutil.rmtree(d, ignore_errors=True)
    wheel = next(wheels.glob("engrama-*.whl"))
    venv = tmp_path / "venv"
    subprocess.run([uv, "venv", "--python", sys.executable, str(venv)], check=True, capture_output=True, timeout=120)
    win = os.name == "nt"
    py = venv / ("Scripts" if win else "bin") / ("python.exe" if win else "python")
    try:
        subprocess.run([uv, "pip", "install", "--python", str(py), str(wheel)], check=True, capture_output=True,
                       timeout=600)
    except subprocess.SubprocessError:
        pytest.skip("cannot install dependencies (network?)")
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()
    env = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
    env.pop("PYTHONPATH", None)
    probe = subprocess.run([str(py), "-c", PROBE], cwd=cwd, env=env, capture_output=True, text=True)
    assert probe.returncode == 0, probe.stderr
    where, n_recipes, n_i18n = probe.stdout.split()
    assert "site-packages" in where and int(n_recipes) >= 10 and int(n_i18n) == 2
    r = subprocess.run([str(py.parent / ("engrama.exe" if win else "engrama")), "--frames", "30", "--no-llm", "--data-dir", str(tmp_path / "data")],
                       cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
