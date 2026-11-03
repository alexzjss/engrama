import json
import re
import threading
import time

import numpy as np

from engrama.services import memory as memory_pkg
from engrama.services.memory.recall import recall
from tests.services.fake_embedder import CONCEPTS, FakeEmbedder
from tests.services.memory.golden_recall import CASES, FIXTURE, build_store, snapshot


def _cos(a, b):
    return float(np.dot(a, b))


def test_recall_matches_m8_golden(tmp_path):
    store = build_store(tmp_path / "memory.sqlite")
    try:
        current = snapshot(store)
    finally:
        store.close()
    golden = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(golden) == len(CASES)
    assert current == golden


def test_golden_covers_degradation_cases():
    golden = json.loads(FIXTURE.read_text(encoding="utf-8"))
    stages = {c["stage"] for c in golden}
    assert stages == {"egg", "baby", "child", "adult", "perfect", "final"}
    assert any(c["text"] == "" for c in golden)
    assert any(re.search(r"\d", c["text"]) for c in golden)
    langs = {c["lang"] for c in golden}
    assert langs == {"pt", "en"}


def test_fake_embedder_concepts():
    fe = FakeEmbedder()
    dog, pet, dog_en, work = fe.query("cachorro"), fe.query("bichinho"), fe.query("dog"), fe.query("trabalho")
    assert _cos(dog, pet) >= 0.7
    assert _cos(dog, dog_en) >= 0.7
    assert _cos(dog, work) <= 0.3
    assert len(CONCEPTS) == 12
    assert abs(float(np.linalg.norm(dog)) - 1.0) < 1e-9
    assert np.array_equal(fe.query("meu cachorro"), fe.query("meu cachorro"))
    empty = fe.query("")
    assert empty is not None and abs(float(np.linalg.norm(empty)) - 1.0) < 1e-9
    assert _cos(empty, dog) <= 0.3


def test_fake_embedder_fail_delay_status():
    fe = FakeEmbedder(status="cold")
    assert fe.query("cachorro") is None and fe.documents(["cachorro"]) is None
    assert fe.calls == []
    assert fe.warm() is True and fe.status == "ready"
    fe.unload()
    assert fe.status == "cold"
    fe.warm()
    fe.delay = 0.05
    t = time.perf_counter()
    assert fe.query("cachorro") is not None
    assert time.perf_counter() - t >= 0.04
    fe.fail = True
    try:
        fe.documents(["a", "b"])
    except RuntimeError:
        pass
    else:
        raise AssertionError("fail=True must raise")
    assert fe.calls[-1][:2] == ("documents", 2)


def test_m9_constants():
    m = memory_pkg
    expected = {
        "EMBED_BATCH": 16, "EMBED_MAX_CHARS": 500, "EMBED_QUERY_TIMEOUT_S": 1.0,
        "EMBED_BATCH_TIMEOUT_S": 10.0, "EMBED_RETRY_S": 60, "EMBED_CHECK_S": 300,
        "EMBED_DIM_MAX": 4096, "INDEX_EVERY_S": 5, "SEM_MIN_SIM": 0.5, "FACT_MIN_SIM": 0.6,
        "TOPIC_MIN_SIM": 0.6, "W_SEM": 0.7, "W_WORD": 0.3, "W_IMPORTANCE": 0.35, "W_RECENCY": 0.15,
        "W_RELEVANCE": 0.5, "VECTOR_RAM_MAX_MB": 16, "SEARCH_BUDGET_MS": 20,
    }
    for name, value in expected.items():
        assert getattr(m, name) == value, name
        assert type(getattr(m, name)) is type(value), name
    # the M8 constants stay where they were
    assert m.MAX_EPISODES == 2000 and m.CURRENT_MIN_SALIENCE == 0.35


def test_recall_function_still_m8_signature():
    import inspect

    params = inspect.signature(recall).parameters
    assert list(params) == ["memory", "text", "stage", "lang"]
