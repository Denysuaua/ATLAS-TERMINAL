#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_MODTEST_MOD10_S021.py — изолированное испытание модуля [MOD10] «ядро с шириной по Хёрсту»
на утверждённых сигналах [MOD1] из реестра, v1.0 (2026-10-04). «Один модуль — один прогон».

ПЕРЕНОС ЯДРА (DZ_SW_Mod_HurstKernel_S021 v1.1, формула в формулу): лог-доходности окна [H04]; R/S на масштабах
N, N/2, … ≥ 8 с ожиданием Аниса–Ллойда (ExpectedRS модуля), σ по n; H = 0,5 + наклон; окно ядра
hb = round(Min + t·(Max − Min)), t = clip((H − HLow)/(HHigh − HLow)); ядро Епанечникова, локальная прямая
(SwAdaptiveKernelEngine.Fit); вердикт: |наклон| ≥ [H09] тиков/бар → Agree по знаку, иначе Neutral.
Приближение стенда: наклон считается на сетке ширин S и берётся ближайшая к hb (паритет — parity-dump).

СЕТКА (экстремально широкая, своя на каждый ТФ): [H04] 32…1024 ×2; ширина (4–12, 8–40, 16–80, 32–160, 8–160);
полоса H (0,37–0,57; 0,30–0,70; 0,42–0,52; 0,45–0,65); порог наклона 0…8 тиков/бар. Зоны отказа: [H04] ≤ 16 —
два масштаба, H вырождается; [H04] ≥ 2048 на 240m — окно больше года.

