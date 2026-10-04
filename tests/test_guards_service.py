import json

from pura import topics
from pura.adapters.local_bus import LocalBus
from pura.config import RoomSpec, Settings
from pura.guards import GuardContext, build_chain
from pura.model.dynamics import sleep_caps
from pura.models import Decision, Reading
from pura.security import NonceCache, sign_sensor, verify_command
from pura.service import PuraService

S = Settings(keys={"sala": "k1", "quarto": "k2"}, cycle_s=10, min_run_s=30, stale_s=60)
T0 = 1_800_000_000.0


def run_chain(decision, co2, stale=False, sleeping=False, prev=None, now=T0, last_change=0.0):
    r = None if co2 is None else Reading("sala", now, co2=co2)
    ctx = GuardContext(S, RoomSpec("sala", 40), decision, r, stale, sleeping, now, prev, last_change)
    return build_chain().handle(ctx).decision


def test_no_data_goes_to_safe_mode_never_off():
    d = run_chain(Decision("sala", 0, 0), None, stale=True)
    assert d.mode == "safe" and d.exhaust >= 1


def test_ceiling_forces_exhaust_even_when_sleeping():
    d = run_chain(Decision("sala", 0, 0), 1800.0, sleeping=True)
    assert d.mode == "emergency" and d.exhaust >= 2


def test_sleeping_caps_noise():
    d = run_chain(Decision("sala", 3, 3), 900.0, sleeping=True)
    assert (d.exhaust, d.purifier) == sleep_caps(S.noise_sleep_db)


def test_min_runtime_blocks_flip_flop_but_not_emergency():
    prev = Decision("sala", 2, 0)
    d = run_chain(Decision("sala", 0, 0), 900.0, prev=prev, now=T0, last_change=T0 - 5)
    assert d.exhaust == 2  # ainda dentro do tempo mínimo
    d = run_chain(Decision("sala", 0, 0), 1700.0, prev=Decision("sala", 0, 0), now=T0, last_change=T0 - 5)
    assert d.exhaust >= 2


def make_service(optimizer="fuzzy"):
    S.optimizer = optimizer
    clock = {"t": T0}
    bus = LocalBus()
    svc = PuraService(S, bus, clock=lambda: clock["t"])
    svc.start = lambda: bus.subscribe("pura/casa1/+/sensor", svc.on_message)  # sem thread
    svc.start()
    return svc, bus, clock


def send(bus, clock, room="sala", co2=1200.0, **kw):
    p = sign_sensor(S, room, {"co2": co2, "pm25": 10.0, "voc": 100.0, "temp": 24.0, "hum": 50.0, **kw}, clock["t"])
    bus.publish(topics.sensor(S.house, room), json.dumps(p))


def last_cmd(bus, room="sala"):
    cmds = [json.loads(p) for t, p in bus.sent if t == topics.cmd(S.house, room)]
    return cmds[-1] if cmds else None


def test_end_to_end_high_co2_yields_signed_command():
    svc, bus, clock = make_service()
    send(bus, clock, co2=1200.0)
    svc.tick()
    cmd = last_cmd(bus)
    assert cmd and cmd["exhaust"] >= 1
    assert verify_command(json.dumps(cmd), "sala", S, NonceCache(), clock["t"])[0] == cmd["exhaust"]


def test_forged_reading_is_dropped_and_event_emitted():
    svc, bus, clock = make_service()
    p = sign_sensor(S, "sala", {"co2": 400.0}, clock["t"])
    p["co2"] = 300.0
    bus.publish(topics.sensor(S.house, "sala"), json.dumps(p))
    assert svc.rooms["sala"].reading is None
    assert svc.events.recent[-1].kind == "reading_rejected"


def test_sensor_silence_triggers_safe_mode_command():
    svc, bus, clock = make_service()
    send(bus, clock, co2=700.0)
    svc.tick()
    clock["t"] += S.stale_s + 5
    svc.tick()
    cmd = last_cmd(bus)
    assert cmd["exhaust"] >= 1
    assert any(e.kind == "safe_mode" for e in svc.events.recent)


def test_heartbeat_republishes_command():
    svc, bus, clock = make_service()
    send(bus, clock, co2=700.0)
    svc.tick()
    n = len([1 for t, _ in bus.sent if t == topics.cmd(S.house, "sala")])
    clock["t"] += S.heartbeat_s + 1
    send(bus, clock, co2=700.0)
    svc.tick()
    assert len([1 for t, _ in bus.sent if t == topics.cmd(S.house, "sala")]) > n


def test_mpc_strategy_returns_valid_levels():
    svc, bus, clock = make_service("ga")
    send(bus, clock, room="quarto", co2=1300.0)
    svc.tick()
    cmd = last_cmd(bus, "quarto")
    assert cmd and 0 <= cmd["exhaust"] <= 3 and 0 <= cmd["purifier"] <= 3


def test_unknown_optimizer_rejected():
    svc, _, _ = make_service()
    import pytest
    with pytest.raises(ValueError):
        svc.set_optimizer("quantum")
