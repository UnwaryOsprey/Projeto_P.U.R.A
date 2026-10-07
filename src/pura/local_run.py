"""Execução local: ESP32 virtuais no mesmo processo do servidor, ligados por LocalBus.

Não precisa de broker MQTT nem de Docker. A lógica é a mesma do modo MQTT:
as leituras e os comandos continuam assinados (HMAC) e passam por todas as guardas.
"""
from __future__ import annotations

import logging
import secrets
import threading
import time

from . import topics
from .config import Settings
from .model.scenarios import make_scenario
from .simulator import VirtualNode

log = logging.getLogger("pura.local")


def ensure_keys(settings: Settings) -> None:
    """Cômodo sem chave no .env ganha uma chave aleatória (vale só nesta execução)."""
    for room in settings.rooms:
        if room.name not in settings.keys:
            settings.keys[room.name] = secrets.token_hex(16)


class LocalSimulation:
    def __init__(self, settings: Settings, bus, speed: float = 30.0, period: float = 2.0, seed: int = 0):
        self.s, self.bus, self.period = settings, bus, period
        scenario = make_scenario(seed, rooms=[(r.name, r.volume_m3, r.bedroom) for r in settings.rooms])
        self.nodes: list[VirtualNode] = []
        for spec in settings.rooms:
            node = VirtualNode(settings, spec.name, scenario, bus, speed)
            bus.subscribe(topics.cmd(settings.house, spec.name), node.on_cmd)
            self.nodes.append(node)
        self._stop = threading.Event()

    def announce(self) -> None:
        for n in self.nodes:
            self.bus.publish(topics.status(self.s.house, n.room), "online", retain=True)

    def step(self, dt: float | None = None) -> None:
        """Avança todos os nós `dt` s (tempo real) e publica uma leitura de cada um."""
        dt = self.period if dt is None else dt
        for n in self.nodes:
            try:
                n.advance(dt)
                n.publish()
            except Exception:
                log.exception("erro no no virtual %s", n.room)

    def start(self) -> None:
        self.announce()
        threading.Thread(target=self._loop, daemon=True, name="pura-sim").start()
        log.info("simulador local ativo: %d nos virtuais, velocidade %.0fx", len(self.nodes), self.nodes[0].speed)

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        last = time.time()
        while not self._stop.wait(self.period):
            now = time.time()
            self.step(now - last)
            last = now
