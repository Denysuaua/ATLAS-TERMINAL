#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_RS_Segments_S021.py — библиотека контрольных участков и измерения к плану исследований,
v1.0 (2026-10-04). Работает на выходах DZ_MS_Market_S021.py (реестры и минутная разметка).

ЧТО СЧИТАЕТ (обучающий период, проверочный не трогается)
  segments   библиотека контрольных участков по ТФ: ТРЕНД (тренды структуры с MFE ≥ 3·MAE и ходом
             ≥ 2 медиан), ФЛЭТ (пробеги состояния S от 8 баров и блуждания с эффективностью ≤ 0,2),
             ХАОС (верхний дециль волатильности при эффективности ≤ 0,2); у каждого — границы UTC и по
             Берлину, ход, MFE — потолок захвата потенциала (знаменатель метрики MFE capture).
  tfs        иерархия таймфреймов по данным: сигналов в месяц, запаздывание подтверждения, доля ложных
             сломов (MFE ≤ MAE), реализуемый PnL, захват потенциала трендов структуры = ход/MFE.
  handoff    проверка условия эстафеты «Хёрст > 0,5 → разрешить структуру на 60–240m»: причинный Хёрст
             (R/S, 128 баров) на старте тренда против его реализуемого PnL.
  timeexit   рубежи 12:30 и 22:30 по Берлину: продолжение или возврат движения после рубежа, ночной
             разрыв, MAE после 12:30 — ожидание календарного выхода без технических сигналов.

ЭКСПЕРИМЕНТЫ, выключены
  Э56 --exit-grid: та же оценка рубежей на сетке ±60 мин с шагом 15 — каждая точка сетки есть
      испытание (AFML с. 205); результат — только для реестра испытаний, не для выбора.
  Э57 --hurst-window N: окно Хёрста для эстафеты (по умолчанию 128, как [H04] модуля MOD10).
