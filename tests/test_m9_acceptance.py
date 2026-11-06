"""M9 acceptance (spec section 7): recall by meaning, with the real MemoryStore/LanguageService, a fake
embedding model and a fake Ollama transport. No test talks to a real Ollama.

Criterion 12 (budget) is the two budget tests of the normal suite plus `tools/bench.py --app`; criterion 15
(manual smoke with the real model downloaded through F5) is the manual checklist in the plan. Criteria 1-11, 13
and 14 are below, with `slow` on the ones that run a subprocess, a lab run or a long simulation."""
import json
import os
import shutil
import sqlite3
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from engrama import balance as B
from engrama import vocab
from engrama.app.host import Host, _memory_provider
from engrama.clock import SimClock
from engrama.config import Config
from engrama.services.language import client as client_mod
from engrama.services.language.client import OllamaClient
from engrama.services.language.embedder import Embedder
from engrama.services.language.lang import detect_lang
from engrama.services.language.persona import PersonaState
from engrama.services.language.service import LanguageService
from engrama.services.memory import (EMBED_BATCH, EMBED_QUERY_TIMEOUT_S, INDEX_EVERY_S, MAX_EPISODES, MAX_FACTS,
                                     MAX_TOPICS, SEARCH_BUDGET_MS, VECTOR_RAM_MAX_MB)
from engrama.services.memory.recall import recall
from engrama.services.memory.store import MemoryStore, WorkingMemory
from tests.services.fake_embedder import FakeEmbedder
from tests.services.memory.golden_recall import CASES, FIXTURE as GOLDEN, build_store

ROOT = Path(__file__).resolve().parents[1]
MINIMAL = ROOT / "engrama" / "recipes" / "minimal-v1.toml"
LAB_FIXTURE = ROOT / "tests" / "fixtures" / "m6_sim_1d_seed1_attentive.json"
M8_DB = ROOT / "tests" / "fixtures" / "m8_memory_v2.sqlite"
ENV = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
DAY = 86400.0
T0 = 1_800_000_000.0


# ---- fakes ---------------------------------------------------------------------------------------------------
class Chat:
    """Fake chat transport (the M4 ScriptedClient shape): records the prompts, answers with a fixed line."""

    def __init__(self):
        self.chats, self.warms, self.unloads = [], 0, 0

    def warm(self, model):
        self.warms += 1

    def unload(self, model):
        self.unloads += 1

    def chat(self, model, messages, num_predict, temperature, timeout=45):
        self.chats.append(messages)
        if messages[0]["content"].startswith(("Extraia", "From the user")):
            return json.dumps({"facts": [], "topics": [], "valence": 0.0})
        return "oi, e ai"

    def tags(self):
        return {"qwen3:1.7b"}


class Server:
    up = True

    def available(self): return True
    def running(self): return self.up
    def start(self): return self.up


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


class Box:
    resting = False

    def idle(self):
        return not self.resting


def make(tmp_path, embedder, store=None, stage="adult", sync=True, cfg=None):
    cfg = cfg or Config(data_dir=tmp_path)
    clock, box = Clock(), Box()
    mem = store or MemoryStore(tmp_path / "m.sqlite", now_fn=clock)
    svc = LanguageService(Chat(), Server(), cfg, mem, WorkingMemory(), lambda: PersonaState(stage=stage),
                          lambda i, l: i, idle=box.idle, now_fn=clock, sync=sync, embedder=embedder)
    svc.clock, svc.box = clock, box
    return svc, mem


def ready(svc):
    svc.warm()
    assert svc.status == "ready"


def index_all(svc, rounds=30):
    for _ in range(rounds):
        svc.clock.t += INDEX_EVERY_S + 1
        svc.tick(svc.clock.t)
        if not svc.pump():
            return


def system(svc, user):
    return next(m[0]["content"] for m in svc.client.chats if m[-1]["content"] == user)


def doc_calls(fe):
    return [c for c in fe.calls if c[0] == "documents"]


def vec_refs(mem):
    return {(k, r) for k, r in mem._db.execute("SELECT kind, ref FROM vectors")}


