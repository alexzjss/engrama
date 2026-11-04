from __future__ import annotations



from engrama.services.perception import (
    ACTIVITY_EPISODE_EVERY_S, PERCEIVED_AFFINITY_CAP, PERCEIVED_AFFINITY_STEP)
from engrama.services.memory.topics import normalize_topic
from engrama.services.memory.store._util import (
    _decay)


class PerceptionMixin:
    # ---- perceived themes (M5) ----------------------------------------
    def bump_perceived(self, theme: str, now: float) -> str:
        """Nudge a theme seen on the user's screen. Returns the topic key, or "" if
        silenced/blocked. Never stores anything but the extracted theme."""
        key = normalize_topic(theme)
        if not key:
            return ""
        with self._lock:
            if self._blocked("perceived", key) or self._blocked("topic", key):
                return ""
            row = self._db.execute(
                "SELECT affinity, salience, t_salience FROM topics WHERE name=?", (key,)).fetchone()
            if row is None:
                self._db.execute(
                    "INSERT INTO topics(name, affinity, t, salience, t_salience, first_t,"
                    " last_t, mentions, source) VALUES(?,?,?,?,?,?,?,?,?)",
                    (key, min(PERCEIVED_AFFINITY_CAP, PERCEIVED_AFFINITY_STEP), now, 0.5, now,
                     now, now, 1, "percepcao"))
            else:
                aff, sal, t_sal = row
                if aff < PERCEIVED_AFFINITY_CAP:
                    aff = min(PERCEIVED_AFFINITY_CAP, aff + PERCEIVED_AFFINITY_STEP)
                self._db.execute(
                    "UPDATE topics SET affinity=?, t=?, salience=?, t_salience=?, last_t=?,"
                    " mentions=mentions+1 WHERE name=?",
                    (aff, now, _decay(sal, t_sal, now) + 0.05, now, now, key))
            mk = f"activity_ep:{key}"
            last = self._db.execute("SELECT v FROM meta WHERE k=?", (mk,)).fetchone()
            due = last is None or now - float(last[0]) >= ACTIVITY_EPISODE_EVERY_S
            if due:
                self._db.execute("INSERT OR REPLACE INTO meta(k, v) VALUES(?, ?)", (mk, repr(float(now))))
            self._db.commit()
        if due:
            self.add_episode("atividade", f"passou um tempo com {key}", 0.0, 0.2,
                             topic=key, topics=[key])
        return key

    def silence_theme(self, name: str) -> None:
        key = normalize_topic(name)
        if not key:
            return
        with self._lock:
            self._block("perceived", key, self._now())
            self._db.commit()

    def unsilence_theme(self, name: str) -> None:
        key = normalize_topic(name)
        with self._lock:
            self._db.execute("DELETE FROM blocklist WHERE kind='perceived' AND ref=?", (key,))
            self._db.commit()

    def silenced_themes(self) -> list[str]:
        with self._lock:
            rows = self._db.execute(
                "SELECT ref FROM blocklist WHERE kind='perceived' ORDER BY ref").fetchall()
        return [r[0] for r in rows]

    # ---- app categories (M5) ------------------------------------------
    def app_category(self, process: str) -> str | None:
        with self._lock:
            row = self._db.execute(
                "SELECT category FROM app_categories WHERE process=?",
                ((process or "").strip().lower(),)).fetchone()
        return row[0] if row else None

    def set_app_category(self, process: str, category: str, source: str) -> bool:
        """Store a category; an LLM answer never overrides a user correction."""
        p = (process or "").strip().lower()
        if not p or not category:
            return False
        with self._lock:
            row = self._db.execute(
                "SELECT source FROM app_categories WHERE process=?", (p,)).fetchone()
            if row and row[0] == "user" and source != "user":
                return False
            self._db.execute(
                "INSERT OR REPLACE INTO app_categories(process, category, source, t) VALUES(?,?,?,?)",
                (p, category, source, self._now()))
            self._db.commit()
        return True

    def app_category_rows(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT process, category, source, t FROM app_categories ORDER BY process").fetchall()
        return [dict(process=p, category=c, source=s, t=t) for p, c, s, t in rows]

    def clear_app_categories(self) -> None:
        with self._lock:
            self._db.execute("DELETE FROM app_categories")
            self._db.commit()
