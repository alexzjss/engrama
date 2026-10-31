import re

_PT_CHARS = set("ãõçáéíóúâêô")
_PT = set("""oi olá ola você voce vc não nao sim tudo bem quer comer brincar fome sono com como que uma um meu minha
bom boa dormir amo carinho tá ta to triste hoje estou está esta gosta gostar jogos jogo muito feliz cansado cansada
obrigado obrigada também tambem eu tu ele ela nós nos eles elas isso isto aquilo aqui ali onde quando porque por
para pra de do da dos das no na nos nas em ao os as ou mas se já ja ainda então entao só so mais menos pouco quase
sempre nunca agora depois antes ontem amanhã amanha dia noite tarde cedo casa amigo amiga vamos vai vou foi ser ter
tem tenho fazer faz fez quero queria pode posso sabe saber falar fala diz conta conte oq hj blz kkk valeu beleza
legal nome qual quem quanto""".split())
_EN = set("""hi hello hey you your yours are is am was were be been the a an and or but not no yes what whats how
why when where who which this that these those it its i me my mine we us our they them their he she him her
do does did done have has had will would can could should want like love hungry sleepy tired sad happy
today tomorrow yesterday now later before after always never just very much more less some any all with without
for from to in on at of up down out over about so if then than too also really please thanks thank
name game games play eat sleep friend home good bad""".split())
_SPLIT = re.compile(r"[^\wÀ-ÿ']+")


def detect_lang(text: str, default: str = "pt") -> str:
    t = text.lower()
    words = [w for w in _SPLIT.split(t) if w]
    pt = sum(1 for c in t if c in _PT_CHARS) * 2 + sum(1 for w in words if w in _PT)
    en = sum(1 for w in words if w in _EN)
    if pt == en:
        return default
    return "pt" if pt > en else "en"
