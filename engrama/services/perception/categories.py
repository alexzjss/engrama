"""Local process -> category table."""

APP_TABLE: dict[str, str] = {
    "chrome.exe": "navegador", "msedge.exe": "navegador", "firefox.exe": "navegador",
    "brave.exe": "navegador", "opera.exe": "navegador", "vivaldi.exe": "navegador",
    "code.exe": "programacao", "devenv.exe": "programacao", "pycharm64.exe": "programacao",
    "idea64.exe": "programacao", "sublime_text.exe": "programacao", "notepad++.exe": "programacao",
    "cursor.exe": "programacao", "rider64.exe": "programacao",
    "steam.exe": "jogo", "epicgameslauncher.exe": "jogo", "minecraft.exe": "jogo",
    "javaw.exe": "jogo", "hollow_knight.exe": "jogo", "godot.exe": "jogo",
    "spotify.exe": "musica", "foobar2000.exe": "musica", "musicbee.exe": "musica", "itunes.exe": "musica",
    "vlc.exe": "video", "mpv.exe": "video", "netflix.exe": "video", "potplayermini64.exe": "video",
    "discord.exe": "chat", "telegram.exe": "chat", "whatsapp.exe": "chat",
    "slack.exe": "chat", "teams.exe": "chat", "zoom.exe": "chat",
    "winword.exe": "escritorio", "excel.exe": "escritorio", "powerpnt.exe": "escritorio",
    "soffice.exe": "escritorio", "onenote.exe": "escritorio",
    "photoshop.exe": "desenho", "krita.exe": "desenho", "gimp-2.10.exe": "desenho",
    "mspaint.exe": "desenho", "blender.exe": "desenho", "aseprite.exe": "desenho",
    "windowsterminal.exe": "terminal", "cmd.exe": "terminal", "powershell.exe": "terminal",
    "pwsh.exe": "terminal", "wt.exe": "terminal",
}

CATEGORIES = tuple(sorted(set(APP_TABLE.values())))


def table_category(process: str) -> str | None:
    return APP_TABLE.get((process or "").strip().lower())


class Categorizer:
    """process -> category: local table, then the SQLite cache, then "programa".

    An unknown process asks the LLM once per session (low-priority job); the answer
    lands in the cache and is used from the next call on. Blocked processes never
    reach here (the caller checks the blocklist first).
    """

    def __init__(self, memory, language=None) -> None:
        self.memory = memory
        self.language = language
        self._asked: set[str] = set()

    def __call__(self, process: str) -> str:
        p = (process or "").strip().lower()
        if not p:
            return "programa"
        cat = table_category(p)
        if cat:
            return cat
        try:
            cat = self.memory.app_category(p)
        except Exception:
            cat = None
        if cat:
            return cat
        if self.language is not None and p not in self._asked:
            self._asked.add(p)
            try:
                self.language.classify_app(p)
            except Exception:
                pass
        return "programa"
