"""M20 glue: turns a chat message or a menu click into one of the three permitted actions, and fires what is due.

The services module (`engrama.services.actions`) parses and stores; this one checks the permission, talks back in
the creature's voice and writes notes to memory. Nothing here can do anything outside that whitelist."""
from __future__ import annotations
import logging
from typing import Callable
from engrama.app import i18n
from engrama.services import actions as A

log = logging.getLogger("engrama.app")
NOTE_KEY_CHARS = 40


class Actions:
    def __init__(self, store: A.ActionStore, cfg, memory, language, snapshot: Callable[[], object],
                 save_config: Callable[[], None] | None = None, say: Callable[[str], None] | None = None,
                 on_alert: Callable[[str], None] | None = None) -> None:
        self.store, self.cfg, self.memory, self.language = store, cfg, memory, language
        self.snapshot = snapshot
        self.save_config = save_config
        self._say = say or (lambda text: None)
        self.on_alert = on_alert or (lambda text: None)   # a reminder fired or a focus session ended

    # --- permissions
    def allowed(self, tool: str) -> bool:
        return bool(getattr(self.cfg, "action_permissions", {}).get(tool, False))

    def set_allowed(self, tool: str, on: bool) -> None:
        if tool not in A.TOOLS:
            return
        self.cfg.action_permissions[tool] = bool(on)
        if tool == "focus" and not on:
            self.store.stop_focus()
        if callable(self.save_config):
            self.save_config()

    def say(self, key: str, **fmt) -> None:
        try:
            self._say(i18n.t(key).format(**fmt))
        except Exception:
            log.exception("action line failed")

    def _alive(self) -> bool:
        snap = self.snapshot()
        return getattr(snap, "stage", "egg") != "egg" and not getattr(snap, "dead", False)

    # --- chat
    def handle_text(self, text: str) -> bool:
        """True when the message was taken as a command (the caller then skips the ordinary chat request)."""
        if not self._alive():
            return False
        intent = A.parse_intent(text)
        if intent is not None:
            self.run(intent)
            return True
        if (A.looks_like_command(text) and any(self.allowed(t) for t in A.TOOLS)
                and getattr(self.language, "status", "") == "ready"
                and callable(getattr(self.language, "request_structured", None))):
            def handler(raw: str) -> bool:
                found = A.intent_from_json(raw)
                if found is None or not self.allowed(A.TOOL_OF[found.kind]):
                    return False      # not a command after all (or not permitted): she just answers
                self.run(found)
                return True
            self.language.request_structured(text, A.intent_messages(text), A.INTENT_SCHEMA, handler)
            return True
        return False

    def run(self, intent: A.Intent) -> str:
        """Execute one validated intent. Returns "ok", "denied", "full", "blocked" or "none"."""
        intent = A.valid(intent)
        if intent is None:
            return "none"
        tool = A.TOOL_OF[intent.kind]
        if not self.allowed(tool):
            self.say(f"action.denied.{tool}")
            return "denied"
        if intent.kind == "reminder":
            if self.store.add_reminder(intent.minutes, intent.text) is None:
                self.say("action.reminder.full")
                return "full"
            self.say("action.reminder.ok" if intent.text else "action.reminder.ok_plain", text=intent.text,
                     when=when_text(intent.minutes))   # she says the time back, so a misheard one is caught at once
        elif intent.kind == "focus":
            self.store.start_focus(intent.minutes)
            self.say("action.focus.start", when=when_text(intent.minutes))
        elif intent.kind == "focus_stop":
            if not self.store.stop_focus():
                self.say("action.focus.none")
                return "none"
            self.say("action.focus.stop")
        elif intent.kind == "note":
            try:
                ok = bool(self.memory.upsert_fact(note_key(intent.text), intent.text, 1.0, "note"))
            except Exception:
                log.exception("note failed")
                ok = False
            self.say("action.note.ok" if ok else "action.note.blocked")
            return "ok" if ok else "blocked"
        return "ok"

    @staticmethod
    def make_intent(kind: str, minutes: float, text: str) -> A.Intent:
        """For the menu: the UI never imports the services layer."""
        return A.Intent(kind, float(minutes), text)

    # --- clock
    def tick(self) -> None:
        for r in self.store.pop_due():
            line = i18n.t("action.reminder.due" if r.text else "action.reminder.due_plain").format(text=r.text)
            self._say(line)
            self.on_alert(line)
        if self.store.pop_focus_done():
            line = i18n.t("action.focus.done")
            self._say(line)
            self.on_alert(line)

    @property
    def quiet(self) -> bool:
        """During a focus session she keeps to herself: no spontaneous talk, no requests."""
        return self.store.focus_active


def when_text(minutes: float) -> str:
    """A duration as she says it back: "30 s", "20 min", "1 h 30"."""
    s = int(round(minutes * 60))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s / 60:g} min"
    return f"{s // 3600} h" + (f" {s % 3600 // 60:02d}" if s % 3600 >= 60 else "")


def note_key(text: str) -> str:
    return (i18n.t("action.note.key") + ": " + " ".join(text.lower().split())[:NOTE_KEY_CHARS]).strip()
