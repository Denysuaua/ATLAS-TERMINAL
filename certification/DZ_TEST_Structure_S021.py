#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DZ_TEST_Structure_S021.py — этап 0 плана тестов: база «структура без модулей», v1.0 (2026-10-04)

Перенос логики модуля структуры [MOD1] v1.4 (DetectPivots, DetectEvents, Register) на ПК —
вторая реализация, которая сверяется с журналом мета-разметки NinjaTrader ([T27]) по
времени и типу событий. Разметка — тройной барьер (AFML 3.4): стоп S тиков, цель R × S,
вертикаль V минуток, касание обоих на одной минутке — худший исход. Вход — открытие
минутки, следующей за закрытием бара события.

  python DZ_TEST_Structure_S021.py --npz MGC_M1.npz --start 2019-01-01 --end 2022-01-01 --out base
"""
import argparse, json, math
import numpy as np, pandas as pd
from scipy.stats import beta, norm

RANK = {"BOS": 100, "CHoCH": 200, "CHoCH+": 300}


def resample(m1, minutes):
    ct = m1.index.tz_convert("America/Chicago").tz_localize(None)
    sh = pd.Timedelta(hours=17)
    st = (ct - sh).floor(f"{minutes}min") + sh
    g = pd.DataFrame({"h": m1.h.values, "l": m1.l.values, "c": m1.c.values}, index=st).groupby(level=0)
    b = pd.DataFrame({"h": g.h.max(), "l": g.l.min(), "c": g.c.last()})
    close = pd.DatetimeIndex(b.index + pd.Timedelta(minutes=minutes)).tz_localize(
        "America/Chicago", ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
    b["close_utc"] = close
    return b.dropna(subset=["close_utc"]).reset_index(drop=True)


def structure_events(b, strength, tf_tag, scope):
    """Опорные точки силы k и события пробоя закрытием — как в модуле v1.4."""
    h, l, c = b.h.values, b.l.values, b.c.values
    n, k = len(b), strength
    lastH = prevH = lastL = prevL = np.nan
    hb = lb = True; trend = 0; out = []
    lastHbar = lastLbar = -1
    for t in range(n):
        ctr = t - k
        if ctr - k >= 0:
            hc, lc = h[ctr], l[ctr]
            isH = all(hc > h[ctr - i] and hc >= h[ctr + i] for i in range(1, k + 1))
            isL = all(lc < l[ctr - i] and lc <= l[ctr + i] for i in range(1, k + 1))
            if isH and ctr != lastHbar: prevH, lastH, lastHbar, hb = lastH, hc, ctr, False
            if isL and ctr != lastLbar: prevL, lastL, lastLbar, lb = lastL, lc, ctr, False
        up = not hb and not np.isnan(lastH) and c[t] > lastH
        dn = not lb and not np.isnan(lastL) and c[t] < lastL
        if up:
            hb = True
            if trend == 0: trend = 1
            else:
                ev = "BOS" if trend > 0 else ("CHoCH+" if not np.isnan(prevH) and c[t] > prevH else "CHoCH")
                trend = 1; out.append((b.close_utc.iloc[t], 1, ev, tf_tag, scope))
        if dn:
            lb = True
            if trend == 0: trend = -1
            else:
                ev = "BOS" if trend < 0 else ("CHoCH+" if not np.isnan(prevL) and c[t] < prevL else "CHoCH")
                trend = -1; out.append((b.close_utc.iloc[t], -1, ev, tf_tag, scope))
    return out


def label(m1, events, stop_ticks, r_mult, vert, tick=0.1):
    """Тройной барьер на минутках: R-результат каждой ставки (цель +R, стоп −1, вертикаль — по закрытию)."""
    t = m1.index.asi8; o, h, l, c = m1.o.values, m1.h.values, m1.l.values, m1.c.values
    rows = []
    for ts, d, ev, tf, sc in events:
        k = np.searchsorted(t, pd.Timestamp(ts).value, side="left")    # первая минутка после закрытия бара
        if k >= len(t) - 1: continue
        e = o[k]; sl = stop_ticks * tick; pt = r_mult * sl
        up, dn = (e + pt, e - sl) if d > 0 else (e + sl, e - pt)
        res = None
        for j in range(k, min(len(t), k + vert)):
            hu, hd = h[j] >= up, l[j] <= dn
            if hu and hd: res = -1.0; break
            if hu: res = r_mult if d > 0 else -1.0; break
            if hd: res = -1.0 if d > 0 else r_mult; break
        if res is None:
            j = min(len(t) - 1, k + vert - 1); res = (c[j] - e) * d / sl
        rows.append({"time": pd.Timestamp(ts), "dir": d, "event": ev, "tf": tf, "scope": sc, "R": res, "win": res > 0})
    return pd.DataFrame(rows)


def stats(df, cost_r):
    r = df.R.values - cost_r
    n = len(r)
    if n < 10: return {"n": n}
    sr = r.mean() / r.std(); g3 = ((r - r.mean()) ** 3).mean() / r.std() ** 3; g4 = ((r - r.mean()) ** 4).mean() / r.std() ** 4
    den = 1 - g3 * sr + (g4 - 1) / 4 * sr * sr
    psr = float(norm.cdf(sr * math.sqrt(n - 1) / math.sqrt(den))) if den > 0 else float("nan")
    w = int((r > 0).sum())
    yr = df.assign(r=r).groupby(df.time.dt.year).r.mean()
    return {"n": n, "точность": round(w / n, 4), "P[p>0.5]": round(float(1 - beta.cdf(0.5, 1 + w, 1 + n - w)), 3),
            "средний R": round(float(r.mean()), 4), "PSR[0]": round(psr, 3),
            "знак по годам": "".join("+" if v > 0 else "−" for v in yr.values)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True); ap.add_argument("--start"); ap.add_argument("--end")
    ap.add_argument("--ltf", type=int, default=5); ap.add_argument("--htf", type=int, default=60)
    ap.add_argument("--stops", default="20,40,80"); ap.add_argument("--r", type=float, default=1.0)
    ap.add_argument("--vert", type=int, default=60); ap.add_argument("--cost-ticks", type=float, default=2.0)
    ap.add_argument("--out", default="base")
    a = ap.parse_args()
    z = np.load(a.npz)
    idx = pd.to_datetime(z["t_open"] if "t_open" in z.files else z["t"], utc=True)
    m1 = pd.DataFrame({"o": z["o"], "h": z["h"], "l": z["l"], "c": z["c"]}, index=idx)
    if a.start: m1 = m1[m1.index >= pd.Timestamp(a.start, tz="UTC")]
    if a.end: m1 = m1[m1.index < pd.Timestamp(a.end, tz="UTC")]
    lo, hi = resample(m1, a.ltf), resample(m1, a.htf)
    allow = lambda tf, sc, ev: tf == "LTF" or sc == "swing"        # умолчания v1.4: младший — все шесть, старший — свинговые
    evs = []
    for b, tf in ((lo, "LTF"), (hi, "HTF")):
        evs += structure_events(b, 3, tf, "internal") + structure_events(b, 10, tf, "swing")
    evs = [e for e in evs if allow(e[3], e[4], e[2])]
    # один сигнал на минутку — наивысший ранг, как Register в модуле
    best = {}
    for e in evs:
        rk = RANK[e[2]] + (40 if e[3] == "HTF" else 0) + (20 if e[4] == "swing" else 0)
        key = pd.Timestamp(e[0]).value
        if key not in best or rk > best[key][0]: best[key] = (rk, e)
    sig = [v[1] for _, v in sorted(best.items())]
    report = {"данные": f"{m1.index[0]} … {m1.index[-1]}", "минуток": len(m1), "ТФ": f"M{a.ltf}/M{a.htf}",
              "событий": len(evs), "сигналов": len(sig), "по стопам": {}}
    for s in [int(x) for x in a.stops.split(",")]:
        lab = label(m1, sig, s, a.r, a.vert)
        cost_r = a.cost_ticks / s
        rep = {"все": stats(lab, cost_r)}
        for (ev, sc, tf), g in lab.groupby(["event", "scope", "tf"]):
            rep[f"{tf} {sc} {ev}"] = stats(g, cost_r)
        report["по стопам"][f"стоп {s} т"] = rep
        lab.to_csv(f"{a.out}_labels_stop{s}.csv", index=False)
    json.dump(report, open(a.out + "_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(report, ensure_ascii=False, default=str)[:6000])


if __name__ == "__main__":
    main()
