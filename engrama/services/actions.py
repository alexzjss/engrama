"""M20: small actions the creature may take for the user, each behind its own permission.

Three tools, and nothing else can ever run (no shell, no network, no files besides the store's own JSON):
reminders ("me lembra em 20 min de tirar o bolo"), a focus session (pomodoro) and notes ("anota: ...").

The intent comes from a deterministic parser (PT and EN); only when that fails on a message that still looks
like a command is the LLM asked, with a JSON schema, and its answer goes through the same validation.
Stdlib only: this module knows neither the app nor the mind."""
from __future__ import annotations
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

KINDS = ("reminder", "focus", "note", "focus_stop")
TOOLS = ("reminders", "focus", "notes")                       # permission names
TOOL_OF = {"reminder": "reminders", "focus": "focus", "focus_stop": "focus", "note": "notes"}
MAX_MINUTES = 24 * 60.0
MIN_MINUTES = 5.0 / 60.0
MAX_TEXT = 120
MAX_REMINDERS = 20
FOCUS_DEFAULT_MIN = 25.0


@dataclass(frozen=True)
class Intent:
    kind: str
    minutes: float = 0.0
    text: str = ""


_WORDS = {"um": 1, "uma": 1, "a": 1, "an": 1, "one": 1, "dois": 2, "duas": 2, "two": 2, "tres": 3, "três": 3, "three": 3,
          "cinco": 5, "five": 5, "dez": 10, "ten": 10, "quinze": 15, "fifteen": 15, "vinte": 20, "twenty": 20,
          "trinta": 30, "thirty": 30, "meia": 0.5, "half a": 0.5, "half an": 0.5}
# "a"/"an" only count right after in/for ("in an hour"): alone they are far too common a word
_NUM = (r"(\d+(?:[.,]\d+)?|half\s+an?|(?:(?<=in\s)|(?<=for\s))an?|"
        + "|".join(sorted((w for w in _WORDS if " " not in w and w not in ("a", "an")), key=len, reverse=True)) + r")")
_UNIT = r"(seg(?:undos?)?|sec(?:ond)?s?|min(?:uto|utinho|ute)?s?|horas?|hours?|hrs?|[smh])"
_DUR = re.compile(r"(?:\b(?:daqui\s+a|daqui|em|dentro\s+de|de|por|in|for|of)\s+)?(?<![\w.,])" + _NUM + r"\s*" + _UNIT + r"\b",
                  re.I)
_AND_HALF = re.compile(r"^\s+(?:e\s+meia|and\s+a\s+half)\b", re.I)
_REMIND = re.compile(r"\b(?:me\s+)?(?:lembr[ae]r?|avis[ae]r?|alert[ae]r?)(?:[- ]me)?\b|\bremind\s+me\b|"
                     r"\b(?:set\s+an?\s+|p[oõ]e\s+um\s+|coloca\s+um\s+)?(?:timer|reminder|temporizador|alarme|lembrete)\b", re.I)
_FOCUS = re.compile(r"\b(?:foco|focar|pomodoro|concentrar|focus)\b", re.I)
_FOCUS_START = re.compile(r"^\W*(?:modo\s+|vamos\s+|bora\s+|come[cç]ar?\s+(?:o\s+)?|inici[ae]r?\s+(?:o\s+)?|quero\s+|"
                          r"start\s+(?:a\s+)?|let'?s\s+|begin\s+)?(?:foco|focar|pomodoro|focus)\b", re.I)
_STOP = re.compile(r"\b(?:par[ae]r?|cancel[ae]r?|chega|encerr[ae]r?|termin[ae]r?|stop|end|cancel|quit)\b", re.I)
_NOTE = re.compile(r"^\W*(?:anot[ae]r?|tom[ae]\s+nota|guard[ae]\s+(?:isso|a[ií])|note|write\s+(?:this\s+|that\s+)?down|"
                   r"take\s+a\s+note|remember\s+that)\b(?:\s+(?:isso|a[ií]|that|this|d[eo]))?\s*[:,\-]?\s*(.*)$", re.I | re.S)