def assert_no_orphans(mem):
    live = set()
    live |= {("episode", str(r[0])) for r in mem._db.execute("SELECT id FROM episodes")}
    live |= {("ancestral", str(r[0])) for r in mem._db.execute("SELECT id FROM episodes WHERE kind='ancestral'")}
    live |= {("fact", r[0]) for r in mem._db.execute("SELECT key FROM facts")}
    live |= {("topic", r[0]) for r in mem._db.execute("SELECT name FROM topics")}
    assert vec_refs(mem) <= live


class EmbedTransport:
    """Fake Ollama /api/embed + /api/tags: vectors from the FakeEmbedder concepts. Counts every call."""

    def __init__(self, models=("embeddinggemma",), dim=32):
        self.models, self.fe, self.calls = set(models), FakeEmbedder(dim=dim), []

    def __call__(self, url, body=None, timeout=20):
        self.calls.append(url.rsplit("/", 1)[-1])
        if url.endswith("/api/tags"):
            return {"models": [{"name": m + ":latest"} for m in self.models]}
        if url.endswith("/api/embed"):
            if not body.get("input"):
                return {"embeddings": []}
            return {"embeddings": [self.fe._vec(t).tolist() for t in body["input"]]}
        if url.endswith("/api/generate"):
            return {}
        raise AssertionError(url)


def seed_dog(mem, with_noise=True):
    """Day 1: the user adopted a dog called Biscoito (an episode and an extracted fact)."""
    mem.add_episode("conversa", "adotei um cachorro, o nome dele e Biscoito", valence=0.7, importance=0.5,
                    topic="cachorro")
    mem.upsert_fact("nome_do_cachorro", "Biscoito", 0.9, "chat")
    if with_noise:   # later chatter and other facts, so the dog is not simply "the latest thing in the prompt"
        for i in range(12):
            mem.add_episode("conversa", f"falamos de outra coisa qualquer, parte {i}", valence=0.0, importance=0.6)
        for k, v in (("cidade", "Curitiba"), ("profissao", "professor"), ("musica_favorita", "banda antiga"),
                     ("comida", "lanche de queijo"), ("jogo_favorito", "hollow knight")):
            mem.upsert_fact(k, v, 0.9, "chat")


# ---- 1, 2: meaning, across languages --------------------------------------------------------------------------
def test_remembers_by_meaning(tmp_path):
    fe = FakeEmbedder(status="cold")
    svc, mem = make(tmp_path, fe)
    seed_dog(mem)
    ready(svc)
    index_all(svc)
    svc.clock.t += 4 * DAY   # day 5
    msg = "meu bichinho anda doente"   # no word in common with the memory
    svc.request(msg)
    svc.pump()
    assert "Biscoito" in system(svc, msg)
    (tmp_path / "plain").mkdir()
    plain, _ = make(tmp_path / "plain", None, store=mem)   # the same memory, no embedder: it is M4
    ready(plain)
    plain.request(msg)
    plain.pump()
    assert "Biscoito" not in system(plain, msg)


def test_cross_language(tmp_path):
    fe = FakeEmbedder(status="cold")
    svc, mem = make(tmp_path, fe)
    seed_dog(mem)   # stored in Portuguese
    ready(svc)
    index_all(svc)
    msg = "my dog is sick"
    assert detect_lang(msg, "pt") == "en"
    svc.request(msg)
    svc.pump()
    assert "Biscoito" in system(svc, msg)


# ---- 3: no model = M8 -----------------------------------------------------------------------------------------
class Slow(FakeEmbedder):
    def query(self, text):
        if self.delay > EMBED_QUERY_TIMEOUT_S:
            return None   # the real client gives up at the query time limit
        return super().query(text)


@pytest.mark.parametrize("mode", ["none", "off", "missing", "cold", "failed", "raises", "slow", "empty_index"])
def test_no_model_is_m8(tmp_path, mode):
    fe = None if mode == "none" else Slow(status={"raises": "ready", "slow": "ready", "empty_index": "ready"}
                                          .get(mode, mode))
    if fe is not None and mode == "raises":
        fe.fail = True
    if fe is not None and mode == "slow":
        fe.delay = EMBED_QUERY_TIMEOUT_S + 1.0
    store = build_store(tmp_path / "g.sqlite")
    svc, _ = make(tmp_path, fe, store=store)
    ready(svc)
    if fe is not None:
        fe.status = {"raises": "ready", "slow": "ready", "empty_index": "ready"}.get(mode, mode)
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
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


