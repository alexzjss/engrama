from pathlib import Path


def pytest_configure(config):
    if not config.option.basetemp:
        config.option.basetemp = Path(__file__).resolve().parents[1] / ".pytest_tmp"
