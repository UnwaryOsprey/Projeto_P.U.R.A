"""Configuração por variáveis de ambiente PURA_* (ver .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class RoomSpec:
    name: str
    volume_m3: float
    bedroom: bool = False


@dataclass
class Settings:
    house: str = "casa1"
    rooms: list[RoomSpec] = field(
        default_factory=lambda: [RoomSpec("sala", 40.0), RoomSpec("quarto", 25.0, True)]
    )
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_user: str | None = None
    mqtt_password: str | None = None
    mqtt_ca: str | None = None
    keys: dict[str, str] = field(default_factory=dict)
    default_key: str = "dev-only-change-me"
    optimizer: str = "fuzzy"
    cycle_s: float = 900.0
    heartbeat_s: float = 60.0
    stale_s: float = 180.0
    max_skew_s: float = 120.0
    min_run_s: float = 600.0
    sleep_start_h: int = 22
    sleep_end_h: int = 7
    co2_ceiling: float = 1500.0
    co2_ref: float = 1000.0
    noise_sleep_db: float = 35.0
    k_inf: float = 0.12
    pm_ext_default: float = 15.0
    t_out_default: float = 20.0
    horizon_slots: int = 16
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_token: str | None = None

    def key_for(self, room: str) -> str:
        return self.keys.get(room, self.default_key)

    def node_id(self, room: str) -> str:
        return f"esp32-{room}"

    def room(self, name: str) -> RoomSpec | None:
        return next((r for r in self.rooms if r.name == name), None)

    def is_sleep(self, spec: RoomSpec, hour: int) -> bool:
        if not spec.bedroom:
            return False
        a, b = self.sleep_start_h, self.sleep_end_h
        return hour >= a or hour < b if a > b else a <= hour < b

    @classmethod
    def from_env(cls) -> Settings:
        g = lambda k, d=None: os.environ.get(f"PURA_{k}", d) or d  # noqa: E731
        rooms = []
        for item in g("ROOMS", "sala:40,quarto:25:bedroom").split(","):
            p = item.strip().split(":")
            rooms.append(RoomSpec(p[0], float(p[1]), "bedroom" in p[2:]))
        keys = dict(kv.split("=", 1) for kv in (g("KEYS", "") or "").split(",") if "=" in kv)
        s = cls(rooms=rooms, keys=keys)
        s.house = g("HOUSE", s.house)
        s.mqtt_host = g("MQTT_HOST", s.mqtt_host)
        s.mqtt_port = int(g("MQTT_PORT", s.mqtt_port))
        s.mqtt_user, s.mqtt_password, s.mqtt_ca = g("MQTT_USER"), g("MQTT_PASSWORD"), g("MQTT_CA")
        s.optimizer = g("OPTIMIZER", s.optimizer)
        for env, attr in (("CYCLE_S", "cycle_s"), ("HEARTBEAT_S", "heartbeat_s"), ("STALE_S", "stale_s"),
                          ("MIN_RUN_S", "min_run_s"), ("MAX_SKEW_S", "max_skew_s")):
            setattr(s, attr, float(g(env, getattr(s, attr))))
        s.api_port = int(g("API_PORT", s.api_port))
        s.api_token = g("API_TOKEN")
        return s
