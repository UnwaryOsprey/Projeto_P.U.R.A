"""Orquestrador: mensagem MQTT -> pipeline -> decisão (Strategy) -> guardas -> comando assinado."""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field

import numpy as np

from . import topics
from .config import RoomSpec, Settings
from .events import Event, EventBus
from .guards import GuardContext, build_chain
from .model.dynamics import CO2_EXT, EXHAUST_FLOW, PURIFIER_CADR, Scenario
from .model.objective import Problem
from .models import Decision, Reading
from .optimizers import OPTIMIZERS, make
from .optimizers.registry import REACTIVE
from .pipeline import Calibrator, Predictor, estimate_occupancy
from .security import NonceCache, Rejected, sign_command, verify_sensor

log = logging.getLogger("pura.service")
MAX_CO2_JUMP = 2000.0  # ppm entre leituras consecutivas


@dataclass
class RoomRuntime:
    spec: RoomSpec
    policy: object | None = None
    predictor: Predictor = field(default_factory=Predictor)
    reading: Reading | None = None
    received_at: float = 0.0
    decision: Decision | None = None
    last_decision_ts: float | None = None
    last_change_ts: float = 0.0
    last_publish_ts: float = 0.0
    was_stale: bool = True
    actuator: dict | None = None
    node_status: str = "unknown"
    over_ref: bool = False
    over_ceiling: bool = False


