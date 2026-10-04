"""Função objetivo e restrições (ver docs/modelagem.md).

Plano: array int (R,T,2) com [:,:,0]=nível do exaustor e [:,:,1]=nível do purificador.
Restrições entram como penalidade; cada uma também é reportada à parte para auditoria.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .dynamics import (
    AIR_RHO_CP,
    EXHAUST_FLOW,
    EXHAUST_W,
    PURIFIER_W,
    Scenario,
    noise_db,
    rollout,
)


@dataclass(frozen=True)
class Limits:
    co2_ref: float = 1000.0  # ppm (referência de conforto)
    pm_ref: float = 15.0  # ug/m3 (OMS, média 24h)
    co2_ceiling: float = 1500.0  # ppm (teto rígido com ocupação)
    noise_sleep_db: float = 35.0
    energy_budget_kwh_day: float = 1.2
    power_limit_w: float = 60.0
    min_run_slots: int = 2  # anti short-cycling do motor


@dataclass(frozen=True)
class Weights:
    alpha: float = 2.0  # energia (kWh)
    beta: float = 1.5  # perda térmica (kWh)
    gamma: float = 0.5  # ruído acordado
    penalty: float = 5.0  # por unidade de violação


@dataclass
class Problem:
    sc: Scenario
    x0_co2: np.ndarray
    x0_pm: np.ndarray
    limits: Limits = Limits()
    weights: Weights = Weights()

    def evaluate(self, plans) -> dict:
        plans = np.asarray(plans)
        if plans.ndim == 3:
            plans = plans[None]
        sc, lim, w = self.sc, self.limits, self.weights
        dt = sc.dt_h
        P = plans.shape[0]
        co2, pm = rollout(plans, sc, self.x0_co2, self.x0_pm)
        c, p = co2[:, :, 1:], pm[:, :, 1:]
        u, f = plans[..., 0], plans[..., 1]
        occ, sleep = sc.occ[None], sc.sleep[None]

        weight = occ + 0.05
        ex_co2 = np.maximum(0, c - lim.co2_ref) / lim.co2_ref
        ex_pm = np.maximum(0, p - lim.pm_ref) / lim.pm_ref
        exposure = (weight * (ex_co2 + ex_pm)).sum((1, 2)) * dt

        power = EXHAUST_W[u] + PURIFIER_W[f]
        energy = power.sum((1, 2)) * dt / 1000
        dT = np.abs(sc.t_in - sc.t_out)[None, None, :]
        thermal = (AIR_RHO_CP * EXHAUST_FLOW[u] * dT).sum((1, 2)) * dt / 1000

        noise = noise_db(u, f)
        awake_occ = (occ > 0) & ~sleep
        noise_soft = (np.maximum(0, noise - 35.0) / 10 * awake_occ).sum((1, 2)) * dt

        v_ceiling = ((c > lim.co2_ceiling) & (occ > 0)).sum((1, 2))
        v_noise = ((noise > lim.noise_sleep_db) & sleep).sum((1, 2))
        budget = lim.energy_budget_kwh_day * sc.n_slots * dt / 24
        v_energy = np.maximum(0, energy - budget)
        v_power = (power.sum(1) > lim.power_limit_w).sum(1)
        on = u > 0
        d = on[..., 1:] != on[..., :-1]
        v_short = np.zeros(P)
        for k in range(1, lim.min_run_slots):
            v_short += (d[..., :-k] & d[..., k:]).sum((1, 2))

        penalty = w.penalty * (v_ceiling + v_noise + 10 * v_energy + v_power + 0.5 * v_short)
        cost = exposure + w.alpha * energy + w.beta * thermal + w.gamma * noise_soft + penalty
        return {
            "cost": cost,
            "exposure": exposure,
            "energy_kwh": energy,
            "thermal_kwh": thermal,
            "ceiling_min": v_ceiling * dt * 60,
            "sleep_noise_min": v_noise * dt * 60,
            "energy_excess_kwh": v_energy,
            "power_slots": v_power,
            "short_cycles": v_short,
            "t_over_co2_min": ((c > lim.co2_ref) & (occ > 0)).sum((1, 2)) * dt * 60,
            "t_over_pm_min": ((p > lim.pm_ref) & (occ > 0)).sum((1, 2)) * dt * 60,
            "co2": co2,
            "pm": pm,
        }

    def cost(self, plans) -> np.ndarray:
        return self.evaluate(plans)["cost"]

    def feasible(self, plan) -> bool:
        m = self.evaluate(plan)
        keys = ("ceiling_min", "sleep_noise_min", "energy_excess_kwh", "power_slots")
        return all(float(m[k][0]) == 0 for k in keys)
