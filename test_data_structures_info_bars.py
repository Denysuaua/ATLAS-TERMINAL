"""Тесты data_structures, часть 2: бары дисбаланса и серий (B04 §2.3.2)."""
import numpy as np
import pandas as pd
import pytest

from dz_afml.data_structures import (
    ConstImbalanceBars, ConstRunBars, EMAImbalanceBars, EMARunBars,
    get_const_dollar_imbalance_bars, get_const_dollar_run_bars, get_const_tick_imbalance_bars,
    get_const_tick_run_bars, get_const_volume_imbalance_bars, get_const_volume_run_bars,
    get_ema_dollar_imbalance_bars, get_ema_dollar_run_bars, get_ema_tick_imbalance_bars,
    get_ema_tick_run_bars, get_ema_volume_imbalance_bars, get_ema_volume_run_bars,
)


def _ticks(prices, volumes=None):
    n = len(prices)
    return pd.DataFrame({"date_time": pd.date_range("2024-01-02 09:00", periods=n, freq="s"),
                         "price": np.asarray(prices, float),
                         "volume": np.ones(n) if volumes is None else np.asarray(volumes, float)})


def _random(n=3000, p_up=0.55, seed=0):
    rng = np.random.default_rng(seed)
    prices = 100 + np.round(np.cumsum(rng.choice([-0.1, 0.1], n, p=[1 - p_up, p_up])), 1)
    return _ticks(prices, rng.integers(1, 10, n))


# --- известные ответы ------------------------------------------------------------
def test_const_tick_imbalance_known_answer():
    # знаки: 0 (первый тик), затем все +1; прогрев 3 тика, окно 3
    bars, _ = get_const_tick_imbalance_bars(_ticks(100 + 0.1 * np.arange(10)), expected_imbalance_window=3,
                                            exp_num_ticks_init=3, verbose=False)
    # после 3-го тика E[b] = EWM(0,1,1) = 1,5/1,75 ≈ 0,857, порог 2,57, θ = 2 — рано; 4-й тик: θ = 3 → бар
    # затем E[b] = 1, порог 3 → бары по 3 тика
    assert bars["tick_num"].tolist() == [4, 7, 10]
    assert bars["cum_ticks"].tolist() == [4, 3, 3]


def test_const_tick_runs_known_answer():
    prices = [100, 100.1, 100.2, 100.1, 100.2, 100.3, 100.2]   # знаки 0, +, +, −, +, +, −
    bars, _ = get_const_tick_run_bars(_ticks(prices), num_prev_bars=3, expected_imbalance_window=3,
                                      exp_num_ticks_init=4, verbose=False)
    # прогрев закончен на 4-м тике (есть и покупки, и продажи): P = 2/4, порог 4·max(0,5; 0,5) = 2,
    # покупок 2 → бар; затем порог снова 2 → бар после двух покупок (тики 5–6)
    assert bars["tick_num"].tolist()[:2] == [4, 6]


def test_volume_imbalance_uses_signed_volume():
    prices = 100 + 0.1 * np.arange(8)                    # все тики вверх, кроме первого
    vols = [5, 1, 1, 10, 1, 1, 10, 1]
    bars, th = get_const_volume_imbalance_bars(_ticks(prices, vols), expected_imbalance_window=2,
                                               exp_num_ticks_init=2, analyse_thresholds=True, verbose=False)
    assert th["cum_theta"].iloc[0] == 0.0                # первый тик без знака не входит в дисбаланс
    assert {"timestamp", "cum_theta", "expected_imbalance", "exp_num_ticks"} <= set(th.columns)
    assert (bars["cum_buy_volume"] <= bars["volume"]).all()


# --- устойчивость: известное свойство формул книги ----------------------------------
def test_ema_tick_imbalance_collapses_without_constraints():
    bars, _ = get_ema_tick_imbalance_bars(_random(), num_prev_bars=3, expected_imbalance_window=50,
                                          exp_num_ticks_init=20, verbose=False)
    assert bars["cum_ticks"].mean() < 1.2                 # E0[T] → 1: поглощающее состояние
    bounded, _ = get_ema_tick_imbalance_bars(_random(), num_prev_bars=3, expected_imbalance_window=50,
                                             exp_num_ticks_init=20, exp_num_ticks_constraints=(50, 500),
                                             verbose=False, min_expected_imbalance=0.2)
    assert bounded["cum_ticks"].mean() > 5


