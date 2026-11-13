"""Record demo videos and stills of the real app with several creatures. Usage:
    python tools/demo_reel.py --out demo-media              # simulate the pets, then record each one
    python tools/demo_reel.py --out demo-media --only draco --no-llm
For each pet in PETS it raises a creature with the lab simulator (cached in OUT/pets), opens the app on a copy of
that save (headless SDL, time scale 1, the terrarium pinned at the pet's hour) and plays a short script: idle, pet,
food, a chat message and sometimes a panel. Every frame is piped to ffmpeg (OUT/video/NAME.mp4, 2x nearest-neighbour)
and key moments are saved as PNGs (OUT/stills). Then it joins the clips (OUT/video/reel.mp4), makes a README gif
(OUT/demo.gif) and a grid of all the pets (OUT/pets.png). With Ollama running the chat replies are real; with
--no-llm they are babble. Needs ffmpeg on the PATH."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FPS = 30
TYPE_CPS = 14.0   # typing speed of the scripted user

# name (family), seed, sim profile, sim days, creature name, terrarium hour, food, chat message, panel or ""
PETS = (
    ("draco", 6, "attentive", 30, "Brasa", 10.0, "carne", "oi Brasa! dormiu bem?", "mind"),
    ("fera", 7, "gamer", 12, "Tico", 13.0, "peixe", "bora jogar mais tarde?", ""),
    ("espirito", 31, "night_owl", 75, "Lume", 21.5, "cache", "você tem medo do escuro?", ""),
    ("aquatico", 3, "attentive", 12, "Marola", 8.0, "peixe", "me lembra em 30 segundos de beber água", "actions"),
    ("maquina", 8, "attentive", 75, "Bit", 15.5, "byte", "foco por 1 min", ""),
    ("inseto", 13, "absent", 4, "Zuzu", 11.0, "fruta", "oi Zuzu, tudo bem?", "food"),
    ("planta", 4, "attentive", 30, "Musgo", 18.4, "fruta", "qual sua comida favorita?", ""),
    ("ave", 1, "night_owl", 12, "Pena", 6.8, "bolinho", "bom dia, Pena!", "memories"),
)


def simulate(pets_dir: Path, which) -> None:
    """Raise each pet with the lab simulator (in parallel); a save already there is reused."""
    procs = []
    for name, seed, profile, days, *_ in which:
        if (pets_dir / name / "save" / "kernel.json").exists():
            continue
        (pets_dir / name).mkdir(parents=True, exist_ok=True)
        log = open(pets_dir / f"{name}.log", "w")
        procs.append(subprocess.Popen([sys.executable, "-m", "engrama.lab", "sim", "--recipe",
                                       str(ROOT / "engrama/recipes/default-v1.toml"), "--days", str(days), "--profile",
                                       profile, "--seed", str(seed), "--save", str(pets_dir / name / "save")],
                                      cwd=ROOT, stdout=log, stderr=subprocess.STDOUT))
    for p in procs:
        p.wait()
    print("simulated", len(procs), "pets", flush=True)


def script(pet) -> list:
    """(wall seconds, action, arg) for one pet. Actions: shot, pet, food, type, enter, panel, close, end.
    The "chat" still is not on the list: it is taken when the reply bubble shows up."""
    _, _, _, _, _, _, food, message, panel = pet
    enter = 9.5 + len(message) / TYPE_CPS + 0.6
    s = [(1.5, "shot", "idle"), (3.0, "pet", None), (3.4, "shot", "pet"), (4.4, "pet", None), (6.5, "food", food),
         (7.2, "shot", "eat"), (9.5, "type", message), (enter, "enter", None)]
    t = enter + 7.0    # counted from the reply: the script holds after "enter" until the bubble shows up
    if panel:
        s += [(t, "panel", panel), (t + 1.5, "shot", panel), (t + 5.0, "close", None)]
        t += 5.0
    return s + [(t + 2.0, "end", None)]


def record_one(pet, data: Path, out: Path, no_llm: bool) -> int:
    """Run the app in this process on `data` and record it (one pet per process: pygame is initialised once)."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    import pygame
    from engrama.app import cli, rest
    from engrama.app.ui import window as W
    rest_update = rest.RestPolicy.update
    # the model in RAM can leave less than REST_RAM_FREE_MB free on a small machine; a rest would unload it mid-take
    rest.RestPolicy.update = lambda self, *a, **k: (lambda r: None if r == "low_ram" else r)(rest_update(self, *a, **k))
    name, _, _, _, _, hour, _, _, _ = pet
    steps = script(pet)
    video = out / "video"
    stills = out / "stills"
    video.mkdir(parents=True, exist_ok=True)
    stills.mkdir(parents=True, exist_ok=True)
    st = {"t0": None, "written": 0, "i": 0, "typing": None, "ff": None, "el": 0.0,
          "reply": None, "reply_shot": None,
          "born": time.monotonic(), "shift": 0.0, "last_el": 0.0, "reply_t": 0.0}

    def ffmpeg(size):
        w, h = size
        return subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                                 f"{w}x{h}", "-r", str(FPS), "-i", "-", "-vf", f"scale={w * 2}:{h * 2}:flags=neighbor",
                                 "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
                                 "-movflags", "+faststart", str(video / f"{name}.mp4")], stdin=subprocess.PIPE)
    orig = W.Window.frame
    W.Window.target_fps = property(lambda self: FPS)   # smoother video than the app's 10-20 FPS

    def creature_pos(win):
        r = win.scene.creature_rect
        return ((r.x + r.w // 2) * W.SCALE, (r.y + r.h // 2) * W.SCALE)

    def act(win, action, arg):
        if action == "shot":
            pygame.image.save(win.screen, str(stills / f"{name}-{arg}.png"))
        elif action == "pet":
            win.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=creature_pos(win)))
        elif action == "food":
            win.give_food(arg)
        elif action == "type":
            st["typing"] = [arg, 0, st["el"]]
        elif action == "enter":
            win.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r"))
            st["reply"], st["reply_t"] = len(win.chat.history), st["el"]
        elif action == "panel":
            win.open_panel(arg)
        elif action == "close":
            win.close_panel()
        elif action == "end":
            win.running = False

    def frame(self, now=None):
        self.scene.hour_fn = lambda: hour
        self.skip_identical = False
        wall = time.monotonic()
        if st["t0"] is None and not no_llm and self.chat.status(wall) != "ready" and wall - st["born"] < 120:
            if self.chat.status(wall) == "offline":
                self.chat.language.warm()   # the app warms up on the first message; the take wants it ready
            return orig(self, now)   # the take starts once the model answers (the first seconds would be "loading")
        if st["t0"] is None:
            st["t0"], st["ff"] = wall, ffmpeg(self.screen.get_size())
        el = st["el"] = wall - st["t0"]
        typing = st["typing"]
        while typing is not None and typing[1] < min(len(typing[0]), int((el - typing[2]) * TYPE_CPS) + 1):
            typing[1] += 1
            self.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=typing[0][typing[1] - 1]))
        orig(self, now)
        if st["reply"] is not None and ((len(self.chat.history) > st["reply"] and self.chat.bubble)
                                        or el - st["reply_t"] > 45):
            st["reply"], st["reply_shot"] = None, el + 1.2   # the bubble is in: let it settle, then take the still
        if st["reply_shot"] is not None and el >= st["reply_shot"]:
            st["reply_shot"] = None
            act(self, "shot", "chat")
        if st["reply"] is not None:   # holding for the reply: the clock of the script stands still
            st["shift"] += el - st["last_el"]
        st["last_el"] = el
        while st["i"] < len(steps) and el - st["shift"] >= steps[st["i"]][0]:
            _, action, arg = steps[st["i"]]
            st["i"] += 1
            act(self, action, arg)
            if action != "shot":
                orig(self, None)   # show the effect in this very frame
        due = int(el * FPS) + 1
        if due > st["written"]:
            st["ff"].stdin.write(pygame.image.tobytes(self.screen, "RGB") * (due - st["written"]))
            st["written"] = due

    W.Window.frame = frame
    argv = ["--data-dir", str(data), "--time-scale", "1", "--fake-perception", "--seconds", str(steps[-1][0] + 150)]
    code = cli.main(argv + (["--no-llm"] if no_llm else [])) or 0
    st["ff"].stdin.close()
    st["ff"].wait()
    print("recorded", name, f"{st['written'] / FPS:.1f}s", flush=True)
    return code


