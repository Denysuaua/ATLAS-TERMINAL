#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_TS_Lab.py — лаборатория временных рядов на локальном ПК, v1.0 (2026-09-27)

Пять шагов, каждый отвечает на свой вопрос:
  1. Стационарность    ADF (H0: единичный корень) + KPSS (H0: стационарность) + отношение
                       дисперсий. Вывод уверенный, только когда ADF и KPSS согласны.
  2. Выравнивание      дробное дифференцирование с фиксированным окном (López de Prado,
                       AFML гл. 5): минимальное d, при котором ряд стационарен; память
                       ряда — корреляция с исходной ценой.
  3. Очистка от шума   ПРИЧИННАЯ локальная прямая (формулы MOD9, сверены с numpy). Двусторонние
                       фильтры не применяются: они видят будущее, и прогноз по ним — фикция.
  4. Прогноз           ARMA(p,q) на доходностях, порядок по AIC на первом окне; скользящее
                       переобучение; только прошлые данные. Эталон — наивный прогноз «изменения
                       не будет»; мера — skill = 1 − MSE_модели / MSE_наивного.
  5. Контроль          тот же прогноз на перемешанных доходностях. Skill там обязан быть ≤ 0;
                       если нет — метод находит закономерность в шуме, и результат шага 4
                       недостоверен.

ЗАПУСК
  python DZ_TS_Lab.py --data gc-1m.npz --tf 15 --start 2025-01-01
