"""Capture README screenshots of the real app (headless SDL). Usage:
    python tools/screenshots.py --out docs/images --seed 3
Runs the app in-process on a scratch data dir with a fast clock and saves PNGs of the
terrarium, Mind View, Memories, Permissions and Foods panels. No LLM, no network."""
from __future__ import annotations

import argparse
import os
import tempfile
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from engrama.app.ui import window as W  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/images")
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--time-scale", type=float, default=20000.0)
    ap.add_argument("--wait", type=float, default=25.0, help="wall seconds before the shots")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix="engrama_shots_", dir=str(Path(".pytest_tmp").resolve())))
    from engrama.config import Config
    cfg = Config(data_dir=data)
    cfg.perception_asked = True
    cfg.save(data / "config.json")
    # plan: (wall seconds from start, key to press, filename)
    t0 = time.monotonic()
    plan = [(a.wait, None, "ui-terrarium.png"), (a.wait + 3, pygame.K_F2, "ui-mind-view.png"),
            (a.wait + 7, pygame.K_F4, "ui-foods.png"), (a.wait + 10, pygame.K_F7, "ui-memories.png"),
            (a.wait + 13, pygame.K_F8, "ui-permissions.png")]
    state = {"i": 0, "pending": None}
    orig = W.Window.frame

    def frame(self, now=None):
        orig(self, now)
        self.skip_identical = False
        if state["pending"]:
            name, due = state["pending"]
            if time.monotonic() >= due:
                pygame.image.save(self.screen, str(out / name))
                print("saved", name, "stage", self._snap.stage, flush=True)
                state["pending"] = None
                state["i"] += 1
                if state["i"] >= len(plan):
                    self.running = False
            return
        if state["i"] < len(plan):
            at, key, name = plan[state["i"]]
            if time.monotonic() - t0 >= at:
                if state["i"] > 0:
                    self.close_panel()
                if key is not None:
                    self.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))
                state["pending"] = (name, time.monotonic() + 1.0)

    W.Window.frame = frame
    from engrama.app import cli
    argv = ["--data-dir", str(data), "--seed", str(a.seed), "--no-llm",
                "--fake-perception", "--time-scale", str(a.time_scale), "--seconds", str(a.wait + 40)]
    return cli.main(argv) or 0


if __name__ == "__main__":
    raise SystemExit(main())