def test_ollama_stopped_is_m8(tmp_path):
    """Ollama down: the real Embedder over a transport that refuses connections never produces a vector."""
    def down(url, body=None, timeout=20):
        raise ConnectionRefusedError("down")
    cfg = Config(data_dir=tmp_path)
    emb = Embedder(OllamaClient(cfg, http_json=down), cfg)
    store = build_store(tmp_path / "g.sqlite")
    svc, _ = make(tmp_path, emb, store=store, cfg=cfg)
    svc.server.up = False
    text, stage, lang = next(c for c in CASES if c[0] == "meu cachorro, o Biscoito, esta doente")
    svc.client.chats.clear()
    svc._chat(text)
    assert svc.client.chats == []   # offline: babble, no prompt at all
    assert emb.query(text) is None and emb.documents([text]) is None


def test_no_llm_never_calls_embed(tmp_path, monkeypatch):
    seen = []

    def spy(url, body=None, timeout=20):
        seen.append(url)
        raise AssertionError(f"network use under --no-llm: {url}")
    monkeypatch.setattr(client_mod, "http_json", spy)
    from engrama.app.host import main
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    assert main(["--no-llm", "--frames", "60", "--data-dir", str(tmp_path / "app"), "--seed", "3"]) == 0
    assert not [u for u in seen if u.endswith("/api/embed")] and seen == []


# ---- 4: never loads a model on its own ------------------------------------------------------------------------
def test_never_loads_model_alone(tmp_path):
    fe = FakeEmbedder(status="ready")
    svc, mem = make(tmp_path, fe)
    seed_dog(mem)
    svc._state = "offline"
    svc._down_until = 1e18
    svc.request("meu bichinho anda doente")
    for _ in range(3):
        svc.clock.t += 100
        svc.tick(svc.clock.t)
        svc.pump()
    svc._state = "loading"
    svc.clock.t += 100
    svc.tick(svc.clock.t)
    svc.pump()
    svc._qvec("meu bichinho")
    assert fe.calls == []
    # ready but not idle: still nothing
    svc._state = "ready"
    svc.box.resting = True
    svc.clock.t += 100
    svc.tick(svc.clock.t)
    svc.pump()
    assert doc_calls(fe) == []
    # ready and idle: batches of at most EMBED_BATCH
    svc.box.resting = False
    for i in range(40):
        mem.upsert_fact(f"chave_{i}", f"valor {i}", 0.5, "chat")
    index_all(svc)
    calls = doc_calls(fe)
    assert calls and all(n <= EMBED_BATCH for _, n, _ in calls)
    assert sum(n for _, n, _ in calls) >= 40


# ---- 5: off the UI thread --------------------------------------------------------------------------------------
def test_embedder_off_ui_thread(tmp_path):
    fe = FakeEmbedder(status="cold")
    svc, mem = make(tmp_path, fe, sync=False)
    try:
        seed_dog(mem)
        svc.warm()
        deadline = time.monotonic() + 10
        while svc.status != "ready" and time.monotonic() < deadline:
            time.sleep(0.02)
        svc.request("meu bichinho anda doente")
        svc.replies.get(timeout=5)
        for _ in range(4):
            svc.tick(svc.clock.t + 100)
            time.sleep(0.3)
        svc.unload()
        time.sleep(0.4)
        names = {c[2] for c in fe.calls}
        assert names and names <= {"language-service", "language-io"}
        assert threading.current_thread().name not in names
        assert {c[0] for c in fe.calls} >= {"warm", "query", "documents"}
    finally:
        svc.shutdown()