_LEAD = re.compile(r"^(?:[\s:,.\-]|\b(?:de|do|da|que|pra|para|sobre|to|that|about|por\s+favor|please|(?:voc[eê]\s+)?pode|can\s+you|could\s+you)\b)+", re.I)
_CLOCK = re.compile(r"\b(?:[àa]s|at)\s+\d", re.I)   # "às 15h" is a time of day, not a duration: not supported
_TAIL = re.compile(r"[\s,]+(?:uns|umas|em|daqui(?:\s+a)?|in|about)\s*$", re.I)
_HINT = re.compile(r"lembr|avis|remind|timer|alarm|foco|focus|pomodoro|anot|\bnote\b|\bnota\b", re.I)


def _minutes(num: str, unit: str) -> float:
    num = re.sub(r"\s+", " ", num.lower())
    n = _WORDS[num] if num in _WORDS else float(num.replace(",", "."))
    u = unit.lower()
    return n / 60.0 if u.startswith("s") else n * 60.0 if u.startswith("h") else float(n)


def _clean(text: str) -> str:
    text = _LEAD.sub("", text or "")
    return re.sub(r"\s+", " ", text).strip(" .!?,;:-")[:MAX_TEXT]


def _duration(text: str) -> tuple[float, tuple[int, int]] | None:
    m = _DUR.search(text)
    if m is None:
        return None
    minutes, end = _minutes(m.group(1), m.group(2)), m.end()
    half = _AND_HALF.match(text[end:])
    if half and m.group(2).lower().startswith("h"):
        minutes, end = minutes + 30.0, end + half.end()
    return minutes, (m.start(), end)


def valid(intent: Intent | None) -> Intent | None:
    """The one gate every intent passes, whatever produced it: known kind, sane duration, bounded text."""
    if intent is None or intent.kind not in KINDS:
        return None
    text = _clean(str(intent.text or ""))
    try:
        minutes = float(intent.minutes or 0.0)
    except (TypeError, ValueError):
        return None
    if intent.kind in ("reminder", "focus") and not MIN_MINUTES <= minutes <= MAX_MINUTES:
        return None
    if intent.kind == "note" and not text:
        return None
    return Intent(intent.kind, minutes if intent.kind in ("reminder", "focus") else 0.0,
                  text if intent.kind in ("reminder", "note") else "")


def parse_intent(text: str) -> Intent | None:
    """Deterministic PT/EN parser. None means "this is ordinary talk" (or a command it could not read)."""
    text = (text or "").strip()
    if not text or len(text) > 400:
        return None
    note = _NOTE.match(text)
    if not note and _CLOCK.search(text):
        return None
    if note:
        return valid(Intent("note", text=note.group(1)))
    dur = _duration(text)
    focus = _FOCUS.search(text)
    if focus:
        if _STOP.search(text):
            return Intent("focus_stop")
        if dur or _FOCUS_START.match(text) or len(text.split()) <= 3:
            return valid(Intent("focus", dur[0] if dur else FOCUS_DEFAULT_MIN))
        return None
    trig = _REMIND.search(text)
    if trig and dur:
        (a0, a1), (b0, b1) = sorted((trig.span(), dur[1]))
        head = text[:a0] if len(text[:a0].split()) > 3 else ""   # a short lead-in ("vê se", "ei,") is filler
        rest = head + " " + (text[a1:b0] + " " + text[b1:] if a1 <= b0 else text[max(a1, b1):])
        return valid(Intent("reminder", dur[0], _TAIL.sub("", rest)))
    return None


def looks_like_command(text: str) -> bool:
    """Cheap filter for the LLM fallback: a command word is there, but the parser could not read the message."""
    text = text or ""
    return bool(_HINT.search(text)) and len(text.split()) <= 30 and not _CLOCK.search(text)


# ---------------------------------------------------------------- LLM fallback (structured output)
INTENT_SCHEMA = {"type": "object",
                 "properties": {"action": {"type": "string", "enum": ["reminder", "focus", "note", "none"]},
                                "minutes": {"type": "number"}, "text": {"type": "string"}},
                 "required": ["action"]}
_SYSTEM = ("You extract a command from one user message. Answer with JSON only. "
           "action is \"reminder\" (the user asks to be reminded after some time; minutes = that time in minutes, "
           "text = what to be reminded of, in the user's words), \"focus\" (the user wants a focus or pomodoro "
           "session; minutes = its length, 25 if not said), \"note\" (the user asks to write something down; "
           "text = what to note) or \"none\" (anything else, including questions and ordinary talk). "
           "When in doubt, answer none.")


