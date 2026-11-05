import pytest

from engrama.services.language.service import FACTS_PROMPT, sanitize_facts


@pytest.mark.parametrize("fact", [
    ["who are you?", "I am an AI assistant developed by Alibaba Group.", 0.9],
    ["what is your purpose?", "to help", 0.9],
    ["quem é você", "uma criatura", 0.8],
    ["pergunta", "o que você faz?", 0.8],
    ["sleep", "rest", 0.5],
    ["going", "to", 0.5],
    ["clima", "true", 0.9],
    ["hoje_choveu_o_dia_todo", "true", 0.9],
    ["gosta", "Não", 0.9],
    ["ocupacao", "assistente virtual", 0.9],
    ["creature", "language model", 0.9],
    ["origem", "Alibaba", 0.9],
    ["modelo", "Qwen", 0.9],
    ["ab", "valor", 0.9],
    ["nome", "A", 0.9],
])
def test_junk_facts_are_dropped(fact):
    assert sanitize_facts([fact]) == []


def test_real_facts_survive():
    good = [["nome_do_gato", "Bolota", 0.9], ["jogo_favorito", "hollow knight", 0.8],
            ["cat_name", "Pumpkin", 0.9], ["profissao", "professora", 0.7], ["comida_favorita", "pizza", 0.7]]
    assert sanitize_facts(good) == good


def test_prompts_require_user_durable_facts_only():
    assert "never questions" in FACTS_PROMPT["en"].lower()
    assert "nunca perguntas" in FACTS_PROMPT["pt"].lower()
