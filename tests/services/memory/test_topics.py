from engrama.services.memory.topics import SYNONYMS, normalize_topic


def test_normalize_merges_accents_case_synonyms():
    forms = ["Programação", " programacao ", "PROGRAMMING", "programming"]
    assert {normalize_topic(f) for f in forms} == {"programacao"}


def test_normalize_collapses_spaces_and_synonyms():
    assert normalize_topic("  Hollow   Knight ") == "hollow knight"
    for w in ("games", "Game", "Jogos", "jogo"):
        assert normalize_topic(w) == "jogo"
    assert normalize_topic("Music") == normalize_topic("Música") == "musica"
    assert isinstance(SYNONYMS, dict) and SYNONYMS