# ---- 6: deleting deletes the vector ---------------------------------------------------------------------------
def test_delete_drops_vectors_end_to_end(tmp_path):
    fe = FakeEmbedder(status="cold")
    svc, mem = make(tmp_path, fe)
    seed_dog(mem)
    mem.bump_topic("cachorro", 1.0)
    mem.bump_topic("musica", 1.0)
    mem.update_opinion("cachorro", lambda t: 0.5, 0.6)
    ready(svc)
    index_all(svc)
    prov = _memory_provider(mem, svc.working, svc)
    assert ("fact", "nome_do_cachorro") in vec_refs(mem) and ("topic", "cachorro") in vec_refs(mem)
    qdog = fe.query("bichinho")
    prov.delete_fact("nome_do_cachorro")
    assert ("fact", "nome_do_cachorro") not in vec_refs(mem)
    assert "nome_do_cachorro" not in [r for r, _ in mem.similar(qdog, "fact", 20, -1.0)]
    prov.delete_topic("cachorro")
    assert ("topic", "cachorro") not in vec_refs(mem)
    assert "cachorro" not in [r for r, _ in mem.similar(qdog, "topic", 20, -1.0)]
    assert_no_orphans(mem)
    prov.forget_all()
    assert_no_orphans(mem)
    assert not [r for r in vec_refs(mem) if r[0] in ("fact", "topic")]
    assert mem.similar(qdog, "fact", 20, -1.0) == [] and mem.similar(qdog, "topic", 20, -1.0) == []
    ids = {str(r[0]) for r in mem._db.execute("SELECT id FROM episodes")}
    assert {r for k, r in vec_refs(mem) if k == "episode"} <= ids


def test_in_flight_batch_for_deleted_item_not_written(tmp_path):
    class Hook(FakeEmbedder):
        def documents(self, texts):
            out = super().documents(texts)
            if not self.__dict__.get("hooked"):
                self.hooked = True
                prov.delete_fact("cidade")
            return out
    fe = Hook(status="cold")
    svc, mem = make(tmp_path, fe)
    prov = _memory_provider(mem, svc.working, svc)
    mem.upsert_fact("cidade", "Curitiba", 0.8, "chat")
    mem.upsert_fact("nome_do_cachorro", "Biscoito", 0.9, "chat")
    ready(svc)
    index_all(svc)
    assert ("fact", "cidade") not in vec_refs(mem)
    assert ("fact", "nome_do_cachorro") in vec_refs(mem)
    assert_no_orphans(mem)


def test_caps_and_compaction_drop_vectors(tmp_path):
    clock = Clock()
    mem = MemoryStore(tmp_path / "m.sqlite", now_fn=clock)
    fe = FakeEmbedder()
    svc, _ = make(tmp_path, fe, store=mem)
    svc.clock = clock
    for i in range(MAX_FACTS + 20):
        mem.upsert_fact(f"k{i}", f"valor {i}", 0.5, "chat")
    ready(svc)
    index_all(svc, rounds=60)
    mem.enforce_caps()
    for i in range(30):
        clock.t += 90 * DAY
        mem.add_episode("conversa", f"coisa antiga {i}", valence=0.0, importance=0.1)
    mem.forget(clock.t + 400 * DAY)
    assert_no_orphans(mem)


# ---- 7: switch / toggle ---------------------------------------------------------------------------------------
def test_model_switch_end_to_end(tmp_path):
    transport = EmbedTransport(models=("embeddinggemma", "nomic-embed-text"))
    cfg = Config(data_dir=tmp_path)
    emb = Embedder(OllamaClient(cfg, http_json=transport), cfg)
    svc, mem = make(tmp_path, emb, cfg=cfg)
    seed_dog(mem)
    ready(svc)
    assert svc.embed_status == "ready"
    index_all(svc)
    n = mem.vector_counts()["vectors"]
    assert n >= 6
    prov = _memory_provider(mem, svc.working, svc)
    assert prov.summary()["semantic"] == "on"
    # F5: toggle off -> vectors dropped, status leaves "ready", F7 says words only
    svc.set_semantic_recall(False)
    assert mem.vector_counts()["vectors"] == 0
    assert svc.embed_status == "off"
    prov._invalidate()
    assert prov.summary()["semantic"] == "words"
    # nothing is embedded while off
    before = len(transport.calls)
    svc.clock.t += 100
    svc.tick(svc.clock.t)
    svc.pump()
    assert "embed" not in transport.calls[before:]
    # toggle on -> checked on the next warm-up, then re-indexed
    svc.set_semantic_recall(True)
    ready(svc)
    index_all(svc)
    assert mem.vector_counts()["vectors"] == n
    assert svc.embed_status == "ready"
    # switch model -> old vectors dropped, the search never mixes models, re-indexed in the background
    svc.set_embed_model("nomic-embed-text")
    assert mem.vector_counts()["vectors"] == 0
    assert mem.vector_model() == "nomic-embed-text"
    ready(svc)
    index_all(svc)
    assert mem.vector_counts()["vectors"] == n
    assert {r[0] for r in mem._db.execute("SELECT DISTINCT model FROM vectors")} == {"nomic-embed-text"}


