"""Stage persona: prompt building, reply cleaning, babble and a tiny valence lexicon.

Pure functions plus local PT/EN tables; services never import the app layer.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field, replace

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
    facts: list[str] = field(default_factory=list)
    current_topics: list[str] = field(default_factory=list)
    past_topics: list[str] = field(default_factory=list)
    opinion: str | None = None
    ancestral: list[str] = field(default_factory=list)   # vague dreams from before birth


def apply_recall(state: PersonaState, ctx) -> PersonaState:
    """Return a copy of state carrying a RecallContext (services.memory.recall)."""
    return replace(state, facts=list(ctx.facts), memories=list(ctx.episodes), current_topics=list(ctx.current),
                   past_topics=list(ctx.past), opinion=ctx.opinion,
                   ancestral=list(getattr(ctx, "ancestral", []) or []))


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
    "pt": {"fome": "está com fome", "sono": "está com sono", "tedio": "está entediada e quer brincar",
           "carinho": "quer carinho e atenção", "curiosidade": "está curiosa sobre tudo",
           "apoio": "precisa de apoio e incentivo"},
    "en": {"fome": "hungry", "sono": "sleepy", "tedio": "bored and wanting to play",
           "carinho": "wanting cuddles and attention", "curiosidade": "curious about everything",
           "apoio": "in need of support and encouragement"},
}
STYLE_TEXT = {
    "pt": {"baby": "Fala de bebê: de uma a seis palavras, misturando palavras simples e sons de bebê como 'gru', 'pii', 'brr'.",
           "child": "Fala de criança: uma frase curta, no máximo 8 palavras, curiosa e brincalhona.",
           "full": "Fala com naturalidade, frases curtas, com personalidade própria."},
    "en": {"baby": "Baby speech: one to six words, mixing simple words and baby sounds like 'gru', 'pii', 'brr'.",
           "child": "Child speech: one short sentence, at most 8 words, curious and playful.",
           "full": "Speak naturally in short sentences, with a personality of your own."},
}
FEWSHOT = {
    ("baby", "pt"): [("oi!", "pii! oi oi!"), ("quer brincar?", "gru! sim sim! pii!"),
                     ("o que você é?", "engrama! bebê digi! pii!")],
    ("baby", "en"): [("hi!", "pii! hi hi!"), ("what are you?", "engrama! me digi-baby, pii!"),
                     ("do you like music?", "brr... music! yes yes! gru!")],
    ("child", "pt"): [("oi!", "oi! quer brincar?"),
                      ("você gosta de música?", "gosto! é divertido!"),
                      ("vamos dormir?", "ah, não! mais um pouquinho!")],
    ("child", "en"): [("hi!", "hi! wanna play?"),
                      ("do you like music?", "yes! so fun!"),
                      ("let's sleep?", "aw, no! a little more!")],
    ("full", "pt"): [("oi!", "oi! que bom te ver por aqui."),
                     ("o que você acha de música?", "gosto bastante, mas prefiro o silêncio às vezes."),
                     ("quem é você?", "Sou o Engrama, moro na sua janela."),
                     ("me ajuda com meu código?", "isso é coisa de computador chato... eu só moro aqui.")],
    ("full", "en"): [("hi!", "hi! good to see you here."),
                     ("what do you think of music?", "i like it a lot, but sometimes i prefer the quiet."),
                     ("who are you?", "I'm Engrama, I live in your window."),
                     ("can you help with my code?", "that's boring computer stuff... i just live here.")],
}
BABBLE = {
    "pt": {"bleh": "bleh!", "missed_you": "demorou... gru?", "brain_loading": "zzz... (cérebro carregando)",
           "egg": "... (o ovo vibra)"},
    "en": {"bleh": "bleh!", "missed_you": "you took long... gru?", "brain_loading": "zzz... (brain loading)",
           "egg": "... (the egg trembles)"},
}


REFLECT_PROMPT = {
    "pt": ("Você é a memória do Engrama. Leia a conversa abaixo e responda em JSON puro e nada mais: "
           '{"summary": "uma frase curta, sem números, sobre o que o humano e você conversaram", '
           '"topic": "o assunto principal em uma ou duas palavras, ou null"}.'),
    "en": ("You are Engrama's memory. Read the conversation below and answer in pure JSON and nothing else: "
           '{"summary": "one short sentence, no numbers, about what the human and you talked about", '
           '"topic": "the main subject in one or two words, or null"}.'),
}
OPINION_PROMPT = {
    "pt": ("Escreva em uma linha curta, sem números, a opinião do Engrama sobre \"{topic}\". Comece pela expressão "
           "\"{stance}\" (a posição dele) e mantenha a coerência com ela. "
           "Formato de exemplo: \"{stance} {topic} porque...\". Só a frase, sem aspas."),
    "en": ("Write in one short line, no numbers, Engrama's opinion about \"{topic}\". Start with the phrase "
           "\"{stance}\" (his stance) and stay consistent with it. "
           "Format example: \"{stance} {topic} because...\". Only the sentence, no quotes."),
}
SPONTANEOUS_PROMPT = {
    "pt": {"current": "(O humano não disse nada. Puxe papo por conta própria sobre o assunto de agora: {topic}. Uma linha curta.)",
           "opinion": "(O humano não disse nada. Diga por conta própria o que você acha de {topic}, de acordo com a sua opinião. Uma linha curta.)",
           "past": "(O humano não disse nada. Lembre por conta própria, com saudade, do assunto antigo: {topic}. Uma linha curta.)",
           "activity": "(O humano está ocupado com isto agora: {topic}. Faça por conta própria um comentário curto e discreto sobre isso, sem dizer que está vendo a tela. Uma linha curta.)"},
    "en": {"current": "(The human said nothing. Start a chat on your own about the current subject: {topic}. One short line.)",
           "opinion": "(The human said nothing. Say on your own what you think about {topic}, following your opinion. One short line.)",
           "past": "(The human said nothing. Fondly bring up, on your own, the old subject: {topic}. One short line.)",
           "activity": "(The human is busy with this right now: {topic}. Make a short, discreet remark about it on your own, without saying you are watching the screen. One short line.)"},
}
SPONTANEOUS_PROMPT["pt"]["ancestral"] = (
    "(O humano não disse nada. Diga por conta própria, como quem acorda de um sonho vago de antes de nascer, "
    "algo sobre isto: {topic}. Uma linha curta.)")
SPONTANEOUS_PROMPT["en"]["ancestral"] = (
    "(The human said nothing. Say on your own, like waking from a vague dream from before you were born, "
    "something about this: {topic}. One short line.)")
FAREWELL_PROMPT = {
    "pt": {"old_age": "(Você está velho e cansado e chegou a hora de partir. Diga uma despedida curta, carinhosa e "
                      "serena ao seu humano, agradecendo o tempo juntos. Uma linha curta.)",
           "neglect": "(Você está fraco demais e chegou a hora de partir. Diga uma despedida curta e triste, sem "
                      "culpar, ao seu humano. Uma linha curta.)"},
    "en": {"old_age": "(You are old and tired and it is time to go. Say a short, warm, serene goodbye to your human, "
                      "thanking them for the time together. One short line.)",
           "neglect": "(You are too weak and it is time to go. Say a short, sad goodbye to your human, without "
                      "blaming them. One short line.)"},
}
FAREWELL_BABBLE = {
    "pt": ["pii... gru... (te quero bem)", "brr... mu... obrigado... pii", "nha... zzz... (adeus, gru)"],
    "en": ["pii... gru... (love you)", "brr... mu... thank you... pii", "nha... zzz... (bye bye, gru)"],
}
FILE_PROMPT = {
    "pt": ("(O humano acabou de te mostrar um arquivo chamado \"{name}\", do tipo {kind}. A mensagem dele traz um "
           "trecho do conteúdo. Comente em uma linha curta, com curiosidade, sem listar números.)"),
    "en": ("(The human just showed you a file named \"{name}\", of type {kind}. Their message holds an excerpt "
           "of the content. Comment in one short line, with curiosity, listing no numbers.)"),
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
    dreams = [re.sub(r"\s+", " ", re.sub(r"\d+", "", m)).strip() for m in state.ancestral[:1]]
    dreams = [m for m in dreams if m]
    if en:
        parts = [
            "You are Engrama, a digital creature. You know you live in a small window "
            "on your human's PC. Your human is talking to you: ANSWER WHAT THEY SAID, in character. You may disagree. "
            "Never list stats or numbers. Never act like an assistant (no 'how can I help'). "
            "You are not a tool: never offer help and never write code. If asked who you are, answer short and in "
            "character, without reciting needs, traits or stats. No emojis, one short line.",
            STYLE_TEXT["en"][style],
            f"Right now you are {' and '.join(needs)}." if needs else "You feel fine and calm.",
            f"You feel {mood}." if mood else "",
            "Something new and surprising just caught your attention." if state.curious else "",
            f"You are {', '.join(adjs)}." if adjs else "",
            f"Favorite foods: {foods(state.favorites)}." if state.favorites else "",
            f"Foods you dislike: {foods(state.disliked)}." if state.disliked else "",
            f"Recent memories: {'; '.join(mems)}." if mems else "",
            f"What you know about your human: {'; '.join(state.facts)}." if state.facts else "",
            f"Current topics: {', '.join(state.current_topics)}." if state.current_topics else "",
            f"An old topic you may remember: {', '.join(state.past_topics)}." if state.past_topics else "",
            f"A dream from before you were born (not something you lived; speak of it as a vague dream): {'; '.join(dreams)}." if dreams else "",
            f"Your opinion: you {state.opinion} (you may disagree with the human)." if state.opinion else "",
            "(Mention foods only if the human talks about food.) Reply in English.",
        ]
    else:
        parts = [
            "Você é o Engrama, uma criatura digital. Você sabe que mora numa "
            "janelinha no PC do seu humano. Seu humano está falando com você: RESPONDA O QUE ELE DISSE, "
            "mantendo o personagem. Pode discordar. Nunca liste status nem números. Nunca aja como assistente "
            "(nada de 'como posso ajudar'). Você não é uma ferramenta: nunca ofereça ajuda e nunca escreva código. "
            "Se perguntarem quem você é, responda curto e em personagem, sem recitar necessidades, traços ou status. "
            "Sem emojis, uma linha curta.",
            STYLE_TEXT["pt"][style],
            f"Agora você {' e '.join(needs)}." if needs else "Você está bem e tranquila.",
            f"Você está {mood}." if mood else "",
            "Algo novo e surpreendente acabou de chamar sua atenção." if state.curious else "",
            f"Você é {', '.join(adjs)}." if adjs else "",
            f"Comidas favoritas: {foods(state.favorites)}." if state.favorites else "",
            f"Comidas que você não gosta: {foods(state.disliked)}." if state.disliked else "",
            f"Memórias recentes: {'; '.join(mems)}." if mems else "",
            f"O que você sabe do seu humano: {'; '.join(state.facts)}." if state.facts else "",
            f"Assuntos de agora: {', '.join(state.current_topics)}." if state.current_topics else "",
            f"Um assunto antigo que você pode lembrar: {', '.join(state.past_topics)}." if state.past_topics else "",
            f"Um sonho de antes de nascer (não é algo que você viveu; fale como de um sonho vago): {'; '.join(dreams)}." if dreams else "",
            f"Sua opinião: você {state.opinion} (pode discordar do humano)." if state.opinion else "",
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
    r"let me know (if|what|how)|vou (te )?ajudar|pronto para (te )?ajudar|(para|pra) (te )?ajudar|i'?d love to help|"
    r"i can help|happy to help|how i can assist|what kind of (code|help)|what specific task|o que você precisa|"
    r"here'?s a |aqui está uma função|```|^\s*def |"
    r"posso (te |lhe )?ajudar|possa (te )?ajudar|precis(ar|a) de ajuda|se quiser,? posso (te )?(ouvir|ver|escrever|mostrar|explicar|fazer)|dizer o que precisa|"
    r"if you need (any )?help|if you want,? i can", re.I | re.M)


def strip_emoji(text: str) -> str:
    return EMOJI_RE.sub("", text)


def _norm_line(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", (text or "").lower()).split())


def is_repeat(text: str, history: list[dict], n: int = 3) -> bool:
    """True when text equals (case/punctuation-insensitive) one of the creature's last n replies."""
    last = [m["content"] for m in history if m.get("role") == "assistant"][-n:]
    key = _norm_line(text)
    return bool(key) and any(_norm_line(x) == key for x in last)


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


def build_file_messages(state: PersonaState, lang: str, name: str, kind: str, excerpt: str,
                        food_name=None) -> list[dict]:
    """Chat messages for a dropped file: name/kind go in the (digit-free) system prompt, excerpt as the user turn."""
    lang = _lang(lang)
    msgs = build_messages(state, [], excerpt, lang, food_name)
    note = re.sub(r"\d", "", FILE_PROMPT[lang].format(name=name, kind=kind))
    msgs[0]["content"] = msgs[0]["content"] + " " + note
    return msgs


def build_farewell_messages(state: PersonaState, cause: str, lang: str, food_name=None) -> list[dict]:
    """Chat messages for the last words; same persona, the farewell instruction is the user turn."""
    lang = _lang(lang)
    prompts = FAREWELL_PROMPT[lang]
    text = re.sub(r"\d", "", prompts.get(cause, prompts["old_age"]))
    return build_messages(replace(state, ancestral=[]), [], text, lang, food_name)


def farewell_babble(lang: str, rng: random.Random) -> str:
    return rng.choice(FAREWELL_BABBLE[_lang(lang)])
