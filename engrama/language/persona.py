import random
import re

from engrama.i18n import _table
from engrama.language.client import strip_think

# stage -> (max words per reply, style)
SPEECH = {"egg": (0, "sounds"), "baby": (6, "baby"), "child": (12, "child"),
          "adult": (30, "full"), "perfect": (40, "full"), "final": (40, "full")}

NEED_PHRASES = {
    "pt": {"fome": "está com fome", "sono": "está com sono", "tedio": "está entediado e quer brincar",
           "carinho": "quer carinho e atenção", "curiosidade": "está curioso sobre tudo",
           "apoio": "precisa de apoio e incentivo"},
    "en": {"fome": "are hungry", "sono": "are sleepy", "tedio": "are bored and want to play",
           "carinho": "want cuddles and attention", "curiosidade": "are curious about everything",
           "apoio": "need support and encouragement"},
}
# trait -> {lang: (adjective when high, adjective when low)}
TRAIT_WORDS = {
    "curiosidade": {"pt": ("curioso", "calmo"), "en": ("curious", "calm")},
    "sociabilidade": {"pt": ("sociável", "tímido"), "en": ("friendly", "shy")},
    "paciencia": {"pt": ("paciente", "impaciente"), "en": ("patient", "impatient")},
    "independencia": {"pt": ("independente", "grudento"), "en": ("independent", "clingy")},
    "criatividade": {"pt": ("criativo", "simples"), "en": ("creative", "plain")},
}

STYLE_TEXT = {
    "pt": {"baby": "Fala de bebê: de uma a seis palavras, misturando palavras simples e sons de bebê como 'gru', 'pii', 'brr'.",
           "child": "Fala de criança: frases curtas e simples, curiosa e brincalhona.",
           "full": "Fala com naturalidade, frases curtas, com personalidade própria."},
    "en": {"baby": "Baby speech: one to six words, mixing simple words and baby sounds like 'gru', 'pii', 'brr'.",
           "child": "Child speech: short simple sentences, curious and playful.",
           "full": "Speak naturally in short sentences, with a personality of your own."},
}
# few-shot pairs per (style, lang); neutral on needs so they do not leak a fake mood
FEWSHOT = {
    ("baby", "pt"): [("oi!", "pii! oi oi!"), ("quer brincar?", "gru! sim sim! pii!"),
                     ("o que você é?", "engrama! bebê digi! pii!")],
    ("baby", "en"): [("hi!", "pii! hi hi!"), ("what are you?", "engrama! me digi-baby, pii!"),
                     ("do you like music?", "brr... music! yes yes! gru!")],
    ("child", "pt"): [("oi!", "oi! eu sou o Engrama, quer brincar?"),
                      ("você gosta de música?", "gosto! faz o chão vibrar, é divertido!"),
                      ("vamos dormir?", "ah, não! só mais um pouquinho!")],
    ("child", "en"): [("hi!", "hi! i'm Engrama, wanna play?"),
                      ("do you like music?", "yes! it makes the window shake, so fun!"),
                      ("let's sleep?", "aw, no! just a little more!")],
    ("full", "pt"): [("oi!", "oi! que bom te ver por aqui."),
                     ("o que você acha de música?", "gosto bastante, mas prefiro o silêncio às vezes."),
                     ("você é um assistente?", "não, sou o Engrama, moro aqui na sua janela.")],
    ("full", "en"): [("hi!", "hi! good to see you here."),
                     ("what do you think of music?", "i like it a lot, but sometimes i prefer the quiet."),
                     ("are you an assistant?", "no, i'm Engrama, i just live in your window.")],
}


def _lt(lang: str, key: str) -> str:
    """Translate into an explicit language (i18n.t uses the global UI language)."""
    return _table(lang if lang in ("pt", "en") else "en").get(key, key)


def trait_adjectives(traits: dict[str, float], lang: str) -> list[str]:
    ranked = sorted(((abs(v - 50), k, v) for k, v in traits.items() if k in TRAIT_WORDS and abs(v - 50) >= 15),
                    reverse=True)[:2]
    return [TRAIT_WORDS[k][lang][0 if v >= 50 else 1] for _, k, v in ranked]