class PuraService:
    def __init__(self, settings: Settings, bus, clock=time.time):
        self.s, self.bus, self.clock = settings, bus, clock
        self.events = EventBus()
        self.nonces = NonceCache()
        self.calibrator = Calibrator()
        self.chain = build_chain()
        self.started = clock()
        self.rooms = {r.name: RoomRuntime(r) for r in settings.rooms}
        self.optimizer_name = settings.optimizer
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._build_strategy(settings.optimizer)

    # ---- estratégia ----
    def _build_strategy(self, name: str) -> None:
        if name not in OPTIMIZERS:
            raise ValueError(f"otimizador inválido: {name} (opções: {', '.join(OPTIMIZERS)})")
        self.optimizer_name = name
        self.mpc = None if name in REACTIVE else make(name, fast=True)
        for rt in self.rooms.values():
            rt.policy = make(name, min_hold=0) if name == "fuzzy" else (make(name) if self.mpc is None else None)
            rt.last_decision_ts = None

    def set_optimizer(self, name: str) -> None:
        with self._lock:
            self._build_strategy(name)
        self.events.publish(Event("optimizer_changed", data={"optimizer": name}, ts=self.clock()))

    # ---- ciclo de vida ----
    def start(self) -> None:
        h = self.s.house
        self.bus.subscribe(f"pura/{h}/+/sensor", self.on_message)
        self.bus.subscribe(f"pura/{h}/+/atuador/state", self.on_message)
        self.bus.subscribe(f"pura/{h}/+/status", self.on_message)
        self.bus.start()
        threading.Thread(target=self._loop, daemon=True, name="pura-loop").start()

    def stop(self) -> None:
        self._stop.set()
        self.bus.stop()

    def _loop(self) -> None:
        while not self._stop.wait(1.0):
            try:
                self.tick()
            except Exception:
                log.exception("erro no tick")

    # ---- entrada ----
    def on_message(self, topic: str, payload: str) -> None:
        parts = topic.split("/")
        room = parts[2] if len(parts) > 3 else None
        if room not in self.rooms:
            return
        with self._lock:
            kind = parts[3]
            if kind == "sensor":
                self._on_sensor(room, payload)
            elif kind == "atuador":
                try:
                    self.rooms[room].actuator = json.loads(payload)
                except ValueError:
                    pass
            elif kind == "status":
                self.rooms[room].node_status = payload.strip()

    def _on_sensor(self, room: str, payload: str) -> None:
        rt, now = self.rooms[room], self.clock()
        try:
            r = verify_sensor(payload, room, self.s, self.nonces, now)
            r = self.calibrator.apply(r)
            if rt.reading and rt.reading.co2 and r.co2 and abs(r.co2 - rt.reading.co2) > MAX_CO2_JUMP:
                raise Rejected("implausible", "salto de CO2 incompatível com a física do ambiente")
        except Rejected as e:
            log.warning("[%s] leitura rejeitada (%s): %s", room, e.kind, e.detail)
            self.events.publish(Event("reading_rejected", room, {"kind": e.kind, "detail": e.detail}, now))
            return
        rt.reading, rt.received_at = r, now
        rt.predictor.update(r)
        self.events.publish(Event("reading_accepted", room, r.to_dict(), now))
        for attr, val, thr, label in (("over_ref", r.co2, self.s.co2_ref, "co2_ref"),
                                      ("over_ceiling", r.co2, self.s.co2_ceiling, "co2_ceiling")):
            over = val is not None and val > thr
            if over and not getattr(rt, attr):
                self.events.publish(Event("limit_exceeded", room, {"limit": label, "value": val}, now))
            setattr(rt, attr, over)

    # ---- decisão ----
    def tick(self, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        with self._lock:
            for rt in self.rooms.values():
                self._tick_room(rt, now)

    def _tick_room(self, rt: RoomRuntime, now: float) -> None:
        name = rt.spec.name
        stale = rt.reading is None or (now - rt.received_at) > self.s.stale_s
        if stale and rt.reading is None and (now - self.started) < self.s.stale_s:
            return  # carência após a partida
        if stale != rt.was_stale:
            kind = "sensor_offline" if stale else "sensor_online"
            self.events.publish(Event(kind, name, {}, now))
        emergency = bool(rt.reading and rt.reading.co2 and rt.reading.co2 > self.s.co2_ceiling and not stale)
        due = (rt.last_decision_ts is None or now - rt.last_decision_ts >= self.s.cycle_s
               or stale != rt.was_stale or emergency)
        rt.was_stale = stale
        if due:
            self._decide(rt, now, stale)
        if rt.decision and (due or now - rt.last_publish_ts >= self.s.heartbeat_s):
            payload = sign_command(self.s, name, rt.decision.exhaust, rt.decision.purifier, now)
            self.bus.publish(topics.cmd(self.s.house, name), json.dumps(payload), qos=1)
            rt.last_publish_ts = now

    def _decide(self, rt: RoomRuntime, now: float, stale: bool) -> None:
        r, spec = rt.reading, rt.spec
        sleeping = self.s.is_sleep(spec, time.localtime(now).tm_hour)
        d = Decision(spec.name, 0, 0, "normal", self.optimizer_name)
        if not stale and r and r.co2 is not None:
            fc = rt.predictor.forecast(900)
            co2 = max(r.co2, fc["co2"] or 0.0)
            pm = max(r.pm25 or 0.0, fc["pm25"] or 0.0)
            occ = estimate_occupancy(r.co2, rt.predictor.slope_per_h("co2"))
            if self.mpc is not None:
                d.exhaust, d.purifier = self._mpc(rt, r, occ, sleeping, now)
            else:
                u, f = rt.policy.decide(int(now // max(self.s.cycle_s, 1)), np.array([co2]), np.array([pm]),
                                        np.array([r.voc or 0.0]), np.array([occ]), np.array([sleeping]))
                d.exhaust, d.purifier = int(u[0]), int(f[0])
        ctx = GuardContext(self.s, spec, d, r, stale, sleeping, now, rt.decision, rt.last_change_ts)
        final = self.chain.handle(ctx).decision
        prev = rt.decision
        if prev is None or (final.exhaust > 0) != (prev.exhaust > 0) or (final.purifier > 0) != (prev.purifier > 0):
            rt.last_change_ts = now
        if final.mode == "safe" and (prev is None or prev.mode != "safe"):
            self.events.publish(Event("safe_mode", spec.name, {"reason": final.reason}, now))
        rt.decision, rt.last_decision_ts = final, now
        self.events.publish(Event("decision", spec.name, final.to_dict(), now))

    def _mpc(self, rt: RoomRuntime, r: Reading, occ: int, sleeping: bool, now: float) -> tuple[int, int]:
        """Horizonte deslizante: otimiza H slots à frente e aplica só o primeiro."""
        V, s = rt.spec.volume_m3, self.s
        prev = rt.decision or Decision(rt.spec.name, 0, 0)
        ke = s.k_inf + EXHAUST_FLOW[prev.exhaust] / V
        kf = PURIFIER_CADR[prev.purifier] / V
        g_co2 = max(0.0, rt.predictor.slope_per_h("co2") + ke * (r.co2 - CO2_EXT))
        pm_now = r.pm25 if r.pm25 is not None else 10.0
        g_pm = max(0.0, rt.predictor.slope_per_h("pm25") - ke * s.pm_ext_default + (ke + kf) * pm_now)
        H = s.horizon_slots
        sc = Scenario([rt.spec.name], np.array([V]), np.array([s.k_inf]), np.full((1, H), float(occ)),
                      np.full((1, H), sleeping), np.full((1, H), g_co2), np.full((1, H), g_pm),
                      np.full(H, s.pm_ext_default), np.full(H, s.t_out_default))
        problem = Problem(sc, np.array([r.co2]), np.array([pm_now]))
        plan = self.mpc.optimize(problem, seed=int(now)).plan
        return int(plan[0, 0, 0]), int(plan[0, 0, 1])

    # ---- leitura ----
    def snapshot(self) -> dict:
        now = self.clock()
        with self._lock:
            rooms = {}
            for name, rt in self.rooms.items():
                age = now - rt.received_at if rt.reading else None
                fc = rt.predictor.forecast(900) if rt.reading else None
                rooms[name] = {
                    "bedroom": rt.spec.bedroom,
                    "online": rt.reading is not None and not rt.was_stale,
                    "node_status": rt.node_status,
                    "age_s": age,
                    "reading": rt.reading.to_dict() if rt.reading else None,
                    "forecast_15min": fc,
                    "decision": rt.decision.to_dict() if rt.decision else None,
                    "actuator": rt.actuator,
                }
            return {"ts": now, "optimizer": self.optimizer_name, "optimizers": list(OPTIMIZERS),
                    "rooms": rooms, "events": [e.to_dict() for e in list(self.events.recent)[-40:]]}