Данные — кэш DZ_DATA_Sanitizer (.npz) либо CSV любого формата через DZ_NTSIM_Engine.
Старший таймфрейм — каноническим ресемплингом DZ_DATA_Sanitizer (постулат П7).
==========================================================================================
"""
import argparse, importlib.util, itertools, json, math, os, sys, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))


def _mod(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


# ------------------------------------------------------------------ 1. стационарность
def stationarity(x, name):
    from statsmodels.tsa.stattools import adfuller, kpss
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    adf_p = float(adfuller(x, autolag="AIC")[1])
    kpss_p = float(kpss(x, regression="c", nlags="auto")[1])
    if adf_p < 0.05 and kpss_p > 0.05: verdict = "стационарен (оба теста согласны)"
    elif adf_p >= 0.05 and kpss_p <= 0.05: verdict = "нестационарен (оба теста согласны)"
    else: verdict = "тесты противоречат друг другу — вывод неуверенный"
    return {"series": name, "ADF_p": round(adf_p, 4), "KPSS_p": round(kpss_p, 4), "verdict": verdict}


def variance_ratio(r, q):
    """VR(q) и z при гомоскедастичности. VR < 1 — возврат к среднему, > 1 — персистентность."""
    r = np.asarray(r, float); r = r - r.mean(); n = len(r)
    v1 = (r ** 2).mean()
    rq = np.convolve(r, np.ones(q), "valid")
    vr = (rq ** 2).mean() / (q * v1)
    z = (vr - 1) / math.sqrt(2 * (2 * q - 1) * (q - 1) / (3 * q * n))
    return round(float(vr), 4), round(float(z), 2)


# ------------------------------------------------------------------ 2. дробная разность
def ffd_weights(d, thresh=1e-4, max_len=5000):
    w = [1.0]
    for k in range(1, max_len):
        wk = -w[-1] * (d - k + 1) / k
        if abs(wk) < thresh: break
        w.append(wk)
    return np.array(w)


def ffd(x, d, thresh=1e-4):
    """Дробная разность с ФИКСИРОВАННЫМ окном: каждое значение — только из прошлых точек."""
    w = ffd_weights(d, thresh)
    return np.convolve(x, w, "valid"), len(w)


def min_ffd(logp):
    from statsmodels.tsa.stattools import adfuller
    for d in np.arange(0.0, 1.01, 0.05):
        y, width = ffd(logp, d)
        if len(y) < 100: continue
        if adfuller(y, autolag="AIC")[1] < 0.05:
            corr = float(np.corrcoef(y, logp[width - 1:])[0, 1])
            return {"d_min": round(float(d), 2), "window": int(width), "memory_corr_with_price": round(corr, 3)}
    return {"d_min": None}


# ------------------------------------------------------------------ 3. причинное сглаживание
def causal_local_linear(y, h):
    """Локальная прямая с ядром Епанечникова на КАЖДОМ баре — только по прошлым h барам."""
    out = np.full(len(y), np.nan)
    i = np.arange(h); w = 1 - (i / h) ** 2; x = -i
    s0, s1, s2 = w.sum(), (w * x).sum(), (w * x * x).sum(); d = s0 * s2 - s1 * s1
    for t in range(h - 1, len(y)):
        yy = y[t - i]
        out[t] = ((w * yy).sum() * s2 - (w * x * yy).sum() * s1) / d
    return out


# ------------------------------------------------------------------ 4. прогноз ARMA
def arma_walk_forward(r, train, refit, order=None):
    from statsmodels.tsa.arima.model import ARIMA
    r = np.asarray(r, float)
    if order is None:                                        # порядок — только по первому окну
        best = None
        for p, q in itertools.product(range(3), range(3)):
            try:
                aic = ARIMA(r[:train], order=(p, 0, q)).fit().aic
                if best is None or aic < best[0]: best = (aic, (p, 0, q))
            except Exception:
                pass
        order = best[1]
    preds = np.full(len(r), np.nan); res = None
    for t in range(train, len(r)):
        if res is None or (t - train) % refit == 0:
            res = ARIMA(r[t - train:t], order=order).fit()
        else:
            res = res.append(r[t - 1:t], refit=False)        # новые наблюдения без переоценки
        preds[t] = float(res.forecast(1)[0])                 # прогноз бара t по данным до t−1
    m = ~np.isnan(preds); e_m = r[m] - preds[m]; e_n = r[m]  # наивный прогноз доходности — ноль
    skill = 1 - (e_m ** 2).mean() / (e_n ** 2).mean()
    nz = preds[m] != 0
    hit = float((np.sign(preds[m][nz]) == np.sign(r[m][nz])).mean())
    up = float((r[m] > 0).mean())
    return {"order": list(order), "forecasts": int(m.sum()), "skill_vs_naive": round(float(skill), 5),
            "direction_accuracy": round(hit, 4), "base_rate_up": round(up, 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--tf", type=int, default=15)
    ap.add_argument("--start"); ap.add_argument("--end")
    ap.add_argument("--train", type=int, default=1000); ap.add_argument("--refit", type=int, default=100)
    ap.add_argument("--smooth", type=int, default=20); ap.add_argument("--max-bars", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=1); ap.add_argument("--out", default="ts_lab_report.json")
    a = ap.parse_args()
    try:
        import statsmodels  # noqa
    except ImportError:
        sys.exit("нужен statsmodels: pip install statsmodels")

    san = _mod("DZ_DATA_Sanitizer")
    m1 = san.load_clean(a.data) if a.data.endswith((".npz", ".parquet")) else \
         _mod("DZ_NTSIM_Engine").load_bars(a.data, "auto", "auto", os.path.join(HERE, "DZ_BT_DualBreakout_S021.py"))[0]
    if "v" not in m1.columns: m1["v"] = 0.0
    if a.start: m1 = m1[m1.index >= pd.Timestamp(a.start, tz="UTC")]
    if a.end: m1 = m1[m1.index <= pd.Timestamp(a.end, tz="UTC")]
    bars = san.resample(m1, a.tf).tail(a.max_bars)
    logp = np.log(bars.c.to_numpy(float)); r = np.diff(logp)

    rep = {"timeframe_min": a.tf, "bars": int(len(bars)),
           "stationarity": [stationarity(logp, "логарифм цены"), stationarity(r, "логдоходность")],
           "variance_ratio": {f"q={q}": variance_ratio(r, q) for q in (2, 4, 8, 16)},
           "fractional_diff": min_ffd(logp)}
    sm = causal_local_linear(logp, a.smooth)
    ok = ~np.isnan(sm)
    rep["causal_smoothing"] = {"window": a.smooth, "residual_std_ticks_rel": round(float(np.std(logp[ok] - sm[ok]) / np.std(r)), 3)}
    rep["forecast_arma"] = arma_walk_forward(r, a.train, a.refit)
    rng = np.random.default_rng(a.seed)
    rep["control_shuffled"] = arma_walk_forward(rng.permutation(r), a.train, a.refit, order=tuple(rep["forecast_arma"]["order"]))
    f, c = rep["forecast_arma"], rep["control_shuffled"]
    rep["verdict"] = ("прогноз ЛУЧШЕ наивного и лучше контроля — линейная предсказуемость есть"
                      if f["skill_vs_naive"] > 0 and f["skill_vs_naive"] > c["skill_vs_naive"] + 0.002
                      else "прогноз НЕ лучше наивного — линейной предсказуемости нет; нелинейная модель вроде LSTM здесь найдёт в основном шум")
    json.dump(rep, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(rep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
