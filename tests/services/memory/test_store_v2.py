import re
import sqlite3

from engrama.services.memory import (CURRENT_MIN_SALIENCE, MAX_EPISODES,
                                      MAX_FACTS)
from engrama.services.memory.store import MemoryStore

DAY = 86400.0

M3_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes(
    id INTEGER PRIMARY KEY, t REAL, kind TEXT, summary TEXT,
    valence REAL, importance REAL, topic TEXT NULL);
CREATE TABLE IF NOT EXISTS facts(
    id INTEGER PRIMARY KEY, key TEXT UNIQUE, value TEXT,
    confidence REAL, source TEXT, t REAL);
CREATE TABLE IF NOT EXISTS topics(name TEXT PRIMARY KEY, affinity REAL, t REAL);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
INSERT OR IGNORE INTO meta(k, v) VALUES('schema_version', '1');
"""


class Clock:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


def make(tmp_path):
    clock = Clock()
    return MemoryStore(tmp_path / "memory.sqlite", now_fn=clock), clock


def test_migrates_m3_db(tmp_path):
    path = tmp_path / "memory.sqlite"
    con = sqlite3.connect(path)
    con.executescript(M3_SCHEMA)
    con.execute("INSERT INTO episodes(t,kind,summary,valence,importance,topic) VALUES(1,'chat','a',0,0.3,NULL)")
    con.execute("INSERT INTO episodes(t,kind,summary,valence,importance,topic) VALUES(2,'chat','b',0,0.3,NULL)")
    con.execute("INSERT INTO facts(key,value,confidence,source,t) VALUES('nome','Ana',0.8,'chat',1)")
    con.execute("INSERT INTO topics(name,affinity,t) VALUES('Jogos',0.4,5)")
    con.commit()
    con.close()
    s = MemoryStore(path, now_fn=Clock())
    assert s._db.execute("SELECT v FROM meta WHERE k='schema_version'").fetchone()[0] == "2"
    assert MemoryStore.schema_version == 2
    assert len(s.recent(10)) == 2
    assert s.facts() == [("nome", "Ana")]
    assert s.top_topics(5) == [("jogo", 0.4)]
    assert s.opinion_rows() == []
    s.close()
    MemoryStore(path, now_fn=Clock()).close()  # reopening a v2 db is a no-op


def test_migration_merges_duplicate_topics(tmp_path):
    path = tmp_path / "memory.sqlite"
    con = sqlite3.connect(path)
    con.executescript(M3_SCHEMA)
    con.executemany("INSERT INTO topics(name,affinity,t) VALUES(?,?,?)",
                    [("Jogos", 0.6, 1), ("games", 0.7, 9), ("Música", 0.2, 3)])
    con.commit()
    con.close()
    s = MemoryStore(path, now_fn=Clock())
    assert s.top_topics(5) == [("jogo", 1.0), ("musica", 0.2)]
    s.close()


def test_corrupt_db_is_set_aside(tmp_path):
    path = tmp_path / "memory.sqlite"
    path.write_bytes(b"this is definitely not a sqlite database" * 50)
    s, _ = make(tmp_path)
    assert list(tmp_path.glob("memory.sqlite.corrupt-*"))
    assert s.recent(10) == [] and s.facts() == []
    s.add_episode("chat", "ok")
    assert s.recent(1) == ["ok"]
    s.close()


def test_salience_current_and_past(tmp_path):
    s, clock = make(tmp_path)
    t0 = clock.t
    for _ in range(5):
        s.bump_topic("jogo", 0.2)
    clock.t = t0 + 20 * DAY
    for _ in range(3):
        s.bump_topic("musica", 0.1)
    clock.t = t0 + 21 * DAY
    assert s.current_topics() == ["musica"]
    assert "jogo" in s.past_topics()
    assert "musica" not in s.past_topics()
    rows = {r["name"]: r for r in s.topic_rows()}
    assert rows["jogo"]["mentions"] == 5 and rows["jogo"]["source"] == "chat"
    assert rows["jogo"]["salience"] < CURRENT_MIN_SALIENCE
    s.close()


def test_bump_topic_normalizes_and_returns_name(tmp_path):
    s, _ = make(tmp_path)
    assert s.bump_topic("Programação", 0.2) == "programacao"
    assert s.bump_topic("programming", 0.2) == "programacao"
    assert s.top_topics(5) == [("programacao", 0.4)]
    s.close()


def test_salience_clock_backwards_is_safe(tmp_path):
    s, clock = make(tmp_path)
    s.bump_topic("jogo", 0.2)
    stored = s.topic_rows()[0]["salience"]
    clock.t -= 10 * DAY
    sal = s.topic_rows()[0]["salience"]
    assert 0.0 <= sal <= stored
    s.bump_topic("jogo", 0.2)
    assert s.topic_rows()[0]["salience"] >= 0.0
    s.current_topics()
    s.past_topics()
    s.close()


def test_fact_consolidation(tmp_path):
    s, _ = make(tmp_path)
    assert s.upsert_fact("nome", "Ana", 0.6, "chat") is True
    s.upsert_fact("nome", "Ana", 0.6, "chat")
    row = s.fact_rows()[0]
    assert abs(row["confidence"] - (0.6 + 0.5 * 0.4 * 0.6)) < 1e-9
    s.upsert_fact("nome", "Bia", 0.9, "chat")
    assert s.facts() == [("nome", "Bia")]
    s.upsert_fact("nome", "Cris", 0.2, "chat")
    assert s.facts() == [("nome", "Bia")]
    s.close()


def test_delete_topic_removes_linked_and_mentioning_episodes(tmp_path):
    s, _ = make(tmp_path)
    s.bump_topic("jogo", 0.5)
    s.add_episode("chat", "conversa sobre algo", topics=["jogo"])
    s.add_episode("chat", "falou de jogos hoje")
    s.add_episode("chat", "comeu maca")
    s._db.execute("INSERT INTO opinions(topic, lean, experience, confidence, t) VALUES('jogo',0.5,0,0,0)")
    s._db.commit()
    assert s.delete_topic("Jogos") == 2
    assert s.recent(10) == ["comeu maca"]
    assert s.opinion_rows() == [] and s.topic_rows() == []
    assert s.bump_topic("jogo", 0.5) == ""
    assert s.is_blocked("topic", "jogo")
    assert s._db.execute("SELECT COUNT(*) FROM episode_links").fetchone()[0] == 0
    s.close()


def test_delete_fact_removes_episodes_with_value(tmp_path):
    s, _ = make(tmp_path)
    s.upsert_fact("time", "Palmeiras", 0.8, "chat")
    s.add_episode("chat", "ele torce pro palmeiras", facts=["time"])
    s.add_episode("chat", "gosta de banana")
    assert s.delete_fact("time") == 1
    assert s.facts() == [] and s.recent(10) == ["gosta de banana"]
    s.close()


def test_blocked_until_newer_mention(tmp_path):
    s, clock = make(tmp_path)
    s.upsert_fact("nome", "Ana", 0.8, "chat")
    t_del = clock.t
    s.delete_fact("nome")
    assert s.facts() == []
    assert s.is_blocked("fact", "nome")
    assert s.is_blocked("fact", "nome", since=t_del - 5)
    assert not s.is_blocked("fact", "nome", since=t_del + 5)
    assert s.upsert_fact("nome", "Ana", 0.9, "chat") is False
    assert s.unblock_on_new_mention("fact", "nome", t_del - 5) is False
    assert s.upsert_fact("nome", "Ana", 0.9, "chat") is False
    s.unblock_on_new_mention("fact", "nome", t_del + 5)
    assert s.upsert_fact("nome", "Ana", 0.9, "chat") is True
    assert s.facts() == [("nome", "Ana")]
    s.close()


def test_forget_all_keeps_innate_lean(tmp_path):
    s, _ = make(tmp_path)
    s.bump_topic("jogo", 0.5)
    s.upsert_fact("nome", "Ana", 0.8, "chat")
    s.add_episode("chat", "oi", topics=["jogo"], facts=["nome"])
    s.add_episode("reflection", "pensou", importance=0.6)
    s._db.execute("INSERT INTO opinions(topic, lean, experience, confidence, phrase, phrase_lang, t)"
                  " VALUES('jogo',-0.7,0.4,0.5,'x','pt',0)")
    s._db.commit()
    s.forget_all_about_user()
    op = s.opinion_rows()
    assert len(op) == 1 and op[0]["lean"] == -0.7
    assert op[0]["experience"] == 0 and op[0]["phrase"] is None and op[0]["confidence"] == 0
    assert s.facts() == [] and s.topic_rows() == [] and s.recent(10) == []
    assert s.recent_reflections() == []
    assert s.is_blocked("topic", "jogo") and s.is_blocked("fact", "nome")
    assert s._db.execute("SELECT v FROM meta WHERE k='schema_version'").fetchone()[0] == "2"
    s.close()


def test_recent_reflections(tmp_path):
    s, clock = make(tmp_path)
    for w in ("a", "b", "c", "d"):
        clock.t += 1
        s.add_episode("reflection", w)
    s.add_episode("chat", "nao")
    assert s.recent_reflections(3) == ["d", "c", "b"]
    s.close()


def test_caps_and_compaction(tmp_path):
    s, clock = make(tmp_path)
    now = clock.t
    rows = []
    for i in range(2500):
        t = now - 30 * DAY + i * (30 * DAY / 2500)
        rows.append((t, "feed" if i % 2 else "chat", f"episodio {i}", 0.0, 0.1,
                     "jogo" if i % 3 == 0 else None))
    s._db.executemany(
        "INSERT INTO episodes(t,kind,summary,valence,importance,topic) VALUES(?,?,?,?,?,?)", rows)
    s._db.executemany(
        "INSERT INTO facts(key,value,confidence,source,t) VALUES(?,?,?,?,?)",
        [(f"k{i}", f"v{i}", (i % 100) / 100, "chat", now - i) for i in range(400)])
    s._db.commit()
    s.forget(now)
    n_ep = s._db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
    n_fa = s._db.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    assert n_ep <= MAX_EPISODES and n_fa <= MAX_FACTS
    summaries = [r[0] for r in s._db.execute("SELECT summary FROM episodes WHERE importance=0.35")]
    assert summaries
    assert not any(re.search(r"\d", x) for x in summaries)
    assert any("jogo" in x for x in summaries)
    s.close()


def test_enforce_caps_drops_least_important(tmp_path):
    s, clock = make(tmp_path)
    rows = [(clock.t + i, "chat", f"e{i}", 0.0, 0.9 if i < 5 else 0.4, None)
            for i in range(MAX_EPISODES + 20)]
    s._db.executemany(
        "INSERT INTO episodes(t,kind,summary,valence,importance,topic) VALUES(?,?,?,?,?,?)", rows)
    s._db.commit()
    s.enforce_caps()
    assert s._db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == MAX_EPISODES
    kept = {r[0] for r in s._db.execute("SELECT summary FROM episodes")}
    assert {f"e{i}" for i in range(5)} <= kept
    s.close()
