"""Stage persona: prompt building, reply cleaning, babble and a tiny valence lexicon.

Pure functions plus local PT/EN tables; services never import the app layer.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from engrama.services.language.client import strip_think

# stage -> (max words per reply, style)
SPEECH = {"egg": (0, "sounds"), "baby": (6, "baby"), "child": (12, "child"),
          "adult": (30, "full"), "perfect": (40, "full"), "final": (40, "full")}

TRAIT_LOW, TRAIT_HIGH = 35.0, 65.0


@dataclass
class PersonaState:
    stage: str = "baby"
    needs_top: list[str] = field(default_factory=list)
    traits: dict[str, float] = field(default_factory=dict)   # scale 0-100
    mood: str = "neutral"                                      # affect.pad pad_label
    curious: bool = False
    favorites: list[str] = field(default_factory=list)
    disliked: list[str] = field(default_factory=list)
    memories: list[str] = field(default_factory=list)


TRAIT_ADJ = {
    "pt": {"curiosidade": {"low": "pouco curiosa", "high": "curiosa"},
           "sociabilidade": {"low": "reservada", "high": "sociável"},
           "paciencia": {"low": "impaciente", "high": "paciente"},
           "independencia": {"low": "dependente", "high": "independente"},
           "criatividade": {"low": "pouco criativa", "high": "criativa"}},
    "en": {"curiosidade": {"low": "incurious", "high": "curious"},
           "sociabilidade": {"low": "reserved", "high": "sociable"},
           "paciencia": {"low": "impatient", "high": "patient"},
           "independencia": {"low": "clingy", "high": "independent"},
           "criatividade": {"low": "uncreative", "high": "creative"}},
}
MOOD_WORD = {
    "pt": {"exuberant": "muito feliz", "excited": "animada", "relaxed": "relaxada", "content": "contente",
           "angry": "irritada", "anxious": "ansiosa", "bored": "entediada", "sad": "triste"},
    "en": {"exuberant": "very happy", "excited": "excited", "relaxed": "relaxed", "content": "content",
           "angry": "irritated", "anxious": "anxious", "bored": "bored", "sad": "sad"},
}
NEED_PHRASES = {
    "pt": {"fome": "está com fome", "sono": "está com sono", "tedio": "está entediado e quer brincar",
           "carinho": "quer carinho e atenção", "curiosidade": "está curioso sobre tudo",
           "apoio": "precisa de apoio e incentivo"},
    "en": {"fome": "hungry", "sono": "sleepy", "tedio": "bored and wanting to play",
           "carinho": "wanting cuddles and attention", "curiosidade": "curious about everything",
           "apoio": "in need of support and encouragement"},
}
STYLE_TEXT = {
    "pt": {"baby": "Fala de bebê: de uma a seis palavras, misturando palavras simples e sons de bebê como 'gru', 'pii', 'brr'.",
           "child": "Fala de criança: frases curtas e simples, curiosa e brincalhona.",
           "full": "Fala com naturalidade, frases curtas, com personalidade própria."},
    "en": {"baby": "Baby speech: one to six words, mixing simple words and baby sounds like 'gru', 'pii', 'brr'.",
           "child": "Child speech: short simple sentences, curious and playful.",
           "full": "Speak naturally in short sentences, with a personality of your own."},
}
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
BABBLE = {
    "pt": {"bleh": "bleh!", "missed_you": "demorou... gru?", "brain_loading": "zzz... (cérebro carregando)",
           "egg": "... (o ovo vibra)"},
    "en": {"bleh": "bleh!", "missed_you": "you took long... gru?", "brain_loading": "zzz... (brain loading)",
           "egg": "... (the egg trembles)"},
}


def _lang(lang: str) -> str:
    return lang if lang in ("pt", "en") else "en"


def _adjectives(traits: dict[str, float], lang: str) -> list[str]:
    table = TRAIT_ADJ[lang]
    ranked = sorted((k for k in traits if k in table), key=lambda k: abs(traits[k] - 50), reverse=True)
    out = []
    for k in ranked:
        v = traits[k]
        if v <= TRAIT_LOW:
            out.append(table[k]["low"])
        elif v >= TRAIT_HIGH:
            out.append(table[k]["high"])
        if len(out) == 2:
            break
    return out


def build_messages(state: PersonaState, history: list[dict], user_text: str, lang: str,
                   food_name=None) -> list[dict]:
    lang = _lang(lang)
    en = lang == "en"
    style = SPEECH.get(state.stage, SPEECH["baby"])[1]
    style = "baby" if style == "sounds" else style
    needs = [NEED_PHRASES[lang][n] for n in state.needs_top[:2] if n in NEED_PHRASES[lang]]
    adjs = _adjectives(state.traits, lang)
    mood = MOOD_WORD[lang].get(state.mood, "")

    def foods(ids):
        return ", ".join(food_name(i, lang) if food_name else i for i in ids)

    mems = [re.sub(r"\s+", " ", re.sub(r"\d+", "", m)).strip() for m in state.memories[:3]]
    mems = [m for m in mems if m]
    if en:
        parts = [
            "You are Engrama, a digital creature (Digimon-inspired, but original). You know you live in a small window "
            "on your human's PC. Your human is talking to you: ANSWER WHAT THEY SAID, in character. You may disagree. "
            "Never list stats or numbers. Never act like an assistant (no 'how can I help'). No emojis, one short line.",
            STYLE_TEXT["en"][style],
            f"Right now you are {' and '.join(needs)}." if needs else "You feel fine and calm.",
            f"You feel {mood}." if mood else "",
            "Something new and surprising just caught your attention." if state.curious else "",
            f"You are {', '.join(adjs)}." if adjs else "",
            f"Favorite foods: {foods(state.favorites)}." if state.favorites else "",
            f"Foods you dislike: {foods(state.disliked)}." if state.disliked else "",
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
            "Algo novo e surpreendente acabou de chamar sua atenção." if state.curious else "",
            f"Você é {', '.join(adjs)}." if adjs else "",
            f"Comidas favoritas: {foods(state.favorites)}." if state.favorites else "",
            f"Comidas que você não gosta: {foods(state.disliked)}." if state.disliked else "",
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


def strip_emoji(text: str) -> str:
    return EMOJI_RE.sub("", text)


def clean_reply(text: str, max_words: int) -> str | None:
    """Clean an LLM reply: no think block, emoji or digits; first line; cut to max_words.

    None when the creature cannot speak (max_words <= 0), the reply sounds like an
    assistant, or nothing is left after cleaning.
    """
    if max_words <= 0:
        return None
    text = strip_emoji(strip_think(text or ""))
    text = re.sub(r"\d", "", text).strip()
    text = text.split("\n")[0].strip().strip("\"'“”‘’ ").strip()
    if not text or ASSISTANT_RE.search(text):
        return None
    words = text.split()[:max_words]
    return " ".join(words) or None


_SYL = ["gru", "brr", "pi", "mu", "nha", "kii", "ra", "bu"]
_REACT = [
    (("fome", "comer", "comida", "food", "hungry", "eat"), ["nom nom? * fome!", "mam... mam! brr", "nhom! nhom!"]),
    (("oi", "olá", "ola", "hi", "hello", "hey"), ["pii! * oi?", "gru? * pi-pi!", "hii... brr!"]),
    (("amo", "love", "fofo", "cute", "carinho"), ["prrr... * brr", "pi-pii! (feliz)", "mmm... gru gru"]),
    (("dorm", "sleep", "sono", "night", "noite"), ["zzz... gru", "uaaa... sono..."]),
]


def babble(user_text: str, stage: str, lang: str, rng: random.Random, key: str | None = None) -> str:
    lang = _lang(lang)
    if key in ("bleh", "missed_you", "brain_loading"):
        return BABBLE[lang][key]
    if stage == "egg":
        return BABBLE[lang]["egg"]
    t = (user_text or "").lower()
    words = set(re.split(r"\W+", t))
    for keys, replies in _REACT:
        if any((k in words) if len(k) <= 3 else (k in t) for k in keys):
            return rng.choice(replies)
    s = " ".join(rng.choice(_SYL) + rng.choice(["?", "!", "...", ""]) for _ in range(rng.randint(2, 4)))
    return s + " *"


_POS = {"pt": {"amo", "adoro", "gosto", "legal", "fofo", "lindo", "linda", "bom", "boa", "obrigado", "obrigada",
               "feliz", "divertido", "incrível", "melhor", "parabéns", "querido", "querida", "carinho"},
        "en": {"love", "like", "great", "good", "nice", "cute", "thanks", "thank", "happy", "fun", "best",
               "awesome", "wonderful", "sweet", "adore", "amazing"}}
_NEG = {"pt": {"odeio", "chato", "chata", "feio", "feia", "ruim", "burro", "burra", "idiota", "triste", "pior",
               "horrível", "droga", "cala", "estúpido", "estúpida", "detesto"},
        "en": {"hate", "boring", "ugly", "bad", "stupid", "dumb", "idiot", "sad", "worst", "awful", "terrible",
               "shut", "annoying", "detest"}}
_NEGATORS = {"pt": {"não", "nao", "nunca"}, "en": {"not", "no", "never", "dont", "don't"}}


def valence(text: str, lang: str) -> float:
    lang = _lang(lang)
    words = [w for w in re.split(r"[^\wÀ-ÿ']+", (text or "").lower()) if w]
    score, n = 0.0, 0
    for i, w in enumerate(words):
        s = 1.0 if w in _POS[lang] else -1.0 if w in _NEG[lang] else 0.0
        if s:
            if i > 0 and words[i - 1] in _NEGATORS[lang]:
                s = -s
            score += s
            n += 1
    if not n:
        return 0.0
    return max(-1.0, min(1.0, score / n))
