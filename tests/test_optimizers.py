import numpy as np
import pytest

from pura.model.objective import Problem
from pura.model.scenarios import initial_state, make_scenario
from pura.optimizers import OPTIMIZERS, make
from pura.optimizers.fuzzy import FuzzyController


@pytest.fixture(scope="module")
def pb():
    sc = make_scenario(1)
    return Problem(sc, *initial_state(sc))


@pytest.mark.parametrize("name", OPTIMIZERS)
def test_plan_shape_and_levels(pb, name):
    plan = make(name, **({"pop": 20, "gens": 10} if name.startswith("ga") else
                         {"chains": 4, "iters": 20} if name == "sa" else {})).optimize(pb, seed=0).plan
    assert plan.shape == (pb.sc.n_rooms, pb.sc.n_slots, 2)
    assert plan.min() >= 0 and plan.max() <= 3


def test_stochastic_reproducible_with_seed(pb):
    a = make("ga", pop=20, gens=10).optimize(pb, seed=7).plan
    b = make("ga", pop=20, gens=10).optimize(pb, seed=7).plan
    assert np.array_equal(a, b)


def test_seeded_ga_never_worse_than_its_seeds(pb):
    seeds = [pb.cost(make(n).optimize(pb).plan)[0] for n in ("hysteresis", "timer", "fuzzy")]
    ga = make("ga_seeded", pop=20, gens=10).optimize(pb, seed=0)
    assert pb.cost(ga.plan)[0] <= min(seeds) + 1e-9
    assert ga.history[-1] <= ga.history[0]


def test_history_is_monotone_non_increasing(pb):
    for opt in (make("ga", pop=20, gens=15), make("sa", chains=4, iters=40)):
        h = opt.optimize(pb, seed=3).history
        assert all(b <= a + 1e-9 for a, b in zip(h, h[1:], strict=False))


def test_hysteresis_sleep_respects_noise(pb):
    m = pb.evaluate(make("hysteresis_sleep").optimize(pb).plan)
    assert m["sleep_noise_min"][0] == 0


def test_fuzzy_monotonic_in_co2():
    c = FuzzyController()
    low, _ = c.infer(500, 5, 0, 1)
    high, _ = c.infer(1600, 5, 0, 1)
    _, pm_low = c.infer(600, 5, 0, 1)
    _, pm_high = c.infer(600, 80, 0, 1)
    assert high > low and pm_high > pm_low
