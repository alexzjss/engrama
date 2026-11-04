import random
import re

import pytest

from engrama.services.language.persona import (SPEECH, PersonaState, babble, build_messages, clean_reply,
                                               valence)


def _states():
    return [
        PersonaState(),
        PersonaState(stage="egg"),
        PersonaState(stage="adult", needs_top=["fome", "sono"], traits={"curiosidade": 90, "paciencia": 5},
                     mood="sad", curious=True, favorites=["peixe"], disliked=["bug"],
                     memories=["comeu 3 peixes às 14h", "ganhou 100 pontos"]),
        PersonaState(stage="child", mood="exuberant", memories=["12345"]),
    ]


@pytest.mark.parametrize("lang", ["pt", "en"])
def test_prompt_has_no_digits_and_no_assistant_talk(lang):
    for st in _states():
        msgs = build_messages(st, [], "oi 42", lang, food_name=lambda i, l: f"{i}9")
        system = msgs[0]["content"]
        assert not re.search(r"\d", system)
        assert not re.search("[\U0001F000-\U0001FAFF]", system)
        # the only "assistant" words allowed are the prohibitions themselves
        assert "Never act like an assistant" in system or "Nunca aja como assistente" in system
    assert msgs[0]["content"].endswith("Reply in English." if lang == "en" else "Responda em português.")
    assert msgs[-1] == {"role": "user", "content": "oi 42"}


def test_clean_reply_strips_digits_emoji_and_assistant():
    assert clean_reply("Como posso ajudar? 42 \U0001F600", 12) is None
    out = clean_reply("oi 42 amigo \U0001F600", 12)
    assert out == "oi amigo"
    assert clean_reply("<think>x</think>", 5) is None
    assert clean_reply("   ", 5) is None
    assert clean_reply("I am an assistant", 5) is None
    assert clean_reply("linha um\nlinha dois", 10) == "linha um"


def test_reply_length_grows_with_stage():
    text = " ".join(f"p{chr(97 + i)}" for i in range(50))
    counts = {s: len((clean_reply(text, SPEECH[s][0]) or "").split()) for s in SPEECH}
    assert counts["egg"] == 0
    assert counts["baby"] == 6 and counts["child"] == 12 and counts["adult"] == 30
    assert counts["perfect"] == counts["final"] == 40
    assert clean_reply(text, SPEECH["egg"][0]) is None


def test_babble_egg_and_keys():
    rng = random.Random(1)
    assert "ovo" in babble("oi", "egg", "pt", rng)
    assert "egg" in babble("hi", "egg", "en", rng)
    assert babble("", "baby", "en", rng, key="brain_loading") == "zzz... (brain loading)"
    assert babble("oi", "baby", "pt", rng)


def test_trait_adjectives_use_thresholds():
    st = PersonaState(stage="adult", traits={"curiosidade": 90, "paciencia": 50})
    assert "curiosa" in build_messages(st, [], "oi", "pt")[0]["content"]
    st = PersonaState(stage="adult", traits={"curiosidade": 50})
    assert "curiosa" not in build_messages(st, [], "oi", "pt")[0]["content"]


def test_valence():
    assert valence("eu te amo", "pt") > 0
    assert valence("você é chato", "pt") < 0
    assert valence("i love you", "en") > 0
    assert valence("you are boring", "en") < 0
    assert valence("mesa", "pt") == 0.0
    assert valence("não gosto", "pt") < 0
    assert -1.0 <= valence("amo odeio", "pt") <= 1.0


def test_prompt_includes_memory_without_digits():
    from engrama.services.language.persona import apply_recall
    from engrama.services.memory.recall import RecallContext
    st = PersonaState(stage="adult", facts=["time: 2 gatos"], opinion="detesta jogo",
                      current_topics=["música"], past_topics=["futebol"])
    for lang in ("pt", "en"):
        system = build_messages(st, [], "oi", lang)[0]["content"]
        assert "gatos" in system and "detesta jogo" in system and "música" in system and "futebol" in system
        assert not re.search(r"\d", system)
    st2 = apply_recall(PersonaState(), RecallContext(["a: b"], ["ep"], ["t"], ["p"], "op"))
    assert (st2.facts, st2.memories, st2.current_topics, st2.past_topics, st2.opinion) == (
        ["a: b"], ["ep"], ["t"], ["p"], "op")


