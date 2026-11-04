"""Calibrate the semantic thresholds (SEM_MIN_SIM, FACT_MIN_SIM, TOPIC_MIN_SIM) on a labelled pairs file (M13 T2).

Each pair is a query and a memory with a ``match`` label. Both sides are embedded with the app's own
Ollama client (``OllamaClient.embed``) and the same preprocessing the app applies:

- query side (service.py ``_qvec`` -> ``Embedder.query``): the raw query text, the family query prefix
  (e.g. ``task: search result | query: `` for embeddinggemma), cut to ``EMBED_MAX_CHARS``;
- memory side (store/vectors.py -> ``_vtext``, then ``Embedder.documents``): digits removed, the family
  document prefix, cut to ``EMBED_MAX_CHARS``; the vector is stored as float16 and read back as float32
  (store/vectors.py ``put_vectors`` / ``_matrix``), so cosine matches the app.

For each kind it sweeps thresholds 0.30..0.90 (step 0.01) and reports precision, recall and F1, the
best-F1 threshold, the lowest threshold with precision >= 0.90 (and its recall), a per-language breakdown
at those thresholds and at the current app value, and a 10-bin text histogram of cosine for positives
and negatives.

Usage:
    python tools/calibrate_sem.py [--pairs tools/data/sem_pairs.jsonl] [--model embeddinggemma]
                                  [--cache CACHE.json] [--out RESULT.json] [--md RESULT.md]

Exit codes: 0 done; 1 bad pairs file or invalid embeddings; 2 Ollama unreachable, timed out or model missing.
The Markdown report is always printed to stdout.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engrama.config import Config  # noqa: E402
from engrama.services.language.client import LLMOffline, LLMTimeout, OllamaClient  # noqa: E402
from engrama.services.language.embedder import PREFIXES, Embedder, family, installed  # noqa: E402
from engrama.services.memory import (EMBED_BATCH, EMBED_BATCH_TIMEOUT_S, EMBED_MAX_CHARS,  # noqa: E402
                                     FACT_MIN_SIM, SEM_MIN_SIM, TOPIC_MIN_SIM)
from engrama.services.memory.store._util import _unit, _vtext  # noqa: E402

KINDS = ("episode", "fact", "topic")
CURRENT = {"episode": SEM_MIN_SIM, "fact": FACT_MIN_SIM, "topic": TOPIC_MIN_SIM}
LANG_ORDER = ("pt", "en", "cross")
GRID = tuple(round(0.30 + i * 0.01, 2) for i in range(61))
P_TARGET = 0.90
HIST_EDGES = np.linspace(0.0, 1.0, 11)
DEFAULT_PAIRS = ROOT / "tools" / "data" / "sem_pairs.jsonl"
CACHE_SEP = "\x1f"


class CalibrationError(Exception):
    """Bad input or invalid embedding response (exit 1)."""


class OllamaUnavailable(Exception):
    """Ollama unreachable, timed out or without the model (exit 2)."""


# ---------------------------------------------------------------- input

def load_pairs(path: Path) -> list[dict]:
    if not path.exists():
        raise CalibrationError(f"pairs file not found: {path}")
    pairs = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            p = json.loads(line)
        except json.JSONDecodeError as e:
            raise CalibrationError(f"{path}:{n}: invalid JSON ({e})") from e
        ok = (isinstance(p, dict) and p.get("kind") in KINDS and isinstance(p.get("match"), bool)
              and isinstance(p.get("query"), str) and p["query"].strip()
              and isinstance(p.get("memory"), str) and p["memory"].strip())
        if not ok:
            raise CalibrationError(f"{path}:{n}: needs kind in {KINDS}, boolean match, non-empty query and memory")
        pairs.append({"kind": p["kind"], "query": p["query"], "memory": p["memory"],
                      "match": p["match"], "lang": str(p.get("lang", "unknown"))})
    if not pairs:
        raise CalibrationError(f"{path}: no pairs")
    return pairs


def load_cache(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        print(f"warning: ignoring unreadable cache {path}", file=sys.stderr)
        return {}


def save_cache(path: Path | None, cache: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- embeddings

def prepared(role: str, text: str, model: str) -> str:
    """Text as the app sends it to Ollama: family prefix, then the cut (Embedder._call)."""
    prefix = PREFIXES.get(family(model), ("", ""))[0 if role == "query" else 1]
    return prefix + text[:EMBED_MAX_CHARS]


def _key(model: str, text: str) -> str:
    return f"{model}{CACHE_SEP}{text}"


def embed_missing(client, model: str, texts: list[str], cache: dict, timeout: float) -> None:
    """Embed the texts not in ``cache`` in batches of EMBED_BATCH; store unit float32 vectors as lists."""
    todo = list(dict.fromkeys(t for t in texts if _key(model, t) not in cache))
    for i in range(0, len(todo), EMBED_BATCH):
        batch = todo[i:i + EMBED_BATCH]
        vecs = Embedder._validate(client.embed(model, batch, timeout), len(batch))
        if vecs is None:
            raise CalibrationError("Ollama returned an invalid embedding batch")
        for t, v in zip(batch, vecs):
            cache[_key(model, t)] = v.tolist()


def score_pairs(client, model: str, pairs: list[dict], cache: dict,
                timeout: float = EMBED_BATCH_TIMEOUT_S) -> list[dict]:
    """Cosine per pair, with the app's query and memory preprocessing."""
    q_texts, m_texts = [], []
    for p in pairs:
        mem = _vtext(p["memory"])
        if not mem:
            raise CalibrationError(f"memory empty after cleaning: {p['memory']!r}")
        q_texts.append(prepared("query", p["query"], model))
        m_texts.append(prepared("memory", mem, model))
    embed_missing(client, model, q_texts + m_texts, cache, timeout)
    out = []
    for p, qt, mt in zip(pairs, q_texts, m_texts):
        q = _unit(np.asarray(cache[_key(model, qt)], dtype=np.float32))
        m = _unit(np.asarray(cache[_key(model, mt)], dtype=np.float32))
        if q is None or m is None:
            raise CalibrationError(f"empty vector for pair {p['query']!r} / {p['memory']!r}")
        # Stored as float16 and read back as float32 (put_vectors / _matrix).
        m = _unit(m.astype(np.float16).astype(np.float32))
        out.append({**p, "cos": float(np.dot(q, m))})
    return out


