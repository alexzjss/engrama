"""M9 Tarefa 2: vector table (schema v3), similarity search and vector-aware deletion."""
import shutil
import sqlite3
import statistics
import time
from pathlib import Path

import numpy as np
import pytest

from engrama.services.memory import (SEARCH_BUDGET_MS,
                                     SEM_MIN_SIM, VECTOR_RAM_MAX_MB, W_IMPORTANCE, W_RECENCY,
                                     W_RELEVANCE, W_SEM, W_WORD)
from engrama.services.memory.store import base as store_base_mod
from engrama.services.memory.store import generations as store_gen_mod
from engrama.services.memory.store import MemoryStore, VECTOR_KINDS
from tests.services.fake_embedder import FakeEmbedder

DAY = 86400.0
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "m8_memory_v2.sqlite"
MODEL = "embeddinggemma"
EMB = FakeEmbedder()


class Clock:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


def make(tmp_path, model=MODEL):
    clock = Clock()
    s = MemoryStore(tmp_path / "memory.sqlite", now_fn=clock)
    if model:
        s.set_vector_model(model)
    return s, clock


def index_all(s, model=MODEL, batch=1000):
    items = s.unindexed(batch)
    vecs = EMB.documents([t for _, _, t, _ in items])
    n = s.put_vectors(model, [(k, r, h, v) for (k, r, _t, h), v in zip(items, vecs)])
    assert n == len(items)
    return n


def vec_rows(s):
    return s._db.execute("SELECT kind, ref FROM vectors").fetchall()


def assert_no_orphans(s):
    ep = {str(r[0]): r[1] for r in s._db.execute("SELECT id, kind FROM episodes")}
    facts = {r[0] for r in s._db.execute("SELECT key FROM facts")}
    topics = {r[0] for r in s._db.execute("SELECT name FROM topics")}
    for kind, ref in vec_rows(s):
        if kind == "episode":
            assert ref in ep and ep[ref] != "ancestral", (kind, ref)
        elif kind == "ancestral":
            assert ref in ep and ep[ref] == "ancestral", (kind, ref)
        elif kind == "fact":
            assert ref in facts, (kind, ref)
        elif kind == "topic":
            assert ref in topics, (kind, ref)
        else:
            raise AssertionError(kind)


def seeded(tmp_path):
    s, clock = make(tmp_path)
    s.upsert_fact("jogo_favorito", "hollow knight", 0.8, "chat")
    s.upsert_fact("nome", "Ana", 0.9, "chat")
    s.bump_topic("cachorro", 0.5)
    s.bump_topic("trabalho", 0.2)
    s.add_episode("chat", "falamos do cachorro", 0.3, 0.6, topic="cachorro", topics=["cachorro"],
                  facts=["nome"])
    s.add_episode("chat", "o chefe demitiu o usuario", -0.5, 0.8, topic="trabalho",
                  topics=["trabalho"])
    s.add_episode("feed", "comeu biscoito", 0.2, 0.3)
    return s, clock


# ---- migration / pragma --------------------------------------------------------------------------