def prepare(pet, pets_dir: Path, scratch: Path) -> Path:
    """A throwaway data dir: a copy of the simulated save plus a config with a name, so no first-use screen shows."""
    from engrama.config import Config
    name = pet[0]
    data = scratch / name
    shutil.copytree(pets_dir / name, data)
    cfg = Config(data_dir=data)
    cfg.perception_asked = True
    cfg.creature_name = pet[4]
    cfg.ui_lang = "pt"
    cfg.action_permissions = {"reminders": True, "focus": True, "notes": False}
    cfg.save(data / "config.json")
    (data / "actions.json").write_text(json.dumps({"reminders": [
        {"id": 1, "due": time.time() + 40 * 60, "text": "regar as plantas"}]}), encoding="utf-8")
    return data


def finish(out: Path, names: list[str]) -> None:
    """Join the clips, cut a README gif out of a few of them and lay the idle stills out in a grid."""
    video = out / "video"
    clips = [video / f"{n}.mp4" for n in names if (video / f"{n}.mp4").exists()]
    if len(clips) > 1:
        lst = video / "reel.txt"
        lst.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                        str(video / "reel.mp4")], check=True)
        lst.unlink()
    # gif: the pet and food beats (2.6 s to 8.6 s) of up to four clips, half size
    parts = clips[:4]
    if parts:
        ins = sum((["-ss", "2.6", "-t", "6", "-i", str(c)] for c in parts), [])
        cat = "".join(f"[{i}:v]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1[v]"
        flt = (f"{cat};[v]fps=15,scale=480:360:flags=neighbor,split[a][b];[a]palettegen=max_colors=128[p];"
               "[b][p]paletteuse=dither=none")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *ins, "-filter_complex", flt, str(out / "demo.gif")],
                       check=True)
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    shots = [out / "stills" / f"{n}-idle.png" for n in names if (out / "stills" / f"{n}-idle.png").exists()]
    if shots:
        cols, tw, th = 4, 320, 240
        rows = (len(shots) + cols - 1) // cols
        grid = pygame.Surface((cols * tw, rows * th))
        grid.fill((24, 22, 32))
        for i, p in enumerate(shots):
            grid.blit(pygame.transform.smoothscale(pygame.image.load(str(p)), (tw, th)), ((i % cols) * tw, (i // cols) * th))
        pygame.image.save(grid, str(out / "pets.png"))
    print("done:", out, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="demo-media")
    ap.add_argument("--only", nargs="*", default=None, help="pet names (families) to record")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--one", default=None, help=argparse.SUPPRESS)   # internal: record this data dir
    a = ap.parse_args()
    out = Path(a.out).resolve()
    if a.one:
        pet = next(p for p in PETS if p[0] == Path(a.one).name)
        return record_one(pet, Path(a.one), out, a.no_llm)
    which = [p for p in PETS if not a.only or p[0] in a.only]
    pets_dir = out / "pets"
    simulate(pets_dir, which)
    scratch = Path(tempfile.mkdtemp(prefix="engrama_reel_", dir=str((ROOT / ".pytest_tmp").resolve())))
    try:
        for pet in which:
            data = prepare(pet, pets_dir, scratch)
            subprocess.run([sys.executable, __file__, "--out", str(out), "--one", str(data)]
                           + (["--no-llm"] if a.no_llm else []), cwd=ROOT, check=False)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    finish(out, [p[0] for p in PETS])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
