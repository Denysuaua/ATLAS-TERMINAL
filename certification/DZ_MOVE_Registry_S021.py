#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_MOVE_Registry_S021.py — реестры движений по восьми ТФ и маркеры [MOD1] у начала каждого движения,
v1.0 (2026-10-05). Обучение 2015–2018; проверочный период не трогается.

ДВИЖЕНИЕ на ТФ X — ход от подтверждённого экстремума структуры до противоположного: вверх — от LL (якорь
тренда разметки DZ_MS) до наивысшего High до переворота в SHORT; вниз — зеркально. Тренд разметки причинен
(подтверждение экстремума через N = 5 баров), но сам реестр — взгляд назад: пик движения известен лишь после
переворота, поэтому реестр служит обучению модулей, а не торговле.
У каждого движения: ID, ТФ, направление, якорь (время, цена), пик (время, цена), ход в тиках и %, длительность
в барах и минутах, внутренняя структура — число подтверждённых откатов (HL в движении вверх, LH вниз),
наибольшая глубина отката в долях хода, доля времени в фазе отката.
МАРКЕРЫ. На каждом из восьми ТФ — события структуры PAC (перенос DZ_SW_Mod_Pac_S021: пивоты 3/10, пробой по
закрытию): BOS, CHoCH, CHoCH+ внутренние и свинговые. Для каждого движения записываются ВСЕ маркеры всех ТФ
того же направления внутри движения с: запаздыванием от якоря (бары ТФ движения и минуты), долей пройденного
хода в момент маркера (progress) и остатком хода (потенциал после маркера, тиков). Маркер «начала» — progress
≤ --start-share (по умолчанию 0,2).
ВЕРОЯТНОСТЬ НАЧАЛА. Для пары (ТФ движения, ТФ маркера, тип): точность = доля всех маркеров этого типа, попавших
в зону начала движения своего направления (движения покрывают всё время: пик одного — якорь следующего);
покрытие = доля движений, у начала которых есть хотя бы один такой маркер. «100 %» не достигает ни одна пара —
показаны лучшие с числом случаев и интервалом Уилсона.
КОМАНДА: python DZ_MOVE_Registry_S021.py --npz M1.npz --labels train --out moves [--min-move-ticks 0]
==========================================================================================
"""
import argparse, importlib.util, json, math, os, time
import numpy as np
import pandas as pd

VERSION = "DZ_MOVE_Registry_S021-v1.0 (2026-10-05)"
HERE = os.path.dirname(os.path.abspath(__file__))
TICK = 0.1
TFS = [1, 5, 15, 30, 45, 60, 120, 240]


def load(name, fn):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn)); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def wilson(k, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - r, c + r)


def movements(bars, ev, tf):
    """Движения из событий разметки: тренд LONG от подтверждения HH до подтверждения LL; якорь — последний LL (цена, бар)."""
    o = bars["o"].to_numpy(float); h = bars["h"].to_numpy(float); l = bars["l"].to_numpy(float); c = bars["c"].to_numpy(float)
    open_utc = pd.DatetimeIndex(bars["open_utc"]); n = len(c)
    flips = ev[(ev["swing"] == 1) | (ev["swing"] == 3)].sort_values("valid_from").reset_index(drop=True)
    # бар якоря: событие с временем anchor_time (open_utc экстремума)
    t_open = open_utc.to_numpy("datetime64[ns]")
    rows = []; cur_dir = 0; anchor_bar = None; anchor_px = np.nan; start_conf = None; pull_count = 0; pull_time = 0
    ev_all = ev.sort_values("bar").reset_index(drop=True)
    pull_events = ev_all[(ev_all["swing"] == 2) | (ev_all["swing"] == 4)]  # HL, LH
    pull_bars = pull_events["bar"].to_numpy(int); pull_kind = pull_events["swing"].to_numpy(int)
    for i in range(len(flips)):
        d = 1 if flips.loc[i, "swing"] == 1 else -1
        if d == cur_dir: continue
        at = flips.loc[i, "anchor_time"]
        ab = int(np.searchsorted(t_open, np.datetime64(at))) if pd.notna(at) else int(flips.loc[i, "bar"])
        ab = min(max(0, ab), n - 1)
        if cur_dir != 0 and anchor_bar is not None:
            # завершить предыдущее движение: пик — экстремум между якорем и якорем нового тренда (который и есть экстремум)
            end_bar = ab
            seg_h = h[anchor_bar:end_bar + 1]; seg_l = l[anchor_bar:end_bar + 1]
            if cur_dir > 0: pk = int(np.argmax(seg_h)); peak_bar = anchor_bar + pk; peak_px = seg_h[pk]
            else: pk = int(np.argmin(seg_l)); peak_bar = anchor_bar + pk; peak_px = seg_l[pk]
            move = (peak_px - anchor_px) * cur_dir
            # внутренняя структура: откаты (HL в росте / LH в падении) между якорем и пиком; глубина — по running max
            m = (pull_bars >= anchor_bar) & (pull_bars <= peak_bar) & (pull_kind == (2 if cur_dir > 0 else 4))
            npull = int(m.sum())
            depth = 0.0
            if peak_bar > anchor_bar and move > 0:
                if cur_dir > 0:
                    run = np.maximum.accumulate(h[anchor_bar:peak_bar + 1]); dd = run - l[anchor_bar:peak_bar + 1]
                else:
                    run = np.minimum.accumulate(l[anchor_bar:peak_bar + 1]); dd = h[anchor_bar:peak_bar + 1] - run
                depth = float(dd.max() / move)
            rows.append({"tf": tf, "dir": cur_dir, "anchor_bar": anchor_bar, "anchor_utc": open_utc[anchor_bar], "anchor_px": anchor_px,
                         "peak_bar": peak_bar, "peak_utc": open_utc[peak_bar], "peak_px": peak_px, "confirmed_at_utc": flips.loc[i, "valid_from"],
                         "move_ticks": move / TICK, "move_pct": move / anchor_px * 100.0, "bars": peak_bar - anchor_bar, "minutes": (peak_bar - anchor_bar) * tf,
                         "pullbacks": npull, "max_pullback_share": depth, "start_conf_bar": start_conf})
        cur_dir = d; anchor_bar = ab; anchor_px = l[ab] if d > 0 else h[ab]; start_conf = int(flips.loc[i, "conf_bar"])
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--npz", required=True); ap.add_argument("--labels", default="train"); ap.add_argument("--start", default="2015-01-01"); ap.add_argument("--end", default="2019-01-01")
    ap.add_argument("--out", default="moves"); ap.add_argument("--start-share", type=float, default=0.2); ap.add_argument("--min-move-ticks", type=float, default=0.0); ap.add_argument("--n", type=int, default=5)
    a = ap.parse_args(); t0 = time.time(); os.makedirs(a.out, exist_ok=True)
    M = load("dz_ms", "DZ_MS_Market_S021.py"); P = load("dz_port", "DZ_PORT_Chains_S021.py")
    m1 = M.load_npz(a.npz); m1 = m1[(m1.index >= pd.Timestamp(a.start, tz="UTC")) & (m1.index < pd.Timestamp(a.end, tz="UTC"))]
    m1 = M.fill_gaps(m1); bars = M.resample_all(m1, TFS)
    # маркеры по всем ТФ
    markers = {}
    for tf in TFS:
        b = bars[tf].reset_index(drop=True); ev = P.pac_series(b["h"].to_numpy(float), b["l"].to_numpy(float), b["c"].to_numpy(float))
        close = pd.DatetimeIndex(b["close_utc"]); c = b["c"].to_numpy(float); rows = []
        for i, lst in enumerate(ev):
            for (scope, kind, d) in lst: rows.append({"mtf": tf, "time_utc": close[i], "type": kind + (" swing" if scope == "sw" else ""), "dir": d, "px": c[i]})
        markers[tf] = pd.DataFrame(rows)
        print(time.strftime("%H:%M:%S"), f"маркеры {tf}m: {len(markers[tf]):,}", flush=True)
    allm = pd.concat(markers.values(), ignore_index=True); allm["t"] = pd.DatetimeIndex(allm["time_utc"]).to_numpy("datetime64[ns]")
    allm = allm.sort_values("t").reset_index(drop=True); mt = allm["t"].to_numpy()
    counts = {}; stats_rows = []; long_rows = []; summary = []
    for tf in TFS:
        b = bars[tf].reset_index(drop=True)
        ev = M.structure(b, a.n)
        mv = movements(b, ev, tf)
        mv = mv[mv.move_ticks >= a.min_move_ticks].reset_index(drop=True)
        mv.insert(0, "id", [f"M{tf}-{i:06d}" for i in range(len(mv))])
        # маркеры внутри движения своего направления
        a_t = pd.DatetimeIndex(mv["anchor_utc"]).to_numpy("datetime64[ns]"); p_t = pd.DatetimeIndex(mv["peak_utc"]).to_numpy("datetime64[ns]") + np.timedelta64(tf, "m")
        i0 = np.searchsorted(mt, a_t, side="left"); i1 = np.searchsorted(mt, p_t, side="right")
        starts_total = {}; per_move_cnt = np.zeros(len(mv), int)
        mdir = mv["dir"].to_numpy(); ap_ = mv["anchor_px"].to_numpy(float); pp = mv["peak_px"].to_numpy(float)
        for k in range(len(mv)):
            sub = allm.iloc[i0[k]:i1[k]]; sub = sub[sub["dir"].to_numpy() == mdir[k]]
            if len(sub) == 0: continue
            move = (pp[k] - ap_[k]) * mdir[k]
            prog = (sub["px"].to_numpy(float) - ap_[k]) * mdir[k] / move if move > 0 else np.full(len(sub), np.nan)
            lag_min = (sub["t"].to_numpy() - a_t[k]) / np.timedelta64(1, "m")
            for j in range(len(sub)):
                r = sub.iloc[j]; pr = float(prog[j])
                long_rows.append({"move_id": mv.loc[k, "id"], "move_tf": tf, "move_dir": int(mdir[k]), "move_ticks": mv.loc[k, "move_ticks"],
                                  "marker_tf": int(r["mtf"]), "marker_type": r["type"], "marker_time_utc": r["time_utc"], "lag_minutes": float(lag_min[j]),
                                  "lag_bars_move_tf": float(lag_min[j]) / tf, "progress": pr, "remaining_ticks": (1 - pr) * move / TICK if move > 0 else np.nan,
                                  "is_start": bool(pr <= a.start_share)})
            per_move_cnt[k] = int((prog <= a.start_share).sum())
        mv["start_markers"] = per_move_cnt
        mv.to_csv(os.path.join(a.out, f"moves_tf{tf}.csv"), sep=";", index=False, float_format="%.4f")
        counts[tf] = {"движений": int(len(mv)), "вверх": int((mv.dir > 0).sum()), "вниз": int((mv.dir < 0).sum()), "ход тиков мед.": float(mv.move_ticks.median()) if len(mv) else None,
                      "баров мед.": float(mv.bars.median()) if len(mv) else None, "откатов мед.": float(mv.pullbacks.median()) if len(mv) else None,
                      "глубина отката мед.": float(mv.max_pullback_share.median()) if len(mv) else None, "с маркером начала": float((per_move_cnt > 0).mean()) if len(mv) else None}
        print(time.strftime("%H:%M:%S"), f"движения {tf}m: {len(mv):,}, с маркером начала {counts[tf]['с маркером начала']:.1%}, {time.time()-t0:.0f} с", flush=True)
    L = pd.DataFrame(long_rows); L.to_csv(os.path.join(a.out, "markers_in_moves.csv"), sep=";", index=False, float_format="%.4f")
    # вероятность начала: точность по (ТФ движения × ТФ маркера × тип) — доля всех маркеров типа, ставших стартом движения
    totals = allm.groupby(["mtf", "type"]).size()
    S = L[L.is_start].groupby(["move_tf", "marker_tf", "marker_type"]).agg(starts=("move_id", "nunique"), hits=("marker_time_utc", "nunique")).reset_index()
    for mtf in TFS:
        nm = counts[mtf]["движений"]
        for r in S[S.move_tf == mtf].itertuples():
            n_all = int(totals.get((r.marker_tf, r.marker_type), 0)); k = int(r.hits); lo, hi = wilson(k, n_all)
            summary.append({"move_tf": mtf, "marker_tf": r.marker_tf, "marker_type": r.marker_type, "markers_total": n_all, "markers_at_start": k,
                            "precision_start": k / n_all if n_all else np.nan, "ci_lo": lo, "ci_hi": hi, "moves_total": nm, "moves_covered": int(r.starts), "coverage": r.starts / nm if nm else np.nan})
    SM = pd.DataFrame(summary); SM.to_csv(os.path.join(a.out, "marker_start_probability.csv"), sep=";", index=False, float_format="%.4f")
    best = SM[SM.markers_total >= 30].sort_values(["move_tf", "precision_start"], ascending=[True, False]).groupby("move_tf").head(5)
    best.to_csv(os.path.join(a.out, "marker_start_best.csv"), sep=";", index=False, float_format="%.4f")
    json.dump({"version": VERSION, "registries": len(TFS), "counts": counts, "start_share": a.start_share}, open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
    pd.set_option("display.width", 220); print(best.round(3).to_string(index=False)); print("готово", round(time.time() - t0), "с")


if __name__ == "__main__":
    main()
