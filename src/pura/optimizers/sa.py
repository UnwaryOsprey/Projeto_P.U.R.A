"""Simulated Annealing com cadeias paralelas (multi-start vetorizado)."""
from __future__ import annotations

import numpy as np

from ..model.objective import Problem
from .base import Optimizer, OptResult, random_plans


class SimulatedAnnealing(Optimizer):
    name = "sa"
    stochastic = True

    def __init__(self, chains=16, iters=600, max_window=8, t_ratio=1e-3):
        self.chains, self.iters, self.max_window, self.t_ratio = chains, iters, max_window, t_ratio

    def optimize(self, problem: Problem, seed=None) -> OptResult:
        rng = np.random.default_rng(seed)
        R, T = problem.sc.n_rooms, problem.sc.n_slots
        C = self.chains
        cur = random_plans(rng, C, R, T)
        cur_cost = problem.cost(cur)
        best, best_cost = cur[int(cur_cost.argmin())].copy(), float(cur_cost.min())
        t0 = max(1.0, 0.1 * float(cur_cost.mean()))
        alpha = self.t_ratio ** (1 / max(1, self.iters))
        temp, hist = t0, [best_cost]
        for _ in range(self.iters):
            room = rng.integers(0, R, C)
            start = rng.integers(0, T, C)
            length = rng.integers(1, self.max_window + 1, C)
            act = rng.integers(0, 2, C)
            val = rng.integers(0, 4, C).astype(np.int8)
            m_room = (np.arange(R)[None, :] == room[:, None])[:, :, None, None]
            tt = np.arange(T)[None, :]
            m_time = ((tt >= start[:, None]) & (tt < (start + length)[:, None]))[:, None, :, None]
            m_act = (np.arange(2)[None, :] == act[:, None])[:, None, None, :]
            cand = np.where(m_room & m_time & m_act, val[:, None, None, None], cur)
            cand_cost = problem.cost(cand)
            delta = cand_cost - cur_cost
            accept = (delta <= 0) | (rng.random(C) < np.exp(-np.maximum(delta, 0) / temp))
            cur = np.where(accept[:, None, None, None], cand, cur)
            cur_cost = np.where(accept, cand_cost, cur_cost)
            if cur_cost.min() < best_cost:
                best_cost, best = float(cur_cost.min()), cur[int(cur_cost.argmin())].copy()
            hist.append(best_cost)
            temp *= alpha
        return OptResult(plan=best, history=hist, evals=C * (self.iters + 1))
