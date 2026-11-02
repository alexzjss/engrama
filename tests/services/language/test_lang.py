import pytest

from engrama.services.language.lang import detect_lang

PT = ["oi, tudo bem?", "vc quer comer?", "eu estou com muito sono hoje", "você gosta de brincar?",
      "não quero dormir agora", "qual é o seu nome?"]
EN = ["hello, how are you?", "do u wanna play", "i am very hungry today", "what is your name?",
      "do you like games?", "i do not want to sleep"]


@pytest.mark.parametrize("t", PT)
def test_detect_pt(t):
    assert detect_lang(t, default="en") == "pt"


@pytest.mark.parametrize("t", EN)
def test_detect_en(t):
    assert detect_lang(t, default="pt") == "en"


def test_detect_lang():
    assert [detect_lang(t, "en") for t in PT] == ["pt"] * 6
    assert [detect_lang(t, "pt") for t in EN] == ["en"] * 6


def test_emoji_only_falls_to_default():
    assert detect_lang("😀😀", "pt") == "pt"
    assert detect_lang("😀😀", "en") == "en"
    assert detect_lang("", "en") == "en"
