"""Esquema de tópicos MQTT (ver docs/protocolo.md)."""
from __future__ import annotations


def sensor(house, room): return f"pura/{house}/{room}/sensor"
def cmd(house, room): return f"pura/{house}/{room}/atuador/cmd"
def state(house, room): return f"pura/{house}/{room}/atuador/state"
def status(house, room): return f"pura/{house}/{room}/status"


def topic_matches(filt: str, topic: str) -> bool:
    f, t = filt.split("/"), topic.split("/")
    for i, part in enumerate(f):
        if part == "#":
            return True
        if i >= len(t) or (part != "+" and part != t[i]):
            return False
    return len(f) == len(t)
