# -*- coding: utf-8 -*-
"""Тест 03: фильтр линий [MOD2] поверх структуры. Исполнение: стоп 200 т, цель 1R, вертикаль 240, издержки 2 т.
Перенос линии диапазонного фильтра: диапазон = EMA(EMA(|Δc|, p), 2p−1) × m; линия не ходит против себя;
направление — знак изменения линии, при равенстве сохраняется. Голос: все включённые линии за сторону сигнала."""
import json, math, sys, importlib.util
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as sw
spec = importlib.util.spec_from_file_location("eng", "/tmp/p6/pc/DZ_OPT_Engine_S021.py"); eng = importlib.util.module_from_spec(spec); spec.loader.exec_module(eng)
z = np.load(sys.argv[1]); t = pd.to_datetime(z["t_open"], utc=True); o, h, l, c = z["o"], z["h"], z["l"], z["c"]
lab = pd.read_csv(sys.argv[2], parse_dates=["time"]); ti = t.asi8
k = np.searchsorted(ti, lab.time.values.astype("datetime64[ns]").astype(np.int64), side="left"); d = lab.dir.values
S, V = 200, 240; H, L = sw(h, V), sw(l, V); kk = np.minimum(k, len(H) - 1); e = o[k]; sl = S * 0.1
hu = H[kk] >= (e + sl)[:, None]; hd = L[kk] <= (e - sl)[:, None]
fu = np.where(hu.any(1), hu.argmax(1), V); fd = np.where(hd.any(1), hd.argmax(1), V)
last = c[np.minimum(k + V - 1, len(c) - 1)]
R = np.where((fu == V) & (fd == V), (last - e) * d / sl, np.where(fu < fd, np.where(d > 0, 1., -1.), np.where(fd < fu, np.where(d > 0, -1., 1.), -1.))) - 2.0 / S
def series(minutes):
    ct = t.tz_convert("America/Chicago").tz_localize(None); sh = pd.Timedelta(hours=17)
    st = (ct - sh).floor(f"{minutes}min") + sh
    cc = pd.Series(c, index=st).groupby(level=0).last()
    cl = pd.DatetimeIndex(cc.index + pd.Timedelta(minutes=minutes)).tz_localize("America/Chicago", ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
    return cc.values[cl.notna()], cl[cl.notna()].asi8
def line(x, p=100, m=3.0):
    a = pd.Series(np.abs(np.diff(x, prepend=x[0])))
    rng = a.ewm(span=p, adjust=False).mean().ewm(span=2 * p - 1, adjust=False).mean().values * m
    f = np.empty_like(x); f[0] = x[0]; tr = np.zeros(len(x), int); since = np.zeros(len(x), int); cur, s = 0, 10 ** 6
    for i in range(1, len(x)):
        f[i] = max(f[i - 1], x[i] - rng[i]) if x[i] > f[i - 1] else min(f[i - 1], x[i] + rng[i])
        nt = 1 if f[i] > f[i - 1] else (-1 if f[i] < f[i - 1] else cur)
        s = 0 if (cur != 0 and nt != cur) else s + 1; cur = nt; tr[i] = cur; since[i] = s
    return tr, since
vals = {}
for name, mins in (("M5", 5), ("M60", 60)):
    x, cl = series(mins); tr, since = line(x)
    j = np.searchsorted(cl, ti[k], side="right") - 1
    vals[name] = (np.where(j >= 100, tr[np.clip(j, 0, None)], 0), np.where(j >= 0, since[np.clip(j, 0, None)], 0))
agree = lambda nm, minbars=0: (vals[nm][0] == d) & (vals[nm][1] >= minbars)
GRID = {"L0 линии M5 и M60 (умолчание)": agree("M5") & agree("M60"), "L1 только M60": agree("M60"),
        "L2 только M5": agree("M5"), "L3 M5 и M60, Э40 не меньше 10 баров после переворота": agree("M5", 10) & agree("M60", 10)}
out, mats = {"база": {"сигналов": len(R), "точность": round(float((R > 0).mean()), 4), "$ на сделку": round(float((R * S).mean()), 2)}}, {}
days = lab.time.dt.tz_convert("Europe/Berlin").dt.date.values
for name, ok in GRID.items():
    pp, cc_ = R[ok], R[~ok]; wp, wc = int((pp > 0).sum()), int((cc_ > 0).sum())
    xs = np.random.default_rng(1).beta(1 + wp, 1 + len(pp) - wp, 200000) > np.random.default_rng(2).beta(1 + wc, 1 + len(cc_) - wc, 200000)
    yr = pd.Series(R * S).groupby(lab.time.dt.year).apply(lambda s_: s_[ok[s_.index]].mean() - s_[~ok[s_.index]].mean())
    out[name] = {"пропущено": f"{ok.mean():.1%}", "точность пр./отс.": f"{wp/len(pp):.4f} / {wc/len(cc_):.4f}", "P[пр.>отс.]": round(float(xs.mean()), 3),
                 "$ пропущ./отс.": f"{(pp*S).mean():+.2f} / {(cc_*S).mean():+.2f}", "лучше по годам": "".join("+" if v > 0 else "−" for v in yr.values)}
    mats[name] = pd.Series(np.where(ok, R * S, 0.0)).groupby(days).sum()
M = pd.DataFrame(mats).fillna(0).values; srs = M.mean(0) / M.std(0); bi = int(np.argmax(srs))
out["PBO"] = eng.pbo_cscv(M, S=10); out["DSR лучшего (29 испытаний)"] = eng.deflated_sharpe(float(srs[bi]), float(np.var(srs)), 29, len(M), float(pd.Series(M[:, bi]).skew()), float(pd.Series(M[:, bi]).kurt() + 3))[0]
json.dump(out, open("test03_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
for kx, v in out.items(): print(kx, "→", v)
