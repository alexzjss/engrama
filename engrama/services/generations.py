"""Generation registry (data/generations.json) and per-generation archive folders."""
from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenerationRecord:
    n: int
    lineage: tuple[str, ...]
    seed: int
    born_wall: float
    died_wall: float
    days: float
    cause: str
    ancestral: tuple[str, ...]


def _from_dict(d: dict) -> GenerationRecord:
    return GenerationRecord(
        n=int(d["n"]), lineage=tuple(str(x) for x in d.get("lineage", ())), seed=int(d.get("seed", 0)),
        born_wall=float(d.get("born_wall", 0.0)), died_wall=float(d.get("died_wall", 0.0)),
        days=float(d.get("days", 0.0)), cause=str(d.get("cause", "")),
        ancestral=tuple(str(x) for x in d.get("ancestral", ())))


def load_generations(path: Path) -> list[GenerationRecord]:
    """Missing or corrupt file -> []; unreadable entries are skipped."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
    except Exception:
        return []
    out = []
    for d in data:
        try:
            out.append(_from_dict(d))
        except Exception:
            log.warning("skipping bad generation entry")
    return out


def append_generation(path: Path, rec: GenerationRecord) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    items = [asdict(r) for r in load_generations(path)] + [asdict(rec)]
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def delete_generation_archive(data_dir: Path, n: int) -> None:
    """Remove data/generations/<n>/ (memory and save copy); the record stays."""
    shutil.rmtree(Path(data_dir) / "generations" / str(int(n)), ignore_errors=True)