def intent_messages(text: str) -> list[dict]:
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": (text or "")[:400]}]


def intent_from_json(raw: str) -> Intent | None:
    """Validate what the model returned. Anything off the schema, off the whitelist or out of bounds is None."""
    try:
        m = re.search(r"\{.*\}", raw or "", re.S)
        d = json.loads(m.group(0)) if m else None
    except (ValueError, TypeError):
        return None
    if not isinstance(d, dict) or d.get("action") not in ("reminder", "focus", "note"):
        return None
    minutes = d.get("minutes", 0)
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)):
        return None
    if d["action"] == "focus" and not minutes:
        minutes = FOCUS_DEFAULT_MIN
    text = d.get("text", "")
    return valid(Intent(d["action"], float(minutes), text if isinstance(text, str) else ""))


# ---------------------------------------------------------------- store
@dataclass
class Reminder:
    id: int
    due: float      # wall time, seconds
    text: str


class ActionStore:
    """Pending reminders and the running focus session, kept in one small JSON file so they survive a restart."""

    def __init__(self, path: Path | None, now_fn: Callable[[], float]) -> None:
        self.path = Path(path) if path is not None else None
        self._now = now_fn
        self.reminders: list[Reminder] = []
        self.focus_until = 0.0
        self.focus_total = 0.0
        self._next = 1
        self._load()

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            self.reminders = [Reminder(int(r["id"]), float(r["due"]), str(r["text"])[:MAX_TEXT])
                              for r in d.get("reminders", [])][:MAX_REMINDERS]
            self.focus_until, self.focus_total = float(d.get("focus_until", 0.0)), float(d.get("focus_total", 0.0))
            self._next = max([r.id for r in self.reminders], default=0) + 1
        except (OSError, ValueError, KeyError, TypeError):   # a broken file never stops the app: start empty
            self.reminders, self.focus_until, self.focus_total = [], 0.0, 0.0

    def _save(self) -> None:
        if self.path is None:
            return
        data = {"reminders": [asdict(r) for r in self.reminders], "focus_until": self.focus_until,
                "focus_total": self.focus_total}
        try:
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass

    # --- reminders
    def add_reminder(self, minutes: float, text: str) -> Reminder | None:
        if len(self.reminders) >= MAX_REMINDERS or not MIN_MINUTES <= minutes <= MAX_MINUTES:
            return None
        r = Reminder(self._next, self._now() + minutes * 60.0, _clean(text))
        self._next += 1
        self.reminders.append(r)
        self.reminders.sort(key=lambda x: x.due)
        self._save()
        return r

    def cancel(self, rid: int) -> bool:
        n = len(self.reminders)
        self.reminders = [r for r in self.reminders if r.id != rid]
        if len(self.reminders) != n:
            self._save()
        return len(self.reminders) != n

    def pop_due(self) -> list[Reminder]:
        now = self._now()
        due = [r for r in self.reminders if r.due <= now]
        if due:
            self.reminders = [r for r in self.reminders if r.due > now]
            self._save()
        return due

    # --- focus
    @property
    def focus_active(self) -> bool:
        return self.focus_until > 0.0

    def focus_left(self) -> float:
        return max(0.0, self.focus_until - self._now()) if self.focus_active else 0.0

    def focus_progress(self) -> float:
        if not self.focus_active or self.focus_total <= 0.0:
            return 0.0
        return max(0.0, min(1.0, 1.0 - self.focus_left() / self.focus_total))

    def start_focus(self, minutes: float) -> bool:
        if not MIN_MINUTES <= minutes <= MAX_MINUTES:
            return False
        self.focus_total = minutes * 60.0
        self.focus_until = self._now() + self.focus_total
        self._save()
        return True

    def stop_focus(self) -> bool:
        was = self.focus_active
        self.focus_until = self.focus_total = 0.0
        if was:
            self._save()
        return was

    def pop_focus_done(self) -> bool:
        """True once, when the running session reaches its end."""
        if self.focus_active and self._now() >= self.focus_until:
            self.stop_focus()
            return True
        return False

    def clear(self) -> None:
        self.reminders = []
        self.focus_until = self.focus_total = 0.0
        self._save()
