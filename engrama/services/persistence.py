"""Atomic, pickle-free persistence: arrays in .npz, everything else in .json."""
from __future__ import annotations

import json
import os
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

BACKUPS = "backups"
KEEP_BACKUPS = 7
_ARRAY_KEY = "__array__"


class SaveCorrupted(Exception):
    pass


def _split(obj: Any, path: str, arrays: dict[str, np.ndarray]) -> Any:
    if isinstance(obj, np.ndarray):
        arrays[path] = obj
        return {_ARRAY_KEY: path}
    if isinstance(obj, dict):
        return {str(k): _split(v, f"{path}.{k}" if path else str(k), arrays) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_split(v, f"{path}.{i}" if path else str(i), arrays) for i, v in enumerate(obj)]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def _join(obj: Any, arrays: dict[str, np.ndarray]) -> Any:
    if isinstance(obj, dict):
        if set(obj) == {_ARRAY_KEY}:
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
    arrays: dict[str, np.ndarray] = {}
    skeleton = _split(d, "", arrays)
    tmp_npz, tmp_js = _tmp(npz), _tmp(js)
    try:
        with open(tmp_npz, "wb") as f:
            np.savez(f, **arrays)
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
    except (OSError, ValueError, KeyError) as e:
        raise SaveCorrupted(f"{path_base}: {e}") from e


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
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
    for old in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.endswith(".tmp"))[:-KEEP_BACKUPS]:
        shutil.rmtree(old, ignore_errors=True)


def save_run(save_dir: Path, kernel_state: dict, modules: dict[str, dict], meta: dict,
             *, today: date | None = None) -> None:
    save_dir = Path(save_dir)
    for name, state in modules.items():
        save_state_dict(save_dir / "modules" / name, state)
    _write_json(save_dir / "kernel.json", kernel_state)
    _write_json(save_dir / "meta.json", meta)
    _backup(save_dir, today or date.today())


def _load_dir(d: Path) -> tuple[dict, dict[str, dict], dict]:
    kernel = _read_json(d / "kernel.json")
    meta = _read_json(d / "meta.json")
    mdir = d / "modules"
    names = sorted(p.stem for p in mdir.glob("*.json")) if mdir.is_dir() else []
    return kernel, {n: load_state_dict(mdir / n) for n in names}, meta


def load_run(save_dir: Path) -> tuple[dict, dict[str, dict], dict]:
    save_dir = Path(save_dir)
    try:
        return _load_dir(save_dir)
    except SaveCorrupted as first:
        root = save_dir / BACKUPS
        cands = sorted((p for p in root.iterdir() if p.is_dir()), reverse=True) if root.is_dir() else []
        for b in cands:
            try:
                return _load_dir(b)
            except SaveCorrupted:
                continue
        raise first


def rng_state(rng: np.random.Generator) -> dict:
    return rng.bit_generator.state


def rng_from_state(d: dict) -> np.random.Generator:
    bg = getattr(np.random, d["bit_generator"])()
    bg.state = d
    return np.random.Generator(bg)
