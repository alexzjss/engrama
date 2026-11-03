import json
import time

import pytest

from engrama.config import Config
from engrama.services.language.persona import PersonaState
from engrama.services.language.lang import detect_lang
from engrama.services.language.service import P_INDEX, LanguageService
from engrama.services.memory import EMBED_BATCH, EMBED_QUERY_TIMEOUT_S, INDEX_EVERY_S
from engrama.services.memory.store import MemoryStore, WorkingMemory
from tests.services.fake_embedder import FakeEmbedder
from tests.services.memory.golden_recall import CASES, FIXTURE, build_store


class Client:
    def __init__(self):
        self.chats, self.warms, self.unloads = [], 0, 0

    def warm(self, model):
        self.warms += 1

    def unload(self, model):
        self.unloads += 1

    def chat(self, model, messages, num_predict, temperature, timeout=45):
        self.chats.append(messages)
        head = messages[0]["content"]
        if head.startswith(("Extraia", "From the user")):
            return json.dumps({"facts": [], "topics": [], "valence": 0.0})
        return "oi, e ai"

    def tags(self):
        return {"qwen3:1.7b"}


class Server:
    def available(self):
        return True

    def running(self):
        return True

    def start(self):
        return True


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class Box:
    resting = False

    def idle(self):
        return not self.resting


class TimeoutEmbedder(FakeEmbedder):
    """Respects the query time limit like the real client: too slow = no vector."""

    def query(self, text):
        if self.delay > EMBED_QUERY_TIMEOUT_S:
            return None
        return super().query(text)


def make(tmp_path, embedder, stage="adult", sync=True, store=None, box=None):
    cfg = Config(data_dir=tmp_path)
    mem = store or MemoryStore(tmp_path / "m.sqlite")
    clock, box = Clock(), box or Box()
    svc = LanguageService(Client(), Server(), cfg, mem, WorkingMemory(), lambda: PersonaState(stage=stage),
                          lambda i, l: i, idle=box.idle, now_fn=clock, sync=sync, embedder=embedder)
    svc.clock, svc.box = clock, box
    return svc, mem


def ready(svc):
    svc.warm()
    assert svc.status == "ready"


def index_all(svc, max_rounds=20):
    for _ in range(max_rounds):
        svc.clock.t += INDEX_EVERY_S + 1
        svc.tick(svc.clock.t)
        if not svc.pump():
            return


def docs_calls(fe):
    return [c for c in fe.calls if c[0] == "documents"]


def system(svc, user):
    return next(m[0]["content"] for m in svc.client.chats if m[-1]["content"] == user)


def test_chat_uses_meaning_when_ready(tmp_path):
    fe = FakeEmbedder(status="cold")
    svc, mem = make(tmp_path, fe)
    mem.upsert_fact("nome_do_cachorro", "Biscoito", 0.9, "chat")
    for k, v in (("cidade", "Curitiba"), ("profissao", "professor"), ("musica_favorita", "banda antiga"),
                 ("comida", "lanche de queijo"), ("jogo_favorito", "hollow knight")):
        mem.upsert_fact(k, v, 0.9, "chat")
    ready(svc)
    index_all(svc)
    assert mem.vector_counts()["vectors"] >= 6
    svc.request("meu bichinho anda doente")
    svc.pump()
    assert "Biscoito" in system(svc, "meu bichinho anda doente")
    (tmp_path / "w").mkdir()
    plain, _ = make(tmp_path / "w", None, store=mem)
    ready(plain)
    plain.request("meu bichinho anda doente")
    plain.pump()
    assert "Biscoito" not in system(plain, "meu bichinho anda doente")   # words alone do not find it