==========================================================================================
"""
import argparse, importlib.util, json, math, os, sys
import numpy as np
import pandas as pd

VERSION = "DZ_RS_Segments_S021-v1.0 (2026-10-04)"
HERE = os.path.dirname(os.path.abspath(__file__))
TZ_REP = "Europe/Berlin"
TICK = 0.1


def ms():
    s = importlib.util.spec_from_file_location("dz_ms", os.path.join(HERE, "DZ_MS_Market_S021.py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def berlin(ts):
    return pd.DatetimeIndex(pd.to_datetime(ts, utc=True)).tz_convert(TZ_REP).strftime("%Y-%m-%d %H:%M")


def cmd_segments(a):
    tr = pd.read_csv(os.path.join(a.out, "registry_trends.csv"), sep=";")
    st = pd.read_csv(os.path.join(a.out, "registry_states.csv"), sep=";")
    rows = []
    for tf, g in tr.groupby("tf"):
        med = g["move_ticks_realized"].abs().median()
        sel = g[(g["mfe_ticks"] >= 3 * g["mae_ticks"]) & (g["move_ticks_realized"] >= 2 * med) & (g["bars"] >= 20)]
        for r in sel.itertuples():
            rows.append({"tf": tf, "class": "ТРЕНД", "direction": r.trend, "start_utc": r.start_valid_utc, "end_utc": r.end_valid_utc,
                         "bars": r.bars, "minutes": r.minutes, "move_ticks": r.move_ticks_realized, "mfe_ticks": r.mfe_ticks, "mae_ticks": r.mae_ticks,
                         "efficiency": r.efficiency, "hurst": r.hurst, "vol_ticks": r.vol_ticks, "potential_ceiling_ticks": r.mfe_ticks})
    for tf, g in st.groupby("tf"):
        flat = g[((g["state"] == "S") & (g["bars"] >= 8)) | ((g["state"] == "W") & (g["efficiency"] <= 0.2) & (g["bars"] >= 24))]
        for r in flat.itertuples():
            rows.append({"tf": tf, "class": "ФЛЭТ", "direction": r.state, "start_utc": r.start_open_utc, "end_utc": r.end_close_utc,
                         "bars": r.bars, "minutes": r.minutes, "move_ticks": r.move_ticks, "mfe_ticks": r.range_ticks, "mae_ticks": np.nan,
                         "efficiency": r.efficiency, "hurst": r.hurst, "vol_ticks": r.vol_ticks, "potential_ceiling_ticks": r.range_ticks})
        v90 = g["vol_ticks"].quantile(0.9)
        chaos = g[(g["vol_ticks"] >= v90) & (g["efficiency"] <= 0.2) & (g["bars"] >= 12)]
        for r in chaos.itertuples():
            rows.append({"tf": tf, "class": "ХАОС", "direction": r.state, "start_utc": r.start_open_utc, "end_utc": r.end_close_utc,
                         "bars": r.bars, "minutes": r.minutes, "move_ticks": r.move_ticks, "mfe_ticks": r.range_ticks, "mae_ticks": np.nan,
                         "efficiency": r.efficiency, "hurst": r.hurst, "vol_ticks": r.vol_ticks, "potential_ceiling_ticks": r.range_ticks})
    lib = pd.DataFrame(rows)
    lib["start_berlin"] = berlin(lib["start_utc"]); lib["end_berlin"] = berlin(lib["end_utc"].fillna(lib["start_utc"]))
    lib = lib.sort_values(["tf", "class", "start_utc"])
    lib.to_csv(os.path.join(a.out, "control_segments_all.csv"), sep=";", index=False, float_format="%.3f")
    # короткий список: по 20 на класс и ТФ — самые выраженные
    top = []
    for (tf, cl), g in lib.groupby(["tf", "class"]):
        key = "move_ticks" if cl == "ТРЕНД" else ("bars" if cl == "ФЛЭТ" else "vol_ticks")
        top.append(g.sort_values(key, ascending=False).head(a.top))
    top = pd.concat(top)
    top.to_csv(os.path.join(a.out, "control_segments_top.csv"), sep=";", index=False, float_format="%.3f")
    summ = lib.groupby(["tf", "class"]).agg(n=("tf", "size"), bars_med=("bars", "median"), move_med=("move_ticks", lambda x: float(np.nanmedian(np.abs(x)))),
                                             ceiling_med=("potential_ceiling_ticks", "median"), eff_med=("efficiency", "median"), hurst_med=("hurst", "median"))
    summ.to_csv(os.path.join(a.out, "control_segments_summary.csv"), sep=";", float_format="%.3f")
    print(summ.round(2))


def cmd_tfs(a):
    tr = pd.read_csv(os.path.join(a.out, "registry_trends.csv"), sep=";")
    legs = pd.read_csv(os.path.join(a.out, "registry_legs.csv"), sep=";")
    man = json.load(open(os.path.join(a.out, "manifest.json"), encoding="utf-8"))
    months = (pd.Timestamp(man["end"]) - pd.Timestamp(man["start"])).days / 30.44
    rows = []
    for tf, g in tr.groupby("tf"):
        g = g.dropna(subset=["pnl_realized_usd"])
        cap = (g["move_ticks_realized"] / g["mfe_ticks"].replace(0, np.nan)).clip(-5, 1)
        rows.append({"tf": tf, "trends": len(g), "trends_per_month": len(g) / months, "lag_minutes": man["n"] * tf,
                     "false_share": float((g["mfe_ticks"] <= g["mae_ticks"]).mean()), "pnl_mean_usd": g["pnl_realized_usd"].mean(),
                     "pnl_sum_usd": g["pnl_realized_usd"].sum(), "win_share": float((g["pnl_realized_usd"] > 0).mean()),
                     "profit_factor": g.loc[g["pnl_realized_usd"] > 0, "pnl_realized_usd"].sum() / max(1e-9, -g.loc[g["pnl_realized_usd"] < 0, "pnl_realized_usd"].sum()),
                     "mfe_med": g["mfe_ticks"].median(), "mae_med": g["mae_ticks"].median(), "capture_of_mfe_med": float(cap.median()),
                     "capture_share_ge_50pct": float((cap >= 0.5).mean()), "leg_eff_med": legs.loc[legs["tf"] == tf, "efficiency"].median()})
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(a.out, "tf_hierarchy.csv"), sep=";", index=False, float_format="%.3f")
    print(t.round(3).to_string(index=False))


def cmd_handoff(a):
    M = ms()
    tr = pd.read_csv(os.path.join(a.out, "registry_trends.csv"), sep=";")
    man = json.load(open(os.path.join(a.out, "manifest.json"), encoding="utf-8"))
    m1 = M.load_npz(a.npz)
    m1 = m1[(m1.index >= pd.Timestamp(man["start"], tz="UTC")) & (m1.index < pd.Timestamp(man["end"], tz="UTC"))]
    if man.get("filled_minutes"):
        m1 = M.fill_gaps(m1)
    bars = M.resample_all(m1, [60, 120, 240])
    W = a.hurst_window
    rows = []
    for tf in (60, 120, 240):
        b = bars[tf].reset_index(drop=True); c = b["c"].to_numpy(float); r = np.diff(c)
        H = np.full(len(c), np.nan)
        for i in range(W, len(c)):
            H[i] = M.hurst_rs(r[i - W:i])
        g = tr[tr["tf"] == tf].dropna(subset=["pnl_realized_usd"]).copy()
        g["hurst_at_start"] = H[np.clip(g["start_conf_bar"].astype(int).to_numpy(), 0, len(H) - 1)]
        for thr in (0.5, 0.55):
            hi = g[g["hurst_at_start"] > thr]; lo = g[g["hurst_at_start"] <= thr]
            rows.append({"tf": tf, "hurst_threshold": thr, "n_above": len(hi), "n_below": len(lo),
                         "pnl_mean_above": hi["pnl_realized_usd"].mean(), "pnl_mean_below": lo["pnl_realized_usd"].mean(),
                         "win_above": float((hi["pnl_realized_usd"] > 0).mean()) if len(hi) else np.nan, "win_below": float((lo["pnl_realized_usd"] > 0).mean()) if len(lo) else np.nan,
                         "mfe_above": hi["mfe_ticks"].median(), "mfe_below": lo["mfe_ticks"].median(),
                         "share_time_above": float(np.nanmean(H > thr))})
        g.to_csv(os.path.join(a.out, f"handoff_hurst_trends_{tf}m.csv"), sep=";", index=False, float_format="%.3f")
    t = pd.DataFrame(rows); t.to_csv(os.path.join(a.out, "handoff_hurst.csv"), sep=";", index=False, float_format="%.3f")
    print(t.round(3).to_string(index=False))


def cmd_timeexit(a):
    M = ms()
    d = M.load_labeled(a.out)
    d = d[d["filled"] == 0]
    be = d.index.tz_convert(TZ_REP)
    df = pd.DataFrame({"c": d["c"].to_numpy(float), "h": d["h"].to_numpy(float), "l": d["l"].to_numpy(float)}, index=be)
    df["date"] = df.index.date; df["tod"] = df.index.hour * 60 + df.index.minute
    marks = {"0800": 8 * 60, "1230": 12 * 60 + 30, "1430": 14 * 60 + 30, "1700": 17 * 60, "2230": 22 * 60 + 30}
    if a.exit_grid:
        for off in range(-60, 61, 15):
            if off: marks[f"1230{off:+d}"] = 12 * 60 + 30 + off; marks[f"2230{off:+d}"] = 22 * 60 + 30 + off
    piv = {}
    for name, m in marks.items():
        sub = df[df["tod"] <= m].groupby("date")["c"].last()
        piv[name] = sub
    P = pd.DataFrame(piv)
    P["next0800"] = P["0800"].shift(-1)
    # дневные пути после рубежей для MAE/MFE
    def excursion(from_m, to_m):
        seg = df[(df["tod"] > from_m) & (df["tod"] <= to_m)]
        g = seg.groupby("date"); return g["h"].max(), g["l"].min()
    h1, l1 = excursion(marks["1230"], marks["2230"])
    P["hi_after1230"], P["lo_after1230"] = h1, l1
    P = P.dropna(subset=["0800", "1230", "2230"])
    r = {}
    pre = (P["1230"] - P["0800"]) / TICK; sgn = np.sign(pre)
    for name, col in [("12:30→14:30", "1430"), ("12:30→17:00", "1700"), ("12:30→22:30", "2230")]:
        post = (P[col] - P["1230"]) / TICK
        r[name] = {"дней": int(post.notna().sum()), "продолжение, тиков (средн.)": float((sgn * post).mean()), "медиана": float((sgn * post).median()),
                   "доля продолжений": float(((sgn * post) > 0).mean()), "|ход до 12:30| медиана": float(pre.abs().median())}
    mae_after = np.where(sgn > 0, (P["1230"] - P["lo_after1230"]) / TICK, (P["hi_after1230"] - P["1230"]) / TICK)
    mfe_after = np.where(sgn > 0, (P["hi_after1230"] - P["1230"]) / TICK, (P["1230"] - P["lo_after1230"]) / TICK)
    r["после 12:30 до 22:30"] = {"MAE против утреннего направления, тиков (мед.)": float(np.nanmedian(mae_after)), "MFE по утреннему направлению (мед.)": float(np.nanmedian(mfe_after)),
                                  "доля дней MAE > |ход до 12:30|": float(np.nanmean(mae_after > pre.abs()))}
    pre2 = (P["2230"] - P["0800"]) / TICK; sgn2 = np.sign(pre2); night = (P["next0800"] - P["2230"]) / TICK
    r["22:30→08:00 следующего дня"] = {"дней": int(night.notna().sum()), "продолжение дневного движения, тиков (средн.)": float((sgn2 * night).mean()),
                                        "медиана": float((sgn2 * night).median()), "доля продолжений": float(((sgn2 * night) > 0).mean()),
                                        "|ночной ход| медиана, тиков": float(night.abs().median()), "|ночной ход| 95-й процентиль": float(night.abs().quantile(0.95)),
                                        "|ход дня 08:00→22:30| медиана": float(pre2.abs().median())}
    if a.exit_grid:
        grid = {}
        for off in range(-60, 61, 15):
            k = f"1230{off:+d}" if off else "1230"
            post = (P["2230"] - P[k]) / TICK; s = np.sign((P[k] - P["0800"]) / TICK)
            grid[f"12:30{off:+d}"] = float((s * post).mean())
        r["Э56 сетка 12:30±60"] = grid
    json.dump(r, open(os.path.join(a.out, "timeexit_berlin.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    P.to_csv(os.path.join(a.out, "timeexit_daily.csv"), sep=";", float_format="%.2f")
    print(json.dumps(r, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("segments", "tfs", "handoff", "timeexit"):
        p = sub.add_parser(name); p.add_argument("--out", default="train"); p.add_argument("--npz")
        p.add_argument("--top", type=int, default=20); p.add_argument("--hurst-window", type=int, default=128)
        p.add_argument("--exit-grid", action="store_true", default=False)
    a = ap.parse_args()
    {"segments": cmd_segments, "tfs": cmd_tfs, "handoff": cmd_handoff, "timeexit": cmd_timeexit}[a.cmd](a)


if __name__ == "__main__":
    main()
