NEED_KEYS = ("fome", "sono", "tedio", "carinho", "curiosidade", "apoio")
TRAIT_KEYS = ("curiosidade", "sociabilidade", "paciencia", "independencia", "criatividade")
INITIAL_TRAITS = {"curiosidade": 50.0, "sociabilidade": 40.0, "paciencia": 70.0, "independencia": 30.0, "criatividade": 50.0}
STAGES = ("egg", "baby", "child", "adult", "perfect", "final")
ACTIONS = ("idle", "wander", "play_alone", "sleep", "ask_attention", "explore", "show_something", "hide")
EVENT_KINDS = ("click", "pet", "message", "food", "user_active", "user_idle",
               "app_focus", "fullscreen_on", "fullscreen_off", "answered")
REWARD_KEYS = ("need_relief", "need_pain", "user_response", "ignored", "petting", "msg_valence", "novelty")
FOOD_IDS = ("carne", "fruta", "peixe", "bolinho", "pacote", "cookie", "bug", "cache", "byte", "ram")
MEDICINE_ID = "remedio"
BRANCH_STAGES = ("child", "adult", "perfect", "final")
BRANCHES = {
    "child": ("brincalhao", "curioso", "sonhador", "arisco"),
    "adult": ("companheiro", "explorador", "artista", "tecnico", "sombrio"),
    "perfect": ("guardiao", "sabio", "virtuoso", "aventureiro", "rebelde"),
    "final": ("lendario", "mestre", "eco", "sombra"),
}
NEGLECT_BRANCHES = frozenset({"arisco", "sombrio", "rebelde", "sombra"})
INTEREST_KEYS = ("jogos", "arte", "tecnologia", "social", "trabalho")
INTEREST_GROUPS = {   # app category (perception PT or sim-user EN) -> interest
    "jogo": "jogos", "game": "jogos",
    "musica": "arte", "video": "arte", "desenho": "arte", "music": "arte",
    "programacao": "tecnologia", "terminal": "tecnologia", "editor": "tecnologia",
    "chat": "social", "navegador": "social", "browser": "social",
    "escritorio": "trabalho", "office": "trabalho",
}
DEATH_CAUSES = ("old_age", "neglect")
# M7
DIGITAL_IDS = ("ram", "defrag", "update", "cache", "cooler")
VARIANTS = ("jump", "dance", "yawn", "nap_clock", "chase", "look_cursor", "peek", "dig", "found")
DISPLAY_MODES = ("terrarium", "overlay")