def test_m13_system_prompt_no_digimon_no_offer_of_help():
    for lang, anti in (("pt", "nunca ofereça ajuda"), ("en", "never offer help")):
        system = build_messages(PersonaState(stage="adult"), [], "oi", lang)[0]["content"]
        assert "digimon" not in system.lower()
        assert anti in system and ("nunca escreva código" in system or "never write code" in system)
    pt = build_messages(PersonaState(stage="adult", needs_top=["tedio", "curiosidade"]), [], "oi", "pt")[0]["content"]
    assert "entediada" in pt and "curiosa" in pt and "tranquilo" not in pt


def test_m13_every_fewshot_answer_is_a_clean_in_character_line():
    from engrama.services.language.persona import FEWSHOT
    for (style, lang), shots in FEWSHOT.items():
        limit = SPEECH[{"full": "adult"}.get(style, style)][0]
        for _, answer in shots:
            out = clean_reply(answer, limit)
            assert out is not None, answer           # would be rejected by ASSISTANT_RE
            assert len(answer.split()) <= limit
            assert not re.search(r"assistente|assistant", answer, re.I)
    for lang in ("pt", "en"):                         # child few-shots stay short (~8 words)
        assert all(len(a.split()) <= 8 for _, a in FEWSHOT[("child", lang)])


@pytest.mark.parametrize("bad", [
    "vou ajudar, mas só se você me mostrar o código!", "Vou te ajudar com alguma dica.",
    "Oi! Estou aqui, sempre pronto para ajudar.", "pronto para te ajudar", "Tchau! sempre aqui para te ajudar",
    "i'd love to help, but i'm more here for cuddles", "i can help with that.", "happy to help!",
    "let me know how i can assist you!", "let me know what you need", "sure, what kind of code do you need help with?",
    "sure, what kind of help do you need?", "what specific task do you want?", "o que você precisa ajudar?",
    "sure! here's a simple python function:", "Aqui está uma função em Python", "```python",
    'def funcao():\n    print("x")',
    "Se precisar de ajuda, eu estou aqui.", "não importa, sou aqui pra te ajudar se quiser.", "toca com cuidado, posso te ajudar a escolher um instrumento",
    "talvez eu possa ajudar a relaxar", "se quiser, posso ouvir seu código", "você pode me dizer o que precisa?",
    "if you need help, i'm here", "if you want, i can write it",
])
def test_m13_new_assistant_patterns_are_rejected(bad):
    assert clean_reply(bad, 40) is None


@pytest.mark.parametrize("good", [      # in-character lines from the M13 baseline, must still pass
    "pii! oi!", "engrama! bebê digi! pii!", "gosto! faz o chão vibrar, é divertido!",
    "isso é coisa de computador chato... eu só moro aqui.", "Sou o Engrama, moro na sua janela.",
    "oh, pumpkin! what a cute name.", "hoje foi cheio de reuniões, que cansaço!", "não sou útil? hmpf, sou sim!",
    "gru! useless? no! pii!", "I'm Engrama, I live in your window.", "ajudei a regar a planta hoje!", "se quiser, posso brincar de esconde-esconde!",
    "no, i can't help with code. i just live here.",
])
def test_m13_good_lines_are_not_rejected(good):
    assert clean_reply(good, 40) == good


def test_m13_is_repeat_ignores_case_and_punctuation_and_only_last_three():
    from engrama.services.language.persona import is_repeat
    hist = [{"role": "assistant", "content": "Oi! Tudo bem?"}, {"role": "user", "content": "x"}]
    assert is_repeat("oi tudo bem", hist) and is_repeat("OI, tudo bem!!", hist)
    assert not is_repeat("oi tudo bem", [{"role": "user", "content": "oi tudo bem"}])
    old = [{"role": "assistant", "content": "a1"}] + [{"role": "assistant", "content": f"b{i}x"} for i in range(3)]
    assert not is_repeat("a1", old)
    assert not is_repeat("!!!", hist)