@pytest.mark.parametrize("mode", ["none", "off", "missing", "cold", "failed", "fail", "slow"])
def test_degraded_paths_match_m8_golden(tmp_path, mode):
    fe = None if mode == "none" else TimeoutEmbedder(status={"fail": "ready", "slow": "ready"}.get(mode, mode))
    if fe is not None and mode == "fail":
        fe.fail = True
    if fe is not None and mode == "slow":
        fe.delay = EMBED_QUERY_TIMEOUT_S + 1.0
    store = build_store(tmp_path / "g.sqlite")
    svc, _ = make(tmp_path, fe, store=store)
    ready(svc)
    if fe is not None:
        fe.status = {"fail": "ready", "slow": "ready"}.get(mode, mode)   # warm may have moved it
    golden = json.loads(FIXTURE.read_text(encoding="utf-8"))
    checked = 0
    for i, (text, stage, lang) in enumerate(CASES):
        if stage in ("egg", "baby") or not text or detect_lang(text, "pt") != lang:
            continue
        svc.get_state = lambda stage=stage: PersonaState(stage=stage)
        svc.client.chats.clear()
        svc.working = WorkingMemory()
        svc._last_lang = lang
        svc._chat(text)
        assert svc.client.chats[0] == golden[i]["messages"]
        checked += 1
    assert checked >= 8


def test_no_embedder_calls_when_llm_not_ready(tmp_path):
    fe = FakeEmbedder(status="ready")
    svc, mem = make(tmp_path, fe)
    mem.upsert_fact("nome_do_cachorro", "Biscoito", 0.9, "chat")
    svc.server.available = lambda: True
    svc._state = "offline"
    svc._down_until = 1e12
    svc.request("meu bichinho")
    svc.tick(2000.0)
    svc.pump()
    assert fe.calls == []
    svc._state = "loading"
    svc.tick(3000.0)
    svc.pump()
    svc._qvec("meu bichinho")
    assert [c for c in fe.calls if c[0] in ("query", "documents")] == []


def test_warm_also_warms_embedder(tmp_path):
    fe = FakeEmbedder(status="cold")
    svc, mem = make(tmp_path, fe)
    ready(svc)
    assert fe.status == "ready" and [c[0] for c in fe.calls][:2] == ["refresh", "warm"]
    assert mem._meta_model() == "embeddinggemma"
    assert svc.embed_status == "ready"


def test_embedder_failure_does_not_touch_llm(tmp_path):
    class Boom(FakeEmbedder):
        def refresh(self):
            raise RuntimeError("x")
    svc, _ = make(tmp_path, Boom(status="cold"))
    ready(svc)
    assert svc.status == "ready"


def test_unload_also_unloads_embedder(tmp_path):
    fe = FakeEmbedder(status="cold")
    svc, _ = make(tmp_path, fe)
    ready(svc)
    svc.unload()
    assert fe.status == "cold" and "unload" in [c[0] for c in fe.calls]
    assert svc.client.unloads == 1


def test_embed_status_and_counts(tmp_path):
    svc, mem = make(tmp_path, None)
    assert svc.embed_status == "off" and svc.embed_counts() == {"vectors": 0, "items": 0}
    assert make(tmp_path, FakeEmbedder(status="missing"))[0].embed_status == "missing"
    svc.memory = None
    assert svc.embed_counts() == {}


def test_index_job_batches_and_stops(tmp_path):
    fe = FakeEmbedder(status="cold")
    svc, mem = make(tmp_path, fe)
    for i in range(60):
        mem.upsert_fact(f"chave_{i}", f"valor {i}", 0.5, "chat")
    ready(svc)
    index_all(svc)
    calls = docs_calls(fe)
    assert len(calls) == 4 and all(n <= EMBED_BATCH for _, n, _ in calls)
    assert sum(n for _, n, _ in calls) == 60
    for _ in range(3):
        svc.clock.t += 100
        svc.tick(svc.clock.t)
        assert svc.pump() == 0
    assert len(docs_calls(fe)) == 4
    svc.request("oi")
    svc.pump()
    index_all(svc)
    assert len(docs_calls(fe)) == 5           # the new chat episode, nothing else


def test_index_not_when_resting(tmp_path):
    fe = FakeEmbedder(status="cold")
    svc, mem = make(tmp_path, fe)
    mem.upsert_fact("a", "cachorro", 0.5, "chat")
    ready(svc)
    svc.box.resting = True
    svc.clock.t += 100
    svc.tick(svc.clock.t)
    svc.pump()
    assert docs_calls(fe) == []
    svc.box.resting = False
    svc.pump()
    assert len(docs_calls(fe)) == 1


