"""Where the app keeps its data. Pure functions: environment, platform and home are injected."""
from __future__ import annotations
import shutil
from pathlib import Path
from typing import Mapping


def is_dev_checkout(package_root: Path) -> bool:
    """The package sits in a git checkout of the project: `<root>/.git` and `<root>/pyproject.toml` exist."""
    repo = Path(package_root).parent
    return (repo / ".git").exists() and (repo / "pyproject.toml").is_file()


def os_data_dir(env: Mapping[str, str], platform: str, home: Path) -> Path:
    home = Path(home)
    if platform == "win32":
        appdata = env.get("APPDATA")
        base = Path(appdata) if appdata else home / "AppData" / "Roaming"
        return base / "Engrama"
    if platform == "darwin":
        return home / "Library" / "Application Support" / "Engrama"
    xdg = env.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else home / ".local" / "share"
    return base / "engrama"


def resolve_data_dir(cli_arg, env: Mapping[str, str], platform: str, home: Path, package_root: Path) -> Path:
    """--data-dir > ENGRAMA_DATA_DIR > dev checkout (<repo>/data) > the OS data folder."""
    if cli_arg:
        return Path(cli_arg)
    if env.get("ENGRAMA_DATA_DIR"):
        return Path(env["ENGRAMA_DATA_DIR"])
    if is_dev_checkout(package_root):
        return Path(package_root).parent / "data"
    return os_data_dir(env, platform, home)


def has_save(data_dir: Path) -> bool:
    d = Path(data_dir)
    save = d / "save"
    return (d / "host.json").exists() or (save.is_dir() and any(save.iterdir()))


def legacy_save_dir(package_root: Path) -> Path | None:
    """`<repo>/data` next to the package, if it holds a save (the pre-M15 location)."""
    legacy = Path(package_root).parent / "data"
    return legacy if (legacy / "save").is_dir() and has_save(legacy) else None


def migrate_data_dir(src: Path, dst: Path) -> str:
    """Copy (never move) an old data dir into `dst`. Returns "ok", "missing" or "has_save"."""
    src, dst = Path(src), Path(dst)
    if not src.is_dir():
        return "missing"
    if has_save(dst):
        return "has_save"
    if src.resolve() == dst.resolve():
        return "has_save"
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("engrama.lock"))
    return "ok"
