# -*- coding: utf-8 -*-
"""Тест 01: фильтр времени [MOD3] поверх сигналов структуры (метки теста 00, стоп 80 т). Перенос
вердикта модуля v1.2: окна по Берлину, включительно; новые входы до 21:30; пн–пт."""
import json, math, sys, importlib.util
import numpy as np, pandas as pd
from scipy.stats import beta, norm
spec = importlib.util.spec_from_file_location("eng", "/tmp/p6/pc/DZ_OPT_Engine_S021.py"); eng = importlib.util.module_from_spec(spec); spec.loader.exec_module(eng)
lab = pd.read_csv(sys.argv[1], parse_dates=["time"]); COST = 2 / 80
b = lab.time.dt.tz_convert("Europe/Berlin"); hms = b.dt.hour * 10000 + b.dt.minute * 100 + b.dt.second
inw = lambda s, e: (hms >= s) & (hms <= e) if s <= e else (hms >= s) | (hms <= e)
wd = b.dt.dayofweek < 5
GRID = {"G0 умолчание 01:00–08:00 и 09:30–18:30": inw(10000, 80000) | inw(93000, 183000),
        "G1 только 09:30–18:30": inw(93000, 183000),
        "G2 только 01:00–08:00": inw(10000, 80000),
        "G3 США 14:30–22:00": inw(143000, 220000)}
r = lab.R.values - COST; days = lab.time.dt.tz_convert("Europe/Berlin").dt.date
out, mats = {}, {}
for name, m in GRID.items():
    ok = (m & wd & (hms <= 213000)).values
    p, c = r[ok], r[~ok]; wp, wc = int((p > 0).sum()), int((c > 0).sum())
    a1, b1, a2, b2 = 1 + wp, 1 + len(p) - wp, 1 + wc, 1 + len(c) - wc
    xs = np.random.default_rng(1).beta(a1, b1, 200000) > np.random.default_rng(2).beta(a2, b2, 200000)
    sr = p.mean() / p.std(); g3 = ((p - p.mean()) ** 3).mean() / p.std() ** 3; g4 = ((p - p.mean()) ** 4).mean() / p.std() ** 4
    psr = float(norm.cdf(sr * math.sqrt(len(p) - 1) / math.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr * sr)))
    yr = pd.Series(r).groupby(lab.time.dt.year).apply(lambda s: s[ok[s.index]].mean() - s[~ok[s.index]].mean())
    out[name] = {"пропущено": f"{ok.mean():.1%}", "точн. пропущ.": round(wp / len(p), 4), "точн. отсеч.": round(wc / len(c), 4),
                 "P[пропущ.>отсеч.]": round(float(xs.mean()), 3), "R пропущ.": round(float(p.mean()), 4), "R отсеч.": round(float(c.mean()), 4),
                 "PSR[0] пропущ.": round(psr, 3), "лучше по годам": "".join("+" if v > 0 else "−" for v in yr.values)}
    mats[name] = pd.Series(np.where(ok, r, 0.0)).groupby(days.values).sum()
M = pd.DataFrame(mats).fillna(0).values
out["PBO по сетке (CSCV)"] = eng.pbo_cscv(M, S=10)
srs = M.mean(0) / M.std(0); best = int(np.argmax(srs)); x = M[:, best]
dsr, sr0 = eng.deflated_sharpe(float(srs[best]), float(np.var(srs)), 7, len(M), float(pd.Series(x).skew()), float(pd.Series(x).kurt() + 3))
out["DSR лучшего (7 испытаний в реестре)"] = {"вариант": list(GRID)[best], "DSR": dsr, "порог случайного лучшего": sr0}
json.dump(out, open("test01_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
for k, v in out.items(): print(k, "→", v)
