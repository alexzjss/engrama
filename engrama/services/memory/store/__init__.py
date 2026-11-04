from __future__ import annotations

from engrama.services.memory.store._util import (  # noqa: F401  (re-exported)
    COMPACT_IMPORTANCE, DAY, FORGET_AGE, FORGET_BELOW, RECENCY_TAU, VECTOR_KINDS,
    _clamp, _compact_summary, _decay, _lang_of, _sem, _term_regex, _unit, _vhash, _vtext)
from engrama.services.memory.store.base import (  # noqa: F401  (re-exported)
    BaseMixin, _BASE_SCHEMA, _V2_STATEMENTS, _V3_STATEMENTS)
from engrama.services.memory.store.blocking import BlockingMixin
from engrama.services.memory.store.episodes import EpisodesMixin
from engrama.services.memory.store.generations import GenerationsMixin
from engrama.services.memory.store.opinions import OpinionsMixin
from engrama.services.memory.store.perception import PerceptionMixin
from engrama.services.memory.store.vectors import VectorsMixin
from engrama.services.memory.store.working import WorkingMemory  # noqa: F401  (re-exported)


class MemoryStore(BaseMixin, EpisodesMixin, PerceptionMixin, OpinionsMixin, VectorsMixin,
                  BlockingMixin, GenerationsMixin):
    """SQLite-backed episodic and semantic memory (schema v3).

    The connection is shared across threads (``check_same_thread=False``);
    every operation runs under ``self._lock`` so callers may use the store
    from several threads at once.
    """

    schema_version = 3
