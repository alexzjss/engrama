import numpy as np
import pytest

from engrama.config import Config
from engrama.services.language.client import LLMOffline, LLMTimeout
from engrama.services.language.embedder import PREFIXES, Embedder, family, installed
from engrama.services.memory import (EMBED_BATCH_TIMEOUT_S, EMBED_CHECK_S, EMBED_DIM_MAX,
                                     EMBED_MAX_CHARS, EMBED_QUERY_TIMEOUT_S, EMBED_RETRY_S)


class FakeClient:
    def __init__(self, tags=("embeddinggemma:latest",), dim=4):
        self.tag_set = None if tags is None else set(tags)
        self.dim = dim
        self.embed_calls = []
        self.tag_calls = 0
        self.unloaded = []
        self.response = None   # override: callable(texts) or value
        self.raises = None

    def tags(self):
        self.tag_calls += 1
        return self.tag_set

    def embed(self, model, texts, timeout):
        self.embed_calls.append((model, list(texts), timeout))
        if self.raises:
            raise self.raises
        if self.response is not None:
            return self.response
        return [[2.0] + [0.0] * (self.dim - 1) for _ in texts]

    def unload_embed(self, model):
        self.unloaded.append(model)

    def pull(self, *a, **k):
        pytest.fail("Embedder must never pull")


class Clock:
    t = 100.0

    def __call__(self):
        return self.t


def make(tmp_path, client=None, **cfg):
    clock = Clock()
    c = client or FakeClient()
    return Embedder(c, Config(data_dir=tmp_path, **cfg), now=clock), c, clock


def test_family_and_installed():
    assert family("embeddinggemma:300m") == "embeddinggemma"
    assert installed("embeddinggemma", {"embeddinggemma:latest"})
    assert installed("embeddinggemma", {"embeddinggemma"})
    assert not installed("nomic-embed-text", {"nomic-embed-text:v1.5"})
    assert installed("nomic-embed-text:v1.5", {"nomic-embed-text:v1.5"})
    assert not installed("", {"a"})


def test_status_off_missing_cold_ready(tmp_path):
    e, _, _ = make(tmp_path, embed_model="")
    assert e.model == "" and e.status == "off" and e.refresh() == "off" and e.warm() is False
    e, _, _ = make(tmp_path, semantic_recall=False)
    assert e.model == "" and e.status == "off"
    e, _, _ = make(tmp_path, FakeClient(tags=("other:latest",)))
    assert e.refresh() == "missing" and e.warm() is False
    e, c, _ = make(tmp_path)
    assert e.refresh() == "cold"
    assert e.warm() is True and e.status == "ready" and e.dim == 4
    assert c.embed_calls[0][1] == [" "] and c.embed_calls[0][2] == EMBED_BATCH_TIMEOUT_S


def test_tags_checked_at_most_every_check_s(tmp_path):
    e, c, clock = make(tmp_path)
    e.refresh(); e.refresh()
    assert c.tag_calls == 1
    clock.t += EMBED_CHECK_S + 1
    e.refresh()
    assert c.tag_calls == 2
    c.tag_set = set()
    clock.t += EMBED_CHECK_S + 1
    assert e.refresh() == "missing"


def test_query_prefix_and_normalized(tmp_path):
    e, c, _ = make(tmp_path)
    e.warm()
    v = e.query("oi")
    assert v.dtype == np.float32 and abs(float(np.linalg.norm(v)) - 1.0) < 1e-6
    _, texts, timeout = c.embed_calls[-1]
    assert texts == [PREFIXES["embeddinggemma"][0] + "oi"] and timeout == EMBED_QUERY_TIMEOUT_S


def test_documents_prefix_and_cut(tmp_path):
    e, c, _ = make(tmp_path)
    e.warm()
    out = e.documents(["x" * 2000, "b"])
    assert len(out) == 2 and all(v.dtype == np.float32 for v in out)
    pre = PREFIXES["embeddinggemma"][1]
    _, texts, timeout = c.embed_calls[-1]
    assert texts[0] == pre + "x" * EMBED_MAX_CHARS and texts[1] == pre + "b"
    assert timeout == EMBED_BATCH_TIMEOUT_S


