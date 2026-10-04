"""Gerador de cenários sintéticos (regras documentadas em docs/modelagem.md)."""
from __future__ import annotations

import numpy as np

from .dynamics import Scenario, co2_from_people

DEFAULT_ROOMS = (("sala", 40.0, False), ("quarto", 25.0, True))


def make_scenario(seed: int = 0, rooms=DEFAULT_ROOMS, T: int = 96, dt_h: float = 0.25,
                  k_inf: float = 0.12) -> Scenario:
    rng = np.random.default_rng(seed)
    hours = np.arange(T) * dt_h
    R = len(rooms)
    occ = np.zeros((R, T))
    sleep = np.zeros((R, T), dtype=bool)
    pm_gen = np.zeros((R, T))
    vols = np.array([r[1] for r in rooms], dtype=float)
    for i, (_, _, bedroom) in enumerate(rooms):
        if bedroom:
            night = (hours >= 22) | (hours < 7)
            occ[i, night] = 2
            sleep[i, night] = True
        else:
            occ[i, (hours >= 7) & (hours < 9)] = 1
            occ[i, (hours >= 12) & (hours < 13.5)] = 1
            occ[i, (hours >= 18) & (hours < 22)] = 2
            for meal in (7.5, 12.2, 19.0):  # cozinhar: picos de PM2.5
                start = meal + rng.uniform(-0.25, 0.25)
                dur = rng.uniform(0.5, 1.0)
                pm_gen[i, (hours >= start) & (hours < start + dur)] += rng.uniform(150, 400)
    pm_ext = np.full(T, 12.0)
    pm_ext[(hours >= 14) & (hours < 17)] += rng.uniform(30, 60)  # fumaça externa
    return Scenario(
        rooms=[r[0] for r in rooms],
        volumes=vols,
        k_inf=np.full(R, k_inf),
        occ=occ,
        sleep=sleep,
        co2_gen=co2_from_people(occ, vols[:, None]),
        pm_gen=pm_gen,
        pm_ext=pm_ext,
        t_out=18 + 7 * np.sin(2 * np.pi * (hours - 9) / 24),
        dt_h=dt_h,
    )


def initial_state(sc: Scenario):
    return np.full(sc.n_rooms, 450.0), np.full(sc.n_rooms, 10.0)