# ---- 8: migration ---------------------------------------------------------------------------------------------
def test_migrates_m8_database(tmp_path):
    path = tmp_path / "memory.sqlite"
    shutil.copy(M8_DB, path)

    def dump():
        con = sqlite3.connect(path)
        try:
            return {t: con.execute(f"SELECT * FROM {t} ORDER BY 1, 2").fetchall()
                    for t in ("episodes", "facts", "topics", "opinions", "episode_links", "blocklist")}
        finally:
            con.close()
    before = dump()
    assert all(before[t] for t in before)
    s = MemoryStore(path)
    assert s.meta_get("schema_version") == "3"
    s.close()
    assert dump() == before


# ---- 9: bounded -----------------------------------------------------------------------------------------------
@pytest.mark.slow
def test_thirty_days_bounded(tmp_path):
    clock = Clock()
    mem = MemoryStore(tmp_path / "m.sqlite", now_fn=clock)
    fe = FakeEmbedder()
    mem.set_vector_model("embeddinggemma")
    for day in range(30):
        for i in range(90):   # 2,700 episodes: well over the cap, so compaction and caps both run
            mem.add_episode("conversa", f"dia {day} conversa sobre cachorro numero {i}", valence=0.1,
                            importance=0.2 + (i % 5) / 10)
        for i in range(12):
            mem.upsert_fact(f"fato_{day}_{i}", f"valor {day} {i}", 0.5, "chat")
            mem.bump_topic(f"assunto_{day}_{i}", 0.3)
        while True:
            items = mem.unindexed(EMBED_BATCH)
            if not items:
                break
            vecs = fe.documents([t for _, _, t, _ in items])
            mem.put_vectors("embeddinggemma", [(k, r, h, v) for (k, r, _t, h), v in zip(items, vecs)])
        clock.t += DAY
        mem.forget(clock.t)
        mem.enforce_caps()
        n_ep = mem._db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        n_f = mem._db.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        n_t = mem._db.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
        assert mem.vector_counts()["vectors"] <= n_ep + n_f + n_t
        assert_no_orphans(mem)
    assert n_ep <= MAX_EPISODES + 10 and n_f <= MAX_FACTS and n_t <= MAX_TOPICS
    q = fe.query("cachorro")
    for kind in ("episode", "fact", "topic"):
        mem.similar(q, kind, 5, 0.0)
    cached = sum(v[2].nbytes for v in mem._vec_cache.values())
    assert cached <= VECTOR_RAM_MAX_MB * 1024 * 1024
    mem.close()


