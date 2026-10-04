"""Controlador fuzzy Takagi-Sugeno de ordem zero (consequentes = níveis 0..3).

Entradas: CO2 (ppm), PM2.5 (ug/m3), VOC (ppb), presença. Saídas: nível do exaustor e do purificador.
"""
from __future__ import annotations

import numpy as np

from ..model.dynamics import sleep_caps
from .baselines import ReactivePolicy

_EPS = 1e-9
_INF = 1e9


def trap(x, a, b, c, d):
    left = np.clip((x - a) / (b - a + _EPS), 0, 1)
    right = np.clip((d - x) / (d - c + _EPS), 0, 1)
    return np.minimum(left, right)


class FuzzyController:
    def infer(self, co2, pm, voc, occ):
        co2, pm, voc = (np.asarray(v, dtype=float) for v in (co2, pm, voc))
        pres = (np.asarray(occ) > 0).astype(float)
        absn = 1.0 - pres
        c_lo, c_mid, c_hi = trap(co2, 0, 0, 700, 950), trap(co2, 700, 950, 1150, 1400), trap(co2, 1150, 1400, _INF, _INF)
        p_lo, p_mid, p_hi = trap(pm, 0, 0, 12, 20), trap(pm, 12, 20, 30, 50), trap(pm, 30, 50, _INF, _INF)
        v_mid, v_hi = trap(voc, 150, 300, 500, 800), trap(voc, 500, 800, _INF, _INF)
        mn = np.minimum
        exhaust = [(c_hi, 3), (mn(c_mid, pres), 2), (mn(c_mid, absn), 1), (c_lo, 0), (v_hi, 2), (mn(v_mid, pres), 1)]
        purifier = [(p_hi, 3), (mn(p_mid, pres), 2), (mn(p_mid, absn), 1), (p_lo, 0), (v_hi, 2), (mn(v_mid, pres), 1)]
        return self._defuzz(exhaust), self._defuzz(purifier)

    @staticmethod
    def _defuzz(rules):
        num = sum(w * y for w, y in rules)
        den = sum(w for w, _ in rules) + _EPS
        return np.clip(np.rint(num / den), 0, 3).astype(int)


class FuzzyPolicy(ReactivePolicy):
    name = "fuzzy"

    def __init__(self, noise_sleep_db: float = 35.0, min_hold: int = 2):
        self.ctrl = FuzzyController()
        self.ucap, self.fcap = sleep_caps(noise_sleep_db)
        self.min_hold = min_hold  # slots mínimos entre liga/desliga (0 = delega ao guarda)
        self.reset(1)

    def reset(self, n_rooms):
        self.on = np.zeros(n_rooms, dtype=bool)
        self.prev_u = np.zeros(n_rooms, dtype=int)
        self.last_change = np.full(n_rooms, -10**6)

    def decide(self, t, co2, pm, voc, occ, sleep):
        u, f = self.ctrl.infer(co2, pm, voc, occ)
        u = np.where(sleep, np.minimum(u, self.ucap), u)
        f = np.where(sleep, np.minimum(f, self.fcap), f)
        if self.min_hold > 0:
            blocked = ((u > 0) != self.on) & ((t - self.last_change) < self.min_hold)
            u = np.where(blocked, self.prev_u, u)
            now_on = u > 0
            self.last_change = np.where(now_on != self.on, t, self.last_change)
            self.on, self.prev_u = now_on, u
        return u, f
