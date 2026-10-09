# -*- coding: utf-8 -*-
"""Тест 02: фильтр режима [MOD4] поверх сигналов структуры (метки теста 00). Перенос: отношение
дисперсий Ло–Маккинлея, q = 2, окно 60 приращений M5, робастная дисперсия без множителя N
(как в модуле v1.2: блуждание z≈0, φ=±0,3 → z≈±2); Э41 — фильтр Гамильтона по z."""
import json, math, sys, importlib.util
import numpy as np, pandas as pd
from scipy.stats import norm
spec = importlib.util.spec_from_file_location("eng", "/tmp/p6/pc/DZ_OPT_Engine_S021.py"); eng = importlib.util.module_from_spec(spec); spec.loader.exec_module(eng)
z = np.load(sys.argv[1]); t = pd.to_datetime(z["t_open"], utc=True)
m1 = pd.DataFrame({"c": z["c"]}, index=t)
ct = m1.index.tz_convert("America/Chicago").tz_localize(None); sh = pd.Timedelta(hours=17)
st = (ct - sh).floor("5min") + sh
b = pd.DataFrame({"c": m1.c.values}, index=st).groupby(level=0).c.last()
close = pd.DatetimeIndex(b.index + pd.Timedelta(minutes=5)).tz_localize("America/Chicago", ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
b = pd.Series(b.values, index=close).dropna(); b = b[b.index.notna()]
r = np.diff(np.log(b.values)); n = 60; zs = np.full(len(b), np.nan)
for k in range(n, len(r)):
    x = r[k - n + 1:k + 1]; e = x - x.mean(); s2 = (e * e).sum()
    if s2 <= 0: continue
    va = s2 / (n - 1); agg = x[1:] + x[:-1] - 2 * x.mean()
    vc = (agg * agg).sum() / (2 * (n - 1) * (1 - 2 / n)); vr = vc / va
    th = (e[1:] ** 2 * e[:-1] ** 2).sum() / s2 ** 2
    zs[k + 1] = (vr - 1) / math.sqrt(th) if th > 0 else np.nan
reg = np.where(zs > 1.96, 1, np.where(zs < -1.96, -1, 0)); reg[np.isnan(zs)] = 9
p = np.array([1 / 3] * 3); ham = np.full(len(zs), 9)
for i, zz in enumerate(zs):                                  # Э41: порог 0,9, сохранение 0,95
    if np.isnan(zz): continue
    pr = np.array([sum(p[j] * (0.95 if j == kk else 0.025) for j in range(3)) * math.exp(-0.5 * (zz - (kk - 1) * 1.96) ** 2) for kk in range(3)])
    p = pr / pr.sum(); kb = int(p.argmax()); ham[i] = kb - 1 if p[kb] >= 0.9 else 0
lab = pd.read_csv(sys.argv[2], parse_dates=["time"]); COST = 2 / 80; rr = lab.R.values - COST
pos = np.searchsorted(b.index.asi8, lab.time.values.astype("datetime64[ns]").astype(np.int64), side="right") - 1
R0, H0 = reg[np.clip(pos, 0, None)], ham[np.clip(pos, 0, None)]
GRID = {"R0 только персистентность (умолчание)": R0 == 1, "R1 только возврат к среднему": R0 == -1,
        "R2 любой, кроме блуждания": (R0 == 1) | (R0 == -1), "R3 персистентность, Э41 Гамильтон": H0 == 1}
out, mats = {}, {}; days = lab.time.dt.tz_convert("Europe/Berlin").dt.date
for name, ok in GRID.items():
    ok = ok & (pos >= 0); pp, cc = rr[ok], rr[~ok]
    if len(pp) < 30: out[name] = {"пропущено": f"{ok.mean():.1%}", "итог": "слишком мало сигналов"}; mats[name] = pd.Series(np.where(ok, rr, 0)).groupby(days.values).sum(); continue
    wp, wc = int((pp > 0).sum()), int((cc > 0).sum())
    xs = np.random.default_rng(1).beta(1 + wp, 1 + len(pp) - wp, 200000) > np.random.default_rng(2).beta(1 + wc, 1 + len(cc) - wc, 200000)
    yr = pd.Series(rr).groupby(lab.time.dt.year).apply(lambda s: s[ok[s.index]].mean() - s[~ok[s.index]].mean())
    out[name] = {"пропущено": f"{ok.mean():.1%}", "точность пр./отс.": f"{wp/len(pp):.4f} / {wc/len(cc):.4f}", "P[пр.>отс.]": round(float(xs.mean()), 3),
                 "R пропущ.": round(float(pp.mean()), 4), "лучше по годам": "".join("+" if v > 0 else "−" for v in yr.values)}
    mats[name] = pd.Series(np.where(ok, rr, 0.0)).groupby(days.values).sum()
M = pd.DataFrame(mats).fillna(0).values; srs = M.mean(0) / M.std(0); bi = int(np.argmax(srs))
out["PBO"] = eng.pbo_cscv(M, S=10)
out["DSR лучшего (11 испытаний)"] = eng.deflated_sharpe(float(srs[bi]), float(np.var(srs)), 11, len(M), float(pd.Series(M[:, bi]).skew()), float(pd.Series(M[:, bi]).kurt() + 3))[0]
out["доли режимов M5 (возврат/блуждание/персист.)"] = [round(float((R0 == v).mean()), 3) for v in (-1, 0, 1)]
json.dump(out, open("test02_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
for k, v in out.items(): print(k, "→", v)
