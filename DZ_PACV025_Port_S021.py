#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_PACV025_Port_S021.py — перенос логики разметки индикатора PACV025MarketStructureCoreFix (v0.2.7) и её
проверка на реестрах движений, v1.0 (2026-10-05).

ИЗВЛЕЧЁННАЯ ЛОГИКА (по исходнику индикатора; детектор пивотов PACPivotDetector в файле отсутствует — принят
стандартный: экстремум центра окна 2L+1, слева строго, справа нестрого, как у PAC проекта):
  1. Два контура: внутренний L = 5 и свинговый L = 50 (у нашего MOD1 — 3 и 10).
  2. Классификация пивота по предыдущему того же типа: High > prevHigh → HH иначе LH; Low > prevLow → HL иначе LL.
  3. Машина структуры (на закрытии бара): тренд не определён → первый пробой задаёт тренд без события;
     в бычьем: close < lastLow → CHoCH, а CHoCH+ если ПЕРЕД этим последний пивот High не обновил максимум
     («несостоявшийся HH» — LH); зеркально в медвежьем; BOS — пробой по тренду, но только после того, как в истории
     был хотя бы один CHoCH (priorEventConfirmed). Уровень считается один раз (флаг broken до нового пивота).
     У нашего MOD1 CHoCH+ = пробой ЗА предыдущий уровень (probe > PrevHigh) — другое правило; BOS без ожидания CHoCH.
  4. Сильные/слабые экстремумы, два режима:
     VolumeRatio — объём «ноги» между подтверждениями пивотов одного типа (сумма объёма баров) сравнивается с
       предыдущей такой ногой: min/max ≥ 50 % → Strong (объём сопоставим), иначе Weak (объём изменился более чем вдвое);
     TrendSide — в медвежьем тренде пивоты High сильные, Low слабые; в бычьем — Low сильные, High слабые;
       при неопределённом тренде метки нет.
  5. Сканер старших ТФ 15/60/240/1440 — та же машина со свинговым L на каждой серии.
