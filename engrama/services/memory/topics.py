from __future__ import annotations

import re
import unicodedata

# PT/EN surface form (already lowercase, no accents) -> canonical PT form.
SYNONYMS: dict[str, str] = {
    "programming": "programacao",
    "programar": "programacao",
    "coding": "programacao",
    "game": "jogo",
    "games": "jogo",
    "jogos": "jogo",
    "gaming": "jogo",
    "music": "musica",
    "musicas": "musica",
    "movie": "filme",
    "movies": "filme",
    "filmes": "filme",
    "book": "livro",
    "books": "livro",
    "livros": "livro",
    "food": "comida",
    "dog": "cachorro",
    "dogs": "cachorro",
    "cachorros": "cachorro",
    "cao": "cachorro",
    "cat": "gato",
    "cats": "gato",
    "gatos": "gato",
    "school": "escola",
    "work": "trabalho",
    "weather": "clima",
    "rain": "chuva",
    "sleep": "sono",
    "football": "futebol",
    "soccer": "futebol",
}

_WS = re.compile(r"\s+")


def plain_text(text: str) -> str:
    """Lowercase, accent-free, whitespace-collapsed text (no synonym mapping)."""
    s = unicodedata.normalize("NFKD", text or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return _WS.sub(" ", s.lower()).strip()


def normalize_topic(name: str) -> str:
    s = plain_text(name)
    return SYNONYMS.get(s, s)