def test_delete_during_index_not_written(tmp_path):
    class Hook(FakeEmbedder):
        def documents(self, texts):
            out = super().documents(texts)
            mem.delete_fact("cidade")
            return out
    fe = Hook(status="cold")
    svc, mem = make(tmp_path, fe)
    mem.upsert_fact("cidade", "Curitiba", 0.8, "chat")
    mem.upsert_fact("nome_do_cachorro", "Biscoito", 0.9, "chat")
    ready(svc)
    index_all(svc)
    assert mem.vector_counts()["vectors"] == 1


def test_model_switch_drops_and_reindexes(tmp_path):
    fe = FakeEmbedder(status="cold")
    svc, mem = make(tmp_path, fe)
    mem.upsert_fact("a", "cachorro", 0.5, "chat")
    ready(svc)
    index_all(svc)
    assert mem.vector_counts()["vectors"] == 1
    fe.model = "nomic-embed-text"
    svc.set_embed_model("nomic-embed-text")
    assert svc.cfg.embed_model == "nomic-embed-text"
    assert mem.vector_counts()["vectors"] == 0
    assert fe.status == "cold"
    svc.clock.t += 100
    svc.tick(svc.clock.t)
    assert svc.pump() == 0                    # cold: nothing is indexed until the next warm
    ready(svc)
    index_all(svc)
    assert mem.vector_counts()["vectors"] == 1


def test_dim_change_treated_as_switch(tmp_path):
    fe = FakeEmbedder(status="cold")
    svc, mem = make(tmp_path, fe)
    mem.upsert_fact("a", "cachorro", 0.5, "chat")
    ready(svc)
    index_all(svc)
    assert mem.vector_counts()["vectors"] == 1
    fe.dim_changed = True
    assert svc._qvec("cachorro") is None
    assert fe.dim_changed is False
    assert mem.vector_counts()["vectors"] == 0 and fe.status == "cold"


def test_semantic_off_drops_vectors(tmp_path):
    fe = FakeEmbedder(status="cold")
    svc, mem = make(tmp_path, fe)
    mem.upsert_fact("a", "cachorro", 0.5, "chat")
    ready(svc)
    index_all(svc)
    svc.set_semantic_recall(False)
    assert svc.cfg.semantic_recall is False
    assert mem.vector_counts()["vectors"] == 0 and fe.status == "cold"
    svc.set_semantic_recall(True)
    assert svc.cfg.semantic_recall is True


def test_embedder_threads_are_language_threads(tmp_path):
    fe = FakeEmbedder(status="cold")
    svc, mem = make(tmp_path, fe, sync=False)
    try:
        mem.upsert_fact("a", "cachorro", 0.5, "chat")
        svc.warm()
        deadline = time.monotonic() + 10
        while svc.status != "ready" and time.monotonic() < deadline:
            time.sleep(0.02)
        svc.request("meu bichinho")
        svc.replies.get(timeout=5)
        for _ in range(3):
            svc.tick(svc.clock.t + 100)
            time.sleep(0.4)
        svc.unload()
        time.sleep(0.4)
        names = {c[2] for c in fe.calls}
        assert names and names <= {"language-service", "language-io"}
        assert {c[0] for c in fe.calls} >= {"warm", "query"}
    finally:
        svc.shutdown()


def test_chat_priority_still_first(tmp_path):
    fe = FakeEmbedder(status="cold")
    svc, mem = make(tmp_path, fe)
    mem.upsert_fact("a", "cachorro", 0.5, "chat")
    ready(svc)
    svc.clock.t += 100
    svc.tick(svc.clock.t)
    assert any(j[0] == P_INDEX for j in svc._jobs)
    svc.request("oi")
    order = []
    while True:
        job = svc._take()
        if job is None:
            break
        order.append(job[0])
    assert order[0] == 0 and order[-1] == P_INDEX