# ---- 10: fast -------------------------------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.perf
def test_search_budget(tmp_path):
    mem = MemoryStore(tmp_path / "m.sqlite", now_fn=Clock())
    mem.set_vector_model("embeddinggemma")
    dim, rng, db, now = 768, np.random.default_rng(1), mem._db, T0
    db.executemany("INSERT INTO episodes(t, kind, summary, valence, importance, topic) VALUES(?,?,?,?,?,?)",
                   [(now - i, "chat", f"episodio {i}", 0.0, 0.3, None) for i in range(MAX_EPISODES)])
    db.executemany("INSERT INTO facts(key, value, confidence, source, t) VALUES(?,?,?,?,?)",
                   [(f"k{i}", f"v{i}", 0.5, "chat", now) for i in range(MAX_FACTS)])
    db.executemany("INSERT INTO topics(name, affinity, t, salience, t_salience, first_t, last_t, mentions, source)"
                   " VALUES(?,?,?,?,?,?,?,?,?)", [(f"t{i}", 0.1, now, 1.0, now, now, now, 1, "chat")
                                                   for i in range(MAX_TOPICS)])
    db.commit()
    for kind, sql in (("episode", "SELECT CAST(id AS TEXT) FROM episodes"), ("fact", "SELECT key FROM facts"),
                      ("topic", "SELECT name FROM topics")):
        refs = [r[0] for r in db.execute(sql)]
        mat = rng.standard_normal((len(refs), dim)).astype(np.float16)
        db.executemany("INSERT INTO vectors(kind, ref, model, dim, h, vec, t) VALUES(?,?,?,?,?,?,?)",
                       [(kind, r, "embeddinggemma", dim, "h", mat[i].tobytes(), now) for i, r in enumerate(refs)])
    db.commit()
    q = rng.standard_normal(dim).astype(np.float32)
    q /= np.linalg.norm(q)
    recall(mem, "alguma coisa sobre cachorro", "adult", "pt", qvec=q)   # warm the matrices
    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        recall(mem, "alguma coisa sobre cachorro", "adult", "pt", qvec=q)
        times.append((time.perf_counter() - t0) * 1000)
    assert statistics.median(times) <= SEARCH_BUDGET_MS
    mem.close()


# ---- 11: generations ------------------------------------------------------------------------------------------
class FakeTime:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t

    def tick(self, s=1.0):
        self.t += s


class FakeFarewell:
    def farewell(self, cause, on_text):
        on_text("adeus, humano")


@pytest.mark.slow
def test_generation_archive_and_ancestral_meaning(tmp_path):
    ft = FakeTime()
    h = Host(Config(data_dir=tmp_path), tmp_path, MINIMAL, seed=7, clock=SimClock(1.0, now_fn=ft),
             ram_free_mb_fn=lambda: 8000.0)
    mem = MemoryStore(tmp_path / "memory.sqlite", now_fn=ft)
    h.attach_services(mem, WorkingMemory(), FakeFarewell())
    try:
        mem.add_episode("conversa", "sonhei com um cachorro feliz no parque", valence=0.9, importance=0.95)
        mem.add_episode("conversa", "falamos de trabalho e de um chefe", valence=0.1, importance=0.5)
        mem.upsert_fact("nome_do_cachorro", "Biscoito", 0.9, "chat")
        fe = FakeEmbedder(status="cold")
        svc, _ = make(tmp_path, fe, store=mem)
        svc.clock = ft
        svc._now = ft
        ready(svc)
        index_all(svc)
        assert mem.vector_counts()["vectors"] >= 3
        for _ in range(3):
            ft.tick()
            h.pump(1)
        k = h.runtime.kernel
        k.dead, k.death_cause = True, "neglect"
        for _ in range(int(B.FAREWELL_S) + 8):
            ft.tick()
            h.pump(1)
        assert h.runtime.kernel.generation == 2
        # the archive of the finished life carries its memory but no vectors
        arch = sqlite3.connect(tmp_path / "generations" / "1" / "memory.sqlite")
        try:
            assert arch.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] >= 2
            assert arch.execute("SELECT COUNT(*) FROM vectors").fetchone()[0] == 0
        finally:
            arch.close()
        # the new life starts with no vectors; only the ancestral episodes get indexed again
        assert mem.vector_counts()["vectors"] == 0
        anc = mem.ancestral_rows(10)
        assert anc
        svc.request("oi")      # first words of the new life: the normal re-index rule picks the data up
        svc.pump()
        index_all(svc)
        kinds = {k for k, _ in vec_refs(mem)}
        assert "fact" not in kinds
        assert_no_orphans(mem)
        # an ancestral memory is recalled by meaning ("bichinho" shares no word with "cachorro feliz")
        ctx = recall(mem, "meu bichinho", "adult", "pt", qvec=fe.query("meu bichinho"))
        assert any("cachorro" in a for a in ctx.ancestral)
    finally:
        h.stop()
        mem.close()


