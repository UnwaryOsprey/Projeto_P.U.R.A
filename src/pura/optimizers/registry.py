from __future__ import annotations

from .base import Optimizer
from .baselines import HysteresisBaseline, TimerBaseline
from .fuzzy import FuzzyPolicy
from .ga import GeneticAlgorithm
from .sa import SimulatedAnnealing

OPTIMIZERS = ("fuzzy", "hysteresis", "hysteresis_sleep", "timer", "ga", "ga_seeded", "sa")
REACTIVE = ("fuzzy", "hysteresis", "hysteresis_sleep", "timer")


def make(name: str, fast: bool = False, **kw) -> Optimizer:
    """Fábrica de estratégias. fast=True reduz o orçamento (usado em decisões ao vivo)."""
    if name == "fuzzy":
        return FuzzyPolicy(**kw)
    if name == "hysteresis":
        return HysteresisBaseline(**kw)
    if name == "hysteresis_sleep":
        return HysteresisBaseline(sleep_aware=True, **kw)
    if name == "timer":
        return TimerBaseline()
    if name in ("ga", "ga_seeded"):
        if fast:
            kw = {"pop": 60, "gens": 60, **kw}
        return GeneticAlgorithm(seed_policies=(name == "ga_seeded"), **kw)
    if name == "sa":
        if fast:
            kw = {"chains": 12, "iters": 300, **kw}
        return SimulatedAnnealing(**kw)
    raise ValueError(f"otimizador desconhecido: {name}")
