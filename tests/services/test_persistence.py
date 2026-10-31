import json
import os
import shutil
from datetime import date, timedelta

import numpy as np
import pytest

from engrama.services import persistence as p


def _modules():
    return {"a": {"w": np.arange(6.0).reshape(2, 3), "n": 3}}


def _save(d, day=date(2026, 1, 1), kernel=None):
    p.save_run(d, kernel or {"tick": 1}, _modules(), {"version": 1, "seed": 7}, today=day)


def test_state_dict_roundtrip_nested_arrays_and_scalars(tmp_path):
    d = {
        "w": np.arange(6, dtype=np.float32).reshape(2, 3),
        "nest": {"a": np.ones(3, dtype=np.int64), "x": 1.5, "s": "hi", "none": None},
        "lst": [np.zeros(2), 3, {"k": np.arange(2)}],
        "np": np.float64(2.5),
        "ni": np.int32(4),
    }
    p.save_state_dict(tmp_path / "st", d)
    out = p.load_state_dict(tmp_path / "st")
    assert np.array_equal(out["w"], d["w"]) and out["w"].dtype == np.float32
    assert np.array_equal(out["nest"]["a"], d["nest"]["a"])
    assert out["nest"]["x"] == 1.5 and out["nest"]["s"] == "hi" and out["nest"]["none"] is None
    assert np.array_equal(out["lst"][0], np.zeros(2)) and out["lst"][1] == 3
    assert np.array_equal(out["lst"][2]["k"], np.arange(2))
    assert out["np"] == 2.5 and out["ni"] == 4


def test_atomic_no_partial_file_on_error(tmp_path, monkeypatch):
    p.save_state_dict(tmp_path / "st", {"a": np.ones(2), "v": 1})

    def boom(*a, **k):
        raise OSError("boom")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        p.save_state_dict(tmp_path / "st", {"a": np.zeros(2), "v": 2})
    monkeypatch.undo()
    out = p.load_state_dict(tmp_path / "st")
    assert out["v"] == 1 and np.array_equal(out["a"], np.ones(2))
    assert not [f for f in tmp_path.iterdir() if f.name.endswith(".tmp")]


def test_backup_rotation_keeps_7(tmp_path):
    for i in range(10):
        _save(tmp_path, date(2026, 1, 1) + timedelta(days=i))
    names = sorted(x.name for x in (tmp_path / "backups").iterdir())
    assert names == [(date(2026, 1, 4) + timedelta(days=i)).isoformat() for i in range(7)]
    _save(tmp_path, date(2026, 1, 10))  # same day: no new backup
    assert len(list((tmp_path / "backups").iterdir())) == 7


def test_run_roundtrip(tmp_path):
    _save(tmp_path)
    k, m, meta = p.load_run(tmp_path)
    assert k == {"tick": 1} and meta["seed"] == 7
    assert np.array_equal(m["a"]["w"], _modules()["a"]["w"]) and m["a"]["n"] == 3


def test_corrupt_kernel_json_falls_back_to_backup(tmp_path):
    _save(tmp_path, kernel={"tick": 1})
    (tmp_path / "kernel.json").write_text("{not json")
    k, m, meta = p.load_run(tmp_path)
    assert k == {"tick": 1} and "a" in m


def test_corrupt_without_backup_raises(tmp_path):
    _save(tmp_path)
    shutil.rmtree(tmp_path / "backups")
    (tmp_path / "kernel.json").write_text("{not json")
    with pytest.raises(p.SaveCorrupted):
        p.load_run(tmp_path)
    with pytest.raises(p.SaveCorrupted):
        p.load_run(tmp_path / "missing")


def test_rng_state_roundtrip_same_draws():
    rng = np.random.default_rng(42)
    rng.random(5)
    st = json.loads(json.dumps(p.rng_state(rng)))
    r2 = p.rng_from_state(st)
    assert np.array_equal(rng.random(10), r2.random(10))
