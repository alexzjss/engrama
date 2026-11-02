from engrama.services.perception.blocklist import FACTORY, Blocklist
from engrama.services.perception.categories import APP_TABLE, table_category


def test_blocklist_accents_case_user_entries():
    b = Blocklist(["Meu Diário"])
    assert b.is_blocked("x.exe", "Internet BANKING")
    assert b.is_blocked("chrome.exe", "Gerenciador de SENHAS")
    assert b.is_blocked("x.exe", "meu diario - notas")
    assert b.is_blocked("keepass.exe", "")
    assert b.is_blocked("x.exe", "Itaú Empresas")
    assert not b.is_blocked("code.exe", "main.py - engrama")
    assert "bitwarden" in FACTORY


def test_empty_user_entries_ignored():
    b = Blocklist(["", "  "])
    assert not b.is_blocked("code.exe", "main.py")


def test_table_category():
    assert table_category("Code.exe") == "programacao"
    assert table_category("nope.exe") is None
    assert len(APP_TABLE) >= 40
