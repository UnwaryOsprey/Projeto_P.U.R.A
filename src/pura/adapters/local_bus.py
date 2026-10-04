"""Barramento em memória (testes e execução sem broker)."""
from __future__ import annotations

from ..topics import topic_matches


class LocalBus:
    def __init__(self):
        self.subs: list = []
        self.sent: list[tuple[str, str]] = []

    def subscribe(self, topic_filter, callback):
        self.subs.append((topic_filter, callback))

    def publish(self, topic, payload, qos=1, retain=False):
        self.sent.append((topic, payload))
        for filt, cb in list(self.subs):
            if topic_matches(filt, topic):
                cb(topic, payload)

    def start(self): ...
    def stop(self): ...
