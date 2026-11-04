import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools import calibrate_sem as cs  # noqa: E402


class FakeClient:
    """Stands in for OllamaClient: vectors keyed by whether the text mentions 'cat'; records inputs."""

    def __init__(self, reachable=True, models=("embeddinggemma:latest",)):
        self.cfg = type("Cfg", (), {"ollama_url": "http://fake"})()
        self.reachable = reachable
        self.models = set(models)
        self.calls = []

    def tags(self):
        return set(self.models) if self.reachable else None

    def embed(self, model, texts, timeout):
        self.calls.append((model, list(texts)))
        return [[1.0, 0.0] if "cat" in t else [0.0, 1.0] for t in texts]


def _recs(pos, neg, kind="fact"):
    recs = [{"kind": kind, "query": "q", "memory": "m", "match": True, "lang": "en", "cos": c} for c in pos]
    recs += [{"kind": kind, "query": "q", "memory": "m", "match": False, "lang": "pt", "cos": c} for c in neg]
    return recs


def test_sweep_math_on_tiny_set():
    # positives 0.9, 0.8, 0.5; negatives 0.7, 0.4, 0.3
    res = cs.analyze_kind(_recs([0.9, 0.8, 0.5], [0.7, 0.4, 0.3]), current=0.6)
    assert len(res["sweep"]) == 61
    assert res["sweep"][0]["threshold"] == 0.15 and res["sweep"][-1]["threshold"] == 0.90
    at = {round(s["threshold"], 2): s for s in res["sweep"]}
    # 0.60: predicted 0.9, 0.8, 0.7 -> TP 2, FP 1, FN 1
    assert (at[0.6]["tp"], at[0.6]["fp"], at[0.6]["fn"]) == (2, 1, 1)
    assert at[0.6]["precision"] == pytest.approx(2 / 3) and at[0.6]["recall"] == pytest.approx(2 / 3)
    # 0.75: TP 2, FP 0, FN 1 -> P 1.0, R 2/3, F1 0.8
    assert at[0.75]["precision"] == 1.0 and at[0.75]["f1"] == pytest.approx(0.8)
    # best F1 = 6/7 (TP 3, FP 1) is reached from 0.41 to 0.50; ties keep the lowest threshold
    assert res["best_f1"]["threshold"] == 0.41
    assert res["best_f1"]["f1"] == pytest.approx(6 / 7)
    # lowest threshold with precision >= 0.90 is 0.71 (0.70 still admits the 0.7 negative)
    assert res["p90"]["threshold"] == 0.71
    assert res["p90"]["precision"] == 1.0 and res["p90"]["recall"] == pytest.approx(2 / 3)
    assert res["current"]["threshold"] == 0.6 and res["current"]["tp"] == 2
    assert res["per_lang"]["current"]["en"]["tp"] == 2 and res["per_lang"]["current"]["pt"]["fp"] == 1


def test_histogram_counts_and_clipping():
    h = cs.histogram(_recs([0.95, 1.0, 0.05], [-0.2, 0.55]))
    assert sum(h["positives"]) == 3 and sum(h["negatives"]) == 2
    assert h["positives"][9] == 2 and h["positives"][0] == 1
    assert h["negatives"][0] == 1 and h["negatives"][5] == 1


def test_no_positives_gives_undefined_recall_not_crash():
    res = cs.analyze_kind(_recs([], [0.2, 0.9]), current=0.6)
    assert res["current"]["recall"] is None
    assert res["p90"] is None   # nothing predicted with precision >= 0.90


def test_pairs_end_to_end_with_fake_client(tmp_path):
    pairs = tmp_path / "pairs.jsonl"
    rows = [
        {"kind": "fact", "query": "tenho um cat", "memory": "pet: cat 12", "match": True, "lang": "pt"},
        {"kind": "fact", "query": "my cat", "memory": "pet: dog", "match": False, "lang": "en"},
        {"kind": "episode", "query": "cat?", "memory": "conversa sobre cat 3 vezes", "match": True, "lang": "cross"},
        {"kind": "topic", "query": "cat", "memory": "dog", "match": False, "lang": "en"},
    ]
    pairs.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    cache = tmp_path / "cache" / "emb.json"
    client = FakeClient()
    res = cs.run(client, pairs, "embeddinggemma", cache)

    assert res["n_pairs"] == 4 and res["missing_kinds"] == []
    # preprocessing: query prefix on queries, document prefix on memories, digits removed
    sent = [t for _, batch in client.calls for t in batch]
    assert "task: search result | query: tenho um cat" in sent
    assert "title: none | text: pet: cat" in sent
    assert "title: none | text: conversa sobre cat vezes" in sent   # digits removed like _vtext
    # perfect separation for every kind
    assert res["kinds"]["fact"]["best_f1"]["f1"] == 1.0
    assert res["kinds"]["fact"]["p90"]["threshold"] == cs.GRID[0]
    assert res["kinds"]["topic"]["current"]["fp"] == 0
    assert res["kinds"]["episode"]["current"]["tp"] == 1
    assert cache.exists() and len(json.loads(cache.read_text(encoding="utf-8"))) > 0

    # second run reuses the cache: no new embed calls for the same texts
    client2 = FakeClient()
    cs.run(client2, pairs, "embeddinggemma", cache)
    assert client2.calls == []


def test_main_exits_2_when_ollama_unreachable(tmp_path, capsys):
    pairs = tmp_path / "p.jsonl"
    pairs.write_text(json.dumps({"kind": "fact", "query": "a", "memory": "b", "match": True, "lang": "en"}) + "\n",
                     encoding="utf-8")
    rc = cs.main(["--pairs", str(pairs)], client_factory=lambda cfg: FakeClient(reachable=False))
    assert rc == 2
    assert "unreachable" in capsys.readouterr().err


def test_main_exits_2_when_model_missing(tmp_path, capsys):
    pairs = tmp_path / "p.jsonl"
    pairs.write_text(json.dumps({"kind": "fact", "query": "a", "memory": "b", "match": True, "lang": "en"}) + "\n",
                     encoding="utf-8")
    rc = cs.main(["--pairs", str(pairs), "--model", "nope"], client_factory=lambda cfg: FakeClient())
    assert rc == 2
    assert "not installed" in capsys.readouterr().err


def test_main_writes_json_and_markdown(tmp_path, capsys):
    pairs = tmp_path / "p.jsonl"
    pairs.write_text("\n".join(json.dumps(r) for r in [
        {"kind": "fact", "query": "cat", "memory": "cat", "match": True, "lang": "en"},
        {"kind": "fact", "query": "cat", "memory": "dog", "match": False, "lang": "en"},
    ]) + "\n", encoding="utf-8")
    out, md = tmp_path / "r.json", tmp_path / "r.md"
    rc = cs.main(["--pairs", str(pairs), "--out", str(out), "--md", str(md)],
                 client_factory=lambda cfg: FakeClient())
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["kinds"]["fact"]["current"]["threshold"] == cs.FACT_MIN_SIM
    assert "| fact |" in md.read_text(encoding="utf-8")
    assert "Summary" in capsys.readouterr().out
