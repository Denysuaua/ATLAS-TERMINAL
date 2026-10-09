#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_REG_Trades_S021.py — ЭТАП 0 директивы: четырёхлетний реестр сделок по маркерам [MOD1] на восьми ТФ,
три категории, статистика «событие × ТФ» с поправкой на множественный выбор, рубежи 12:30 и 22:00 Берлин.
v1.0 (2026-10-04). Работает на сертифицированных ценах M1 и разметке DZ_MS_Market_S021 (контекст).

СДЕЛКА РЕЕСТРА. Триггер — маркер структуры PAC (перенос ядра DZ_SW_Mod_Pac_S021 v1.4: пивоты 3/10, пробой по
закрытию): BOS, CHoCH, CHoCH+ внутренние и свинговые, на каждом из ТФ 1/5/15/30/45/60/120/240 отдельно.
Вход — рынок по открытию следующего бара своего ТФ, проскальзывание 1 тик; стоп = 1·ATR14 своего ТФ,
цель = 1·ATR14 (R = 1), вертикальный барьер 24 бара своего ТФ; худший путь — оба барьера одним баром =
убыток; комиссия 0,44 $ за круг. Так доля прибыльных сравнима между ТФ: базовая около 50 %.
КАТЕГОРИИ по контексту разметки DZ_MS того же ТФ (тренд и фаза в момент маркера):
  1 Разворот — CHoCH/CHoCH+ против текущего тренда разметки или без тренда;
  2 Тренд — BOS в направлении тренда вне фазы отката (и BOS без контекста);
  3 Откат — любой маркер в направлении тренда в фазе PULLBACK (вход после коррекции).