# ---------------------------------------------------------------- metrics

def confusion(scores: np.ndarray, labels: np.ndarray, thr: float) -> dict:
    """Counts and metrics for ``score >= thr`` (as recall.py / _sem use). None = undefined."""
    pred = scores >= thr
    tp = int(np.sum(pred & labels))
    fp = int(np.sum(pred & ~labels))
    fn = int(np.sum(~pred & labels))
    tn = int(np.sum(~pred & ~labels))
    return {
        "threshold": float(thr), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
    }


def _arrays(recs: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    return (np.array([r["cos"] for r in recs], dtype=np.float64),
            np.array([r["match"] for r in recs], dtype=bool))


def per_lang(recs: list[dict], thr: float) -> dict:
    langs = sorted({r["lang"] for r in recs},
                   key=lambda x: (LANG_ORDER.index(x) if x in LANG_ORDER else len(LANG_ORDER), x))
    out = {}
    for lang in langs:
        sub = [r for r in recs if r["lang"] == lang]
        s, lab = _arrays(sub)
        out[lang] = {"n": len(sub), "positives": int(lab.sum()), **confusion(s, lab, thr)}
    return out


def histogram(recs: list[dict]) -> dict:
    out = {"edges": [round(float(e), 2) for e in HIST_EDGES], "clipped_to": [0.0, 1.0]}
    for label, name in ((True, "positives"), (False, "negatives")):
        s = np.clip(np.array([r["cos"] for r in recs if r["match"] == label], dtype=np.float64), 0.0, 1.0)
        out[name] = np.histogram(s, HIST_EDGES)[0].tolist() if s.size else [0] * (len(HIST_EDGES) - 1)
    return out


def analyze_kind(recs: list[dict], current: float) -> dict:
    scores, labels = _arrays(recs)
    sweep = [confusion(scores, labels, t) for t in GRID]
    best = sweep[0]
    for s in sweep[1:]:
        if s["f1"] > best["f1"]:          # ties keep the lowest threshold
            best = s
    p90 = next((s for s in sweep if s["precision"] is not None and s["precision"] >= P_TARGET), None)
    return {
        "n": len(recs),
        "positives": int(labels.sum()),
        "negatives": int(len(labels) - labels.sum()),
        "current": confusion(scores, labels, current),
        "best_f1": best,
        "p90": p90,
        "per_lang": {
            "best_f1": per_lang(recs, best["threshold"]),
            "p90": per_lang(recs, p90["threshold"]) if p90 else None,
            "current": per_lang(recs, current),
        },
        "sweep": sweep,
        "histogram": histogram(recs),
    }


def analyze(scored: list[dict], model: str, pairs_path: Path) -> dict:
    kinds = {k: analyze_kind([r for r in scored if r["kind"] == k], CURRENT[k])
             for k in KINDS if any(r["kind"] == k for r in scored)}
    return {
        "model": model,
        "pairs": str(pairs_path),
        "n_pairs": len(scored),
        "grid": {"min": GRID[0], "max": GRID[-1], "step": 0.01},
        "missing_kinds": [k for k in KINDS if k not in kinds],
        "kinds": kinds,
        "scores": [{k: r[k] for k in ("kind", "query", "memory", "match", "lang", "cos")} for r in scored],
    }


# ---------------------------------------------------------------- report

def _f(x) -> str:
    return "–" if x is None else f"{x:.3f}"


def _hist_block(name: str, h: dict) -> list[str]:
    width = 30
    top = max(max(h["positives"]), max(h["negatives"]), 1)
    lines = [f"{name} (cosine clipped to [0, 1])", "bin          positives                 negatives"]
    edges = h["edges"]
    for i in range(len(edges) - 1):
        p, n = h["positives"][i], h["negatives"][i]
        lines.append(f"{edges[i]:.1f}-{edges[i + 1]:.1f}  "
                     f"{('#' * round(width * p / top)).ljust(width)} {p:>4}  "
                     f"{('#' * round(width * n / top)).ljust(width)} {n:>4}")
    return lines


def to_markdown(res: dict) -> str:
    g = res["grid"]
    L = ["# Semantic threshold calibration", "",
         f"- Model: `{res['model']}`",
         f"- Pairs: `{res['pairs']}` ({res['n_pairs']} pairs)",
         f"- Thresholds {g['min']:.2f}..{g['max']:.2f} step {g['step']:.2f}; predicted match when cosine >= threshold",
         "- Memory vectors stored as float16 and read back, as in the app", ""]
    if res["missing_kinds"]:
        L += [f"- No pairs for: {', '.join(res['missing_kinds'])}", ""]
    L += ["## Summary", "",
          "| kind | n (pos/neg) | current | P | R | F1 | best-F1 thr | P | R | F1 | P>=0.90 thr | P | R |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, r in res["kinds"].items():
        c, b, p = r["current"], r["best_f1"], r["p90"]
        pc = (f"{p['threshold']:.2f} | {_f(p['precision'])} | {_f(p['recall'])}" if p else "– | – | –")
        L.append(f"| {k} | {r['n']} ({r['positives']}/{r['negatives']}) | {c['threshold']:.2f} | "
                 f"{_f(c['precision'])} | {_f(c['recall'])} | {_f(c['f1'])} | "
                 f"{b['threshold']:.2f} | {_f(b['precision'])} | {_f(b['recall'])} | {_f(b['f1'])} | {pc} |")
    L += ["", "## Per language", "",
          "| kind | threshold | lang | n | pos | P | R | F1 |", "|---|---|---|---|---|---|---|---|"]
    for k, r in res["kinds"].items():
        sets = [(f"best F1 {r['best_f1']['threshold']:.2f}", r["per_lang"]["best_f1"]),
                (f"P>=0.90 {r['p90']['threshold']:.2f}" if r["p90"] else "P>=0.90 –", r["per_lang"]["p90"]),
                (f"current {r['current']['threshold']:.2f}", r["per_lang"]["current"])]
        for label, block in sets:
            if not block:
                L.append(f"| {k} | {label} | – | – | – | – | – | – |")
                continue
            for lang, m in block.items():
                L.append(f"| {k} | {label} | {lang} | {m['n']} | {m['positives']} | {_f(m['precision'])} | "
                         f"{_f(m['recall'])} | {_f(m['f1'])} |")
    L += ["", "## Sweep (every 0.05)", "",
          "| kind | thr | TP | FP | FN | P | R | F1 |", "|---|---|---|---|---|---|---|---|"]
    for k, r in res["kinds"].items():
        for s in r["sweep"]:
            if round(s["threshold"] * 100) % 5 == 0:
                L.append(f"| {k} | {s['threshold']:.2f} | {s['tp']} | {s['fp']} | {s['fn']} | "
                         f"{_f(s['precision'])} | {_f(s['recall'])} | {_f(s['f1'])} |")
    L += ["", "## Histograms", ""]
    for k, r in res["kinds"].items():
        L += ["```text", *_hist_block(k, r["histogram"]), "```", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- run

def check_ollama(client, model: str) -> None:
    tags = client.tags()
    if tags is None:
        raise OllamaUnavailable(f"Ollama unreachable at {client.cfg.ollama_url}; start it and retry")
    if not installed(model, tags):
        raise OllamaUnavailable(f"model {model!r} is not installed in Ollama (ollama pull {model})")


def run(client, pairs_path: Path, model: str, cache_path: Path | None) -> dict:
    pairs = load_pairs(pairs_path)
    cache = load_cache(cache_path)
    try:
        scored = score_pairs(client, model, pairs, cache)
    finally:
        save_cache(cache_path, cache)
    return analyze(scored, model, pairs_path)


def main(argv: list[str] | None = None, client_factory: Callable = OllamaClient) -> int:
    ap = argparse.ArgumentParser(description="Calibrate SEM/FACT/TOPIC thresholds on a labelled pairs file.")
    ap.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS)
    ap.add_argument("--model", default="embeddinggemma")
    ap.add_argument("--cache", type=Path, default=None, help="JSON cache of embeddings (reruns are fast)")
    ap.add_argument("--out", type=Path, default=None, help="write all numbers as JSON")
    ap.add_argument("--md", type=Path, default=None, help="write the Markdown tables")
    args = ap.parse_args(argv)
    client = client_factory(Config())
    try:
        check_ollama(client, args.model)
        res = run(client, args.pairs, args.model, args.cache)
    except OllamaUnavailable as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except (LLMOffline, LLMTimeout) as e:
        print(f"error: Ollama unreachable or timed out ({e})", file=sys.stderr)
        return 2
    except CalibrationError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    md = to_markdown(res)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(md + "\n", encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
