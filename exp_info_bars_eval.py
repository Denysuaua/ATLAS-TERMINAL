"""Бары дисбаланса и серий на синтетических тиках: «часы информации» и устойчивость.

Запуск из корня репозитория:  python experiments/exp_info_bars_eval.py   (только печать)

Поток тиков из четырёх участков по 50 000: сбалансированный (P[вверх] = 0,5),
информированный (0,62), снова сбалансированный и информированный. По книге
(B04, с.30) бары дисбаланса должны чаще закрываться при информированной
торговле. Проверяется и известная неустойчивость E0[T] в варианте EMA.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from dz_afml.data_structures import (  # noqa: E402
    get_const_tick_imbalance_bars, get_const_volume_run_bars, get_ema_tick_imbalance_bars,
    get_ema_volume_run_bars,
)

REGIMES = [0.5, 0.62, 0.5, 0.62]
LENGTH = 50_000


def synthetic(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    steps = np.concatenate([rng.choice([-0.1, 0.1], LENGTH, p=[1 - p, p]) for p in REGIMES])
    n = len(steps)
    return pd.DataFrame({"date_time": pd.date_range("2024-01-02", periods=n, freq="s"),
                         "price": 2000 + np.round(np.cumsum(steps), 1),
                         "volume": 1.0 + rng.poisson(4, n)})


def summary(bars: pd.DataFrame) -> dict:
    regime = (bars["tick_num"].to_numpy() - 1) // LENGTH
    counts = np.bincount(regime, minlength=len(REGIMES))
    balanced, informed = counts[[0, 2]].sum() / 2, counts[[1, 3]].sum() / 2
    return {"баров": len(bars), "тиков в баре, среднее": bars["cum_ticks"].mean(),
            "баров на участок: сбаланс.": balanced, "информ.": informed,
            "информ./сбаланс.": informed / balanced if balanced else np.nan}


def main() -> pd.DataFrame:
    ticks = synthetic()
    base = dict(expected_imbalance_window=1000, exp_num_ticks_init=200, verbose=False)
    variants = {
        "TIB Const": get_const_tick_imbalance_bars(ticks, **base)[0],
        "TIB Const + E8 (|E[b]| ≥ 0,1)": get_const_tick_imbalance_bars(ticks, **base, min_expected_imbalance=0.1)[0],
        "TIB EMA без границ": get_ema_tick_imbalance_bars(ticks, num_prev_bars=10, **base)[0],
        "TIB EMA, границы 50–1000, E8": get_ema_tick_imbalance_bars(
            ticks, num_prev_bars=10, exp_num_ticks_constraints=(50, 1000), min_expected_imbalance=0.1, **base)[0],
        "VRB Const": get_const_volume_run_bars(ticks, num_prev_bars=10, **base)[0],
        "VRB EMA, границы 50–1000": get_ema_volume_run_bars(
            ticks, num_prev_bars=10, exp_num_ticks_constraints=(50, 1000), **base)[0],
    }
    return pd.DataFrame({k: summary(v) for k, v in variants.items()}).T


if __name__ == "__main__":
    print(main().to_string(float_format=lambda x: f"{x:.1f}"))
