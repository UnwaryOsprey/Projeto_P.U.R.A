from pura.adapters.local_bus import LocalBus
from pura.config import Settings
from pura.local_run import LocalSimulation, ensure_keys
from pura.service import PuraService


def test_ensure_keys_fills_only_missing():
    s = Settings(keys={"sala": "fixa"})
    ensure_keys(s)
    assert s.keys["sala"] == "fixa" and len(s.keys["quarto"]) == 32


def test_end_to_end_without_broker():
    """Sensor virtual -> servidor -> decisao -> comando assinado -> no virtual -> estado de volta."""
    s = Settings(cycle_s=10, min_run_s=30, stale_s=60)
    ensure_keys(s)
    bus = LocalBus()
    svc = PuraService(s, bus)
    sim = LocalSimulation(s, bus, speed=30, period=2)
    svc.start()
    sim.announce()
    try:
        for _ in range(6):
            sim.step(2.0)
            svc.tick()
        snap = svc.snapshot()
    finally:
        svc.stop()
    assert set(snap["rooms"]) == {"sala", "quarto"}
    for room in snap["rooms"].values():
        assert room["online"] and room["reading"] and room["decision"]
        assert room["actuator"] is not None and room["node_status"] == "online"
    assert not [e for e in snap["events"] if e["kind"] == "reading_rejected"]
