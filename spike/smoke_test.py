"""Headless smoke test: python smoke_test.py"""
import os, sys, time
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
import json
import numpy as np, pygame
import llm
llm.CONFIG_PATH = os.path.join(os.path.dirname(llm.__file__), "config_smoke.json")  # keep the real config.json untouched
import main
main.SAVE = os.path.join(os.path.dirname(main.__file__), "save_smoke.json")
from snn import SNN

if os.environ.get("REAL_LLM") == "1":  # python smoke_test.py with REAL_LLM=1: talk to a real Ollama (see config)
    g = main.Game(); g.c.stage = "baby"; g.build_sprites()
    t0 = time.time()
    while g.llm.state == "loading" and time.time() - t0 < 320: time.sleep(0.5)
    print("warm-up:", g.llm.state, "%.1fs" % (time.time() - t0), "|", g.llm.label())
    for msg in ["oi engrama, tudo bem?", "você gosta de jogos?", "hey, are you hungry?", "to triste hoje"]:
        g.chat_text = msg; g.send_chat(); t1 = time.time()
        while g.llm.out.empty() and time.time() - t1 < 60: time.sleep(0.05)
        print(f"{msg!r} -> {g.llm.out.get()!r}  [{time.time() - t1:.1f}s, mode {g.llm.mode}]")
    print("system prompt:", llm.build_system(g.c, "", "Write in English.")); os.remove(llm.CONFIG_PATH); sys.exit(0)

llm.http_json = lambda *a, **k: {}  # mocked Ollama for the Game's start-up warm-up

# 1) SNN firing rates
for name, stim in [("quiet", [0,0,0,0,0,.5,.2,0,0,0]), ("bored", [0,0,0,0,.8,.5,.2,0,0,0]),
                   ("lonely+click", [.8,.5,0,0,0,.5,.2,0,.9,0]), ("all-high", [1]*10)]:
    s = SNN()
    for _ in range(100): s.run(stim, 30)   # 3000 steps
    print(f"SNN {name:13s} hidden {s.h_rate:5.1f} Hz | groups(idle,wand,play,slp,ask,expl) {np.round(s.group_rate,1)}")

