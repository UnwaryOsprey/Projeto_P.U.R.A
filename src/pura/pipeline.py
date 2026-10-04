"""Etapas do pipeline: calibração -> previsão (Holt) -> estimativa de ocupação."""
from __future__ import annotations

from dataclasses import replace

from .models import Reading


class Calibrator:
    """Ganho/offset por sensor. Ex.: {"co2": (1.0, -20.0)} corrige 20 ppm de offset."""

    def __init__(self, table: dict[str, tuple[float, float]] | None = None):
        self.table = table or {}

    def apply(self, r: Reading) -> Reading:
        changes = {}
        for k, (gain, off) in self.table.items():
            v = getattr(r, k)
            if v is not None:
                changes[k] = v * gain + off
        return replace(r, **changes) if changes else r


class Holt:
    """Suavização exponencial dupla (nível + tendência) para amostragem irregular."""

    def __init__(self, alpha=0.5, beta=0.3):
        self.alpha, self.beta = alpha, beta
        self.level: float | None = None
        self.trend = 0.0  # unidade/s
        self.last_ts: float | None = None

    def update(self, x: float, ts: float) -> None:
        if self.level is None:
            self.level, self.last_ts = x, ts
            return
        dt = ts - self.last_ts
        if dt <= 0:
            return
        prev = self.level
        self.level = self.alpha * x + (1 - self.alpha) * (self.level + self.trend * dt)
        self.trend = self.beta * (self.level - prev) / dt + (1 - self.beta) * self.trend
        self.last_ts = ts

    def forecast(self, horizon_s: float) -> float | None:
        return None if self.level is None else max(0.0, self.level + self.trend * horizon_s)


class Predictor:
    VARS = ("co2", "pm25")

    def __init__(self):
        self.models = {v: Holt() for v in self.VARS}

    def update(self, r: Reading) -> None:
        for v in self.VARS:
            x = getattr(r, v)
            if x is not None:
                self.models[v].update(x, r.ts)

    def forecast(self, horizon_s: float) -> dict[str, float | None]:
        return {v: self.models[v].forecast(horizon_s) for v in self.VARS}

    def slope_per_h(self, var: str) -> float:
        return self.models[var].trend * 3600


def estimate_occupancy(co2: float, slope_ppm_h: float) -> int:
    """Sem sensor de presença: CO2 acima do exterior (ou subindo) indica gente no cômodo."""
    return 1 if co2 >= 650 or slope_ppm_h > 100 else 0
