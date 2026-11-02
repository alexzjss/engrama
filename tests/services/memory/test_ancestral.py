import sqlite3

from engrama.services.memory.recall import recall
from engrama.services.memory.store import MemoryStore

T0 = 1_800_000_000.0


def make(tmp_path):
    clock = {"t": T0}
    return MemoryStore(tmp_path / "m.sqlite", now_fn=lambda: clock["t"]), clock


def test_candidates_top_importance(tmp_path):
    s, clock = make(tmp_path)
    s.add_episode("chat", "pouco importante", 0.1, 0.2)
    s.add_episode("chat", "muito importante", 0.1, 0.9)
    s.add_episode("play", "medio com valencia", 0.8, 0.5)
    s.add_episode("play", "medio neutro", 0.0, 0.5)
    s.add_episode("ancestral", "ja ancestral", 0.0, 1.0)
    s.add_episode("arquivo", "arquivado", 0.0, 1.0)
    assert s.ancestral_candidates(3) == ["muito importante", "medio com valencia", "medio neutro"]
    assert s.ancestral_candidates() == s.ancestral_candidates(3)


def test_candidates_skip_digits_and_blocked(tmp_path):
    s, clock = make(tmp_path)
    s.add_episode("chat", "viu 3 passaros", 0.0, 0.9)
    s.add_episode("chat", "conversou sobre jardim", 0.0, 0.8, topic="jardim", topics=["jardim"])
    s.add_episode("chat", "falou do foguete", 0.0, 0.7, topic="foguete")
    s.add_episode("chat", "sabe que o humano gosta de azul", 0.0, 0.65, facts=["cor"])
    s.add_episode("chat", "ouviu uma musica boa", 0.0, 0.6)
    s.delete_topic("jardim")
    s.silence_theme("foguete")
    s.add_episode("play", "brincou de bola", 0.0, 0.5)
    assert s.ancestral_candidates(5) == ["ouviu uma musica boa", "brincou de bola"]


def test_archive_copy_opens(tmp_path):
    s, _ = make(tmp_path)
    s.add_episode("chat", "lembranca", 0.0, 0.5)
    dest = tmp_path / "a" / "b" / "memory.sqlite"
    s.archive_to(dest)
    db = sqlite3.connect(dest)
    assert db.execute("SELECT summary FROM episodes").fetchall() == [("lembranca",)]
    db.close()


def test_new_generation_keeps_blocklist_and_categories(tmp_path):
    s, _ = make(tmp_path)
    s.set_app_category("game.exe", "jogo", "user")
    s.silence_theme("foguete")
    s.add_episode("chat", "x", 0.0, 0.5, topics=["jardim"])
    s.delete_topic("jardim")
    s.new_generation(["um sonho"])
    assert s.app_category("game.exe") == "jogo"
    assert s.is_blocked("topic", "jardim")
    assert "foguete" in s.silenced_themes()


def test_new_generation_wipes_user_facts(tmp_path):
    s, _ = make(tmp_path)
    s.upsert_fact("cor", "azul", 0.9, "chat")
    s.bump_topic("musica", 0.5)
    for _ in range(3):
        s.update_opinion("musica", lambda t: 0.3, 0.5)
    s.add_episode("chat", "conversa", 0.0, 0.5)
    s.add_episode("reflection", "reflexao", 0.0, 0.5)
    s.meta_set("initiative_usage", "99")
    s.new_generation(["sonho um", "sonho dois", ""])
    assert s.fact_rows() == [] and s.topic_rows() == [] and s.opinion_rows() == []
    assert s.recent_reflections() == []
    assert s.meta_get("initiative_usage") is None
    rows = s._db.execute("SELECT kind, summary, importance FROM episodes ORDER BY id").fetchall()
    assert rows == [("ancestral", "sonho um", 0.6), ("ancestral", "sonho dois", 0.6)]
    assert s._db.execute("SELECT COUNT(*) FROM episode_links").fetchone()[0] == 0


def test_ancestral_recalled_on_match(tmp_path):
    s, _ = make(tmp_path)
    s.new_generation(["brincou muito no jardim ao sol"])
    ctx = recall(s, "vamos falar do jardim?", "adult", "pt")
    assert ctx.ancestral == ["brincou muito no jardim ao sol"]
    assert ctx.episodes == []
    assert recall(s, "oi tudo bem", "adult", "pt").ancestral == []
    assert recall(s, "jardim", "egg", "pt").ancestral == []


def test_persona_presents_dream():
    from engrama.services.language.persona import PersonaState, build_messages
    for lang, needle in (("pt", "sonho de antes de nascer"), ("en", "dream from before you were born")):
        st = PersonaState(stage="adult", ancestral=["brincou no jardim"])
        assert needle in build_messages(st, [], "oi", lang)[0]["content"]
