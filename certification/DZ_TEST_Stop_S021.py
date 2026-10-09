# -*- coding: utf-8 -*-
"""Тест стартового стопа: постоянный 100–250 тиков и адаптивный k×ATR(M5,14) поверх сигналов структуры
(тест 00). Тройной барьер: цель 1R, вертикаль 60 и 240 минуток, касание обоих — худший исход, издержки 2 т."""
import json, math, sys, importlib.util
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as sw
from scipy.stats import norm
spec = importlib.util.spec_from_file_location("eng", "/tmp/p6/pc/DZ_OPT_Engine_S021.py"); eng = importlib.util.module_from_spec(spec); spec.loader.exec_module(eng)
z = np.load(sys.argv[1]); t = pd.to_datetime(z["t_open"], utc=True)
o, h, l, c = z["o"], z["h"], z["l"], z["c"]
lab = pd.read_csv(sys.argv[2], parse_dates=["time"])
ti = t.asi8; k = np.searchsorted(ti, lab.time.values.astype("datetime64[ns]").astype(np.int64), side="left")
d = lab.dir.values
ct = t.tz_convert("America/Chicago").tz_localize(None); sh = pd.Timedelta(hours=17)
st = (ct - sh).floor("5min") + sh
g = pd.DataFrame({"h": h, "l": l, "c": c}, index=st).groupby(level=0)
b = pd.DataFrame({"h": g.h.max(), "l": g.l.min(), "c": g.c.last()})
bc = pd.DatetimeIndex(b.index + pd.Timedelta(minutes=5)).tz_localize("America/Chicago", ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
b = b[bc.notna()]; bc = bc[bc.notna()]
pc = b.c.shift(1); tr = np.fmax(b.h - b.l, np.fmax((b.h - pc).abs(), (b.l - pc).abs())).to_numpy(copy=True); tr[0] = b.h.iloc[0] - b.l.iloc[0]
atr = np.zeros_like(tr); atr[0] = tr[0]
for i in range(1, len(tr)): atr[i] = (atr[i - 1] * 13 + tr[i]) / 14
ia = np.searchsorted(bc.asi8, ti[k], side="right") - 1
atr_t = atr[np.clip(ia, 0, None)] / 0.1                                    # ATR M5 в тиках на момент входа
CFG = {f"постоянный {s} т": np.full(len(k), float(s)) for s in (100, 150, 200, 250)}
for m in (5, 8, 12): CFG[f"адаптивный {m}×ATR M5"] = np.round(np.maximum(20, m * atr_t))
res, mats, years = {}, {}, lab.time.dt.year.values
days = lab.time.dt.tz_convert("Europe/Berlin").dt.date.values
for V in (60, 240):
    H, L = sw(h, V), sw(l, V); kk = np.minimum(k, len(H) - 1); e = o[k]
    for name, s in CFG.items():
        sl = s * 0.1; up = np.where(d > 0, e + sl, e + sl); dn = np.where(d > 0, e - sl, e - sl)
        hu = H[kk] >= up[:, None]; hd = L[kk] <= dn[:, None]
        fu = np.where(hu.any(1), hu.argmax(1), V); fd = np.where(hd.any(1), hd.argmax(1), V)
        last = c[np.minimum(k + V - 1, len(c) - 1)]
        R = np.where((fu == V) & (fd == V), (last - e) * d / sl,
            np.where(fu < fd, np.where(d > 0, 1.0, -1.0), np.where(fd < fu, np.where(d > 0, -1.0, 1.0), -1.0)))
        R = R - 2.0 / s; usd = R * s                                         # $ на 1 контракт MGC: тик = $1
        n = len(R); sr = R.mean() / R.std(); g3 = ((R - R.mean()) ** 3).mean() / R.std() ** 3; g4 = ((R - R.mean()) ** 4).mean() / R.std() ** 4
        psr = float(norm.cdf(sr * math.sqrt(n - 1) / math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr * sr))))
        yr = pd.Series(usd).groupby(years).mean()
        key = f"{name}, вертикаль {V}"
        res[key] = {"стоп, медиана т": int(np.median(s)), "точность": round(float((R > 0).mean()), 4), "R": round(float(R.mean()), 4),
                    "$ на сделку": round(float(usd.mean()), 2), "PSR[0]": round(psr, 3), "по годам $": " / ".join(f"{v:+.1f}" for v in yr.values),
                    "выход по вертикали": f"{((fu == V) & (fd == V)).mean():.0%}"}
        mats[key] = pd.Series(usd).groupby(days).sum()
M = pd.DataFrame(mats).fillna(0).values; srs = M.mean(0) / M.std(0); bi = int(np.argmax(srs))
res["лучший по дневному Шарпу"] = list(mats)[bi]
res["DSR лучшего (25 испытаний)"] = eng.deflated_sharpe(float(srs[bi]), float(np.var(srs)), 25, len(M), float(pd.Series(M[:, bi]).skew()), float(pd.Series(M[:, bi]).kurt() + 3))[0]
res["PBO по 14 вариантам"] = eng.pbo_cscv(M, S=10)
json.dump(res, open("test_stop_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
for kx, v in res.items(): print(kx, "→", v)
