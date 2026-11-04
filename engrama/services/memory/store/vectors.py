from __future__ import annotations


import numpy as np

from engrama.services.memory import (
    VECTOR_RAM_MAX_MB)
from engrama.services.memory.store._util import (
    VECTOR_KINDS,
    _vtext, _vhash, _unit, _decay)


class VectorsMixin:
    # ---- vectors (M9) --------------------------------------------------
    def _vdel(self, where: str, params: tuple = ()) -> int:
        """Delete vector rows inside the caller's transaction (no commit here)."""
        n = self._db.execute(f"DELETE FROM vectors WHERE {where}", params).rowcount
        if n:
            self._vec_version += 1
        return max(n, 0)

    def _vdel_many(self, where: str, rows: list[tuple]) -> None:
        n = self._db.executemany(f"DELETE FROM vectors WHERE {where}", rows).rowcount
        if n:
            self._vec_version += 1

    def vector_model(self) -> str:
        return self.meta_get("vector_model") or ""

    def set_vector_model(self, model: str) -> bool:
        """Switch the embedding model. A different name deletes every vector (they live in another
        space); returns True if it did."""
        model = model or ""
        with self._lock:
            row = self._db.execute("SELECT v FROM meta WHERE k='vector_model'").fetchone()
            current = row[0] if row else ""
            if current == model:
                return False
            self._vdel("1=1")
            self._db.execute("INSERT OR REPLACE INTO meta(k, v) VALUES('vector_model', ?)", (model,))
            self._db.commit()
            self._vec_cache.clear()
            return True

    def drop_vectors(self) -> None:
        with self._lock:
            self._vdel("1=1")
            self._db.execute("DELETE FROM meta WHERE k='vector_model'")
            self._db.commit()
            self._vec_cache.clear()

    def _vector_texts(self) -> list[tuple[str, str, str]]:
        """(kind, ref, text) of everything that can have a vector, in indexing order.

        Called under the lock. Facts by confidence, topics by salience, ancestral, then episodes
        by importance and recency. The text is what is stored, digits removed; empty ones are out."""
        now = self._now()
        out: list[tuple[str, str, str]] = []
        for key, value in self._db.execute(
                "SELECT key, value FROM facts ORDER BY confidence DESC, t DESC, id DESC"):
            out.append(("fact", key, _vtext(f"{(key or '').replace('_', ' ')}: {value}")))
        trows = self._db.execute(
            "SELECT name, affinity, salience, t_salience FROM topics").fetchall()
        trows.sort(key=lambda r: (-_decay(r[2], r[3], now), -r[1], r[0]))
        out.extend(("topic", r[0], _vtext(r[0])) for r in trows)
        for eid, summary in self._db.execute(
                "SELECT id, summary FROM episodes WHERE kind='ancestral' ORDER BY id DESC"):
            out.append(("ancestral", str(eid), _vtext(summary)))
        for eid, summary, topic in self._db.execute(
                "SELECT id, summary, topic FROM episodes WHERE kind != 'ancestral'"
                " ORDER BY importance DESC, t DESC, id DESC"):
            out.append(("episode", str(eid), _vtext(f"{summary or ''} {topic or ''}")))
        return [x for x in out if x[2]]

    def unindexed(self, limit: int) -> list[tuple[str, str, str, str]]:
        """(kind, ref, text, hash) of memories with no vector of the current model, in indexing order."""
        with self._lock:
            model = self._meta_model()
            have = {(k, r): h for k, r, h in self._db.execute(
                "SELECT kind, ref, h FROM vectors WHERE model=?", (model,))}
            out = []
            for kind, ref, text in self._vector_texts():
                h = _vhash(text)
                if have.get((kind, ref)) == h:
                    continue
                out.append((kind, ref, text, h))
                if len(out) >= limit:
                    break
            return out

    def _meta_model(self) -> str:
        row = self._db.execute("SELECT v FROM meta WHERE k='vector_model'").fetchone()
        return row[0] if row else ""

    def put_vectors(self, model: str, items: list[tuple[str, str, str, np.ndarray]]) -> int:
        """Store vectors (float16). Each one is written only if, inside the lock, ``model`` is still
        the current model, the memory still exists and its text still has hash ``h``. Returns how
        many were written."""
        wrote = 0
        with self._lock:
            if not model or model != self._meta_model():
                return 0
            texts = {(k, r): _vhash(t) for k, r, t in self._vector_texts()}
            now = self._now()
            for kind, ref, h, vec in items:
                if kind not in VECTOR_KINDS or texts.get((kind, ref)) != h:
                    continue
                u = _unit(vec)
                if u is None:
                    continue
                self._db.execute(
                    "INSERT OR REPLACE INTO vectors(kind, ref, model, dim, h, vec, t)"
                    " VALUES(?,?,?,?,?,?,?)",
                    (kind, ref, model, int(u.size), h, u.astype(np.float16).tobytes(), now))
                wrote += 1
            if wrote:
                self._vec_version += 1
            self._db.commit()
        return wrote

    def _matrix(self, kind: str, dim: int, model: str) -> tuple[list[str], np.ndarray] | None:
        """Cached (refs, float32 [n, dim]) of unit vectors; rebuilt when the vectors change. Under lock."""
        key = (kind, dim)
        hit = self._vec_cache.get(key)
        if hit is not None and hit[0] == self._vec_version:
            return hit[1], hit[2]
        self._vec_cache.pop(key, None)
        rows = self._db.execute(
            "SELECT ref, vec FROM vectors WHERE kind=? AND model=? AND dim=? ORDER BY ref",
            (kind, model, dim)).fetchall()
        if not rows:
            return None
        refs = [r[0] for r in rows]
        mat = np.frombuffer(b"".join(r[1] for r in rows), dtype=np.float16).astype(np.float32)
        mat = mat.reshape(len(rows), dim)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        mat = mat / np.where(norms > 0, norms, 1.0)
        cap = VECTOR_RAM_MAX_MB * 1024 * 1024
        if mat.nbytes <= cap:
            while self._vec_cache and sum(v[2].nbytes for v in self._vec_cache.values()) + mat.nbytes > cap:
                self._vec_cache.pop(next(iter(self._vec_cache)))
            self._vec_cache[key] = (self._vec_version, refs, mat)
        return refs, mat

    def similar(self, qvec: np.ndarray, kind: str, k: int, min_sim: float) -> list[tuple[str, float]]:
        """(ref, cosine) best first, for vectors of the current model and the same dimension as qvec."""
        q = _unit(qvec)
        if q is None or kind not in VECTOR_KINDS or k <= 0:
            return []
        with self._lock:
            model = self._meta_model()
            if not model:
                return []
            built = self._matrix(kind, int(q.size), model)
            if built is None:
                return []
            refs, mat = built
            sims = mat @ q
        idx = np.flatnonzero(sims >= min_sim)
        if idx.size == 0:
            return []
        if idx.size > k:
            idx = idx[np.argpartition(-sims[idx], k - 1)[:k]]
        out = sorted(((refs[i], float(sims[i])) for i in idx), key=lambda x: (-x[1], x[0]))
        return out[:k]

    def release_vectors(self) -> None:
        with self._lock:
            self._vec_cache.clear()

    def vector_counts(self) -> dict:
        with self._lock:
            n = self._db.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
            items = sum(self._db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                        for t in ("episodes", "facts", "topics"))
        return {"vectors": n, "items": items}