def test_e8_floor_stabilises_const_bars_on_balanced_flow():
    ticks = _random(n=4000, p_up=0.5, seed=3)
    plain, _ = get_const_tick_imbalance_bars(ticks, expected_imbalance_window=100, exp_num_ticks_init=50,
                                             verbose=False)
    floored, _ = get_const_tick_imbalance_bars(ticks, expected_imbalance_window=100, exp_num_ticks_init=50,
                                               verbose=False, min_expected_imbalance=0.2)
    assert len(floored) < len(plain)
    assert floored["cum_ticks"].median() > plain["cum_ticks"].median()


# --- пакеты, причинность, интерфейс --------------------------------------------------
CASES = [
    (EMAImbalanceBars, dict(metric="dollar_imbalance", num_prev_bars=3, expected_imbalance_window=50,
                            exp_num_ticks_init=20, exp_num_ticks_constraints=(5, 200))),
    (ConstImbalanceBars, dict(metric="volume_imbalance", expected_imbalance_window=50, exp_num_ticks_init=20)),
    (EMARunBars, dict(metric="volume_run", num_prev_bars=3, expected_imbalance_window=50, exp_num_ticks_init=20)),
    (ConstRunBars, dict(metric="tick_run", num_prev_bars=3, expected_imbalance_window=50, exp_num_ticks_init=20)),
]


@pytest.mark.parametrize("cls, kw", CASES)
def test_batches_do_not_change_result(cls, kw):
    ticks = _random()
    full = cls(**kw).batch_run(ticks, verbose=False)
    parts = cls(**kw, batch_size=13).batch_run(ticks, verbose=False)
    pd.testing.assert_frame_equal(full, parts)
    assert len(full) > 10


@pytest.mark.parametrize("cls, kw", CASES)
def test_bars_are_causal(cls, kw):
    ticks = _random()
    full = cls(**kw).batch_run(ticks, verbose=False)
    cut = int(full["tick_num"].iloc[len(full) // 2])
    part = cls(**kw).batch_run(ticks.iloc[:cut], verbose=False)
    pd.testing.assert_frame_equal(part, full[full["tick_num"] <= cut].reset_index(drop=True))


def test_all_wrappers_return_bars_and_thresholds():
    ticks = _random(1500)
    ema = dict(num_prev_bars=3, expected_imbalance_window=50, exp_num_ticks_init=20,
               exp_num_ticks_constraints=(5, 100), verbose=False)
    const_imb = dict(expected_imbalance_window=50, exp_num_ticks_init=20, verbose=False)
    const_run = dict(num_prev_bars=3, expected_imbalance_window=50, exp_num_ticks_init=20, verbose=False)
    calls = [(get_ema_dollar_imbalance_bars, ema), (get_ema_volume_imbalance_bars, ema),
             (get_ema_tick_imbalance_bars, ema), (get_const_dollar_imbalance_bars, const_imb),
             (get_const_volume_imbalance_bars, const_imb), (get_const_tick_imbalance_bars, const_imb),
             (get_ema_dollar_run_bars, ema), (get_ema_volume_run_bars, ema), (get_ema_tick_run_bars, ema),
             (get_const_dollar_run_bars, const_run), (get_const_volume_run_bars, const_run),
             (get_const_tick_run_bars, const_run)]
    for func, kw in calls:
        bars, thresholds = func(ticks, **kw)
        assert isinstance(bars, pd.DataFrame) and isinstance(thresholds, pd.DataFrame), func.__name__
        assert len(bars) > 0, func.__name__


def test_validation():
    with pytest.raises(ValueError):
        ConstImbalanceBars("tick_run", 10, 10)
    with pytest.raises(ValueError):
        ConstRunBars("tick_imbalance", 3, 10, 10)
    with pytest.raises(ValueError):
        EMAImbalanceBars("tick_imbalance", 3, 10, 10, exp_num_ticks_constraints=(10, 5))
    with pytest.raises(ValueError):
        ConstImbalanceBars("tick_imbalance", 10, 10, min_expected_imbalance=0)
    with pytest.raises(ValueError):
        get_const_tick_run_bars(_random(50), verbose=False, to_csv=True)