СТАТИСТИКА. По (категория, событие, ТФ): n, WinRate с интервалом Уилсона 95 %, PF, ожидание $/сделку.
«Доверенное» — n ≥ 100, WinRate выше базовой доли своего ТФ и категории на величину ожидаемого максимума из 48 комбинаций при
нулевой гипотезе (6 событий × 8 ТФ; MLAM 8.4, теорема о ложной стратегии): порог = база + E[max]·√(p(1−p)/n),
E[max] для 48 — 2,17; и t-статистика ожидания в $ выше 2,17; и PF > 1. Это обучение 2015–2018; заморозка — только после проверки 2022–2025.
ЭКСПЕРИМЕНТЫ, умолчания = реестр: Э60 --barrier-r R — цель в R при стопе 1 ATR (гипотеза: асимметрия R = 2 меняет
ранжирование комбинаций); Э61 --vertical N — вертикальный барьер (24 бара). Любое их изменение — испытание в реестре.
РУБЕЖИ. Для каждой сделки реестра — PnL при вариантах: 12:30 А полное закрытие; 12:30 Б половина и безубыток;
22:00 А полное закрытие; 22:00 Б закрытие только прибыльных. Дельта ожидания и максимальная просадка по ТФ.
==========================================================================================
"""
import argparse, importlib.util, json, math, os, sys, time
import numpy as np
import pandas as pd

VERSION = "DZ_REG_Trades_S021-v1.0 (2026-10-04)"
HERE = os.path.dirname(os.path.abspath(__file__))
TICK = 0.1; TICK_USD = 1.0; COST_RT = 0.44; SLIP = 1; TZB = "Europe/Berlin"
TFS = [1, 5, 15, 30, 45, 60, 120, 240]
EMAX48 = 2.17


def load(name, fn):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn)); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def atr14(h, l, c):
    tr = np.empty(len(c)); tr[0] = h[0] - l[0]
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    return pd.Series(tr).ewm(alpha=1 / 14.0, adjust=False).mean().to_numpy()


def wilson(k, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - r, c + r)


def simulate_tf(bars, events, tf, lab_trend, lab_phase, lab_idx, vertical=24, r_mult=1.0):
    """Сделки по маркерам одного ТФ; возвращает DataFrame реестра."""
    o = bars["o"].to_numpy(float); h = bars["h"].to_numpy(float); l = bars["l"].to_numpy(float); c = bars["c"].to_numpy(float)
    co = pd.DatetimeIndex(bars["close_utc"]); cb = co.tz_convert(TZB); tod = (cb.hour * 60 + cb.minute).to_numpy(); wd = cb.dayofweek.to_numpy()
    atr = atr14(h, l, c); n = len(c); rows = []
    tcl = co.to_numpy("datetime64[ns]")
    pos_l = np.searchsorted(lab_idx, tcl, side="right") - 1
    for i in range(14, n - 2):
        if not events[i]: continue
        for (scope, ev, d) in events[i]:
            R = max(2 * TICK, atr[i]); ent = o[i + 1] + d * SLIP * TICK; stop = ent - d * R; tgt = ent + d * R * r_mult
            mfe = mae = 0.0; k = i + 1; exit_px = None; reason = ""; path = []
            while k < min(n, i + 1 + vertical):
                mfe = max(mfe, (h[k] - ent) if d > 0 else (ent - l[k])); mae = max(mae, (ent - l[k]) if d > 0 else (h[k] - ent))
                hu = h[k] >= tgt if d > 0 else l[k] <= tgt
                hd = l[k] <= stop if d > 0 else h[k] >= stop
                if hu and hd: exit_px = stop; reason = "стоп"; break
                if hd: exit_px = (min(o[k], stop) if d > 0 else max(o[k], stop)); reason = "стоп"; break
                if hu: exit_px = (max(o[k], tgt) if d > 0 else min(o[k], tgt)); reason = "цель"; break
                k += 1
            if exit_px is None:
                k = min(n - 1, i + vertical); exit_px = c[k]; reason = "вертикаль"
            exit_px -= d * SLIP * TICK
            ticks = (exit_px - ent) * d / TICK; pnl = ticks * TICK_USD - COST_RT
            # контекст разметки DZ_MS на своём ТФ в момент маркера
            pl = pos_l[i]; tr_ = int(lab_trend[pl]) if pl >= 0 else 0; ph = int(lab_phase[pl]) if pl >= 0 else 0
            if ev.startswith("CHOCH") and (tr_ == 0 or tr_ != d): cat = 1
            elif tr_ == d and ph == 2: cat = 3
            elif ev == "BOS": cat = 2
            else: cat = 1
            rows.append({"tf": tf, "bar": i, "time_utc": co[i], "berlin": cb[i].strftime("%Y-%m-%d %H:%M"), "weekday": int(wd[i]), "tod_min": int(tod[i]),
                         "event": ev + (" swing" if scope == "sw" else ""), "dir": d, "category": cat, "ctx_trend": tr_, "ctx_phase": ph,
                         "entry": ent, "exit": exit_px, "exit_bar": k, "bars": k - i, "reason": reason, "atr_ticks": R / TICK,
                         "ticks_move": ticks, "absolute_move": abs(exit_px - ent), "price_delta_pct": (exit_px - ent) * d / ent * 100.0,
                         "mfe_ticks": mfe / TICK, "mae_ticks": mae / TICK, "pnl_usd": pnl, "win": int(pnl > 0)})
    return pd.DataFrame(rows)


def time_exit_variants(bars, reg, tf):
    """PnL сделок при рубежах 12:30 и 22:00 Берлин (варианты А/Б) против базового выхода."""
    o = bars["o"].to_numpy(float); h = bars["h"].to_numpy(float); l = bars["l"].to_numpy(float); c = bars["c"].to_numpy(float)
    cb = pd.DatetimeIndex(bars["close_utc"]).tz_convert(TZB); tod = (cb.hour * 60 + cb.minute).to_numpy(); day = cb.strftime("%Y-%m-%d").to_numpy()
    out = {v: [] for v in ("base", "1230A", "1230B", "2200A", "2200B")}
    for r in reg.itertuples():
        i, k, d, ent = int(r.bar), int(r.exit_bar), int(r.dir), float(r.entry); base = float(r.pnl_usd)
        out["base"].append(base)
        for mark, v in ((12 * 60 + 30, "1230"), (22 * 60, "2200")):
            # первый бар после входа, закрывшийся в/после рубежа того же берлинского дня, до базового выхода
            j = None
            for q in range(i + 1, k + 1):
                if tod[q] >= mark and day[q] == day[i] and tod[i] < mark: j = q; break
            if j is None or j >= k:
                out[v + "A"].append(base); out[v + "B"].append(base); continue
            px = c[j] - d * SLIP * TICK; pnl_at = (px - ent) * d / TICK * TICK_USD - COST_RT
            out[v + "A"].append(pnl_at)
            if v == "1230":
                # Б: половина по рынку, остаток — стоп в безубыток до базового выхода
                rest = base
                for q in range(j + 1, k + 1):
                    if (d > 0 and l[q] <= ent) or (d < 0 and h[q] >= ent): rest = (-SLIP * TICK / TICK * TICK_USD) - COST_RT / 2; break
                else: rest = base
                out[v + "B"].append(0.5 * pnl_at + 0.5 * rest)
            else:
                out[v + "B"].append(pnl_at if pnl_at > 0 else base)
    res = {}
    for v, arr in out.items():
        a = np.array(arr); cum = np.cumsum(a); dd = float((np.maximum.accumulate(cum) - cum).max()) if len(a) else np.nan
        res[v] = {"n": int(len(a)), "mean": round(float(a.mean()), 3) if len(a) else np.nan, "sum": round(float(a.sum()), 1) if len(a) else np.nan, "maxdd": round(dd, 1)}
    return res


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--npz", required=True); ap.add_argument("--labels", default="train"); ap.add_argument("--start", default="2015-01-01"); ap.add_argument("--end", default="2019-01-01")
    ap.add_argument("--out", default="registry"); ap.add_argument("--tfs", nargs="*", default=[str(x) for x in TFS]); ap.add_argument("--min-n", type=int, default=100); ap.add_argument("--barrier-r", type=float, default=1.0, help="Э60: цель в R (стоп = 1 ATR)"); ap.add_argument("--vertical", type=int, default=24, help="Э61: вертикальный барьер, баров своего ТФ")
    a = ap.parse_args(); t0 = time.time()
    M = load("dz_ms", "DZ_MS_Market_S021.py"); P = load("dz_port", "DZ_PORT_Chains_S021.py")
    m1 = M.load_npz(a.npz); m1 = m1[(m1.index >= pd.Timestamp(a.start, tz="UTC")) & (m1.index < pd.Timestamp(a.end, tz="UTC"))]
    tfs = [int(x) for x in a.tfs]; bars = M.resample_all(m1, tfs)
    lab = M.load_labeled(a.labels); lab_idx = lab.index.values.astype("datetime64[ns]")
    os.makedirs(a.out, exist_ok=True); regs = []; texits = {}
    for tf in tfs:
        b = bars[tf].reset_index(drop=True)
        ev = P.pac_series(b["h"].to_numpy(float), b["l"].to_numpy(float), b["c"].to_numpy(float))
        reg = simulate_tf(b, ev, tf, lab[f"{tf}m_trend"].to_numpy(np.int8), lab[f"{tf}m_phase"].to_numpy(np.int8), lab_idx, a.vertical, a.barrier_r)
        texits[tf] = time_exit_variants(b, reg, tf)
        regs.append(reg)
        print(time.strftime("%H:%M:%S"), f"ТФ {tf}m: баров {len(b):,}, сделок реестра {len(reg):,}, прибыльных {reg.win.mean():.1%}, {time.time()-t0:.0f} с", flush=True)
    reg = pd.concat(regs, ignore_index=True); reg.insert(0, "id", [f"R{tf}-{i:07d}" for tf, i in zip(reg.tf, range(len(reg)))])
    reg.to_csv(os.path.join(a.out, "registry_trades_mod1.csv"), sep=";", index=False, float_format="%.4f")
    # статистика событие × ТФ по категориям
    rows = []
    for cat, g in reg.groupby("category"):
        for (ev, tf), s in g.groupby(["event", "tf"]):
            base = g.loc[g.tf == tf, "win"].mean()          # база — своего ТФ: издержки относительно ATR разные
            n = len(s); k = int(s.win.sum()); lo, hi = wilson(k, n)
            w = s.loc[s.pnl_usd > 0, "pnl_usd"].sum(); L = -s.loc[s.pnl_usd < 0, "pnl_usd"].sum()
            thr = base + EMAX48 * math.sqrt(base * (1 - base) / max(1, n))
            t_exp = s.pnl_usd.mean() / (s.pnl_usd.std(ddof=1) / math.sqrt(n)) if n > 2 and s.pnl_usd.std(ddof=1) > 0 else np.nan
            rows.append({"category": cat, "event": ev, "tf": tf, "n": n, "winrate": k / n, "ci_lo": lo, "ci_hi": hi, "base_rate_cat_tf": base, "t_exp": t_exp,
                         "pf": (w / L) if L > 0 else np.inf, "exp_usd": s.pnl_usd.mean(), "exp_ticks": s.ticks_move.mean(),
                         "mfe_med": s.mfe_ticks.median(), "capture_mfe_winners": float((s.loc[s.win == 1, "ticks_move"] / s.loc[s.win == 1, "mfe_ticks"].replace(0, np.nan)).median()) if k else np.nan,
                         "null_max_threshold": thr, "trusted": bool(n >= a.min_n and k / n > thr and (w / L if L > 0 else 9) > 1.0 and t_exp > EMAX48)})
    st = pd.DataFrame(rows).sort_values(["category", "winrate"], ascending=[True, False])
    st.to_csv(os.path.join(a.out, "stats_event_tf.csv"), sep=";", index=False, float_format="%.4f")
    # итоговая таблица: лучшая комбинация по категории среди n ≥ min_n по ожиданию в $, затем по WinRate
    best = []
    for cat, g in st.groupby("category"):
        g2 = g[g.n >= a.min_n].sort_values(["exp_usd", "winrate"], ascending=False)
        best.append(g2.head(5))
    best = pd.concat(best); best.to_csv(os.path.join(a.out, "trusted_candidates.csv"), sep=";", index=False, float_format="%.4f")
    json.dump({"version": VERSION, "trades": int(len(reg)), "time_exits_by_tf": texits}, open(os.path.join(a.out, "time_exits.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(st[st.n >= a.min_n].groupby("category").head(6).round(3).to_string(index=False))
    print(json.dumps(texits, ensure_ascii=False)[:3000])
    print("готово", round(time.time() - t0), "с")


if __name__ == "__main__":
    main()
