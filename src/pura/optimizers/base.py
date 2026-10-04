"""Interface Strategy dos otimizadores."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from ..model.objective import Problem


@dataclass
class OptResult:
    plan: np.ndarray  # (R,T,2) int8
    history: list[float] = field(default_factory=list)  # melhor custo por iteração
    evals: int = 0


class Optimizer(ABC):
    name = "base"
    stochastic = False

    @abstractmethod
    def optimize(self, problem: Problem, seed: int | None = None) -> OptResult:
        ...


def random_plans(rng, n, R, T, block=4):
    """Planos aleatórios constantes por blocos (evita liga/desliga caótico)."""
    nb = -(-T // block)
    g = rng.choice(4, size=(n, R, nb, 2), p=[0.4, 0.3, 0.2, 0.1]).astype(np.int8)
    return np.repeat(g, block, axis=2)[:, :, :T, :]
