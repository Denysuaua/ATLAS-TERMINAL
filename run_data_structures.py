"""Бары серий: тиков, объёма, денег (B04 §2.3.2.3–2.3.2.4, с.31–32, PDF 58–59).

EMA — E0[T] следует за длинами прошлых баров; Const — E0[T] постоянна.
Функции get_* возвращают пару (бары, пороги по тикам).

На минутках GC неприменимо без тиков (ТЗ, п.6).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from dz_afml.data_structures.base_bars import BaseRunBars
from dz_afml.util.fast_ewma import ewma

def _constraints(value: Any) -> tuple | None:
    if value is None:
        return None
    lo, hi = (float(x) for x in value)
    if not 0 < lo <= hi:
        raise ValueError("exp_num_ticks_constraints — пара (min, max), 0 < min <= max")
    return lo, hi


def _ema_ticks(history: list, num_prev_bars: int, constraints: tuple | None) -> float:
    """E0[T]: EWM-среднее (span = num_prev_bars) длин последних num_prev_bars баров, с границами."""
    recent = np.asarray(history[-num_prev_bars:], dtype=np.float64)
    value = float(ewma(recent, num_prev_bars)[-1])
    if constraints is not None:
        value = min(max(value, constraints[0]), constraints[1])
    return value


class EMARunBars(BaseRunBars):
    """Бары серий с E0[T] = EWM длин прошлых баров, в границах exp_num_ticks_constraints.
    Источник: B04, с.31–32. Статус: Подтверждено по официальному учебнику."""

    def __init__(self, metric: str, num_prev_bars: int, expected_imbalance_window: int,
                 exp_num_ticks_init: int, exp_num_ticks_constraints: Any = None, batch_size: float = 2e7,
                 analyse_thresholds: bool = False) -> None:
        self.exp_num_ticks_constraints = _constraints(exp_num_ticks_constraints)
        super().__init__(metric, batch_size, num_prev_bars, expected_imbalance_window, exp_num_ticks_init,
                         analyse_thresholds)

    def _get_exp_num_ticks(self) -> float:
        """E0[T] по длинам прошлых баров."""
        return _ema_ticks(self.num_ticks_bar, self.num_prev_bars, self.exp_num_ticks_constraints)


class ConstRunBars(BaseRunBars):
    """Бары серий с постоянным E0[T] = exp_num_ticks_init. Источник: B04, с.31–32.
    Статус: Подтверждено по официальному учебнику."""

    def __init__(self, metric: str, num_prev_bars: int, expected_imbalance_window: int,
                 exp_num_ticks_init: int, batch_size: float = 2e7, analyse_thresholds: bool = False) -> None:
        super().__init__(metric, batch_size, num_prev_bars, expected_imbalance_window, exp_num_ticks_init,
                         analyse_thresholds)

    def _get_exp_num_ticks(self) -> float:
        """E0[T] не меняется."""
        return self.thresholds["exp_num_ticks"]


def _run(bars: BaseRunBars, source: Any, verbose: bool, to_csv: bool, output_path: Any):
    out = bars.batch_run(source, verbose=verbose, to_csv=to_csv, output_path=output_path)
    return out, pd.DataFrame(bars.bars_thresholds)


def get_ema_dollar_run_bars(file_path_or_df, num_prev_bars=3, expected_imbalance_window=10000,
                            exp_num_ticks_init=20000, exp_num_ticks_constraints=None, batch_size=2e7,
                            analyse_thresholds=False, verbose=True, to_csv=False, output_path=None):
    """Бары серий денег (DRB), E0[T] по EWM. Выход: (бары, пороги)."""
    return _run(EMARunBars("dollar_run", num_prev_bars, expected_imbalance_window, exp_num_ticks_init,
                           exp_num_ticks_constraints, batch_size, analyse_thresholds),
                file_path_or_df, verbose, to_csv, output_path)


def get_ema_volume_run_bars(file_path_or_df, num_prev_bars=3, expected_imbalance_window=10000,
                            exp_num_ticks_init=20000, exp_num_ticks_constraints=None, batch_size=2e7,
                            analyse_thresholds=False, verbose=True, to_csv=False, output_path=None):
    """Бары серий объёма (VRB), E0[T] по EWM. Выход: (бары, пороги)."""
    return _run(EMARunBars("volume_run", num_prev_bars, expected_imbalance_window, exp_num_ticks_init,
                           exp_num_ticks_constraints, batch_size, analyse_thresholds),
                file_path_or_df, verbose, to_csv, output_path)


def get_ema_tick_run_bars(file_path_or_df, num_prev_bars=3, expected_imbalance_window=10000,
                          exp_num_ticks_init=20000, exp_num_ticks_constraints=None, batch_size=2e7,
                          analyse_thresholds=False, verbose=True, to_csv=False, output_path=None):
    """Бары серий тиков (TRB), E0[T] по EWM. Выход: (бары, пороги)."""
    return _run(EMARunBars("tick_run", num_prev_bars, expected_imbalance_window, exp_num_ticks_init,
                           exp_num_ticks_constraints, batch_size, analyse_thresholds),
                file_path_or_df, verbose, to_csv, output_path)


def get_const_dollar_run_bars(file_path_or_df, num_prev_bars=3, expected_imbalance_window=10000,
                              exp_num_ticks_init=20000, batch_size=2e7, analyse_thresholds=False, verbose=True,
                              to_csv=False, output_path=None):
    """Бары серий денег (DRB) с постоянным E0[T]. Выход: (бары, пороги)."""
    return _run(ConstRunBars("dollar_run", num_prev_bars, expected_imbalance_window, exp_num_ticks_init,
                             batch_size, analyse_thresholds),
                file_path_or_df, verbose, to_csv, output_path)


def get_const_volume_run_bars(file_path_or_df, num_prev_bars=3, expected_imbalance_window=10000,
                              exp_num_ticks_init=20000, batch_size=2e7, analyse_thresholds=False, verbose=True,
                              to_csv=False, output_path=None):
    """Бары серий объёма (VRB) с постоянным E0[T]. Выход: (бары, пороги)."""
    return _run(ConstRunBars("volume_run", num_prev_bars, expected_imbalance_window, exp_num_ticks_init,
                             batch_size, analyse_thresholds),
                file_path_or_df, verbose, to_csv, output_path)


def get_const_tick_run_bars(file_path_or_df, num_prev_bars=3, expected_imbalance_window=10000,
                            exp_num_ticks_init=20000, batch_size=2e7, analyse_thresholds=False, verbose=True,
                            to_csv=False, output_path=None):
    """Бары серий тиков (TRB) с постоянным E0[T]. Выход: (бары, пороги)."""
    return _run(ConstRunBars("tick_run", num_prev_bars, expected_imbalance_window, exp_num_ticks_init,
                             batch_size, analyse_thresholds),
                file_path_or_df, verbose, to_csv, output_path)
