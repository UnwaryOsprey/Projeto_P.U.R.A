import json

import pytest

from pura.config import Settings
from pura.security import NonceCache, Rejected, sign_command, sign_sensor, verify_command, verify_sensor

S = Settings(keys={"sala": "k-sala", "quarto": "k-quarto"})
VALS = {"co2": 612.3, "pm25": 8.0, "voc": None, "temp": 24.1, "hum": 55.0}
NOW = 1_800_000_000.0


def test_valid_message_accepted_and_missing_sensor_is_none():
    r = verify_sensor(json.dumps(sign_sensor(S, "sala", VALS, NOW)), "sala", S, NonceCache(), NOW)
    assert r.co2 == 612.3 and r.voc is None and r.room == "sala"


def test_tampered_payload_rejected():
    p = sign_sensor(S, "sala", VALS, NOW)
    p["co2"] = 400.0  # atacante tenta esconder CO2 alto
    with pytest.raises(Rejected) as e:
        verify_sensor(json.dumps(p), "sala", S, NonceCache(), NOW)
    assert e.value.kind == "auth"


def test_wrong_key_and_cross_room_rejected():
    p = sign_sensor(S, "quarto", VALS, NOW)
    with pytest.raises(Rejected) as e:
        verify_sensor(json.dumps(p), "sala", S, NonceCache(), NOW)  # publicado no tópico errado
    assert e.value.kind == "auth"


def test_replay_rejected():
    raw, cache = json.dumps(sign_sensor(S, "sala", VALS, NOW)), NonceCache()
    verify_sensor(raw, "sala", S, cache, NOW)
    with pytest.raises(Rejected) as e:
        verify_sensor(raw, "sala", S, cache, NOW + 1)
    assert e.value.kind == "replay"


def test_stale_timestamp_rejected():
    raw = json.dumps(sign_sensor(S, "sala", VALS, NOW - 1000))
    with pytest.raises(Rejected) as e:
        verify_sensor(raw, "sala", S, NonceCache(), NOW)
    assert e.value.kind == "stale"


def test_implausible_value_rejected():
    raw = json.dumps(sign_sensor(S, "sala", {**VALS, "co2": 50000.0}, NOW))
    with pytest.raises(Rejected) as e:
        verify_sensor(raw, "sala", S, NonceCache(), NOW)
    assert e.value.kind == "implausible"


@pytest.mark.parametrize("raw", ["", "not json", "[]", "{}", '{"node":"esp32-sala"}'])
def test_malformed_rejected(raw):
    with pytest.raises(Rejected) as e:
        verify_sensor(raw, "sala", S, NonceCache(), NOW)
    assert e.value.kind == "malformed"


def test_command_roundtrip_and_tamper():
    raw = json.dumps(sign_command(S, "sala", 2, 1, NOW))
    assert verify_command(raw, "sala", S, NonceCache(), NOW) == (2, 1)
    p = json.loads(raw)
    p["exhaust"] = 0  # desliga a ventilação sem a chave
    with pytest.raises(Rejected):
        verify_command(json.dumps(p), "sala", S, NonceCache(), NOW)
    with pytest.raises(Rejected):  # comando de outro cômodo
        verify_command(raw, "quarto", S, NonceCache(), NOW)
