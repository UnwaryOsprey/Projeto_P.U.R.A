import numpy as np

from pura.model.dynamics import CO2_EXT, advance
from pura.model.objective import Problem
from pura.model.scenarios import initial_state, make_scenario


def problem(seed=0):
    sc = make_scenario(seed)
    return Problem(sc, *initial_state(sc))


def plan_of(pb, u=0, f=0):
    R, T = pb.sc.n_rooms, pb.sc.n_slots
    p = np.zeros((R, T, 2), dtype=np.int8)
    p[..., 0], p[..., 1] = u, f
    return p


def test_empty_room_converges_to_outdoor():
    sc = make_scenario(0)
    sc.co2_gen[:] = 0
    co2, pm = np.full(2, 2000.0), np.full(2, 100.0)
    z = np.zeros(2, dtype=int)
    for _ in range(200):
        co2, pm = advance(sc, 0, co2, pm, z + 2, z)
    assert np.allclose(co2, CO2_EXT, atol=1) and np.all(pm < 20)


def test_exhaust_lowers_co2_and_purifier_lowers_pm():
    sc = make_scenario(0)
    co2, pm = np.full(2, 1500.0), np.full(2, 80.0)
    off = np.zeros(2, dtype=int)
    c_off, _ = advance(sc, 0, co2, pm, off, off)
    c_on, _ = advance(sc, 0, co2, pm, off + 2, off)
    _, p_off = advance(sc, 40, co2, pm, off, off)
    _, p_on = advance(sc, 40, co2, pm, off, off + 2)
    assert np.all(c_on < c_off) and np.all(p_on < p_off)


def test_zero_plan_has_zero_energy_and_cost_components():
    m = problem().evaluate(plan_of(problem()))
    assert m["energy_kwh"][0] == 0 and m["thermal_kwh"][0] == 0 and m["short_cycles"][0] == 0


def test_idle_bedroom_violates_co2_ceiling():
    pb = problem()
    m = pb.evaluate(plan_of(pb))
    assert m["ceiling_min"][0] > 0 and not pb.feasible(plan_of(pb))


def test_sleep_noise_constraint_detected():
    pb = problem()
    m = pb.evaluate(plan_of(pb, u=3, f=3))  # tudo no máximo, inclusive à noite
    assert m["sleep_noise_min"][0] > 0
    assert m["power_slots"][0] > 0  # 2 cômodos x 60 W > limite


def test_energy_budget_constraint():
    pb = problem()
    pb.limits = type(pb.limits)(energy_budget_kwh_day=0.1)
    assert pb.evaluate(plan_of(pb, u=1, f=1))["energy_excess_kwh"][0] > 0


def test_short_cycling_counted():
    pb = problem()
    p = plan_of(pb)
    p[0, ::2, 0] = 1  # liga/desliga a cada slot
    assert pb.evaluate(p)["short_cycles"][0] > 20


def test_batch_matches_single():
    pb = problem()
    rng = np.random.default_rng(0)
    plans = rng.integers(0, 4, (5, 2, 96, 2)).astype(np.int8)
    batch = pb.cost(plans)
    single = np.array([pb.cost(p)[0] for p in plans])
    assert np.allclose(batch, single)
