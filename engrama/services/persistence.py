"""Atomic, pickle-free persistence: arrays in .npz, everything else in .json."""
from __future__ import annotations

import json
import os
import re
import shutil
import uuid
import warnings
import zipfile
import zlib
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

BACKUPS = "backups"
KEEP_BACKUPS = 7
_ARRAY_KEY = "__array__"
_DATE_DIR = re.compile(r"\d{4}-\d{2}-\d{2}")


SAVE_VERSION = 1


class SaveCorrupted(Exception):
    pass


class SaveVersionError(Exception):
    """A save written by a newer schema. Never a reason to fall back to an older backup."""


# Only these mean "the files on disk are damaged"; anything else is a bug and must propagate.
_CORRUPTION = (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError, KeyError, EOFError,
               zlib.error, NotImplementedError)   # the last two: how zipfile reports flipped bytes


def _split(obj: Any, path: list, arrays: list[np.ndarray]) -> Any:
    """Arrays go to `arrays`; the JSON marker keeps the npz name and the key path."""
    if isinstance(obj, np.ndarray):
        arrays.append(obj)
        return {_ARRAY_KEY: f"a{len(arrays) - 1}", "path": path}
    if isinstance(obj, dict):
        return {str(k): _split(v, path + [str(k)], arrays) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_split(v, path + [i], arrays) for i, v in enumerate(obj)]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def _join(obj: Any, arrays: dict[str, np.ndarray]) -> Any:
    if isinstance(obj, dict):
        if set(obj) == {_ARRAY_KEY, "path"}:
            return arrays[obj[_ARRAY_KEY]]
        return {k: _join(v, arrays) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_join(v, arrays) for v in obj]
    return obj


def _tmp(path: Path) -> Path:
    return path.with_name(path.name + ".tmp")


def _write_json_tmp(path: Path, obj: Any) -> Path:
    tmp = _tmp(path)
    tmp.write_text(json.dumps(obj), encoding="utf-8")
    return tmp


def _cleanup(*tmps: Path) -> None:
    for t in tmps:
        t.unlink(missing_ok=True)


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _write_json_tmp(path, obj)
    try:
        os.replace(tmp, path)
    except BaseException:
        _cleanup(tmp)
        raise


def save_state_dict(path_base: Path, d: dict) -> None:
    path_base = Path(path_base)
    path_base.parent.mkdir(parents=True, exist_ok=True)
    npz, js = path_base.with_name(path_base.name + ".npz"), path_base.with_name(path_base.name + ".json")
    arrays: list[np.ndarray] = []
    skeleton = _split(d, [], arrays)
    tmp_npz, tmp_js = _tmp(npz), _tmp(js)
    try:
        with open(tmp_npz, "wb") as f:
            np.savez(f, **{f"a{i}": a for i, a in enumerate(arrays)})
        _write_json_tmp(js, skeleton)
        os.replace(tmp_npz, npz)
        os.replace(tmp_js, js)
    except BaseException:
        _cleanup(tmp_npz, tmp_js)
        raise


def load_state_dict(path_base: Path) -> dict:
    path_base = Path(path_base)
    npz, js = path_base.with_name(path_base.name + ".npz"), path_base.with_name(path_base.name + ".json")
    try:
        skeleton = json.loads(js.read_text(encoding="utf-8"))
        with np.load(npz, allow_pickle=False) as z:
            arrays = {k: z[k] for k in z.files}
        return _join(skeleton, arrays)
    except _CORRUPTION as e:
        raise SaveCorrupted(f"{path_base}: {e}") from e


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except _CORRUPTION as e:
        raise SaveCorrupted(f"{path}: {e}") from e


