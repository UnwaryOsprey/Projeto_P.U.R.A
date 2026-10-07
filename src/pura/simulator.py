"""ESP32 virtual: publica leituras assinadas e obedece comandos assinados.

    python -m pura.simulator            (modo MQTT; usa as mesmas variaveis PURA_* do servidor)

Roda a mesma física do otimizador, acelerada (PURA_SIM_SPEED, padrão 30x).
"""
from __future__ import annotations

import json
import logging
import os
import time

import numpy as np

from . import topics
from .config import Settings
from .envfile import load_dotenv
from .model.dynamics import CO2_EXT, EXHAUST_FLOW, PURIFIER_CADR, step
from .model.scenarios import make_scenario
from .security import NonceCache, Rejected, sign_sensor, verify_command

log = logging.getLogger("pura.sim")
FAILSAFE_S = 300.0


class VirtualNode:
    def __init__(self, settings: Settings, room: str, scenario, bus, speed=30.0, start_hour=8.0, seed=0):
        self.s, self.room, self.sc, self.bus, self.speed = settings, room, scenario, bus, speed
        self.i = scenario.rooms.index(room)
        self.co2, self.pm = 450.0, 10.0
        self.sim_s = start_hour * 3600.0
        self.exhaust, self.purifier = 1, 0
        self.last_cmd = time.time()
        self.nonces = NonceCache()
        self.rng = np.random.default_rng(seed)

    def on_cmd(self, topic: str, payload: str) -> None:
        try:
            self.exhaust, self.purifier = verify_command(payload, self.room, self.s, self.nonces)
            self.last_cmd = time.time()
            self._publish_state(False)
        except Rejected as e:
            log.warning("[%s] comando rejeitado (%s): %s", self.room, e.kind, e.detail)

    def advance(self, real_dt: float) -> None:
        if time.time() - self.last_cmd > FAILSAFE_S and (self.exhaust, self.purifier) != (1, 0):
            self.exhaust, self.purifier = 1, 0
            self._publish_state(True)
        sc, i = self.sc, self.i
        slot = int(self.sim_s / 3600 / sc.dt_h) % sc.n_slots
        dt_h = real_dt * self.speed / 3600
        ke = sc.k_inf[i] + EXHAUST_FLOW[self.exhaust] / sc.volumes[i]
        kf = PURIFIER_CADR[self.purifier] / sc.volumes[i]
        self.co2 = float(step(self.co2, sc.co2_gen[i, slot], ke, 0.0, CO2_EXT, dt_h))
        self.pm = float(step(self.pm, sc.pm_gen[i, slot], ke, kf, sc.pm_ext[slot], dt_h))
        self.sim_s += real_dt * self.speed

    def publish(self) -> None:
        vals = {"co2": self.co2 + self.rng.normal(0, 5), "pm25": max(0.0, self.pm + self.rng.normal(0, 1)),
                "voc": 120.0, "temp": 24.0, "hum": 55.0}
        self.bus.publish(topics.sensor(self.s.house, self.room), json.dumps(sign_sensor(self.s, self.room, vals, time.time())))

    def _publish_state(self, failsafe: bool) -> None:
        self.bus.publish(topics.state(self.s.house, self.room),
                         json.dumps({"exhaust": self.exhaust, "purifier": self.purifier, "failsafe": failsafe}))


def main() -> None:
    from .adapters.mqtt_bus import MqttBus  # so o modo MQTT precisa do paho-mqtt

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = Settings.from_env()
    speed = float(os.environ.get("PURA_SIM_SPEED", 30))
    period = float(os.environ.get("PURA_SIM_PERIOD_S", 2))
    sc = make_scenario(int(os.environ.get("PURA_SIM_SEED", 0)),
                       rooms=[(r.name, r.volume_m3, r.bedroom) for r in s.rooms])
    nodes = []
    for spec in s.rooms:
        node_id = s.node_id(spec.name)
        user = node_id if s.mqtt_user else None
        bus = MqttBus(s, client_id=node_id, username=user, password=os.environ.get("PURA_SIM_PASSWORD"),
                      will=(topics.status(s.house, spec.name), "offline"))
        node = VirtualNode(s, spec.name, sc, bus, speed)
        bus.subscribe(topics.cmd(s.house, spec.name), node.on_cmd)
        bus.start()
        bus.publish(topics.status(s.house, spec.name), "online", retain=True)
        nodes.append(node)
    log.info("simulador ativo: %d nós, velocidade %.0fx", len(nodes), speed)
    while True:
        time.sleep(period)
        for n in nodes:
            n.advance(period)
            n.publish()


if __name__ == "__main__":
    main()
