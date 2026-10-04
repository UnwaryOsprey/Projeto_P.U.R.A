"""Benchmark: otimizadores x baselines com múltiplas execuções (média ± desvio-padrão).

    python experiments/run_benchmark.py --runs 30
    python experiments/run_benchmark.py --quick          # 5 execuções, orçamento menor
"""
from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import numpy as np

from pura.model.objective import Problem
from pura.model.scenarios import initial_state, make_scenario
from pura.optimizers import make

METRICS = ["cost", "exposure", "energy_kwh", "thermal_kwh", "t_over_co2_min", "t_over_pm_min",
           "sleep_noise_min", "ceiling_min", "short_cycles"]
BASELINES = ["timer", "hysteresis", "hysteresis_sleep"]
CANDIDATES = ["fuzzy", "ga", "ga_seeded", "sa"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--scenario-seed", type=int, default=0)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    runs = 5 if a.quick else a.runs
    kw = {"ga": {"pop": 40, "gens": 40}, "ga_seeded": {"pop": 40, "gens": 40},
          "sa": {"chains": 8, "iters": 200}} if a.quick else {}

    sc = make_scenario(a.scenario_seed)
    problem = Problem(sc, *initial_state(sc))
    rows, costs, curves = [], {}, {}
    for name in BASELINES + CANDIDATES:
        opt = make(name, **kw.get(name, {}))
        n = runs if opt.stochastic else 1
        res = []
        t0 = time.perf_counter()
        for seed in range(n):
            r = opt.optimize(problem, seed=seed)
            m = problem.evaluate(r.plan)
            res.append({k: float(m[k][0]) for k in METRICS})
            rows.append({"optimizer": name, "seed": seed, **res[-1]})
            if opt.stochastic and seed == 0:
                curves[name] = r.history
        ms = (time.perf_counter() - t0) / n * 1000
        costs[name] = np.array([x["cost"] for x in res])
        costs[name + "_t"] = ms

    ref = costs["hysteresis_sleep"][0]
    print(f"\nCenário seed={a.scenario_seed} | {runs} execuções por algoritmo estocástico | "
          f"referência = hysteresis_sleep (custo {ref:.2f})\n")
    print("| otimizador | custo (média ± dp) | exposição | kWh | min CO2>1000 | min PM>15 | ruído noturno (min) | tempo/execução | vence ref. |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name in BASELINES + CANDIDATES:
        sel = [r for r in rows if r["optimizer"] == name]
        def f(k, sel=sel):
            return np.array([r[k] for r in sel])

        c = f("cost")
        wins = f"{(c < ref).mean() * 100:.0f}%" if name not in BASELINES else "—"
        print(f"| {name} | {c.mean():.2f} ± {c.std():.2f} | {f('exposure').mean():.2f} | {f('energy_kwh').mean():.2f} | "
              f"{f('t_over_co2_min').mean():.0f} | {f('t_over_pm_min').mean():.0f} | {f('sleep_noise_min').mean():.0f} | "
              f"{costs[name + '_t']:.0f} ms | {wins} |")

    out = Path(a.out)
    out.mkdir(exist_ok=True)
    with open(out / "benchmark.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["optimizer", "seed", *METRICS])
        w.writeheader()
        w.writerows(rows)
    print(f"\nCSV: {out / 'benchmark.csv'}")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(11, 4))
        for n, h in curves.items():
            ax[0].plot(h, label=n)
        ax[0].set(title="Convergência (melhor custo, seed 0)", xlabel="iteração", ylabel="custo")
        ax[0].legend()
        names = BASELINES + CANDIDATES
        ax[1].boxplot([[r["cost"] for r in rows if r["optimizer"] == n] for n in names], tick_labels=names)
        ax[1].set(title="Custo por otimizador", ylabel="custo")
        ax[1].tick_params(axis="x", rotation=30)
        fig.tight_layout()
        fig.savefig(out / "benchmark.png", dpi=130)
        print(f"Gráfico: {out / 'benchmark.png'}")
    except ImportError:
        print("matplotlib não instalado: pulei o gráfico (pip install -e '.[dev]').")


if __name__ == "__main__":
    main()
