import queue
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Event:
    kind: str
    data: dict = field(default_factory=dict)
    t: float = field(default_factory=time.time)


class EventBus:
    def __init__(self) -> None:
        self._q: queue.SimpleQueue[Event] = queue.SimpleQueue()

    def post(self, event: Event) -> None:
        self._q.put(event)

    def drain(self) -> list[Event]:
        out: list[Event] = []
        while True:
            try:
                out.append(self._q.get_nowait())
            except queue.Empty:
                return out
