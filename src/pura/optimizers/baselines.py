"""Baselines obrigatórios (malha fechada simulada sobre o mesmo modelo)."""
from __future__ import annotations

import numpy as np

from ..model.dynamics import advance, sleep_caps
from ..model.objective import Problem
from .base import Optimizer, OptResult


class ReactivePolicy(Optimizer):
    """Política que observa o estado a cada slot e decide (sem olhar o futuro)."""

    def reset(self, n_rooms: int) -> None:
        pass

    def decide(self, t, co2, pm, voc, occ, sleep):
        raise NotImplementedError

    def optimize(self, problem: Problem, seed=None) -> OptResult:
        sc = problem.sc
        R, T = sc.n_rooms, sc.n_slots
        plan = np.zeros((R, T, 2), dtype=np.int8)
        co2, pm = problem.x0_co2.copy(), problem.x0_pm.copy()
        self.reset(R)
        for t in range(T):
            u, f = self.decide(t, co2, pm, np.zeros(R), sc.occ[:, t], sc.sleep[:, t])
            u = np.asarray(u, dtype=np.int8)
            f = np.asarray(f, dtype=np.int8)
            plan[:, t, 0], plan[:, t, 1] = u, f
            co2, pm = advance(sc, t, co2, pm, u, f)
        return OptResult(plan=plan, evals=1)


class TimerBaseline(ReactivePolicy):
    """Baseline 2: nível 1 constante, sem sensor."""

    name = "timer"

    def decide(self, t, co2, pm, voc, occ, sleep):
        n = len(co2)
        return np.ones(n, dtype=int), np.ones(n, dtype=int)


class HysteresisBaseline(ReactivePolicy):
    """Baseline 1: liga acima de X, desliga abaixo de Y (purificador comercial)."""

    name = "hysteresis"

    def __init__(self, co2_on=1000.0, co2_off=800.0, pm_on=25.0, pm_off=15.0, level=2,
                 sleep_aware=False, noise_sleep_db=35.0):
        self.co2_on, self.co2_off = co2_on, co2_off
        self.pm_on, self.pm_off = pm_on, pm_off
        self.level = level
        self.caps = sleep_caps(noise_sleep_db) if sleep_aware else None
        if sleep_aware:
            self.name = "hysteresis_sleep"
        self.reset(1)

    def reset(self, n_rooms):
        self.ex_on = np.zeros(n_rooms, dtype=bool)
        self.pu_on = np.zeros(n_rooms, dtype=bool)

    def decide(self, t, co2, pm, voc, occ, sleep):
        self.ex_on = np.where(co2 > self.co2_on, True, np.where(co2 < self.co2_off, False, self.ex_on))
        self.pu_on = np.where(pm > self.pm_on, True, np.where(pm < self.pm_off, False, self.pu_on))
        u, f = np.where(self.ex_on, self.level, 0), np.where(self.pu_on, self.level, 0)
        if self.caps:
            u = np.where(sleep, np.minimum(u, self.caps[0]), u)
            f = np.where(sleep, np.minimum(f, self.caps[1]), f)
        return u, f