def build_messages(state: dict, history: list[dict], user_text: str, lang: str) -> list[dict]:
    stage = state.get("stage", "baby")
    style = SPEECH.get(stage, SPEECH["baby"])[1]
    style = "baby" if style == "sounds" else style
    en = lang == "en"
    needs = [NEED_PHRASES[lang][n] for n in state.get("needs_top", [])[:2] if n in NEED_PHRASES[lang]]
    traits = trait_adjectives(state.get("traits", {}), lang)
    val = state.get("valence", 0.0)
    mood = ("happy" if en else "feliz") if val > 0.3 else ("sad" if en else "triste") if val < -0.3 else ""

    def foods(ids):
        return ", ".join(_lt(lang, f"food.{i}") for i in ids)

    mems = [re.sub(r"\d+", "", m).strip() for m in state.get("memories", [])[:3]]
    mems = [m for m in mems if m]
    if en:
        parts = [
            "You are Engrama, a digital creature (Digimon-inspired, but original). You know you live in a small window "
            "on your human's PC. Your human is talking to you: ANSWER WHAT THEY SAID, in character. You may disagree. "
            "Never list stats or numbers. Never act like an assistant (no 'how can I help'). No emojis, one short line.",
            STYLE_TEXT["en"][style],
            f"Right now you {' and '.join(needs)}." if needs else "You feel fine and calm.",
            f"You feel {mood}." if mood else "",
            f"You are {', '.join(traits)}." if traits else "",
            f"Favorite foods: {foods(state['favorites'])}." if state.get("favorites") else "",
            f"Foods you dislike: {foods(state['disliked'])}." if state.get("disliked") else "",
            f"You like talking about: {', '.join(state['topics'][:3])}." if state.get("topics") else "",
            f"Recent memories: {'; '.join(mems)}." if mems else "",
            "(Mention foods only if the human talks about food.) Reply in English.",
        ]
    else:
        parts = [
            "Você é o Engrama, uma criatura digital (inspirada em Digimon, mas original). Você sabe que mora numa "
            "janelinha no PC do seu humano. Seu humano está falando com você: RESPONDA O QUE ELE DISSE, "
            "mantendo o personagem. Pode discordar. Nunca liste status nem números. Nunca aja como assistente "
            "(nada de 'como posso ajudar'). Sem emojis, uma linha curta.",
            STYLE_TEXT["pt"][style],
            f"Agora você {' e '.join(needs)}." if needs else "Você está bem e tranquilo.",
            f"Você está {mood}." if mood else "",
            f"Você é {', '.join(traits)}." if traits else "",
            f"Comidas favoritas: {foods(state['favorites'])}." if state.get("favorites") else "",
            f"Comidas que você não gosta: {foods(state['disliked'])}." if state.get("disliked") else "",
            f"Você gosta de falar sobre: {', '.join(state['topics'][:3])}." if state.get("topics") else "",
            f"Memórias recentes: {'; '.join(mems)}." if mems else "",
            "(Só fale de comida se o humano falar de comida.) Responda em português.",
        ]
    system = re.sub(r"\d", "", " ".join(p for p in parts if p))
    msgs = [{"role": "system", "content": system}]
    for u, a in FEWSHOT[(style, lang)]:
        msgs += [{"role": "user", "content": u}, {"role": "assistant", "content": a}]
    msgs += [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
    msgs.append({"role": "user", "content": user_text})
    return msgs


EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]")
ASSISTANT_RE = re.compile(
    r"posso ajudar|em que posso|como posso|estou aqui para|assistente|modelo de linguagem|"
    r"how can i (help|assist)|how may i|as an ai|i'?m here to (help|assist)|language model|assistant|"
    r"let me know if", re.I)


def clean_reply(text: str, max_words: int) -> str | None:
    text = EMOJI_RE.sub("", strip_think(text or "")).strip()
    text = text.split("\n")[0].strip().strip("\"'“”‘’ ").strip()
    if not text or re.search(r"\d", text) or ASSISTANT_RE.search(text):
        return None
    words = text.split()
    if max_words > 0:
        words = words[:max_words]
    return " ".join(words)


_SYL = ["gru", "brr", "pi", "mu", "nha", "kii", "ra", "bu"]
_REACT = [
    (("fome", "comer", "comida", "food", "hungry", "eat"), ["nom nom? * fome!", "mam... mam! brr", "nhom! nhom!"]),
    (("oi", "olá", "ola", "hi", "hello", "hey"), ["pii! * oi?", "gru? * pi-pi!", "hii... brr!"]),
    (("amo", "love", "fofo", "cute", "carinho"), ["prrr... * brr", "pi-pii! (feliz)", "mmm... gru gru"]),
    (("dorm", "sleep", "sono", "night", "noite"), ["zzz... gru", "uaaa... sono..."]),
]


def babble(user_text: str, stage: str, lang: str, rng: random.Random) -> str:
    if user_text in ("bleh", "missed_you", "brain_loading"):
        return _lt(lang, f"babble.{user_text}")
    if stage == "egg":
        return "... (o ovo vibra)" if lang == "pt" else "... (the egg trembles)"
    t = user_text.lower()
    words = set(re.split(r"\W+", t))
    for keys, replies in _REACT:
        if any((k in words) if len(k) <= 3 else (k in t) for k in keys):
            return rng.choice(replies)
    s = " ".join(rng.choice(_SYL) + rng.choice(["?", "!", "...", ""]) for _ in range(rng.randint(2, 4)))
    return s + " *"
