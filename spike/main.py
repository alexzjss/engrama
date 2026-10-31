"""Virtual pet spike. Run: .venv\\Scripts\\python main.py"""
import json
import math
import os
import random
import sys
import time

import numpy as np
import pygame

import behavior as bh
import foods
import sprite
from creature import Creature, NEEDS, LABELS, WORLD_W, WORLD_H
from llm import LLM, RECOMMENDED, babble, build_system, is_pt
from snn import SNN, NI
from sound import Sound

HERE = os.path.dirname(os.path.abspath(__file__))
SAVE = os.path.join(HERE, "save.json")
W, H, SC = 480, 400, 5
VIEW_H = WORLD_H * SC  # 340
FPS, FPS_REST = 18, 5
EGG_SECONDS, EGG_CLICKS = 20, 5


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Engrama")
        self.screen = pygame.display.set_mode((W, H))
        self.world = pygame.Surface((WORLD_W, WORLD_H))
        self.scaled = pygame.Surface((W, VIEW_H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas,dejavusansmono,arial", 12)
        self.big = pygame.font.SysFont("consolas,dejavusansmono,arial", 14, bold=True)
        pygame.key.set_repeat(350, 40)
        self.c = Creature()
        self.snn = SNN()
        self.bandit = bh.Bandit()
        self.events = []
        self.bubble = None  # (text, until)
        self.llm = LLM()
        self.llm.warm()  # load the model in the background so the first chat is not a cold start
        self.running = True
        self.debug = False
        self.rest = False
        self.auto_rest = False
        self.focus_lost_at = None
        self.chat_focus = False
        self.chat_text = ""
        self.pulses = {"click": 0.0, "chat": 0.0, "feed": 0.0}
        self.beh_t = 0.0
        self.rest_acc = 0.0
        self.t = 0.0
        self.last_utils = {}
        self.pending_reply = False
        self.flash = 0.0
        self.food_menu = False
        self.food_sel = 0
        self.food_show = None  # (food id, until)
        self.model_screen = False
        self.msel = 0
        self.mcustom_edit = False
        self.mcustom_text = ""
        self.load()
        if not self.c.prefs:
            self.c.prefs = foods.init_prefs(self.c.seed, self.c.traits)
        self.snd = Sound(self.c.seed)
        self.frames = None
        self.egg = None
        self.build_sprites()

    # ---------- persistence ----------
    def load(self):
        try:
            with open(SAVE, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            return
        try:
            c = self.c
            c.seed, c.traits, c.needs = d["seed"], d["traits"], d["needs"]
            c.stage, c.egg_t, c.egg_clicks = d["stage"], d.get("egg_t", 0), d.get("egg_clicks", 0)
            self.bandit.q = d["bandit"]
            self.snn = SNN(weights=d["snn"])
            self.events = d.get("events", [])[-50:]
            c.prefs = d.get("prefs") or None
            elapsed = max(0, time.time() - d.get("saved_at", time.time()))
            if c.stage != "egg":
                mins = min(elapsed / 60, 60)
                for k in NEEDS:
                    c.needs[k] = min(100, c.needs[k] + min(40, mins * 0.5))
            if elapsed > 3600:
                h = int(elapsed // 3600)
                self.say(f"demorou... ({h}h)", 6)
        except Exception as e:
            print("save ignored:", e)

    def save(self):
        d = {"seed": self.c.seed, "traits": self.c.traits, "needs": self.c.needs, "stage": self.c.stage,
             "egg_t": self.c.egg_t, "egg_clicks": self.c.egg_clicks, "bandit": self.bandit.q,
             "snn": self.snn.weights(), "prefs": self.c.prefs, "events": self.events[-50:], "saved_at": time.time()}
        try:
            with open(SAVE, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
        except Exception as e:
            print("save failed:", e)

    def log(self, e):
        self.events.append({"t": int(time.time()), "e": e})
        self.events = self.events[-50:]

    def build_sprites(self):
        self.egg = sprite.make_egg(self.c.seed, self.c.traits)
        self.cracks = sprite.crack_pixels(self.c.seed)
        if self.c.stage != "egg":
            self.frames = sprite.make_baby(self.c.seed, self.c.traits)

    # ---------- actions ----------
    def say(self, text, secs=4.0):
        self.bubble = (text, time.time() + secs)

    def responded(self):
        c = self.c
        if c.ask_t is not None and time.time() - c.ask_t <= 10:
            self.bandit.update("ask_attention", +1.0)
            self.log("ask_attention rewarded")
            c.ask_t = None

    def hatch(self):
        self.c.stage = "baby"
        self.frames = sprite.make_baby(self.c.seed, self.c.traits)
        self.snd.play("hatch")
        self.flash = 1.0
        self.say("pii!", 3)
        self.log("hatched")

    def poke(self):  # click on creature / egg
        c = self.c
        self.pulses["click"] = 1.0
        if c.stage == "egg":
            c.egg_clicks += 1
            return
        if c.sleeping:
            c.sleeping = False
            c.change(sono=+5)
            self.say("mm!?", 2)
        else:
            self.say(random.choice(["prrr", "pi-pi!", "gru~"]), 2)
        c.change(carinho=-25, tedio=-5)
        self.log("pet")
        self.responded()

    def feed(self, fid=None):
        c = self.c
        if c.stage == "egg":
            return
        if fid is None:  # open the menu instead of instant feeding
            self.food_menu, self.food_sel = True, 0
            return
        name, kind, fome, fx, _ = foods.FOODS[fid]
        self.food_show = (fid, time.time() + 1.6)
        v = foods.verdict(c.prefs[fid])
        if v == "dislike" and random.random() < 0.6:
            foods.update_pref(c.prefs, fid)
            c.prefs[fid] = max(-1.0, c.prefs[fid] - 0.03)  # refusing sours the taste a bit
            self.say("bleh!", 2.5)
            self.snd.play("bleh")
            self.log(f"refused {name}")
            self.responded()
            return
        c.change(fome=-fome * (0.5 if v == "dislike" else 1), **fx)
        if v == "like":
            c.change(carinho=-10, tedio=-5)
            self.say("nhom nhom! *", 2.5)
        elif v == "dislike":
            self.say("bleh... nhom", 2.5)
            self.snd.play("bleh")
        else:
            self.say("nom nom!", 2)
        foods.update_pref(c.prefs, fid)
        self.pulses["feed"] = 1.0
        self.log(f"feed {name} ({v})")
        self.responded()

    def play(self):
        if self.c.stage == "egg":
            return
        self.c.change(tedio=-35, curiosidade=-10, sono=+3)
        self.say("pii pii!", 2)
        self.log("play")
        self.responded()

    def toggle_sleep(self):
        c = self.c
        if c.stage == "egg":
            return
        c.sleeping = not c.sleeping
        c.behavior = "sleep" if c.sleeping else "idle"
        self.log("sleep toggle")

    def toggle_rest(self, auto=False):
        self.rest = not self.rest
        self.auto_rest = auto and self.rest
        self.rest_acc = 0.0
        self.say("zZz... (descanso)" if self.rest else "voltei!", 2)
        self.llm.unload() if self.rest else self.llm.warm()  # rest frees the model's RAM

    def send_chat(self):
        text = self.chat_text.strip()
        self.chat_text = ""
        if not text:
            return
        c = self.c
        self.pulses["chat"] = 1.0
        if c.stage != "egg":
            c.change(carinho=-8, tedio=-15)
        self.log("user: " + text[:60])
        self.responded()
        mem = "; ".join(e["e"] for e in self.events[-6:])
        lang = "Write in Portuguese." if is_pt(text) else "Write in English."
        system = build_system(c, mem, lang)
        use = (not self.rest) and c.stage != "egg"
        self.pending_reply = True
        self.say("...", 30)
        self.llm.ask(text, system, lambda t: babble(t, c.stage, c.seed), use_llm=use)

    def poll_llm(self):
        try:
            while True:
                r = self.llm.out.get_nowait()
                self.pending_reply = False
                self.say(r, 5)
                self.log("creature: " + r[:60])
                if not self.rest and not self.c.sleeping:
                    self.snd.play("speak")
        except Exception:
            pass

    # ---------- events ----------
    def handle_events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.WINDOWFOCUSLOST:
                self.focus_lost_at = time.time()
            elif ev.type == pygame.WINDOWFOCUSGAINED:
                self.focus_lost_at = None
                if self.auto_rest and self.rest:
                    self.toggle_rest()
            elif ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_TAB, pygame.K_F1):
                    self.debug = not self.debug
                elif self.model_screen:
                    self.model_key(ev)
                elif self.food_menu:
                    self.food_key(ev)
                elif self.chat_focus:
                    if ev.key == pygame.K_RETURN:
                        self.send_chat(); self.chat_focus = False
                    elif ev.key == pygame.K_ESCAPE:
                        self.chat_focus = False
                    elif ev.key == pygame.K_BACKSPACE:
                        self.chat_text = self.chat_text[:-1]
                    elif ev.unicode and ev.unicode.isprintable() and len(self.chat_text) < 70:
                        self.chat_text += ev.unicode
                else:
                    if ev.key == pygame.K_RETURN:
                        self.chat_focus = True
                    elif ev.key == pygame.K_f:
                        self.feed()
                    elif ev.key == pygame.K_m:
                        self.open_models()
                    elif ev.key == pygame.K_p:
                        self.play()
                    elif ev.key == pygame.K_s:
                        self.toggle_sleep()
                    elif ev.key == pygame.K_r:
                        self.toggle_rest()
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                x, y = ev.pos
                if y >= H - 26:
                    self.chat_focus = True
                elif self.creature_rect().inflate(10, 10).collidepoint(ev.pos):
                    self.poke()
                else:
                    self.pulses["click"] = 1.0

    def food_key(self, ev):
        k, n = ev.key, len(foods.ORDER)
        if k == pygame.K_ESCAPE:
            self.food_menu = False
        elif k == pygame.K_UP:
            self.food_sel = (self.food_sel - 1) % n
        elif k == pygame.K_DOWN:
            self.food_sel = (self.food_sel + 1) % n
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.food_menu = False
            self.feed(foods.ORDER[self.food_sel])
        elif pygame.K_1 <= k <= pygame.K_9 and k - pygame.K_1 < n:
            self.food_menu = False
            self.feed(foods.ORDER[k - pygame.K_1])

    def open_models(self):
        self.model_screen, self.mcustom_edit, self.mcustom_text = True, False, ""
        names = [n for n, _ in RECOMMENDED]
        self.msel = names.index(self.llm.model) if self.llm.model in names else 0
        self.llm.refresh_tags()

    def model_key(self, ev):
        k, n = ev.key, len(RECOMMENDED) + 1  # last entry = "outro..."
        if self.mcustom_edit:
            if k == pygame.K_ESCAPE:
                self.mcustom_edit = False
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.mcustom_edit = False
                self.llm.choose(self.mcustom_text)
            elif k == pygame.K_BACKSPACE:
                self.mcustom_text = self.mcustom_text[:-1]
            elif ev.unicode and ev.unicode.isprintable() and len(self.mcustom_text) < 50:
                self.mcustom_text += ev.unicode
        elif k == pygame.K_ESCAPE:
            self.model_screen = False
        elif k == pygame.K_UP:
            self.msel = (self.msel - 1) % n
        elif k == pygame.K_DOWN:
            self.msel = (self.msel + 1) % n
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.msel == n - 1:
                self.mcustom_edit = True
            else:
                self.llm.choose(RECOMMENDED[self.msel][0])

    def creature_rect(self):
        c = self.c
        w, h = (sprite.EW, sprite.EH) if c.stage == "egg" else (sprite.W, sprite.H)
        return pygame.Rect(int((c.x - w / 2) * SC), int((c.y - h - c.hop) * SC), w * SC, h * SC)

    # ---------- simulation ----------
    def stimuli(self):
        n = {k: v / 100 for k, v in self.c.needs.items()}
        hour = time.localtime().tm_hour + time.localtime().tm_min / 60
        cl = lambda v: float(min(1, max(0, v)))
        return [self.pulses["click"], self.pulses["chat"], self.pulses["feed"], cl((n["fome"] - 0.6) / 0.4),
                cl((n["tedio"] - 0.5) / 0.5), 0.5 + 0.5 * math.cos(2 * math.pi * hour / 24),
                0.15 + random.random() * 0.1, cl((n["sono"] - 0.5) / 0.5), cl((n["carinho"] - 0.5) / 0.5),
                cl((n["curiosidade"] - 0.5) / 0.5)]

    def sim(self, dt, decay):
        c = self.c
        if c.stage == "egg":
            if not self.rest:
                c.egg_t += dt
            if c.egg_t >= EGG_SECONDS or c.egg_clicks >= EGG_CLICKS:
                self.hatch()
        c.tick_needs(dt)
        self.snn.run(self.stimuli(), 30)
        for k in self.pulses:
            self.pulses[k] *= decay
        if c.stage == "egg":
            return
        # behavior tick (~1 Hz)
        self.beh_t += dt
        if self.beh_t >= 1.0:
            self.beh_t = 0.0
            if c.sleeping:
                c.behavior = "sleep"
            else:
                b, self.last_utils = bh.choose(c, self.snn.group_rate, self.snn.arousal, self.bandit)
                if b == "sleep":
                    c.sleeping = True
                if b == "ask_attention" and not self.rest and c.behavior != "ask_attention":
                    c.ask_t = time.time()
                    self.snd.play("ask")
                    self.say("gru? ... *", 2)
                    self.log("ask_attention")
                c.behavior = b
                if b in ("wander", "explore", "play_alone"):
                    c.new_target()
        if c.ask_t is not None and time.time() - c.ask_t > 10:
            self.bandit.update("ask_attention", -0.3)
            self.log("ask_attention ignored")
            c.ask_t = None
        if not self.rest:
            c.move(dt, c.behavior)

    # ---------- drawing ----------
    def draw_world(self):
        w, c = self.world, self.c
        w.fill((22, 24, 44))
        pygame.draw.rect(w, (34, 38, 64), (0, 30, WORLD_W, WORLD_H - 30))
        pygame.draw.line(w, (60, 66, 100), (0, 30), (WORLD_W, 30))
        blink = int(self.t * 10) % 40 == 0
        if c.stage == "egg":
            prog = max(c.egg_t / EGG_SECONDS, c.egg_clicks / EGG_CLICKS)
            wob = round(math.sin(self.t * 9) * 1.5 * (0.3 + prog)) if math.sin(self.t * 1.3) > 0.4 or prog > 0.6 else 0
            ox, oy = int(c.x - sprite.EW / 2) + wob, int(c.y - sprite.EH)
            w.blit(self.egg, (ox, oy))
            for (px, py) in self.cracks[: int(prog * len(self.cracks))]:
                w.set_at((ox + px, oy + py), (30, 20, 40))
        else:
            asleep = c.sleeping or self.rest
            fr = self.frames["blink" if (blink or asleep) else "open"]
            bob = 1 if int(self.t * 2.5) % 2 and c.behavior != "sleep" else 0
            ox, oy = int(c.x - sprite.W / 2), int(c.y - sprite.H - c.hop + bob)
            w.blit(fr, (ox, oy))
        if self.flash > 0:
            self.flash = max(0, self.flash - 0.08)
            pygame.draw.rect(w, (255, 255, 255), (0, 0, WORLD_W, WORLD_H), width=2)
        pygame.transform.scale(w, (W, VIEW_H), self.scaled)
        self.screen.blit(self.scaled, (0, 0))

    def text(self, s, pos, color=(230, 230, 240), font=None):
        self.screen.blit((font or self.font).render(s, True, color), pos)

    def draw_bubble(self):
        if not self.bubble or time.time() > self.bubble[1]:
            return
        words, lines, cur = self.bubble[0].replace("✦", "*").split(), [], ""
        for wd in words:
            if self.font.size(cur + " " + wd)[0] > 150 and cur:
                lines.append(cur); cur = wd
            else:
                cur = (cur + " " + wd).strip()
        lines.append(cur)
        bw = max(self.font.size(l)[0] for l in lines) + 12
        bh_ = len(lines) * 14 + 8
        r = self.creature_rect()
        bx = max(4, min(W - bw - 4, r.centerx - bw // 2))
        by = max(24, r.top - bh_ - 8)
        pygame.draw.rect(self.screen, (250, 250, 245), (bx, by, bw, bh_), border_radius=6)
        pygame.draw.polygon(self.screen, (250, 250, 245), [(r.centerx - 5, by + bh_), (r.centerx + 5, by + bh_), (r.centerx, by + bh_ + 7)])
        for i, l in enumerate(lines):
            self.text(l, (bx + 6, by + 4 + i * 14), (20, 20, 30))

    def draw_hud(self):
        for i, k in enumerate(NEEDS):
            x = 6 + i * 94
            v = self.c.needs[k]
            self.text(LABELS[k], (x, 3), (200, 200, 220))
            pygame.draw.rect(self.screen, (50, 50, 70), (x, 17, 86, 5))
            col = (90, 200, 120) if v < 50 else (230, 190, 70) if v < 75 else (230, 80, 80)
            pygame.draw.rect(self.screen, col, (x, 17, int(86 * v / 100), 5))

    def draw_effects(self):
        c, r = self.c, self.creature_rect()
        if c.stage == "egg":
            return
        if c.sleeping or self.rest:
            self.text("z" if int(self.t * 2) % 2 else "Z", (r.right - 6, r.top - 6), (180, 200, 255), self.big)
        elif c.behavior == "ask_attention":
            self.text("!", (r.right - 4, r.top - 14), (255, 220, 80), self.big)
        elif c.behavior == "explore":
            self.text("?", (r.right - 4, r.top - 14), (120, 220, 255), self.big)

    def draw_panel(self, x, y, w, h):
        p = pygame.Surface((w, h), pygame.SRCALPHA)
        p.fill((8, 8, 20, 235))
        self.screen.blit(p, (x, y))
        pygame.draw.rect(self.screen, (90, 100, 160), (x, y, w, h), 1, border_radius=4)

    def draw_food(self):
        if self.food_show and time.time() < self.food_show[1]:
            r = self.creature_rect()
            bob = int(math.sin(self.t * 8) * 2)
            self.screen.blit(foods.icon(self.food_show[0], 4), (r.right + 2, r.centery - 10 + bob))
        if not self.food_menu:
            return
        n = len(foods.ORDER)
        x, y, w = 90, 30, 300
        self.draw_panel(x, y, w, 28 + n * 26)
        self.text("Comer o que?  (1-9 / setas + Enter, Esc)", (x + 8, y + 5), (150, 255, 180))
        for i, fid in enumerate(foods.ORDER):
            yy = y + 26 + i * 26
            if i == self.food_sel:
                pygame.draw.rect(self.screen, (50, 60, 110), (x + 4, yy - 2, w - 8, 24), border_radius=3)
            self.screen.blit(foods.icon(fid, 2), (x + 10, yy + 2))
            name, kind, fome = foods.FOODS[fid][:3]
            self.text(f"{i + 1} {name}", (x + 34, yy + 4), (240, 240, 255))
            self.text(f"fome -{fome}", (x + w - 70, yy + 4), (140, 140, 170))
            if self.debug:  # peek at the taste score
                self.text(f"{self.c.prefs[fid]:+.1f}", (x + w - 110, yy + 4), (255, 190, 150))

    def draw_models(self):
        if not self.model_screen:
            return
        llm = self.llm
        x, y, w = 20, 20, W - 40
        rows = RECOMMENDED + [("outro...", "digitar qualquer nome de modelo")]
        self.draw_panel(x, y, w, 96 + len(rows) * 30)
        self.text(f"Modelo LLM  (ativo: {llm.model})", (x + 8, y + 5), (150, 255, 180), self.big)
        st = {"ok": "Ollama conectado", "loading": "consultando Ollama...",
              "down": "Ollama inacessível (você ainda pode definir o nome)"}
        self.text(st.get(llm.tags_state, ""), (x + 8, y + 24), (255, 200, 120) if llm.tags_state == "down" else (150, 150, 180))
        for i, (name, note) in enumerate(rows):
            yy = y + 44 + i * 30
            if i == self.msel:
                pygame.draw.rect(self.screen, (50, 60, 110), (x + 4, yy - 2, w - 8, 28), border_radius=3)
            last = i == len(rows) - 1
            mark = "" if last else ("[ativo] " if name == llm.model else "[instalado] " if llm.is_installed(name) else "")
            self.text(name, (x + 10, yy), (240, 240, 255))
            self.text(mark + note, (x + 10, yy + 13), (140, 200, 140) if mark else (130, 130, 160))
        yy = y + 50 + len(rows) * 30
        if self.mcustom_edit:
            cur = "_" if int(self.t * 2) % 2 else ""
            self.text("nome: " + self.mcustom_text + cur, (x + 10, yy), (255, 255, 255))
        p = llm.pull
        if p:
            if p["error"]:
                self.text("falhou: " + p["error"], (x + 10, yy + 14), (255, 120, 120))
            else:
                self.text(f"baixando {p['model']}: {p['pct']}%  {p['status'][:26]}", (x + 10, yy + 14), (255, 220, 120))
                pygame.draw.rect(self.screen, (50, 50, 70), (x + 10, yy + 30, w - 20, 5))
                pygame.draw.rect(self.screen, (90, 200, 120), (x + 10, yy + 30, int((w - 20) * p["pct"] / 100), 5))
        self.text("Cima/Baixo escolhe, Enter seleciona, Esc fecha", (x + 8, y + 78 + len(rows) * 30), (120, 120, 150))

    def draw_footer(self):
        y0 = VIEW_H
        pygame.draw.rect(self.screen, (14, 14, 26), (0, y0, W, H - y0))
        c = self.c
        if c.stage == "egg":
            prog = int(100 * max(c.egg_t / EGG_SECONDS, c.egg_clicks / EGG_CLICKS))
            info = f"Ovo {prog}%  (clique p/ chocar: {c.egg_clicks}/{EGG_CLICKS})"
        else:
            info = (f"{'(descanso) ' if self.rest else ''}comp: {c.behavior}  humor: {self.snn.arousal:.2f}  "
                    f"[Bebê > ??? > ??? > ???]")
        self.text(info, (6, y0 + 4), (180, 220, 255))
        self.text("F comer P brincar S dormir R descanso M modelo Tab SNN",
                  (6, y0 + 20), (120, 120, 150))
        mode = self.llm.label()
        self.text(mode, (W - 8 - self.font.size(mode)[0], y0 + 4), (140, 140, 170))
        pygame.draw.rect(self.screen, (40, 44, 70) if not self.chat_focus else (60, 70, 120), (4, H - 24, W - 8, 20), border_radius=4)
        cur = "_" if self.chat_focus and int(self.t * 2) % 2 else ""
        shown = self.chat_text if (self.chat_text or self.chat_focus) else "Enter para falar..."
        self.text("> " + shown + cur, (10, H - 21), (240, 240, 255) if self.chat_text or self.chat_focus else (110, 110, 140))

    def draw_debug(self):
        raster, vm = self.snn.ordered()
        pw, ph = 420, 270
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((8, 8, 20, 225))
        self.screen.blit(panel, (30, 30))
        self.text("SNN  (raster 200 passos: in|hid|out)", (38, 33), (150, 255, 180))
        # raster: x = time, y = neuron
        img = np.zeros((raster.shape[0], raster.shape[1], 3), np.uint8)
        img[..., 0] = raster * 255; img[..., 1] = raster * 255; img[..., 2] = raster * 255
        img[:, :NI, 2] = np.where(raster[:, :NI], 255, 0); img[:, :NI, 0] = 0; img[:, :NI, 1] = raster[:, :NI] * 120
        img[:, 30:, 0] = raster[:, 30:] * 255; img[:, 30:, 1] = raster[:, 30:] * 100; img[:, 30:, 2] = 0
        surf = pygame.transform.scale(pygame.surfarray.make_surface(img), (400, 80))
        self.screen.blit(surf, (40, 48))
        # membrane potentials
        y0 = 134
        pygame.draw.rect(self.screen, (20, 20, 40), (40, y0, 400, 50))
        cols = [(255, 120, 120), (120, 255, 120), (120, 160, 255), (255, 220, 100)]
        for j in range(4):
            pts = [(40 + i * 2, y0 + 48 - int(min(1.1, vm[i, j]) * 44)) for i in range(0, vm.shape[0])]
            pygame.draw.lines(self.screen, cols[j], False, pts, 1)
        self.text("Vm (h0,h7,o0,o8) limiar=1", (44, y0 + 2), (150, 150, 180))
        # weight heatmaps
        def heat(Wm, pos, label):
            a = np.clip(Wm / 1.2, 0, 1)
            im = np.stack([a * 255, a * 200, 80 + a * 100], -1).astype(np.uint8)
            s = pygame.transform.scale(pygame.surfarray.make_surface(im), (Wm.shape[0] * 7, Wm.shape[1] * 7))
            self.screen.blit(s, pos)
            self.text(label, (pos[0], pos[1] - 13), (150, 150, 180))
        heat(self.snn.W_ih.T, (40, 204), "W in->hid (20x10)")
        heat(self.snn.W_ho, (200, 204), "W hid->out")
        gr = self.snn.group_rate
        names = ["idle", "wand", "play", "slp", "ask", "expl"]
        for i, n in enumerate(names):
            self.text(f"{n}:{gr[i]:4.1f}Hz", (360, 192 + i * 11), (255, 200, 120))
        self.text(f"hid {self.snn.h_rate:4.1f}Hz  arousal {self.snn.arousal:.2f}", (40, 262), (150, 255, 180))
        q = " ".join(f"{k[:3]}:{v:+.1f}" for k, v in self.bandit.q.items())
        self.text("bandit " + q, (40, 276), (180, 180, 220))

    def draw(self):
        self.draw_world()
        self.draw_effects()
        self.draw_hud()
        self.draw_bubble()
        self.draw_food()
        if self.debug:
            self.draw_debug()
        self.draw_footer()
        self.draw_models()
        pygame.display.flip()

    # ---------- main loop ----------
    def frame(self, dt):
        self.t += dt
        self.handle_events()
        self.poll_llm()
        if (not self.rest and self.focus_lost_at and time.time() - self.focus_lost_at > 60):
            self.toggle_rest(auto=True)
        if self.rest:
            self.rest_acc += dt
            if self.rest_acc >= 1.0:
                self.sim(self.rest_acc, 0.3)
                self.rest_acc = 0.0
        else:
            self.sim(dt, 0.88)
        self.draw()

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS_REST if self.rest else FPS) / 1000
            self.frame(min(dt, 0.25))
        self.save()
        pygame.quit()


if __name__ == "__main__":
    Game().run()
