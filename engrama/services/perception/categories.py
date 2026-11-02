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