def _backup(save_dir: Path, today: date) -> None:
    root = save_dir / BACKUPS
    dest = root / today.isoformat()
    if dest.exists():
        return
    tmp = root / (today.isoformat() + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(save_dir, tmp, ignore=shutil.ignore_patterns(BACKUPS, "*.tmp"))
    os.replace(tmp, dest)
    for old in sorted(p for p in root.iterdir() if p.is_dir() and _DATE_DIR.fullmatch(p.name))[:-KEEP_BACKUPS]:
        shutil.rmtree(old, ignore_errors=True)


def _sibling(save_dir: Path, tag: str) -> Path:
    return save_dir.with_name(f".{save_dir.name}.{tag}-{uuid.uuid4().hex[:8]}")


def _recover(save_dir: Path) -> None:
    """A crash between the two renames of a save leaves `.<name>.old-*` and no save_dir: put it back."""
    if save_dir.exists():
        return
    olds = sorted(save_dir.parent.glob(f".{save_dir.name}.old-*"), key=lambda p: p.stat().st_mtime)         if save_dir.parent.is_dir() else []
    if olds:
        os.replace(olds[-1], save_dir)


def save_run(save_dir: Path, kernel_state: dict, modules: dict[str, dict], meta: dict,
             *, today: date | None = None) -> None:
    """Write the whole save set into a staging directory next to save_dir, then swap it into place with
    directory renames, so a crash never leaves module files from one save beside a kernel from another."""
    save_dir = Path(save_dir)
    save_dir.parent.mkdir(parents=True, exist_ok=True)
    _recover(save_dir)
    stage = _sibling(save_dir, "staging")
    old: Path | None = None
    try:
        stage.mkdir()
        for name, state in modules.items():
            save_state_dict(stage / "modules" / name, state)
        _write_json(stage / "kernel.json", kernel_state)
        _write_json(stage / "meta.json", {**meta, "version": SAVE_VERSION})
        if save_dir.exists():
            old = _sibling(save_dir, "old")
            os.replace(save_dir, old)
        os.replace(stage, save_dir)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        if old is not None and not save_dir.exists():
            os.replace(old, save_dir)
        raise
    if old is not None:
        if (old / BACKUPS).is_dir():
            os.replace(old / BACKUPS, save_dir / BACKUPS)
        shutil.rmtree(old, ignore_errors=True)
    _backup(save_dir, today or date.today())


def _load_dir(d: Path) -> tuple[dict, dict[str, dict], dict]:
    try:
        kernel = _read_json(d / "kernel.json")
        meta = _read_json(d / "meta.json")
        if not isinstance(meta, dict) or not isinstance(kernel, dict):
            raise SaveCorrupted(f"{d}: kernel.json / meta.json must hold objects")
        if int(meta.get("version", SAVE_VERSION)) > SAVE_VERSION:
            raise SaveVersionError(f"{d}: save version {meta['version']} is newer than {SAVE_VERSION}")
        mdir = d / "modules"
        names = sorted(p.stem for p in mdir.glob("*.json")) if mdir.is_dir() else []
        return kernel, {n: load_state_dict(mdir / n) for n in names}, meta
    except _CORRUPTION as e:
        raise SaveCorrupted(f"{d}: {e}") from e


def load_run(save_dir: Path) -> tuple[dict, dict[str, dict], dict]:
    """Falls back to the newest readable backup ONLY when the save is damaged (SaveCorrupted), and says so."""
    save_dir = Path(save_dir)
    _recover(save_dir)
    try:
        return _load_dir(save_dir)
    except SaveCorrupted as first:
        root = save_dir / BACKUPS
        cands = sorted((p for p in root.iterdir() if p.is_dir() and _DATE_DIR.fullmatch(p.name)),
                       reverse=True) if root.is_dir() else []
        for b in cands:
            try:
                out = _load_dir(b)
            except SaveCorrupted:
                continue
            warnings.warn(f"save at {save_dir} is corrupt ({first}); loaded backup {b.name}", RuntimeWarning,
                          stacklevel=2)
            return out
        raise first


def rng_state(rng: np.random.Generator) -> dict:
    return rng.bit_generator.state


def rng_from_state(d: dict) -> np.random.Generator:
    bg = getattr(np.random, d["bit_generator"])()
    bg.state = d
    return np.random.Generator(bg)