# 2) main loop 300 frames with simulated events
g = main.Game()
post = pygame.event.post
E = pygame.event.Event
t0 = time.time(); frames = 0
for i in range(300):
    if i == 10: post(E(pygame.MOUSEBUTTONDOWN, pos=(240, 200), button=1))
    if 12 <= i < 22 and i % 2 == 0: post(E(pygame.MOUSEBUTTONDOWN, pos=g.creature_rect().center, button=1))
    if i in (150, 151): post(E(pygame.MOUSEBUTTONDOWN, pos=g.creature_rect().center, button=1))
    if i == 30: post(E(pygame.KEYDOWN, key=pygame.K_TAB, unicode="", mod=0))
    if i == 40: post(E(pygame.KEYDOWN, key=pygame.K_f, unicode="f", mod=0))
    if i == 42: post(E(pygame.KEYDOWN, key=pygame.K_1, unicode="1", mod=0))  # food menu -> carne
    if i == 45: post(E(pygame.KEYDOWN, key=pygame.K_p, unicode="p", mod=0))
    if i == 50: post(E(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r", mod=0))
    if 51 <= i < 51 + len("oi, tudo bem?"):
        ch = "oi, tudo bem?"[i-51]; post(E(pygame.KEYDOWN, key=ord(ch) if ch.isalpha() else 0, unicode=ch, mod=0))
    if i == 70: post(E(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r", mod=0))
    if i == 100: post(E(pygame.KEYDOWN, key=pygame.K_TAB, unicode="", mod=0))
    if i == 120: post(E(pygame.KEYDOWN, key=pygame.K_r, unicode="r", mod=0))
    if i == 160: post(E(pygame.KEYDOWN, key=pygame.K_r, unicode="r", mod=0))
    if i == 200: post(E(pygame.KEYDOWN, key=pygame.K_s, unicode="s", mod=0))
    g.frame(1/18); frames += 1
    time.sleep(0.005)
g.save()
print("frames", frames, "stage", g.c.stage, "behavior", g.c.behavior, "rest", g.rest, "debug", g.debug)
print("llm mode", g.llm.mode, "| last bubble", g.bubble[0] if g.bubble else None)
print("needs", {k: round(v) for k, v in g.c.needs.items()}, "bandit", {k: round(v,2) for k,v in g.bandit.q.items()})
print("events", [e["e"] for e in g.events[-8:]])
print("audio ok:", g.snd.ok, "| elapsed %.1fs" % (time.time()-t0))

# 3) food menu, preferences, save round-trip
import foods
assert not g.food_menu and g.c.prefs and set(g.c.prefs) == set(foods.ORDER)
def key(k, ch=""): post(E(pygame.KEYDOWN, key=k, unicode=ch, mod=0)); g.frame(1/18)
g.chat_focus = False; g.c.stage = "baby"; g.build_sprites()
g.c.needs["fome"] = 80; g.c.prefs["bug"] = 0.9
key(pygame.K_f); assert g.food_menu
key(pygame.K_ESCAPE); assert not g.food_menu
key(pygame.K_f); key(pygame.K_DOWN); key(pygame.K_UP); key(pygame.K_RETURN)  # carne via arrows
assert not g.food_menu and g.food_show and g.food_show[0] == "carne"
g.c.needs["fome"] = 80
key(pygame.K_f); [key(pygame.K_DOWN) for _ in range(foods.ORDER.index("bug"))]; key(pygame.K_RETURN)
assert g.food_show[0] == "bug" and g.c.needs["fome"] < 80 and "feed bug fr" in g.events[-1]["e"], g.events[-1]
g.c.prefs["cache"] = -0.9
import random as _r; _r.seed(1); refused = 0
for _ in range(10):
    g.feed("cache"); refused += g.events[-1]["e"].startswith("refused")
assert refused >= 1, "disliked food never refused"
g.c.prefs["cache"] = -0.9
fav, bad = foods.taste_summary(g.c.prefs); assert "cache quentinho" in bad and "bug frito" in fav
assert "cache quentinho" in llm.build_system(g.c, "", "Write in Portuguese.")
for fid in foods.ORDER: foods.icon(fid, 4)
g.save(); g.c.prefs = None; g.load(); assert g.c.prefs and g.c.prefs["bug"] > 0.5
print("food ok | refused", refused, "/10 | prefs", g.c.prefs)

# 4) model screen (Ollama mocked: tags OK, streaming pull)
def wait(cond):
    for _ in range(100):
        if cond(): return
        time.sleep(0.02)
    raise AssertionError("timeout")
llm.http_json = lambda url, body=None, timeout=20: {"models": [{"name": "qwen3:1.7b"}]}
llm.http_stream = lambda url, body, timeout=60: iter([{"status": "pulling x", "total": 100, "completed": 40},
                                                       {"status": "pulling x", "total": 100, "completed": 100}, {"status": "success"}])
key(pygame.K_m); assert g.model_screen; wait(lambda: g.llm.tags_state == "ok"); g.frame(1/18)
assert g.llm.is_installed("qwen3:1.7b") and not g.llm.is_installed("gemma3:1b")
key(pygame.K_ESCAPE); assert not g.model_screen
key(pygame.K_m); [key(pygame.K_DOWN) for _ in range(len(llm.RECOMMENDED))]; key(pygame.K_RETURN); assert g.mcustom_edit
for ch in "foo:1b": key(ord(ch), ch)
assert g.mcustom_text == "foo:1b"
key(pygame.K_RETURN)
wait(lambda: g.llm.pull and g.llm.pull["done"]); g.frame(1/18)
assert g.llm.pull["error"] is None and g.llm.model == "foo:1b", g.llm.pull
assert json.load(open(llm.CONFIG_PATH))["model"] == "foo:1b"
key(pygame.K_ESCAPE)
# Ollama unreachable: screen opens, name can still be set, no pull
def boom(*a, **k): raise OSError("down")
llm.http_json = boom
key(pygame.K_m); wait(lambda: g.llm.tags_state == "down"); g.frame(1/18)
g.msel = 1; key(pygame.K_RETURN); assert g.llm.model == "gemma3:1b" and g.llm.pull["model"] == "foo:1b"
key(pygame.K_ESCAPE)
# 5) mocked /api/chat with a <think> block; the request also carries think:false
seen = {}
def fake_chat(url, body=None, timeout=20):
    seen.update(body); return {"message": {"content": "<think>\nhmm let me think\n</think>\npii! *"}}
llm.http_json = fake_chat
g.llm.state = "ready"; g.llm.last_ok = time.time(); g.llm.down_until = 0; g.llm._work("oi", "sys", lambda t: "BABBLE", True)
r = g.llm.out.get(timeout=2)
assert r == "pii! *" and g.llm.mode == "ollama" and seen["think"] is False and seen["options"]["num_ctx"] == 2048
assert g.llm.label() == "llm: gemma3:1b", g.llm.label()
assert llm.strip_think("a<think>x</think>b<think>unclosed") == "ab"
# post-processing: digits / stat dumps rejected, retried once, then babble; emojis stripped
assert llm.clean_reply("gru 😀 pii!") == "gru  pii!" and llm.clean_reply("fome 20 carinho 30") == ""
calls = []
def fake_dump(url, body=None, timeout=20):
    calls.append(body["options"]["temperature"]); return {"message": {"content": "fome 20 carinho 30"}}
llm.http_json = fake_dump; g.llm.state = "ready"; g.llm._work("oi", "sys", lambda t: "BABBLE", True)
assert g.llm.out.get(timeout=2) == "BABBLE" and calls == [0.8, 0.9], calls
sysmsg = llm.build_system(g.c, "feed 20", "Write in English.")
assert not any(ch.isdigit() for ch in sysmsg) and "Engrama" in sysmsg, sysmsg
# loading state: babble + sleepy hint, no chat request, server not marked dead; refused/error -> offline + cooldown
g.llm.state = "loading"; llm.http_json = lambda *a, **k: 1 / 0
g.llm._work("oi", "sys", lambda t: "BABBLE", True)
assert "cérebro carregando" in g.llm.out.get(timeout=2) and g.llm.down_until < time.time()
assert g.llm.label() == "llm: acordando..."
llm.http_json = boom; g.llm.state = "ready"; g.llm._work("oi", "sys", lambda t: "BABBLE", True)
assert g.llm.out.get(timeout=2) == "BABBLE" and g.llm.label() == "llm: babble (offline)" and g.llm.state == "offline"
# timeout while ready is not "dead": no cooldown
def slow(*a, **k): raise TimeoutError("slow")
llm.http_json = slow; g.llm.state = "ready"; g.llm.down_until = 0; g.llm._work("oi", "sys", lambda t: "BABBLE", True)
g.llm.out.get(timeout=2); assert g.llm.down_until == 0
# warm-up / unload requests
reqs = []
llm.http_json = lambda url, body=None, timeout=20: reqs.append((url[-13:], body, timeout)) or {}
g.llm.warm(); wait(lambda: g.llm.state == "ready"); g.llm.unload(); wait(lambda: len(reqs) == 2)
assert reqs[0][2] == 300 and reqs[0][1]["prompt"] == "" and reqs[1][1]["keep_alive"] == 0 and g.llm.state == "offline", reqs
assert llm.load_config()["keep_alive"] in ("10m", "2m")
print("model/llm ok:", repr(r))
os.remove(main.SAVE); os.remove(llm.CONFIG_PATH)
pygame.quit(); print("SMOKE OK")
