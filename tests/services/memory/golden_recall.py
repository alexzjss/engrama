"""M8 recall golden: a fixed memory and a fixed set of messages, and what recall + prompt produce.

``python -m tests.services.memory.golden_recall --write`` regenerates the fixture. It must only be
run with the M8 behaviour (the fixture is the reference for the "no model = M8" rule).
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from engrama.services.language.persona import PersonaState, apply_recall, build_messages
from engrama.services.memory.recall import recall
from engrama.services.memory.store import MemoryStore

DAY = 86400.0
T0 = 1_800_000_000.0
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "m8_recall_golden.json"

# (texto, estágio, idioma)
CASES: tuple[tuple[str, str, str], ...] = (
    ("oi, tudo bem?", "adult", "pt"),
    ("meu cachorro, o Biscoito, esta doente", "adult", "pt"),
    ("me fala do bichinho", "perfect", "pt"),
    ("I miss my dog Biscoito", "final", "en"),
    ("estou triste com meu emprego", "final", "pt"),
    ("o chefe me demitiu", "perfect", "pt"),
    ("tell me about music", "adult", "en"),
    ("what is the weather like in Recife 2024", "adult", "en"),
    ("", "adult", "pt"),
    ("qual e o seu jogo favorito?", "final", "pt"),
    ("hollow knight is so hard", "perfect", "en"),
    ("oi", "egg", "pt"),
    ("oi", "baby", "en"),
    ("como vai a escola", "child", "pt"),
    ("quero falar de aviao", "adult", "pt"),
    ("programming all day", "final", "en"),
    ("cidade", "adult", "pt"),
    ("Curitiba", "perfect", "pt"),
    ("e a sua opiniao sobre cachorros?", "final", "pt"),
    ("what do you think about work", "final", "en"),
    ("sonhos de antes de nascer", "child", "pt"),
    ("a chuva de sabado", "adult", "pt"),
)


def build_store(path: Path) -> MemoryStore:
    """Memory with a fixed clock: facts, current and past topics, opinions with and without a phrase,
    episodes of every kind (chat, reflection, activity, compaction), ancestral memories and a deleted topic."""
    clock = [T0]
    store = MemoryStore(Path(path), now_fn=lambda: clock[0])

    # Ancestral memories come from a generation reset, so they go in first.
    store.new_generation([
        "Eu sonhei com uma chuva dourada sobre o mar.",
        "I dreamed of a golden tide over a quiet shore.",
        "Sonho vago de uma torre branca nas nuvens.",
    ])

    # Old low-importance chat, compacted by forget() below.
    clock[0] = T0 - 10 * DAY
    store.add_episode("chat", "falamos de um filme antigo", 0.1, 0.1, topic="filme", topics=["filme"])
    store.add_episode("chat", "uma conversa curta sobre livros", 0.0, 0.1, topic="livro", topics=["livro"])
    store.bump_topic("musica", 0.5)
    store.add_episode("chat", "falamos de musica e de uma banda antiga", 0.3, 0.45,
                      topic="musica", topics=["musica"])
    clock[0] = T0
    store.forget()

    clock[0] = T0 - 2 * DAY
    store.upsert_fact("nome_do_cachorro", "Biscoito", 0.9, "chat")
    store.upsert_fact("cidade", "Curitiba", 0.8, "chat")
    store.upsert_fact("profissao", "professor de matematica", 0.7, "chat")
    store.bump_topic("cachorro", 0.6)
    store.update_opinion("cachorro", lambda k: 0.5, 0.6)
    store.update_opinion("cachorro", lambda k: 0.5, 0.7)
    store.set_opinion_phrase("cachorro", "adora cachorros de verdade", "pt")
    store.add_episode("chat", "o usuario disse que o cachorro dele se chama Biscoito", 0.5, 0.6,
                      topic="cachorro", topics=["cachorro"], facts=["nome_do_cachorro"])

    clock[0] = T0 - 1 * DAY
    store.bump_topic("jogo", 0.4)
    store.update_opinion("jogo", lambda k: 0.1, 0.4)
    store.set_opinion_phrase("jogo", "loves hard games", "en")
    store.add_episode("chat", "falamos de Hollow Knight e de como o jogo e dificil", 0.4, 0.7,
                      topic="jogo", topics=["jogo"])
    store.bump_topic("aviao", 0.2)
    store.add_episode("chat", "o usuario mencionou um aviao de papel", 0.0, 0.4,
                      topic="aviao", topics=["aviao"])
    store.delete_topic("aviao")
    store.upsert_fact("apelido", "Xis", 0.8, "chat")
    store.delete_fact("apelido")

    clock[0] = T0 - 3 * 3600.0
    store.bump_topic("trabalho", -0.3)
    store.update_opinion("trabalho", lambda k: -0.6, -0.5)
    store.add_episode("chat", "o usuario esta triste porque o chefe o demitiu", -0.7, 0.8,
                      topic="trabalho", topics=["trabalho"])
    store.add_episode("reflection", "pensei sobre o trabalho e o chefe cansativo", -0.4, 0.5,
                      topic="trabalho", topics=["trabalho"])
    store.add_episode("chat", "conversa sobre a chuva e o clima de sabado", 0.1, 0.5,
                      topic="clima", topics=["clima"])

    clock[0] = T0 - 30 * 60.0
    store.bump_topic("programacao", 0.3)
    store.add_episode("atividade", "passou um tempo com programacao", 0.0, 0.2,
                      topic="programacao", topics=["programacao"])
    store.upsert_fact("profissao", "professor de matematica", 0.7, "chat")
    clock[0] = T0
    return store


def snapshot(store: MemoryStore) -> list[dict]:
    out = []
    for text, stage, lang in CASES:
        ctx = recall(store, text, stage, lang)
        state = apply_recall(PersonaState(stage=stage), ctx)
        out.append({
            "text": text,
            "stage": stage,
            "lang": lang,
            "recall": asdict(ctx),
            "messages": build_messages(state, [], text, lang),
        })
    return out


def _fresh_snapshot(tmp_dir: Path) -> list[dict]:
    store = build_store(tmp_dir / "memory.sqlite")
    try:
        return snapshot(store)
    finally:
        store.close()


def main(argv: list[str]) -> int:
    import tempfile

    if "--write" not in argv:
        print("usage: python -m tests.services.memory.golden_recall --write")
        return 2
    with tempfile.TemporaryDirectory() as d:
        data = _fresh_snapshot(Path(d))
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {FIXTURE} ({len(data)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
