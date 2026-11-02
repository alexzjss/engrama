import sqlite3

from engrama.services.memory.store import MemoryStore
from engrama.services.perception import (ACTIVITY_EPISODE_EVERY_S, PERCEIVED_AFFINITY_CAP,
                                         PERCEIVED_AFFINITY_STEP)
from engrama.services.perception.themes import make_theme_sink


def test_perceived_affinity_capped_and_episode_throttled(tmp_path):
    mem = MemoryStore(tmp_path / "m.sqlite")
    t = 1000.0
    assert mem.bump_perceived("hollow knight", t) == "hollow knight"
    assert abs(mem.top_topics(1)[0][1] - PERCEIVED_AFFINITY_STEP) < 1e-9
    for i in range(100):
        mem.bump_perceived("hollow knight", t + i)
    assert mem.top_topics(1)[0][1] == PERCEIVED_AFFINITY_CAP
    assert len([e for e in mem.recent(50) if "passou um tempo" in e]) == 1
    mem.bump_perceived("hollow knight", t + ACTIVITY_EPISODE_EVERY_S + 1)
    eps = [e for e in mem.recent(50) if "passou um tempo" in e]
    assert len(eps) == 2 and not any(c.isdigit() for c in eps[0])
    assert mem.topic_rows()[0]["source"] == "percepcao"


def test_higher_chat_affinity_not_reduced(tmp_path):
    mem = MemoryStore(tmp_path / "m.sqlite")
    mem.bump_topic("musica", 0.9)
    mem.bump_perceived("musica", 5.0)
    assert mem.top_topics(1)[0][1] == 0.9


def test_silenced_theme_never_returns(tmp_path):
    mem = MemoryStore(tmp_path / "m.sqlite")
    sink = make_theme_sink(mem, lambda: 10.0)
    sink("hollow_knight.exe", "Hollow Knight", "jogo")
    mem.delete_topic("hollow knight")
    mem.silence_theme("hollow knight")
    assert mem.silenced_themes() == ["hollow knight"]
    for _ in range(100):
        sink("hollow_knight.exe", "Hollow Knight", "jogo")
    assert mem.topic_rows() == []
    mem.unblock_on_new_mention("topic", "hollow knight")   # a chat mention does not free it
    assert mem.bump_perceived("hollow knight", 20.0) == ""
    mem.unsilence_theme("hollow knight")
    assert mem.bump_perceived("hollow knight", 20.0) == "hollow knight"


def test_forget_all_clears_app_categories(tmp_path):
    mem = MemoryStore(tmp_path / "m.sqlite")
    mem.set_app_category("a.exe", "jogo", "llm")
    mem.forget_all_about_user()
    assert mem.app_category_rows() == []


def test_old_db_opens_with_new_table(tmp_path):
    p = tmp_path / "m.sqlite"
    MemoryStore(p).close()
    db = sqlite3.connect(str(p))
    db.execute("DROP TABLE app_categories")
    db.commit()
    db.close()
    assert MemoryStore(p).app_category("x.exe") is None
