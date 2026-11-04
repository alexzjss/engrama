from __future__ import annotations

from collections import deque


class WorkingMemory:
    def __init__(self, maxlen: int = 12) -> None:
        self._msgs: deque[dict] = deque(maxlen=maxlen)

    def add(self, role: str, content: str) -> None:
        self._msgs.append({"role": role, "content": content})

    def messages(self) -> list[dict]:
        return list(self._msgs)

    def clear(self) -> None:
        self._msgs.clear()