МЕТРИКИ на каждой точке: пропущено n, WinRate, PF, ожидание $; отвергнуто n, WinRate; доля сохранённых прибыльных;
доля отсечённых убыточных; захват MFE пропущенных (сумма PnL / сумма MFE$, медиана у прибыльных); покрытие по
времени (доля баров с направлением, прогрев). Отбор: ожидание пропущенных при n ≥ 100; порог доверия —
t > E[max] по числу точек сетки (≈3,1 для 840), MLAM 8.4. Эксперименты H11, H13, H14, Э46 — отдельно.
==========================================================================================
"""
import argparse, importlib.util, itertools, json, math, os, sys, time
import numpy as np
import pandas as pd

VERSION = "DZ_MODTEST_MOD10_S021-v1.0 (2026-10-04)"
HERE = os.path.dirname(os.path.abspath(__file__))
TICK = 0.1; TICK_USD = 1.0
S_BW = [4, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160]
GRID = {"period": [32, 64, 128, 256, 512, 1024], "bw": [(4, 12), (8, 40), (16, 80), (32, 160), (8, 160)],
        "band": [(0.37, 0.57), (0.30, 0.70), (0.42, 0.52), (0.45, 0.65)], "thr": [0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0]}
APPROVED = [(1, "CHOCH+", 120), (1, "CHOCH+", 60), (2, "BOS swing", 120), (2, "BOS", 240)]


def load(name, fn):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn)); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def expected_rs(n):
    r = math.sqrt(math.pi) if n % 2 == 0 else 2.0 / math.sqrt(math.pi)
    m = 2 if n % 2 == 0 else 3
    while m < n: r *= (m - 1.0) / m; m += 2
    s = sum(math.sqrt((n - i) / i) for i in range(1, n))
    return ((n - 0.5) / n) * (r / math.sqrt(math.pi)) * s


def hurst_series(c, N, step=1):
    """H по модулю: на каждом баре (или каждом step-м, с удержанием) по последним N лог-доходностям."""
    lr = np.diff(np.log(c)); n = len(c); H = np.full(n, np.nan)
    scales = []; m = N
    while m >= 8: scales.append(m); m //= 2
    logN = np.log(scales); logE = np.array([math.log(expected_rs(s)) for s in scales])
    last = np.nan
    for i in range(N, n):          # бар i: доходности lr[i-N … i-1] — последние N
        if (i - N) % step == 0:
            r = lr[i - N:i]; xs = []; ys = []
            for s, lN, lE in zip(scales, logN, logE):
                k = N // s; blocks = r[:k * s].reshape(k, s)
                dev = blocks - blocks.mean(1, keepdims=True); cum = np.cumsum(dev, 1)
                rng = cum.max(1) - cum.min(1); sd = np.sqrt((dev * dev).mean(1))
                ok = sd > 0
                if not ok.any(): continue
                xs.append(lN); ys.append(math.log((rng[ok] / sd[ok]).mean()) - lE)
            if len(xs) >= 2:
                xs = np.array(xs); ys = np.array(ys); den = len(xs) * (xs * xs).sum() - xs.sum() ** 2
                last = 0.5 + (len(xs) * (xs * ys).sum() - xs.sum() * ys.sum()) / den if den > 0 else 0.5
            else: last = 0.5
        H[i] = last
    return H


def slope_grid(c, bws):
    """Наклон локальной прямой с ядром Епанечникова для каждого окна из bws, тиков/бар; [bar, окно]."""
    P = load("dz_port", "DZ_PORT_Chains_S021.py"); n = len(c); out = np.full((n, len(bws)), np.nan)
    for j, hb in enumerate(bws):
        for i in range(hb - 1, n):
            a, b, t = P.kernel_fit(c[i::-1][:hb], hb)
            if not math.isnan(b): out[i, j] = b / TICK
    return out


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--npz", required=True); ap.add_argument("--registry", default="registry/registry_trades_mod1.csv"); ap.add_argument("--tf", type=int, required=True)
    ap.add_argument("--start", default="2015-01-01"); ap.add_argument("--end", default="2019-01-01"); ap.add_argument("--out", default="modtest/mod10"); ap.add_argument("--hstep", type=int, default=1)
    ap.add_argument("--stage", choices=["prep", "grid", "all"], default="all")
    a = ap.parse_args(); t0 = time.time(); os.makedirs(a.out, exist_ok=True)
    M = load("dz_ms", "DZ_MS_Market_S021.py")
    cache = os.path.join(a.out, f"cache_tf{a.tf}.npz")
    if a.stage in ("prep", "all"):
        m1 = M.load_npz(a.npz); m1 = m1[(m1.index >= pd.Timestamp(a.start, tz="UTC")) & (m1.index < pd.Timestamp(a.end, tz="UTC"))]
        b = M.resample_all(m1, [a.tf])[a.tf].reset_index(drop=True); c = b["c"].to_numpy(float)
        close = pd.DatetimeIndex(b["close_utc"]).to_numpy("datetime64[ns]")
        Hs = {}
        for N in GRID["period"]:
            Hs[N] = hurst_series(c, N, a.hstep); print(time.strftime("%H:%M:%S"), f"H[{N}] готов, {time.time()-t0:.0f} с", flush=True)
        SL = slope_grid(c, S_BW); print(time.strftime("%H:%M:%S"), f"наклоны по {len(S_BW)} окнам, {time.time()-t0:.0f} с", flush=True)
        np.savez_compressed(cache, close=close.astype("int64"), slopes=SL, **{f"H{N}": Hs[N] for N in GRID["period"]})
        if a.stage == "prep": return
    z = np.load(cache); close = z["close"].astype("datetime64[ns]"); SL = z["slopes"]; Hs = {N: z[f"H{N}"] for N in GRID["period"]}
    reg = pd.read_csv(a.registry, sep=";"); reg["t"] = pd.to_datetime(reg["time_utc"], utc=True).values.astype("datetime64[ns]")
    appr = reg[[((r.category, r.event, r.tf) in APPROVED) for r in reg.itertuples()]].copy()
    wide = reg[reg.tf.isin([60, 120, 240])].copy()
    sets = {"approved": appr, "wide60_240": wide}
    bwarr = np.array(S_BW); rows = []
    def dir_series(N, bw, band, thr):
        H = Hs[N]; t = np.clip((H - band[0]) / max(1e-9, band[1] - band[0]), 0, 1)
        hb = np.round(bw[0] + t * (bw[1] - bw[0])); hb = np.clip(hb, 3, 160)
        j = np.abs(bwarr[None, :] - hb[:, None]).argmin(1)
        sl = SL[np.arange(len(H)), j]
        d = np.where(np.isnan(sl) | np.isnan(H), 0, np.where(np.abs(sl) >= thr, np.sign(sl), 0)).astype(np.int8)
        warm = np.isnan(H) | np.isnan(sl)
        return d, warm
    for N, bw, band, thr in itertools.product(GRID["period"], GRID["bw"], GRID["band"], GRID["thr"]):
        d, warm = dir_series(N, bw, band, thr)
        row = {"tf_module": a.tf, "period": N, "bw_min": bw[0], "bw_max": bw[1], "h_low": band[0], "h_high": band[1], "thr": thr,
               "time_dir_share": float(np.mean(d != 0)), "time_warmup_share": float(np.mean(warm))}
        for sname, s in sets.items():
            strict = (s.tf.to_numpy() != a.tf)
            pos = np.searchsorted(close, s["t"].to_numpy(), side="left") - 1
            pos = np.where(strict, pos, np.searchsorted(close, s["t"].to_numpy(), side="right") - 1)
            md = np.where(pos >= 0, d[np.clip(pos, 0, len(d) - 1)], 0)
            ok = (md == 0) | (md == s.dir.to_numpy())
            p = s[ok]; r = s[~ok]
            win_all = s.win.sum(); los_all = (1 - s.win).sum()
            pw = p.loc[p.pnl_usd > 0, "pnl_usd"].sum(); pl = -p.loc[p.pnl_usd < 0, "pnl_usd"].sum()
            mfe_usd = (p.mfe_ticks * TICK_USD).sum()
            row.update({f"{sname}_n": len(s), f"{sname}_pass_n": len(p), f"{sname}_pass_wr": p.win.mean() if len(p) else np.nan, f"{sname}_pass_exp": p.pnl_usd.mean() if len(p) else np.nan,
                        f"{sname}_pass_pf": (pw / pl) if pl > 0 else np.inf, f"{sname}_pass_t": (p.pnl_usd.mean() / (p.pnl_usd.std(ddof=1) / math.sqrt(len(p)))) if len(p) > 2 and p.pnl_usd.std(ddof=1) > 0 else np.nan,
                        f"{sname}_rej_n": len(r), f"{sname}_rej_wr": r.win.mean() if len(r) else np.nan, f"{sname}_kept_winners": p.win.sum() / max(1, win_all), f"{sname}_cut_losers": (1 - r.win).sum() / max(1, los_all),
                        f"{sname}_capture_total": p.pnl_usd.sum() / mfe_usd if mfe_usd > 0 else np.nan,
                        f"{sname}_capture_winners_med": float((p.loc[p.win == 1, "ticks_move"] / p.loc[p.win == 1, "mfe_ticks"].replace(0, np.nan)).median()) if p.win.sum() else np.nan})
        rows.append(row)
    G = pd.DataFrame(rows); G.to_csv(os.path.join(a.out, f"grid_tf{a.tf}.csv"), sep=";", index=False, float_format="%.4f")
    base = {k: {"n": len(s), "wr": s.win.mean(), "exp": s.pnl_usd.mean(), "pf": s.loc[s.pnl_usd > 0, "pnl_usd"].sum() / max(1e-9, -s.loc[s.pnl_usd < 0, "pnl_usd"].sum())} for k, s in sets.items()}
    json.dump({"version": VERSION, "tf": a.tf, "points": len(G), "base": base}, open(os.path.join(a.out, f"base_tf{a.tf}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("база:", json.dumps(base, ensure_ascii=False))
    g = G[G.approved_pass_n >= 100].sort_values("approved_pass_exp", ascending=False)
    print(g.head(8)[["period", "bw_min", "bw_max", "h_low", "h_high", "thr", "approved_pass_n", "approved_pass_wr", "approved_pass_exp", "approved_pass_t", "approved_rej_wr", "approved_kept_winners", "approved_cut_losers", "approved_capture_total", "time_dir_share"]].round(3).to_string(index=False))
    print("директива (≥85 % прибыльных сохранено и ≥70 % убыточных отсечено):", int(((G.approved_kept_winners >= 0.85) & (G.approved_cut_losers >= 0.70)).sum()), "точек")
    print("готово", round(time.time() - t0), "с")


if __name__ == "__main__":
    main()
