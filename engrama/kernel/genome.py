"""Procedural creature genome: body traits, palette and voice."""
import colorsys
import random
from dataclasses import dataclass

Color = tuple[int, int, int]


def _rgb(h: float, s: float, v: float) -> Color:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (round(r * 255), round(g * 255), round(b * 255))


def _palette(rng: random.Random) -> tuple[Color, Color, Color, Color]:
    hue = rng.random()
    sat = rng.uniform(0.45, 0.75)
    val = rng.uniform(0.75, 0.95)
    main = _rgb(hue, sat, val)
    outline = _rgb(hue, min(1.0, sat + 0.2), 0.22)
    shade = _rgb(hue, min(1.0, sat + 0.1), val * 0.7)
    accent = _rgb(hue + 0.5, rng.uniform(0.5, 0.8), 0.95)
    return (outline, main, shade, accent)


@dataclass(frozen=True)
class Genome:
    seed: int
    body: int
    eyes: int
    ears: int
    tail: int
    pattern: int
    palette: tuple[Color, ...]
    voice_pitch: float
    branch: str = "base"

    @classmethod
    def from_seed(cls, seed: int) -> "Genome":
        rng = random.Random(seed)
        return cls(
            seed=seed,
            body=rng.randint(0, 5),
            eyes=rng.randint(0, 3),
            ears=rng.randint(0, 4),
            tail=rng.randint(0, 3),
            pattern=rng.randint(0, 3),
            palette=_palette(rng),
            voice_pitch=round(rng.uniform(180.0, 520.0), 1),
        )

    @classmethod
    def inherit(cls, parent: "Genome", new_seed: int) -> "Genome":
        fresh = cls.from_seed(new_seed)
        keep = random.Random(new_seed).choice(("body", "ears", "tail"))
        values = {"body": fresh.body, "ears": fresh.ears, "tail": fresh.tail}
        values[keep] = getattr(parent, keep)
        return cls(
            seed=new_seed,
            eyes=fresh.eyes,
            pattern=fresh.pattern,
            palette=(fresh.palette[0], parent.palette[1], *fresh.palette[2:]),
            voice_pitch=fresh.voice_pitch,
            branch=parent.branch,
            **values,
        )

    def to_dict(self) -> dict:
        d = {f: getattr(self, f) for f in
             ("seed", "body", "eyes", "ears", "tail", "pattern", "voice_pitch", "branch")}
        d["palette"] = [list(c) for c in self.palette]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Genome":
        return cls(
            seed=int(d["seed"]), body=int(d["body"]), eyes=int(d["eyes"]),
            ears=int(d["ears"]), tail=int(d["tail"]), pattern=int(d["pattern"]),
            palette=tuple(tuple(int(x) for x in c) for c in d["palette"]),
            voice_pitch=float(d["voice_pitch"]), branch=d.get("branch", "base"),
        )