@pytest.mark.parametrize("bad", [
    [], [[1.0, 0.0]], [[1.0, 0.0], [1.0]], [[float("nan"), 1.0], [1.0, 1.0]],
    [[float("inf"), 1.0], [1.0, 1.0]], [[0.0, 0.0], [1.0, 1.0]],
    [[1.0] * (EMBED_DIM_MAX + 1)] * 2, [[], []], [["a", "b"], [1, 2]],
])
def test_invalid_responses_fail(tmp_path, bad):
    e, c, _ = make(tmp_path)
    e.warm()
    assert e.status == "ready"
    c.response = bad
    assert e.documents(["a", "b"]) is None
    assert e.status == "failed"


@pytest.mark.parametrize("exc", [RuntimeError("does not support embeddings"), LLMTimeout("t"),
                                 LLMOffline("o"), KeyError("embeddings")])
def test_exceptions_fail(tmp_path, exc):
    e, c, _ = make(tmp_path)
    e.warm()
    c.raises = exc
    assert e.query("a") is None and e.status == "failed"


def test_failed_retry_after_retry_s(tmp_path):
    e, c, clock = make(tmp_path)
    e.warm()
    c.raises = RuntimeError("x")
    e.query("a")
    assert e.status == "failed"
    n = len(c.embed_calls)
    assert e.warm() is False and len(c.embed_calls) == n
    clock.t += EMBED_RETRY_S + 1
    assert e.status == "cold"
    c.raises = None
    assert e.warm() is True and e.status == "ready"


def test_offline_clears_tags_cache(tmp_path):
    e, c, _ = make(tmp_path)
    e.warm()
    c.raises = LLMOffline("o")
    e.query("a")
    before = c.tag_calls
    e._failed_until = 0
    e.refresh()
    assert c.tag_calls == before + 1


def test_not_ready_never_calls_client(tmp_path):
    for kw, client in (({"embed_model": ""}, None), ({}, FakeClient(tags=("x",)))):
        e, c, _ = make(tmp_path, client, **kw)
        e.refresh()
        assert e.query("a") is None and e.documents(["a"]) is None
        assert c.embed_calls == []
    e, c, _ = make(tmp_path)           # cold
    assert e.query("a") is None and e.documents(["a"]) is None and c.embed_calls == []
    e.warm()
    c.raises = RuntimeError("x")
    e.query("a")                       # failed
    n = len(c.embed_calls)
    assert e.query("a") is None and e.documents(["a"]) is None and len(c.embed_calls) == n


def test_dim_change_flag(tmp_path):
    e, c, _ = make(tmp_path)
    e.warm()
    assert e.dim == 4 and not e.dim_changed
    c.dim = 8
    assert e.documents(["a"]) is not None
    assert e.dim == 8 and e.dim_changed


def test_model_change_resets_to_cold(tmp_path):
    e, c, _ = make(tmp_path)
    e.warm()
    assert e.status == "ready"
    e.cfg.embed_model = "nomic-embed-text"
    assert e.status == "cold" and e.dim is None
    c.tag_set = {"nomic-embed-text:latest"}
    assert e.refresh() == "cold"
    e.warm()
    e.query("q")
    assert c.embed_calls[-1][1] == [PREFIXES["nomic-embed-text"][0] + "q"]


def test_unload(tmp_path):
    e, c, _ = make(tmp_path)
    e.warm()
    e.unload()
    assert c.unloaded == ["embeddinggemma"] and e.status == "cold"
    c.unload_embed = lambda m: (_ for _ in ()).throw(RuntimeError("x"))
    e.unload()


def test_never_pulls(tmp_path):
    e, c, _ = make(tmp_path, FakeClient(tags=()))
    e.refresh(); e.warm(); e.query("a"); e.documents(["a"]); e.unload()
