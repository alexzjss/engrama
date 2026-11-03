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
    # Linux (sem sufixo) e nomes só do Linux
    "firefox": "navegador", "chromium": "navegador", "google-chrome": "navegador",
    "chrome": "navegador", "brave": "navegador", "brave-browser": "navegador",
    "code": "programacao", "codium": "programacao", "cursor": "programacao",
    "nvim": "programacao", "zed": "programacao", "pycharm": "programacao", "idea": "programacao",
    "steam": "jogo", "lutris": "jogo", "heroic": "jogo", "minecraft-launcher": "jogo",
    "hollow_knight": "jogo", "hollowknight": "jogo", "godot": "jogo",
    "spotify": "musica", "rhythmbox": "musica", "elisa": "musica", "strawberry": "musica",
    "audacious": "musica", "lollypop": "musica", "amberol": "musica",
    "vlc": "video", "mpv": "video", "celluloid": "video",
    "discord": "chat", "vesktop": "chat", "telegram-desktop": "chat", "slack": "chat",
    "soffice.bin": "escritorio", "soffice": "escritorio", "libreoffice": "escritorio",
    "krita": "desenho", "gimp": "desenho", "inkscape": "desenho", "blender": "desenho",
    "aseprite": "desenho",
    "kitty": "terminal", "alacritty": "terminal", "foot": "terminal", "wezterm-gui": "terminal",
    "konsole": "terminal", "gnome-terminal-server": "terminal", "ghostty": "terminal",
}

CATEGORIES = tuple(sorted(set(APP_TABLE.values())))


_SUFFIXES = (".appimage", ".x86_64", ".x86", ".exe", ".bin", ".sh", "-bin")


def normalize_process(name: str) -> str:
    n = (name or "").strip().lower()
    changed = True
    while changed:
        changed = False
        for suf in _SUFFIXES:
            if n.endswith(suf) and len(n) > len(suf):
                n = n[: -len(suf)]
                changed = True
    return n


def table_category(process: str) -> str | None:
    p = (process or "").strip().lower()
    return APP_TABLE.get(p) or APP_TABLE.get(normalize_process(p))


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
