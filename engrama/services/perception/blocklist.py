"""Block list: factory patterns plus user entries, matched accent/case-insensitively."""
import unicodedata

FACTORY = ("banco", "bank", "senha", "password", "keepass", "bitwarden", "1password",
           "itau", "bradesco", "nubank", "caixa", "santander", "paypal")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


class Blocklist:
    def __init__(self, user_entries: list[str] | None = None):
        self._terms = tuple(t for t in (_norm(e).strip() for e in (*FACTORY, *(user_entries or []))) if t)

    def is_blocked(self, process: str, title: str) -> bool:
        p, t = _norm(process), _norm(title)
        return any(term in p or term in t for term in self._terms)
