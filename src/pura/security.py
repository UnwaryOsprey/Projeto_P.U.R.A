"""Autenticação/integridade das mensagens (HMAC-SHA256 + timestamp + nonce).

Assinatura da leitura:  node|ts|nonce|co2|pm25|voc|temp|hum   (floats com %.1f)
Assinatura do comando:  cmd|room|ts|nonce|exhaust|purifier
Valor -1.0 em um sensor significa "sensor ausente".
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time

from .config import Settings
from .models import Reading

FIELDS = ("co2", "pm25", "voc", "temp", "hum")
RANGES = {"co2": (250, 10000), "pm25": (0, 1000), "voc": (0, 60000), "temp": (-20, 60), "hum": (0, 100)}


class Rejected(Exception):
    """Mensagem descartada. kind: malformed | auth | stale | replay | implausible."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}")
        self.kind, self.detail = kind, detail


def hmac_hex(key: str, msg: str) -> str:
    return hmac.new(key.encode(), msg.encode(), hashlib.sha256).hexdigest()


class NonceCache:
    def __init__(self, ttl_s: float = 300.0, maxsize: int = 4096):
        self.ttl_s, self.maxsize, self._seen = ttl_s, maxsize, {}

    def check_and_add(self, nonce: str, now: float) -> bool:
        if len(self._seen) >= self.maxsize:
            self._seen = {n: t for n, t in self._seen.items() if now - t < self.ttl_s}
            if len(self._seen) >= self.maxsize:
                self._seen.clear()
        t = self._seen.get(nonce)
        if t is not None and now - t < self.ttl_s:
            return False
        self._seen[nonce] = now
        return True


def sensor_signing_string(p: dict) -> str:
    vals = [f"{float(p[k]):.1f}" for k in FIELDS]
    return "|".join([str(p["node"]), str(int(p["ts"])), str(p["nonce"]), *vals])


def sign_sensor(settings: Settings, room: str, values: dict, now: float, nonce: str | None = None) -> dict:
    p = {"v": 1, "node": settings.node_id(room), "ts": int(now), "nonce": nonce or secrets.token_hex(8)}
    for k in FIELDS:
        v = values.get(k)
        p[k] = -1.0 if v is None else round(float(v), 1)
    p["sig"] = hmac_hex(settings.key_for(room), sensor_signing_string(p))
    return p


def verify_sensor(raw, room: str, settings: Settings, nonces: NonceCache, now: float | None = None) -> Reading:
    now = time.time() if now is None else now
    try:
        p = json.loads(raw)
        if not isinstance(p, dict):
            raise ValueError
        missing = [k for k in ("node", "ts", "nonce", "sig", *FIELDS) if k not in p]
        if missing:
            raise ValueError(missing)
        expected = hmac_hex(settings.key_for(room), sensor_signing_string(p))
        ts = float(p["ts"])
    except (ValueError, TypeError, KeyError) as e:
        raise Rejected("malformed", str(e)) from e
    if p["node"] != settings.node_id(room):
        raise Rejected("auth", "node não corresponde ao tópico")
    if not hmac.compare_digest(expected, str(p["sig"])):
        raise Rejected("auth", "assinatura inválida")
    if abs(now - ts) > settings.max_skew_s:
        raise Rejected("stale", f"timestamp fora da janela ({now - ts:.0f}s)")
    if not nonces.check_and_add(str(p["nonce"]), now):
        raise Rejected("replay", "nonce repetido")
    values = {}
    for k in FIELDS:
        v = float(p[k])
        if v == -1.0:
            values[k] = None
            continue
        lo, hi = RANGES[k]
        if not (lo <= v <= hi):
            raise Rejected("implausible", f"{k}={v}")
        values[k] = v
    return Reading(room=room, ts=ts, **values)


def command_signing_string(room, ts, nonce, exhaust, purifier) -> str:
    return f"cmd|{room}|{int(ts)}|{nonce}|{int(exhaust)}|{int(purifier)}"


def sign_command(settings: Settings, room: str, exhaust: int, purifier: int, now: float,
                 nonce: str | None = None) -> dict:
    nonce = nonce or secrets.token_hex(8)
    sig = hmac_hex(settings.key_for(room), command_signing_string(room, now, nonce, exhaust, purifier))
    return {"v": 1, "ts": int(now), "nonce": nonce, "exhaust": int(exhaust), "purifier": int(purifier), "sig": sig}


def verify_command(raw, room: str, settings: Settings, nonces: NonceCache, now: float | None = None):
    now = time.time() if now is None else now
    try:
        p = json.loads(raw)
        ex, pu, ts = int(p["exhaust"]), int(p["purifier"]), float(p["ts"])
        expected = hmac_hex(settings.key_for(room), command_signing_string(room, ts, p["nonce"], ex, pu))
        sig = str(p["sig"])
    except (ValueError, TypeError, KeyError) as e:
        raise Rejected("malformed", str(e)) from e
    if not (0 <= ex <= 3 and 0 <= pu <= 3):
        raise Rejected("malformed", "nível fora de 0..3")
    if not hmac.compare_digest(expected, sig):
        raise Rejected("auth", "assinatura inválida")
    if abs(now - ts) > settings.max_skew_s:
        raise Rejected("stale", "timestamp fora da janela")
    if not nonces.check_and_add(str(p["nonce"]), now):
        raise Rejected("replay", "nonce repetido")
    return ex, pu