ПРОВЕРКА: (а) точность и покрытие начала движений (реестры DZ_MOVE) для CHoCH+ по правилу PACV025 против нашего
правила; (б) ход движения после якоря-пивота в зависимости от метки Strong/Weak обоих режимов.
==========================================================================================
"""
import argparse, importlib.util, json, math, os, time
import numpy as np
import pandas as pd

VERSION = "DZ_PACV025_Port_S021-v1.0 (2026-10-05)"
HERE = os.path.dirname(os.path.abspath(__file__))
TICK = 0.1


def load(name, fn):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn)); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def pivots(h, l, L):
    """Пивоты центра окна 2L+1; возвращает булевы массивы по индексу центра (подтверждение на баре centre+L)."""
    n = len(h); ph = np.zeros(n, bool); pl = np.zeros(n, bool)
    hs, ls = pd.Series(h), pd.Series(l)
    left_max = hs.rolling(L).max().shift(1); right_max = hs[::-1].rolling(L).max().shift(1)[::-1]
    left_min = ls.rolling(L).min().shift(1); right_min = ls[::-1].rolling(L).min().shift(1)[::-1]
    ph[:] = (hs > left_max) & (hs >= right_max); pl[:] = (ls < left_min) & (ls <= right_min)
    ph[:L] = False; ph[n - L:] = False; pl[:L] = False; pl[n - L:] = False
    return ph, pl


def pacv025(h, l, c, v, L):
    """Одна машина PACV025 (один контур L). Возвращает события по барам и таблицу пивотов с метками и силой."""
    n = len(c); ph, pl = pivots(h, l, L)
    prevH = prevL = math.nan            # для классификации HH/HL/LH/LL
    lastH = lastL = math.nan; lastHbar = lastLbar = -1
    prevPivH = prevPivL = math.nan      # для несостоявшегося экстремума
    failedHH = failedLL = False; prior = False; trend = 0; hBroken = lBroken = False
    volH = volL = 0.0; prevLegH = prevLegL = math.nan
    events = [[] for _ in range(n)]; piv = []
    for i in range(n):
        volH += v[i]; volL += v[i]
        cI = i - L                      # подтверждаемый центр
        if cI >= 0 and ph[cI]:
            px = h[cI]; lab = "" if math.isnan(prevH) else ("HH" if px > prevH else "LH"); prevH = px
            if not math.isnan(prevPivH): failedHH = True if px < prevPivH else (False if px > prevPivH else failedHH)
            prevPivH = px; lastH = px; lastHbar = cI; hBroken = False
            sv = "" if math.isnan(prevLegH) or prevLegH <= 0 or volH <= 0 else ("Strong" if min(prevLegH, volH) / max(prevLegH, volH) >= 0.5 else "Weak")
            st = "" if trend == 0 else ("Strong" if trend < 0 else "Weak")
            piv.append({"bar": cI, "confirm_bar": i, "kind": "H", "label": lab, "price": px, "strong_vol": sv, "strong_trend": st, "leg_vol": volH, "prev_leg_vol": prevLegH})
            prevLegH = volH; volH = 0.0
        if cI >= 0 and pl[cI]:
            px = l[cI]; lab = "" if math.isnan(prevL) else ("HL" if px > prevL else "LL"); prevL = px
            if not math.isnan(prevPivL): failedLL = True if px > prevPivL else (False if px < prevPivL else failedLL)
            prevPivL = px; lastL = px; lastLbar = cI; lBroken = False
            sv = "" if math.isnan(prevLegL) or prevLegL <= 0 or volL <= 0 else ("Strong" if min(prevLegL, volL) / max(prevLegL, volL) >= 0.5 else "Weak")
            st = "" if trend == 0 else ("Strong" if trend > 0 else "Weak")
            piv.append({"bar": cI, "confirm_bar": i, "kind": "L", "label": lab, "price": px, "strong_vol": sv, "strong_trend": st, "leg_vol": volL, "prev_leg_vol": prevLegL})
            prevLegL = volL; volL = 0.0
        if math.isnan(lastH) or math.isnan(lastL): continue
        close = c[i]
        if trend == 0:
            if close > lastH and not hBroken: trend = 1; hBroken = True
            elif close < lastL and not lBroken: trend = -1; lBroken = True
            continue
        if trend > 0:
            if close < lastL and not lBroken:
                events[i].append(("CHOCH+" if failedHH else "CHOCH", -1)); trend = -1; lBroken = True; failedHH = False; prior = True
            elif close > lastH and not hBroken and prior:
                events[i].append(("BOS", 1)); hBroken = True
        else:
            if close > lastH and not hBroken:
                events[i].append(("CHOCH+" if failedLL else "CHOCH", 1)); trend = 1; hBroken = True; failedLL = False; prior = True
            elif close < lastL and not lBroken and prior:
                events[i].append(("BOS", -1)); lBroken = True
    return events, pd.DataFrame(piv)


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--npz", required=True); ap.add_argument("--volume-nt", required=True); ap.add_argument("--moves", default="moves"); ap.add_argument("--out", default="pacv025")
    ap.add_argument("--start", default="2015-01-01"); ap.add_argument("--end", default="2019-01-01"); ap.add_argument("--tfs", nargs="*", type=int, default=[15, 60, 120, 240]); ap.add_argument("--start-share", type=float, default=0.2)
    a = ap.parse_args(); t0 = time.time(); os.makedirs(a.out, exist_ok=True)
    M = load("dz_ms", "DZ_MS_Market_S021.py")
    m1 = M.load_npz(a.npz); m1 = m1[(m1.index >= pd.Timestamp(a.start, tz="UTC")) & (m1.index < pd.Timestamp(a.end, tz="UTC"))]
    nt = M.load_nt_volume(a.volume_nt, a.start, a.end); jj = m1.join(nt[["v"]], how="left", rsuffix="_nt"); m1["v"] = jj["v_nt"].fillna(0.0).to_numpy()
    m1 = M.fill_gaps(m1); bars = M.resample_all(m1, a.tfs)
    rows_prec = []; rows_strong = []
    for tf in a.tfs:
        b = bars[tf].reset_index(drop=True); h = b["h"].to_numpy(float); l = b["l"].to_numpy(float); c = b["c"].to_numpy(float); v = b["v"].to_numpy(float)
        close = pd.DatetimeIndex(b["close_utc"]).to_numpy("datetime64[ns]"); open_t = pd.DatetimeIndex(b["open_utc"]).to_numpy("datetime64[ns]")
        mk = []
        for L, scope in ((5, "int5"), (50, "sw50"), (3, "int3"), (10, "sw10")):
            ev, piv = pacv025(h, l, c, v, L)
            for i, lst in enumerate(ev):
                for kind, d in lst: mk.append({"t": close[i], "type": f"{kind} {scope}", "dir": d, "px": c[i]})
            piv["scope"] = scope; piv["tf"] = tf; piv["time"] = open_t[piv["bar"].to_numpy()]
            piv.to_csv(os.path.join(a.out, f"pivots_tf{tf}_{scope}.csv"), sep=";", index=False, float_format="%.4f")
            if scope == "int5":
                piv5 = piv
        mk = pd.DataFrame(mk).sort_values("t").reset_index(drop=True); mt = mk["t"].to_numpy()
        mv = pd.read_csv(os.path.join(a.moves, f"moves_tf{tf}.csv"), sep=";")
        a_t = pd.to_datetime(mv["anchor_utc"], utc=True).values.astype("datetime64[ns]"); p_t = pd.to_datetime(mv["peak_utc"], utc=True).values.astype("datetime64[ns]") + np.timedelta64(tf, "m")
        i0 = np.searchsorted(mt, a_t, "left"); i1 = np.searchsorted(mt, p_t, "right"); mdir = mv["dir"].to_numpy(); ap_ = mv["anchor_px"].to_numpy(float); pp = mv["peak_px"].to_numpy(float)
        start_hits = {}; covered = {}
        for k in range(len(mv)):
            sub = mk.iloc[i0[k]:i1[k]]; sub = sub[sub["dir"].to_numpy() == mdir[k]]
            if len(sub) == 0: continue
            move = (pp[k] - ap_[k]) * mdir[k]
            prog = (sub["px"].to_numpy(float) - ap_[k]) * mdir[k] / move if move > 0 else np.full(len(sub), 9.0)
            st = sub[prog <= a.start_share]
            for ty in st["type"].unique(): covered[ty] = covered.get(ty, 0) + 1
            for ty, cnt in st["type"].value_counts().items(): start_hits[ty] = start_hits.get(ty, 0) + int(cnt)
        totals = mk["type"].value_counts()
        for ty in totals.index:
            n_all = int(totals[ty]); k_ = start_hits.get(ty, 0)
            rows_prec.append({"move_tf": tf, "marker": ty, "markers_total": n_all, "at_start": k_, "precision_start": k_ / n_all, "moves": len(mv), "covered": covered.get(ty, 0), "coverage": covered.get(ty, 0) / len(mv)})
        # сила якоря: внутренний пивот (L = 5) на баре якоря
        pv = piv5.copy(); pv["t"] = open_t[pv["bar"].to_numpy()]
        key = {(t, k): r for t, k, r in zip(pv["t"].to_numpy(), pv["kind"].to_numpy(), pv.itertuples())}
        for mode in ("strong_vol", "strong_trend"):
            lab = []
            for k in range(len(mv)):
                r = key.get((a_t[k], "L" if mdir[k] > 0 else "H")); lab.append(getattr(r, mode) if r is not None else "нет пивота")
            mv[mode] = lab
            g = mv.groupby(mode).agg(n=("id", "size"), move_med=("move_ticks", "median"), move_mean=("move_ticks", "mean"), bars_med=("bars", "median"), big_share=("move_ticks", lambda x: float((x >= mv.move_ticks.median()).mean())))
            for lbl, r in g.iterrows(): rows_strong.append({"tf": tf, "mode": mode, "label": lbl, "n": int(r.n), "move_med": r.move_med, "move_mean": r.move_mean, "bars_med": r.bars_med, "share_above_median": r.big_share})
        print(time.strftime("%H:%M:%S"), f"ТФ {tf}m: маркеров {len(mk):,}, движений {len(mv):,}, {time.time()-t0:.0f} с", flush=True)
    P = pd.DataFrame(rows_prec); P.to_csv(os.path.join(a.out, "start_precision_pacv025.csv"), sep=";", index=False, float_format="%.4f")
    S = pd.DataFrame(rows_strong); S.to_csv(os.path.join(a.out, "anchor_strength.csv"), sep=";", index=False, float_format="%.4f")
    pd.set_option("display.width", 220)
    print(P[P.marker.str.startswith("CHOCH")].sort_values(["move_tf", "precision_start"], ascending=[True, False]).round(3).to_string(index=False))
    print(S.round(2).to_string(index=False)); print("готово", round(time.time() - t0), "с")


if __name__ == "__main__":
    main()