def _dump(path):
    con = sqlite3.connect(path)
    try:
        out = {}
        for (name,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
            out[name] = con.execute(f"SELECT * FROM {name} ORDER BY 1, 2").fetchall()
        return out
    finally:
        con.close()


def test_migrate_v2_to_v3_keeps_everything(tmp_path):
    """FIXTURE was written by the real M8 MemoryStore (schema v2)."""
    path = tmp_path / "memory.sqlite"
    shutil.copy(FIXTURE, path)
    before = _dump(path)
    assert before["meta"] and ("schema_version", "2") in before["meta"]
    assert "vectors" not in before
    assert before["episodes"] and before["facts"] and before["topics"] and before["opinions"]
    assert before["episode_links"] and before["blocklist"] and before["app_categories"]
    s = MemoryStore(path, now_fn=Clock())
    assert MemoryStore.schema_version == 3
    assert s.meta_get("schema_version") == "3"
    s.close()
    after = _dump(path)
    for table, rows in before.items():
        if table == "meta":
            assert sorted(r for r in after["meta"] if r[0] != "schema_version") == \
                sorted(r for r in rows if r[0] != "schema_version")
        else:
            assert after[table] == rows, table
    assert after["vectors"] == []
    cols = [r[1] for r in sqlite3.connect(path).execute("PRAGMA table_info(vectors)")]
    assert cols == ["kind", "ref", "model", "dim", "h", "vec", "t"]
    # reopening a v3 DB does not migrate again and keeps working
    s = MemoryStore(path, now_fn=Clock())
    assert s.meta_get("schema_version") == "3"
    assert s.facts() == [("nome", "Ana"), ("jogo_favorito", "hollow knight")]
    s.set_vector_model(MODEL)
    assert index_all(s) > 0
    s.close()


def test_migrate_v2_failure_rolls_back(tmp_path, monkeypatch):
    path = tmp_path / "memory.sqlite"
    shutil.copy(FIXTURE, path)
    before = _dump(path)
    monkeypatch.setattr(store_base_mod, "_V3_STATEMENTS", ("CREATE TABLE vectors(x)", "NOT SQL"))
    with pytest.raises(sqlite3.Error):
        MemoryStore(path, now_fn=Clock())
    assert _dump(path) == before


def test_new_db_is_v3(tmp_path):
    s, _ = make(tmp_path, model="")
    assert s.meta_get("schema_version") == "3"
    assert s._db.execute("SELECT COUNT(*) FROM vectors").fetchone()[0] == 0
    s.close()


def test_secure_delete_on(tmp_path):
    s, _ = make(tmp_path)
    assert s._db.execute("PRAGMA secure_delete").fetchone()[0] == 1
    s.close()


# ---- unindexed / put_vectors ---------------------------------------------------------------------

def test_unindexed_order_and_texts(tmp_path):
    s, clock = make(tmp_path)
    s.upsert_fact("jogo_favorito", "hollow knight", 0.8, "chat")
    s.upsert_fact("nome", "Ana", 0.95, "chat")
    s.bump_topic("cachorro", 0.5)
    clock.t += 1
    s.bump_topic("cachorro", 0.5)       # more salient than "trabalho"
    s.bump_topic("trabalho", 0.2)
    e_low = s.add_episode("chat", "conversa 12 sobre jogos", 0.0, 0.3, topic="jogo")
    clock.t += 5
    e_hi = s.add_episode("chat", "o chefe demitiu o usuario", -0.5, 0.9)
    s.add_episode("atividade", "   ", 0.0, 0.9)  # nothing to embed
    s._db.execute("INSERT INTO episodes(t, kind, summary, valence, importance, topic)"
                  " VALUES(1,'ancestral','sonho 7 com um mar',0,0.6,NULL)")
    s._db.commit()
    items = s.unindexed(100)
    kinds = [k for k, _, _, _ in items]
    assert kinds == ["fact", "fact", "topic", "topic", "ancestral", "episode", "episode"]
    texts = {(k, r): t for k, r, t, _ in items}
    assert texts[("fact", "jogo_favorito")] == "jogo favorito: hollow knight"
    assert texts[("fact", "nome")] == "nome: Ana"
    assert [r for k, r, _, _ in items if k == "fact"] == ["nome", "jogo_favorito"]   # confidence
    assert [r for k, r, _, _ in items if k == "topic"] == ["cachorro", "trabalho"]   # salience
    assert [r for k, r, _, _ in items if k == "episode"] == [str(e_hi), str(e_low)]
    assert texts[("episode", str(e_low))] == "conversa sobre jogos jogo"
    assert texts[("ancestral", [r for k, r, _, _ in items if k == "ancestral"][0])] == "sonho com um mar"
    assert not any(any(c.isdigit() for c in t) for t in texts.values())
    assert all(len(h) == 16 for _, _, _, h in items)
    assert len(s.unindexed(3)) == 3
    # nothing with a valid vector comes back
    n = index_all(s)
    assert n == len(items) and s.unindexed(100) == []
    # a vector from another model does not count
    s._db.execute("UPDATE vectors SET model='other'")
    assert len(s.unindexed(100)) == len(items)
    s.close()


def test_put_vectors_checks_model_ref_hash(tmp_path):
    s, _ = make(tmp_path)
    s.upsert_fact("nome", "Ana", 0.9, "chat")
    s.add_episode("chat", "falamos do cachorro", 0.3, 0.6)
    s.upsert_fact("cor", "azul", 0.8, "chat")
    items = s.unindexed(10)
    v = EMB.documents([t for _, _, t, _ in items])
    pack = [(k, r, h, x) for (k, r, _t, h), x in zip(items, v)]
    assert s.put_vectors("other-model", pack) == 0                  # wrong model
    assert s.put_vectors(MODEL, [(k, r, "0" * 16, x) for k, r, h, x in pack]) == 0   # wrong hash
    s.delete_fact("cor")
    s.upsert_fact("nome", "Bia", 0.9, "chat")                       # value changed after unindexed()
    assert s.put_vectors(MODEL, pack) == 1                          # only the episode survives
    assert vec_rows(s) == [("episode", "1")]
    assert s.put_vectors(MODEL, [("episode", "999", "0" * 16, v[0]), ("nada", "x", "0" * 16, v[0])]) == 0
    s.set_vector_model("new")                                       # model switched mid-flight
    assert s.put_vectors(MODEL, pack) == 0
    assert vec_rows(s) == []
    s.close()


def test_put_vectors_rejects_bad_vectors(tmp_path):
    s, _ = make(tmp_path)
    s.upsert_fact("nome", "Ana", 0.9, "chat")
    (k, r, _t, h), = s.unindexed(1)
    for bad in (np.zeros(8), np.full(8, np.nan), np.full(8, np.inf), np.zeros((2, 4)), np.zeros(0)):
        assert s.put_vectors(MODEL, [(k, r, h, bad)]) == 0
    assert vec_rows(s) == []
    s.close()


def test_vectors_stored_as_float16(tmp_path):
    s, _ = seeded(tmp_path)
    index_all(s)
    dim, blob = s._db.execute("SELECT dim, vec FROM vectors LIMIT 1").fetchone()
    assert dim == EMB.dim and len(blob) == dim * 2
    s.close()


# ---- similar -------------------------------------------------------------------------------------

def test_similar_ranks_and_threshold(tmp_path):
    s, _ = make(tmp_path)
    s.add_episode("chat", "o cachorro latiu muito", 0.3, 0.5)
    s.add_episode("chat", "o gato dormiu no sofa", 0.3, 0.5)
    s.add_episode("chat", "o chefe demitiu o usuario do trabalho", -0.5, 0.5)
    index_all(s)
    q = EMB.query("bichinho")
    hits = s.similar(q, "episode", 5, SEM_MIN_SIM)
    refs = [r for r, _ in hits]
    assert refs[0] == "1" and "3" not in refs
    assert [x for _, x in hits] == sorted((x for _, x in hits), reverse=True)
    assert all(x >= SEM_MIN_SIM for _, x in hits)
    assert len(s.similar(q, "episode", 1, 0.0)) == 1
    assert s.similar(q, "fact", 5, 0.0) == []
    assert s.similar(q, "bogus", 5, 0.0) == []
    assert s.similar(np.zeros(EMB.dim), "episode", 5, 0.0) == []
    assert s.similar(np.full(EMB.dim, np.nan), "episode", 5, 0.0) == []
    s.close()


def test_similar_without_model_or_vectors(tmp_path):
    s, _ = make(tmp_path, model="")
    s.add_episode("chat", "o cachorro latiu", 0.3, 0.5)
    assert s.similar(EMB.query("cachorro"), "episode", 5, 0.0) == []
    s.set_vector_model(MODEL)
    assert s.similar(EMB.query("cachorro"), "episode", 5, 0.0) == []
    s.close()


def test_similar_ignores_other_dim(tmp_path):
    s, _ = make(tmp_path)
    s.add_episode("chat", "o cachorro latiu", 0.3, 0.5)
    s.add_episode("chat", "o gato dormiu", 0.3, 0.5)
    items = s.unindexed(10)
    a, b = FakeEmbedder(dim=16), FakeEmbedder(dim=24)
    s.put_vectors(MODEL, [(k, r, h, a._vec(t)) for k, r, t, h in items[:1]])
    s.put_vectors(MODEL, [(k, r, h, b._vec(t)) for k, r, t, h in items[1:]])
    hits16 = s.similar(a.query("cachorro"), "episode", 5, 0.0)
    hits24 = s.similar(b.query("gato"), "episode", 5, 0.0)
    assert [r for r, _ in hits16] == [items[0][1]]
    assert [r for r, _ in hits24] == [items[1][1]]
    assert s.similar(FakeEmbedder(dim=14).query("x"), "episode", 5, 0.0) == []
    s.close()


def test_similar_cache_invalidated_on_write_and_delete(tmp_path):
    s, _ = make(tmp_path)
    s.upsert_fact("pet", "cachorro", 0.8, "chat")
    index_all(s)
    q = EMB.query("cachorro")
    assert [r for r, _ in s.similar(q, "fact", 5, 0.5)] == ["pet"]
    assert s._vec_cache                          # built
    s.upsert_fact("bicho", "gato", 0.8, "chat")
    index_all(s)                                 # write -> new version
    assert {r for r, _ in s.similar(q, "fact", 5, 0.5)} == {"pet", "bicho"}
    s.delete_fact("pet")                         # delete -> new version
    assert [r for r, _ in s.similar(q, "fact", 5, 0.5)] == ["bicho"]
    s.release_vectors()
    assert not s._vec_cache
    assert [r for r, _ in s.similar(q, "fact", 5, 0.5)] == ["bicho"]
    s.close()


def test_vector_counts(tmp_path):
    s, _ = seeded(tmp_path)
    assert s.vector_counts() == {"vectors": 0, "items": 3 + 2 + 2}
    index_all(s)
    assert s.vector_counts() == {"vectors": 7, "items": 7}
    s.close()


# ---- deletion paths ------------------------------------------------------------------------------

def _fill(s, clock):
    s.upsert_fact("jogo_favorito", "hollow knight", 0.8, "chat")
    s.upsert_fact("nome", "Ana", 0.9, "chat")
    s.bump_topic("cachorro", 0.5)
    s.bump_topic("trabalho", 0.2)
    s.add_episode("chat", "falamos do cachorro", 0.3, 0.6, topic="cachorro", topics=["cachorro"],
                  facts=["nome"])
    s.add_episode("chat", "o chefe demitiu o usuario", -0.5, 0.8, topic="trabalho",
                  topics=["trabalho"])
    s.add_episode("feed", "comeu biscoito", 0.2, 0.3)
    s._db.execute("INSERT INTO episodes(t, kind, summary, valence, importance, topic)"
                  " VALUES(1,'ancestral','sonho com um gato',0,0.6,NULL)")
    s._db.commit()
    index_all(s)


def _del_fact(s, clock):
    s.delete_fact("jogo_favorito")
    return [("fact", "jogo_favorito")]


def _del_topic(s, clock):
    s.delete_topic("cachorro")          # also drops the linked episode
    return [("topic", "cachorro"), ("episode", "1")]


def _forget_all(s, clock):
    s.forget_all_about_user()
    return [("fact", "nome"), ("topic", "trabalho"), ("episode", "2"), ("ancestral", "4")]


def _caps(s, clock):
    s.enforce_caps()                    # caps lowered by the test
    return None


def _forget(s, clock):
    old = s.add_episode("chat", "conversa velha sobre musica", 0.0, 0.1, topic="musica")
    s._db.execute("UPDATE episodes SET t=? WHERE id=?", (clock.t - 10 * DAY, old))
    s._db.commit()
    index_all(s)
    assert ("episode", str(old)) in vec_rows(s)
    assert s.forget() == 1
    return [("episode", str(old))]


def _new_gen(s, clock):
    s.new_generation(["sonho novo"])
    return [("fact", "nome"), ("topic", "cachorro"), ("episode", "1"), ("ancestral", "4")]


def _fact_value(s, clock):
    s.upsert_fact("nome", "Bia", 0.9, "chat")
    return [("fact", "nome")]


@pytest.mark.parametrize("path", [_del_fact, _del_topic, _forget_all, _caps, _forget, _new_gen,
                                  _fact_value])
def test_every_delete_path_drops_vectors(tmp_path, monkeypatch, path):
    s, clock = make(tmp_path)
    _fill(s, clock)
    assert len(vec_rows(s)) == 8
    if path is _caps:
        for i in range(6):
            s.upsert_fact(f"extra{i}", f"valor{i}x", 0.1 + i * 0.001, "chat")
            s.bump_topic(f"assunto{i}", 0.1)
        index_all(s)
        before = set(vec_rows(s))
        monkeypatch.setattr(store_gen_mod, "MAX_EPISODES", 3)
        monkeypatch.setattr(store_gen_mod, "MAX_FACTS", 3)
        monkeypatch.setattr(store_gen_mod, "MAX_TOPICS", 3)
    gone = path(s, clock)
    assert_no_orphans(s)
    if path is _caps:
        assert len(vec_rows(s)) < len(before)
        assert s._db.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 3
        assert s._db.execute("SELECT COUNT(*) FROM topics").fetchone()[0] == 3
        assert s._db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 3
        gone = sorted(before - set(vec_rows(s)))
        assert {k for k, _ in gone} == {"fact", "topic", "episode"}
    for g in gone:
        assert g not in vec_rows(s)
    # nothing returned by similar points at something that no longer exists
    live = set(vec_rows(s))
    for kind in VECTOR_KINDS:
        for ref, _ in s.similar(EMB.query("cachorro gato nome trabalho"), kind, 50, -1.0):
            assert (kind, ref) in live
        assert not {(kind, r) for r, _ in s.similar(EMB.query("cachorro"), kind, 50, -1.0)} & set(gone)
    if path is _forget_all or path is _new_gen:
        assert vec_rows(s) == []
    if path is _fact_value:
        # the old vector encoded the old value: the fact is pending again
        assert ("fact", "nome") in {(k, r) for k, r, _, _ in s.unindexed(50)}
    s.close()


def test_delete_topic_drops_vectors_of_mentioning_episodes(tmp_path):
    s, clock = make(tmp_path)
    s.bump_topic("cachorro", 0.5)
    s.add_episode("chat", "o cachorro latiu", 0.3, 0.6)          # no link, only mentions the topic
    s.add_episode("chat", "falamos de outra coisa", 0.3, 0.6, topics=["cachorro"])
    s.add_episode("chat", "sem relacao", 0.3, 0.6)
    index_all(s)
    assert s.delete_topic("cachorro") == 2
    assert [r for k, r in vec_rows(s) if k == "episode"] == ["3"]
    assert ("topic", "cachorro") not in vec_rows(s)
    assert_no_orphans(s)
    s.close()


def test_delete_fact_drops_vectors_of_episodes_with_value(tmp_path):
    s, _ = make(tmp_path)
    s.upsert_fact("time", "Flamengo", 0.8, "chat")
    s.add_episode("chat", "o usuario torce pro Flamengo", 0.3, 0.6)
    s.add_episode("chat", "outra coisa", 0.3, 0.6)
    index_all(s)
    s.delete_fact("time")
    assert vec_rows(s) == [("episode", "2")]
    s.close()


def test_forget_all_keeps_model_name(tmp_path):
    s, clock = make(tmp_path)
    _fill(s, clock)
    s.forget_all_about_user()
    assert s.vector_model() == MODEL
    assert vec_rows(s) == []
    s.close()


def test_new_generation_keeps_vector_model(tmp_path):
    s, clock = make(tmp_path)
    _fill(s, clock)
    s.new_generation(["um sonho"])
    assert s.vector_model() == MODEL and s.meta_get("schema_version") == "3"
    assert vec_rows(s) == []
    s.close()


def test_same_value_upsert_keeps_vector(tmp_path):
    s, _ = make(tmp_path)
    s.upsert_fact("nome", "Ana", 0.5, "chat")
    index_all(s)
    s.upsert_fact("nome", "Ana", 0.9, "chat")
    assert ("fact", "nome") in vec_rows(s)
    s.upsert_fact("nome", "Bia", 0.1, "chat")        # rejected: value unchanged, vector kept
    assert ("fact", "nome") in vec_rows(s) and s.facts() == [("nome", "Ana")]
    s.close()


def test_orphan_vector_rows_cannot_survive_caps(tmp_path, monkeypatch):
    """A stray row (e.g. written by an older build) is swept by enforce_caps."""
    s, _ = make(tmp_path)
    s.upsert_fact("nome", "Ana", 0.5, "chat")
    index_all(s)
    s._db.execute("INSERT INTO vectors VALUES('fact','fantasma','m',2,'h',x'0000',0)")
    s._db.commit()
    s.enforce_caps()
    assert vec_rows(s) == [("fact", "nome")]
    s.close()


def test_set_vector_model_switch_drops(tmp_path):
    s, _ = seeded(tmp_path)
    index_all(s)
    assert len(vec_rows(s)) == 7
    assert s.set_vector_model(MODEL) is False        # same model: kept
    assert len(vec_rows(s)) == 7
    assert s.set_vector_model("nomic-embed-text") is True
    assert vec_rows(s) == [] and s.vector_model() == "nomic-embed-text"
    assert s.similar(EMB.query("cachorro"), "episode", 5, 0.0) == []
    s.close()


def test_drop_vectors(tmp_path):
    s, _ = seeded(tmp_path)
    index_all(s)
    s.similar(EMB.query("cachorro"), "episode", 5, 0.0)
    s.drop_vectors()
    assert vec_rows(s) == [] and s.vector_model() == ""
    assert s.similar(EMB.query("cachorro"), "episode", 5, 0.0) == []
    s.close()


def test_deleted_bytes_are_scrubbed(tmp_path):
    s, _ = make(tmp_path)
    s.upsert_fact("segredo", "ZXQSEGREDOUNICOZXQ", 0.9, "chat")
    s.add_episode("chat", "ZXQSEGREDOUNICOZXQ foi dito", 0.0, 0.5)
    index_all(s)
    s.delete_fact("segredo")
    s.close()
    raw = (tmp_path / "memory.sqlite").read_bytes()
    assert b"ZXQSEGREDOUNICOZXQ" not in raw


# ---- retrieve / retrieve_ancestral ----------------------------------------------------------------

def _m4_retrieve(s, words, k):
    import math
    now = s._now()
    ws = [w.lower() for w in words if w]
    scored = []
    for _id, t, summary, importance, topic in s._db.execute(
            "SELECT id, t, summary, importance, topic FROM episodes WHERE kind != 'ancestral'"):
        text = f"{summary} {topic or ''}".lower()
        overlap = sum(1 for w in ws if w in text) / len(ws) if ws else 0.0
        recency = math.exp(-max(0.0, now - t) / (7 * DAY))
        scored.append((0.5 * importance + 0.3 * recency + 0.2 * overlap, _id, summary))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [x[2] for x in scored[:k]]


def test_retrieve_without_sims_is_m4(tmp_path):
    s, clock = seeded(tmp_path)
    clock.t += 3 * DAY
    s.add_episode("chat", "falamos de musica", 0.1, 0.4, topic="musica")
    for words in (["cachorro"], ["chefe", "demitiu"], [], ["xyz"]):
        for k in (1, 3, 5):
            assert s.retrieve(words, k) == _m4_retrieve(s, words, k)
            assert s.retrieve(words, k, sims=None) == _m4_retrieve(s, words, k)
    s.close()


def test_retrieve_with_sims_hybrid(tmp_path):
    s, clock = make(tmp_path)
    a = s.add_episode("chat", "o cachorro latiu muito", 0.3, 0.3)        # semantically close
    clock.t += 2 * DAY
    b = s.add_episode("chat", "falamos de trabalho", 0.3, 0.4)
    c = s.add_episode("chat", "comeu biscoito", 0.3, 0.5)
    # M4 order for words with no match: importance/recency decide -> c, b, a
    assert s.retrieve(["bichinho"], 3) == ["comeu biscoito", "falamos de trabalho", "o cachorro latiu muito"]
    out = s.retrieve(["bichinho"], 3, sims={a: 0.95, b: 0.2})
    assert out[0] == "o cachorro latiu muito"
    # exact formula
    import math
    now = s._now()
    def score(eid, imp, t, sim, ov):
        sp = max(0.0, (sim - SEM_MIN_SIM) / (1 - SEM_MIN_SIM))
        return (W_IMPORTANCE * imp + W_RECENCY * math.exp(-(now - t) / (7 * DAY))
                + W_RELEVANCE * (W_SEM * sp + W_WORD * ov))
    assert score(a, 0.3, now - 2 * DAY, 0.95, 0) > score(c, 0.5, now - 0, 0.0, 0) - 1  # sanity
    # a sim below the threshold adds nothing: same as sim 0 / absent
    assert s.retrieve(["bichinho"], 3, sims={a: 0.3, b: 0.49}) == s.retrieve(["bichinho"], 3, sims={})
    # ancestral episodes never come back from retrieve
    s._db.execute("INSERT INTO episodes(t, kind, summary, valence, importance, topic)"
                  " VALUES(1,'ancestral','sonho com bichinho',0,0.9,NULL)")
    s._db.commit()
    assert "sonho com bichinho" not in s.retrieve(["bichinho"], 10, sims={4: 1.0})
    s.close()


def test_retrieve_ancestral_semantic(tmp_path):
    s, _ = make(tmp_path)
    s.new_generation(["sonho com um gato dormindo", "sonho com uma torre", "sonho de chuva no mar"])
    ids = [r[0] for r in s._db.execute("SELECT id FROM episodes ORDER BY id")]
    # M4 path: words only
    assert s.retrieve_ancestral(["chuva"], 1) == ["sonho de chuva no mar"]
    assert s.retrieve_ancestral(["bichinho"], 1) == []
    assert s.retrieve_ancestral(["bichinho"], 1, sims=None) == []
    # semantic hit without any word in common
    assert s.retrieve_ancestral(["bichinho"], 1, sims={ids[0]: 0.9}) == ["sonho com um gato dormindo"]
    # below the threshold and no word: not a candidate
    assert s.retrieve_ancestral(["bichinho"], 3, sims={ids[0]: 0.4}) == []
    # word hit still enters even with a low sim; ordering by relevance
    out = s.retrieve_ancestral(["chuva"], 3, sims={ids[0]: 0.9, ids[2]: 0.1})
    assert out == ["sonho com um gato dormindo", "sonho de chuva no mar"]
    # no words at all but a semantic hit
    assert s.retrieve_ancestral([], 1, sims={ids[1]: 0.8}) == ["sonho com uma torre"]
    assert s.retrieve_ancestral([], 1) == []
    s.close()


# ---- archive -------------------------------------------------------------------------------------

def test_archive_has_no_vectors(tmp_path):
    s, _ = seeded(tmp_path)
    index_all(s)
    dest = tmp_path / "gen" / "1" / "memory.sqlite"
    s.archive_to(dest)
    con = sqlite3.connect(dest)
    assert con.execute("SELECT COUNT(*) FROM vectors").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM meta WHERE k='vector_model'").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 3     # the memory itself is archived
    con.close()
    # the original keeps them
    assert len(vec_rows(s)) == 7 and s.vector_model() == MODEL
    assert s.similar(EMB.query("cachorro"), "episode", 5, 0.0)
    s.close()


# ---- RAM and speed ---------------------------------------------------------------------------------

def _vector_store(tmp_path):
    s, _ = make(tmp_path)
    dim = 768
    rng = np.random.default_rng(1)
    db = s._db
    now = s._now()
    db.executemany(
        "INSERT INTO episodes(t, kind, summary, valence, importance, topic) VALUES(?,?,?,?,?,?)",
        [(now - i, "chat", f"episodio {i}", 0.0, 0.3, None) for i in range(2000)])
    db.executemany("INSERT INTO facts(key, value, confidence, source, t) VALUES(?,?,?,?,?)",
                   [(f"k{i}", f"v{i}", 0.5, "chat", now) for i in range(300)])
    db.executemany(
        "INSERT INTO topics(name, affinity, t, salience, t_salience, first_t, last_t, mentions, source)"
        " VALUES(?,?,?,?,?,?,?,?,?)", [(f"t{i}", 0.1, now, 1.0, now, now, now, 1, "chat") for i in range(300)])
    db.commit()
    for kind, sql in (("episode", "SELECT CAST(id AS TEXT) FROM episodes"),
                      ("fact", "SELECT key FROM facts"), ("topic", "SELECT name FROM topics")):
        refs = [r[0] for r in db.execute(sql)]
        mat = rng.standard_normal((len(refs), dim)).astype(np.float16)
        db.executemany("INSERT INTO vectors(kind, ref, model, dim, h, vec, t) VALUES(?,?,?,?,?,?,?)",
                       [(kind, r, MODEL, dim, "h", mat[i].tobytes(), now) for i, r in enumerate(refs)])
    db.commit()
    q = rng.standard_normal(dim).astype(np.float32)
    return s, q


@pytest.mark.slow
def test_vector_ram_within_budget(tmp_path):
    s, q = _vector_store(tmp_path)
    for kind in ("episode", "fact", "topic"):
        s.similar(q, kind, 5, 0.0)
    cached = sum(v[2].nbytes for v in s._vec_cache.values())
    assert cached <= VECTOR_RAM_MAX_MB * 1024 * 1024
    s.close()


@pytest.mark.slow
@pytest.mark.perf
def test_vector_search_budget(tmp_path):
    s, q = _vector_store(tmp_path)
    for kind in ("episode", "fact", "topic"):
        s.similar(q, kind, 5, 0.0)
    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        for kind in ("episode", "fact", "topic"):
            s.similar(q, kind, 5, 0.0)
        times.append((time.perf_counter() - t0) * 1000)
    assert statistics.median(times) <= SEARCH_BUDGET_MS
    s.close()
