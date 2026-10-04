"""Dinâmica física do ambiente (balanço de massa com solução exata por slot).

    dC/dt = G + ke*C_ext - (ke + kf)*C     ->   C(t+dt) = Ceq + (C - Ceq) * exp(-(ke+kf)*dt)

ke = k_inf + vazão_exaustor/V   (troca com o exterior, 1/h)
kf = CADR_purificador/V         (remoção de partículas, só PM2.5, 1/h)
Níveis de atuação: 0 (off), 1, 2, 3.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EXHAUST_FLOW = np.array([0.0, 40.0, 80.0, 140.0])  # m3/h
PURIFIER_CADR = np.array([0.0, 60.0, 120.0, 200.0])  # m3/h
EXHAUST_W = np.array([0.0, 8.0, 18.0, 35.0])
PURIFIER_W = np.array([0.0, 5.0, 12.0, 25.0])
EXHAUST_DB = np.array([0.0, 30.0, 36.0, 42.0])
PURIFIER_DB = np.array([0.0, 26.0, 32.0, 39.0])
BACKGROUND_DB = 25.0
AIR_RHO_CP = 0.34  # Wh/(m3.K)
CO2_EXT = 420.0  # ppm
CO2_PER_PERSON_M3H = 0.018  # m3/h de CO2 exalado por pessoa em repouso


@dataclass
class Scenario:
    rooms: list[str]
    volumes: np.ndarray  # (R,)
    k_inf: np.ndarray  # (R,) 1/h
    occ: np.ndarray  # (R,T) pessoas
    sleep: np.ndarray  # (R,T) bool
    co2_gen: np.ndarray  # (R,T) ppm/h
    pm_gen: np.ndarray  # (R,T) ug/m3/h
    pm_ext: np.ndarray  # (T,)
    t_out: np.ndarray  # (T,) graus C
    t_in: float = 22.0
    dt_h: float = 0.25

    @property
    def n_rooms(self) -> int:
        return len(self.rooms)

    @property
    def n_slots(self) -> int:
        return self.occ.shape[1]


def co2_from_people(people, volume_m3):
    return np.asarray(people) * CO2_PER_PERSON_M3H / volume_m3 * 1e6


def step(x, gen, ke, kf, ext, dt_h):
    k = np.maximum(ke + kf, 1e-9)
    eq = (gen + ke * ext) / k
    return eq + (x - eq) * np.exp(-k * dt_h)


def advance(sc: Scenario, t: int, co2, pm, u, f):
    """Avança um slot. co2/pm/u/f têm shape (..., R)."""
    ke = sc.k_inf + EXHAUST_FLOW[u] / sc.volumes
    kf = PURIFIER_CADR[f] / sc.volumes
    return (
        step(co2, sc.co2_gen[:, t], ke, 0.0, CO2_EXT, sc.dt_h),
        step(pm, sc.pm_gen[:, t], ke, kf, sc.pm_ext[t], sc.dt_h),
    )


def rollout(plans, sc: Scenario, x0_co2, x0_pm):
    """plans: (P,R,T,2) int. Retorna co2, pm com shape (P,R,T+1)."""
    P, R, T, _ = plans.shape
    co2 = np.empty((P, R, T + 1))
    pm = np.empty((P, R, T + 1))
    co2[:, :, 0] = x0_co2
    pm[:, :, 0] = x0_pm
    for t in range(T):
        co2[:, :, t + 1], pm[:, :, t + 1] = advance(
            sc, t, co2[:, :, t], pm[:, :, t], plans[:, :, t, 0], plans[:, :, t, 1]
        )
    return co2, pm


def noise_db(u, f):
    power = (
        np.where(u > 0, 10 ** (EXHAUST_DB[u] / 10), 0.0)
        + np.where(f > 0, 10 ** (PURIFIER_DB[f] / 10), 0.0)
        + 10 ** (BACKGROUND_DB / 10)
    )
    return 10 * np.log10(power)


def sleep_caps(limit_db: float) -> tuple[int, int]:
    """Maior nível de exaustor/purificador que, somados, ainda respeitam o limite noturno."""
    u_cap = int(np.max(np.nonzero(EXHAUST_DB <= limit_db - 3)[0]))
    f_cap = int(np.max(np.nonzero(PURIFIER_DB <= limit_db - 3)[0]))
    return u_cap, f_cap
