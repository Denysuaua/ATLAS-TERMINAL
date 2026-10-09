#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_MODTEST_MOD9_S021.py — изолированное испытание модуля [MOD9] «адаптивное ядро» (Kernel Regression Core)
на утверждённых сигналах [MOD1], v1.0 (2026-10-05). «Один модуль — один проход».

ПЕРЕНОС ЯДРА (DZ_SW_Mod_AdaptiveKernel_S021 v1.1 / SwAdaptiveKernelEngine, формула в формулу): веса K(i/h) по
типу ядра [K50]; локальная прямая по x = −i (наклон β, t по взвешенным остаткам) или Надарая–Ватсон (наклон =
приращение уровня); адаптивная ширина [K54]: h = round([K53]·clip(ATR20/ATR5, [K5x]мин, макс)); вердикт:
|β/тик| ≥ [K59] → Agree по знаку, иначе Neutral. Стендовые приближения: при адаптации берётся ближайшая ширина
из сетки S; веса по объёму [K55] — отдельный эксперимент; дивергенция с позицией [K60] — этап защиты.

СЕТКА: ядро {Епанечников, Гаусс, трикуб, треугольное, косинус} × регрессия {LL, NW} × ширина 3…160 (×≈1,4,
13 значений) × адаптация {выкл; 0,5–2,0; 0,25–4,0} × порог 0…8 тиков/бар = 2 730 точек на ТФ; ТФ 15/60/240m.
Зоны отказа: ширина < 3 — прямая не определена; ширина ≥ 128 на 240m — окно больше квартала; порог ≥ 4 на 15m —
модуль молчит > 90 % времени.
==========================================================================================
"""
import argparse, importlib.util, itertools, json, math, os, time
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

VERSION = "DZ_MODTEST_MOD9_S021-v1.0 (2026-10-05)"
HERE = os.path.dirname(os.path.abspath(__file__))
TICK = 0.1; TICK_USD = 1.0
S_BW = [3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 160]
KERNELS = ["Epanechnikov", "Gaussian", "Tricube", "Triangular", "Cosine"]
ADAPT = [(0, 1.0, 1.0), (1, 0.5, 2.0), (1, 0.25, 4.0)]
THR = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0]
APPROVED = [(1, "CHOCH+", 120), (1, "CHOCH+", 60), (2, "BOS swing", 120), (2, "BOS", 240)]


def load(name, fn):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn)); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def kweights(kernel, h):
    u = np.arange(h) / h
    if kernel == "Triangular": return np.where(u < 1, 1 - u, 0.0)
    if kernel == "Tricube": return np.where(u < 1, (1 - u ** 3) ** 3, 0.0)
    if kernel == "Cosine": return np.where(u < 1, np.cos(np.pi * 0.5 * u), 0.0)
    if kernel == "Gaussian": return np.exp(-0.5 * (3.0 * u) ** 2)
    return np.where(u < 1, 1 - u * u, 0.0)


def fit_all(c, kernel, h):
    """Векторно по всем барам: α, β (цена/бар), t локальной прямой и α Надарая–Ватсона; y[i] = c[t−i], x = −i."""
    n = len(c); w = kweights(kernel, h); x = -np.arange(h, dtype=float)
    Y = sliding_window_view(c, h)[:, ::-1]          # строка t: c[t], c[t−1], … c[t−h+1]
    s0 = w.sum(); s1 = (w * x).sum(); s2 = (w * x * x).sum(); d = s0 * s2 - s1 * s1
    t0 = Y @ w; t1 = Y @ (w * x); yy = (Y * Y) @ w
    alpha = np.full(n, np.nan); beta = np.full(n, np.nan); tst = np.full(n, np.nan); nw = np.full(n, np.nan)
    nw[h - 1:] = t0 / s0
    if d <= 1e-12 * s0 * s0:
        alpha[h - 1:] = t0 / s0; return alpha, beta, tst, nw
    a = (t0 * s2 - t1 * s1) / d; b = (s0 * t1 - s1 * t0) / d
    rss = yy - 2 * a * t0 - 2 * b * t1 + a * a * s0 + 2 * a * b * s1 + b * b * s2
    cc = ((w * (s0 * x - s1) / d) ** 2).sum(); se = np.sqrt(np.maximum(0.0, rss / s0 * cc))
    alpha[h - 1:] = a; beta[h - 1:] = b; tst[h - 1:] = np.where(se > 0, b / se, 0.0)
    return alpha, beta, tst, nw


def tr_ratio(h, l, c):
    tr = np.empty(len(c)); tr[0] = h[0] - l[0]
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    s = pd.Series(tr); a5 = s.rolling(5).mean(); a20 = s.rolling(20).mean()
    return (a20 / a5).to_numpy(float)


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--npz", required=True); ap.add_argument("--registry", default="registry/registry_trades_mod1.csv"); ap.add_argument("--tf", type=int, required=True)
    ap.add_argument("--start", default="2015-01-01"); ap.add_argument("--end", default="2019-01-01"); ap.add_argument("--out", default="modtest/mod9"); ap.add_argument("--stage", choices=["prep", "grid", "all"], default="all")
    a = ap.parse_args(); t0 = time.time(); os.makedirs(a.out, exist_ok=True); M = load("dz_ms", "DZ_MS_Market_S021.py")
    cache = os.path.join(a.out, f"cache_tf{a.tf}.npz")
    if a.stage in ("prep", "all"):
        m1 = M.load_npz(a.npz); m1 = m1[(m1.index >= pd.Timestamp(a.start, tz="UTC")) & (m1.index < pd.Timestamp(a.end, tz="UTC"))]
        b = M.resample_all(m1, [a.tf])[a.tf].reset_index(drop=True); c = b["c"].to_numpy(float)
        arrs = {"close": pd.DatetimeIndex(b["close_utc"]).to_numpy("datetime64[ns]").astype("int64"), "ratio": tr_ratio(b["h"].to_numpy(float), b["l"].to_numpy(float), c), "c": c}
        for k in KERNELS:
            for h in S_BW:
                al, be, ts, nw = fit_all(c, k, h)
                arrs[f"beta_{k}_{h}"] = be / TICK; arrs[f"t_{k}_{h}"] = ts; arrs[f"alpha_{k}_{h}"] = al; arrs[f"nw_{k}_{h}"] = nw
            print(time.strftime("%H:%M:%S"), f"ядро {k}: {len(S_BW)} ширин, {time.time()-t0:.0f} с", flush=True)
        np.savez_compressed(cache, **arrs)
        if a.stage == "prep": return
    z = np.load(cache); close = z["close"].astype("datetime64[ns]"); ratio = z["ratio"]; n = len(close); S = np.array(S_BW)
    reg = pd.read_csv(a.registry, sep=";"); reg["t"] = pd.to_datetime(reg["time_utc"], utc=True).values.astype("datetime64[ns]")
    appr = reg[[((r.category, r.event, r.tf) in APPROVED) for r in reg.itertuples()]].copy(); wide = reg[reg.tf.isin([60, 120, 240])].copy()
    sets = {"approved": appr, "wide60_240": wide}
    pos_cache = {}
    for sname, s in sets.items():
        strict = (s.tf.to_numpy() != a.tf); pos = np.searchsorted(close, s["t"].to_numpy(), side="left") - 1
        pos_cache[sname] = np.where(strict, pos, np.searchsorted(close, s["t"].to_numpy(), side="right") - 1)
    def slope_series(kernel, reg_type, bw, adapt):
        on, amin, amax = adapt
        if on:
            hb = np.clip(np.round(bw * np.clip(np.nan_to_num(ratio, nan=1.0), amin, amax)), 3, 160); j = np.abs(S[None, :] - hb[:, None]).argmin(1)
        else: j = np.full(n, S_BW.index(bw))
        if reg_type == "LL":
            B = np.column_stack([z[f"beta_{kernel}_{h}"] for h in S_BW]); return B[np.arange(n), j]
        A = np.column_stack([z[f"nw_{kernel}_{h}"] for h in S_BW]); al = A[np.arange(n), j]
        d = np.diff(al, prepend=np.nan) / TICK; return d
    rows = []
    for kernel, reg_type, bw, adapt in itertools.product(KERNELS, ["LL", "NW"], S_BW, ADAPT):
        sl = slope_series(kernel, reg_type, bw, adapt)
        for thr in THR:
            d = np.where(np.isnan(sl), 0, np.where(np.abs(sl) >= thr, np.sign(sl), 0)).astype(np.int8)
            row = {"tf_module": a.tf, "kernel": kernel, "regression": reg_type, "bw": bw, "adaptive": adapt[0], "adapt_min": adapt[1], "adapt_max": adapt[2], "thr": thr,
                   "time_dir_share": float(np.mean(d != 0)), "time_warmup_share": float(np.mean(np.isnan(sl)))}
            for sname, s in sets.items():
                pos = pos_cache[sname]; md = np.where(pos >= 0, d[np.clip(pos, 0, n - 1)], 0); ok = (md == 0) | (md == s.dir.to_numpy()); p = s[ok]; r = s[~ok]
                pw = p.loc[p.pnl_usd > 0, "pnl_usd"].sum(); pl = -p.loc[p.pnl_usd < 0, "pnl_usd"].sum(); mfe = p.mfe_ticks.sum()
                row.update({f"{sname}_pass_n": len(p), f"{sname}_pass_wr": p.win.mean() if len(p) else np.nan, f"{sname}_pass_exp": p.pnl_usd.mean() if len(p) else np.nan,
                            f"{sname}_pass_pf": (pw / pl) if pl > 0 else np.inf, f"{sname}_pass_t": (p.pnl_usd.mean() / (p.pnl_usd.std(ddof=1) / math.sqrt(len(p)))) if len(p) > 2 and p.pnl_usd.std(ddof=1) > 0 else np.nan,
                            f"{sname}_rej_n": len(r), f"{sname}_rej_wr": r.win.mean() if len(r) else np.nan, f"{sname}_kept_winners": p.win.sum() / max(1, s.win.sum()), f"{sname}_cut_losers": (1 - r.win).sum() / max(1, (1 - s.win).sum()),
                            f"{sname}_capture_total": p.pnl_usd.sum() / mfe if mfe > 0 else np.nan, f"{sname}_hold_bars": p.bars.mean() if len(p) else np.nan})
            rows.append(row)
    G = pd.DataFrame(rows); G.to_csv(os.path.join(a.out, f"grid_tf{a.tf}.csv"), sep=";", index=False, float_format="%.4f")
    base = {k: {"n": len(s), "wr": s.win.mean(), "exp": s.pnl_usd.mean()} for k, s in sets.items()}
    g = G[G.approved_pass_n >= 100].sort_values("approved_pass_exp", ascending=False)
    print("база:", json.dumps(base, ensure_ascii=False)); print("точек", len(G))
    print(g.head(8)[["kernel", "regression", "bw", "adaptive", "adapt_max", "thr", "approved_pass_n", "approved_pass_wr", "approved_pass_exp", "approved_pass_t", "approved_rej_wr", "approved_kept_winners", "approved_cut_losers", "time_dir_share"]].round(3).to_string(index=False))
    print("директива 85/70:", int(((G.approved_kept_winners >= 0.85) & (G.approved_cut_losers >= 0.70)).sum()), "точек; готово", round(time.time() - t0), "с")


if __name__ == "__main__":
    main()
