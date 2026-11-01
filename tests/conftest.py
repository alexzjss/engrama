import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def pytest_configure(config):
    if not config.option.basetemp:
        config.option.basetemp = Path(__file__).resolve().parents[1] / ".pytest_tmp"
