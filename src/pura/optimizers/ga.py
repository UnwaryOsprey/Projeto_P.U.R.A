"""Algoritmo Genético vetorizado sobre toda a população."""
from __future__ import annotations

import numpy as np

from ..model.objective import Problem
from .base import Optimizer, OptResult, random_plans
from .baselines import HysteresisBaseline, TimerBaseline
from .fuzzy import FuzzyPolicy


class GeneticAlgorithm(Optimizer):
    stochastic = True

    def __init__(self, pop=80, gens=120, cx=0.9, mut=0.02, tour=3, elite=2, seed_policies=False):
        self.pop, self.gens, self.cx, self.mut = pop, gens, cx, mut
        self.tour, self.elite, self.seed_policies = tour, elite, seed_policies
        self.name = "ga_seeded" if seed_policies else "ga"

    def optimize(self, problem: Problem, seed=None) -> OptResult:
        rng = np.random.default_rng(seed)
        R, T = problem.sc.n_rooms, problem.sc.n_slots
        P = self.pop
        pop = random_plans(rng, P, R, T)
        if self.seed_policies:
            seeds = [cls().optimize(problem).plan for cls in (HysteresisBaseline, TimerBaseline, FuzzyPolicy)]
            pop[: len(seeds)] = np.stack(seeds)
        cost = problem.cost(pop)
        hist = [float(cost.min())]
        ar = np.arange(P)
        for _ in range(self.gens):
            elites = pop[np.argsort(cost)[: self.elite]].copy()
            ia = rng.integers(0, P, (P, self.tour))
            ib = rng.integers(0, P, (P, self.tour))
            A = pop[ia[ar, cost[ia].argmin(1)]]
            B = pop[ib[ar, cost[ib].argmin(1)]]
            cut = rng.integers(1, T, (P, R, 1))
            take_b = (np.arange(T)[None, None, :] >= cut)[..., None] & (rng.random((P, 1, 1, 1)) < self.cx)
            child = np.where(take_b, B, A)
            mut = rng.random(child.shape) < self.mut
            child = np.where(mut, rng.integers(0, 4, child.shape, dtype=np.int8), child)
            smooth = rng.random((P, R, T, 1)) < self.mut * 2  # copia o slot anterior: favorece trechos longos
            child[:, :, 1:] = np.where(smooth[:, :, 1:], child[:, :, :-1], child[:, :, 1:])
            child[: self.elite] = elites
            pop, cost = child, problem.cost(child)
            hist.append(float(cost.min()))
        return OptResult(plan=pop[int(cost.argmin())].copy(), history=hist, evals=P * (self.gens + 1))
