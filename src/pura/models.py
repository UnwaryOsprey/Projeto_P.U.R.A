from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Reading:
    room: str
    ts: float
    co2: float | None = None
    pm25: float | None = None
    voc: float | None = None
    temp: float | None = None
    hum: float | None = None

    def to_dict(self):
        return asdict(self)


@dataclass
class Decision:
    room: str
    exhaust: int
    purifier: int
    mode: str = "normal"  # normal | emergency | safe
    reason: str = ""

    def to_dict(self):
        return asdict(self)
