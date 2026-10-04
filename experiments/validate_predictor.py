"""Valida o previsor Holt no dataset UCI Air Quality contra a persistência (baseline ingênuo).

    1) Baixe https://archive.ics.uci.edu/dataset/360/air+quality  ->  AirQualityUCI.csv
    2) python experiments/validate_predictor.py data/AirQualityUCI.csv

Série usada: CO(GT) (mg/m3), horária. Mede MAE em 1 e 2 passos à frente.
"""
from __future__ import annotations

import csv
import sys

import numpy as np

from pura.pipeline import Holt


def load(path: str) -> np.ndarray:
    vals = []
    with open(path, newline="", encoding="utf-8", errors="ignore") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            try:
                v = float(row["CO(GT)"].replace(",", "."))
            except (KeyError, ValueError, AttributeError):
                continue
            if v != -200:  # -200 = valor ausente no dataset
                vals.append(v)
    return np.array(vals)


def main(path: str) -> None:
    y = load(path)
    print(f"{len(y)} amostras válidas")
    for alpha, beta in ((0.5, 0.3), (0.7, 0.2), (0.8, 0.1)):
        for h in (1, 2):
            model, errs, naive = Holt(alpha, beta), [], []
            for i, x in enumerate(y[:-h]):
                model.update(float(x), i * 3600.0)
                if i > 24:
                    errs.append(abs(model.forecast(h * 3600.0) - y[i + h]))
                    naive.append(abs(x - y[i + h]))
            print(f"alpha={alpha} beta={beta} h={h}h  MAE Holt={np.mean(errs):.3f}  persistência={np.mean(naive):.3f}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