# ---- 13: odd Ollama answers -----------------------------------------------------------------------------------
@pytest.mark.parametrize("answer", [
    {"embeddings": []}, {"embeddings": [[]]}, {"embeddings": [[float("nan")] * 4]},
    {"embeddings": [[float("inf")] * 4]}, {"embeddings": [[0.0] * 4]}, {"embeddings": "x"},
    {"embeddings": [[1.0, 2.0], [1.0]]}, {"error": 'model "x" does not support embeddings'}, {}, [], None])
def test_odd_ollama_answers_harmless(tmp_path, answer):
    def odd(url, body=None, timeout=20):
        if url.endswith("/api/tags"):
            return {"models": [{"name": "embeddinggemma:latest"}]}
        return answer
    cfg = Config(data_dir=tmp_path)
    emb = Embedder(OllamaClient(cfg, http_json=odd), cfg)
    assert emb.refresh() == "cold"
    assert emb.warm() is False and emb.status == "failed"
    emb._status = "ready"   # as if it had been ready before the odd answer
    assert emb.query("cachorro") is None
    assert emb.status == "failed"
    emb._status = "ready"
    assert emb.documents(["a", "b"]) is None
    assert emb.status == "failed"


def test_odd_http_errors_harmless(tmp_path):
    import urllib.error
    cfg = Config(data_dir=tmp_path)
    for exc in (urllib.error.HTTPError("u", 500, "boom", {}, None), TimeoutError("t"), ConnectionResetError("r"),
                ValueError("v")):
        def bad(url, body=None, timeout=20, exc=exc):
            if url.endswith("/api/tags"):
                return {"models": [{"name": "embeddinggemma:latest"}]}
            raise exc
        emb = Embedder(OllamaClient(cfg, http_json=bad), cfg)
        emb.refresh()
        emb._status = "ready"
        assert emb.query("x") is None
        emb._status = "ready"
        assert emb.documents(["x"]) is None
    # a dimension that changes under the same model name is flagged, never raised
    dims = iter([4, 6])

    def shifting(url, body=None, timeout=20):
        if url.endswith("/api/tags"):
            return {"models": [{"name": "embeddinggemma:latest"}]}
        return {"embeddings": [[1.0] * next(dims)]}
    emb = Embedder(OllamaClient(cfg, http_json=shifting), cfg)
    emb.refresh()
    assert emb.warm() is True and emb.dim == 4
    assert emb.query("a") is not None and emb.dim == 6 and emb.dim_changed is True


# ---- 14: lab and vocabulary -----------------------------------------------------------------------------------
@pytest.mark.slow
def test_lab_identical_to_m8(capsys):
    from engrama.lab.cli import main as lab_main
    assert lab_main(["sim", "--recipe", str(ROOT / "engrama" / "recipes" / "default-v1.toml"), "--days", "1", "--seed", "1",
                     "--profile", "attentive"]) == 0
    assert json.loads(capsys.readouterr().out) == json.loads(LAB_FIXTURE.read_text(encoding="utf-8"))


def test_vocab_frozen():
    assert vocab.DIGITAL_IDS == ("ram", "defrag", "update", "cache", "cooler")
    assert vocab.VARIANTS == ("jump", "dance", "yawn", "nap_clock", "chase", "look_cursor", "peek", "dig", "found")
    assert vocab.DISPLAY_MODES == ("terrarium", "overlay")


# ---- wiring ---------------------------------------------------------------------------------------------------
def test_memory_summary_is_cached_and_follows_deletes(tmp_path):
    fe = FakeEmbedder(status="ready")
    svc, mem = make(tmp_path, fe)
    mem.upsert_fact("a", "cachorro", 0.5, "chat")
    prov = _memory_provider(mem, svc.working, svc)
    calls = []
    real = mem.vector_counts
    mem.vector_counts = lambda: (calls.append(1), real())[1]
    for _ in range(50):   # the Mind View asks every frame
        prov.summary()
    assert len(calls) == 1
    prov.delete_fact("a")
    assert prov.summary()["facts"] == 0 and len(calls) == 2


@pytest.mark.slow
def test_smoke_frames(tmp_path):
    r = subprocess.run([sys.executable, "-m", "engrama", "--frames", "120", "--no-llm", "--data-dir",
                        str(tmp_path / "smoke")], cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-500:]
