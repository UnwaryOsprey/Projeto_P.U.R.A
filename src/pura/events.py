"""Observer: barramento de eventos interno."""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import asdict, dataclass, field

log = logging.getLogger("pura.events")


@dataclass(frozen=True)
class Event:
    kind: str  # reading_accepted | reading_rejected | sensor_offline | sensor_online | limit_exceeded | decision | safe_mode | optimizer_changed
    room: str | None = None
    data: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self):
        return asdict(self)


class EventBus:
    def __init__(self, keep: int = 100):
        self._subs: list = []
        self.recent: deque = deque(maxlen=keep)

    def subscribe(self, handler, kinds: set[str] | None = None) -> None:
        self._subs.append((handler, kinds))

    def publish(self, event: Event) -> None:
        self.recent.append(event)
        for handler, kinds in self._subs:
            if kinds is None or event.kind in kinds:
                try:
                    handler(event)
                except Exception:  # um observador com erro não derruba o pipeline
                    log.exception("observer falhou")
