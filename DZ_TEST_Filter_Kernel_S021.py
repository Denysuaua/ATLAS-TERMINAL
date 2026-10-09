# -*- coding: utf-8 -*-
"""Тест 05: адаптивное ядро [MOD9] как фильтр (ширина постоянная — адаптация ширины не перенесена). Перенос HurstRS (R/S по масштабам с вычетом ожидания Аниса–Ллойда,
H = 0,5 + наклон), ширина окна 8…40 по H в [0,37; 0,57], локально-линейная регрессия с ядром Епанечникова,
направление — знак наклона при |β| ≥ 0,5 тика/бар. Фильтр пропускает согласие и нейтраль. Серия — M5."""
import json, math, sys, importlib.util
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as sw
from scipy.special import gammaln
spec = importlib.util.spec_from_file_location("eng", "/tmp/p6/pc/DZ_OPT_Engine_S021.py"); eng = importlib.util.module_from_spec(spec); spec.loader.exec_module(eng)
z = np.load(sys.argv[1]); t = pd.to_datetime(z["t_open"], utc=True); o, h, l, c = z["o"], z["h"], z["l"], z["c"]
lab = pd.read_csv(sys.argv[2], parse_dates=["time"]); ti = t.asi8
k = np.searchsorted(ti, lab.time.values.astype("datetime64[ns]").astype(np.int64), side="left"); d = lab.dir.values
S, V = 200, 240; H, L = sw(h, V), sw(l, V); kk = np.minimum(k, len(H) - 1); e = o[k]; sl = S * 0.1
hu = H[kk] >= (e + sl)[:, None]; hd = L[kk] <= (e - sl)[:, None]
fu = np.where(hu.any(1), hu.argmax(1), V); fd = np.where(hd.any(1), hd.argmax(1), V); last = c[np.minimum(k + V - 1, len(c) - 1)]
R = np.where((fu == V) & (fd == V), (last - e) * d / sl, np.where(fu < fd, np.where(d > 0, 1., -1.), np.where(fd < fu, np.where(d > 0, -1., 1.), -1.))) - 2.0 / S
ct = t.tz_convert("America/Chicago").tz_localize(None); sh = pd.Timedelta(hours=17)
cc = pd.Series(c, index=(ct - sh).floor("5min") + sh).groupby(level=0).last()
cl = pd.DatetimeIndex(cc.index + pd.Timedelta(minutes=5)).tz_localize("America/Chicago", ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
x5 = cc.values[cl.notna()]; c5 = cl[cl.notna()].asi8; r5 = np.diff(np.log(x5))
SC = [8, 16, 32, 64]
def ealloyd(n):
    i = np.arange(1, n); return math.exp(gammaln((n - 1) / 2) - gammaln(n / 2)) / math.sqrt(math.pi) * np.sqrt((n - i) / i).sum()
LE = np.log([ealloyd(n) for n in SC]); LN = np.log(SC)
def hurst(ret):
    ys = []
    for n, le in zip(SC, LE):
        w = ret[: (len(ret) // n) * n].reshape(-1, n); dv = w - w.mean(1, keepdims=True); cs = dv.cumsum(1)
        rng = np.maximum(cs.max(1), 0) - np.minimum(cs.min(1), 0); sd = np.sqrt((dv ** 2).mean(1)); ok = sd > 0
        ys.append(math.log((rng[ok] / sd[ok]).mean()) - le)
    return 0.5 + np.polyfit(LN, ys, 1)[0]
def slope(y):
    n = len(y); xx = np.arange(n); u = (n - 1 - xx) / n; w = 1 - u * u
    xm = (w * xx).sum() / w.sum(); ym = (w * y).sum() / w.sum()
    return (w * (xx - xm) * (y - ym)).sum() / (w * (xx - xm) ** 2).sum()
j5 = np.searchsorted(c5, ti[k], side="right") - 1
def kfit(y):
    n = len(y); xx = np.arange(n); u = (n - 1 - xx) / n; w = 1 - u * u
    xm = (w * xx).sum() / w.sum(); ym = (w * y).sum() / w.sum(); sxx = (w * (xx - xm) ** 2).sum()
    b = (w * (xx - xm) * (y - ym)).sum() / sxx; res = y - (ym + b * (xx - xm))
    s2 = (w * res ** 2).sum() / max(1e-12, w.sum() - 2); se = math.sqrt(s2 / sxx) if sxx > 0 else float("nan")
    return b, (b / se if se > 0 else 0.0), se
def run(bw=20, tgate=0.0, tau=0.0):
    dirs = np.zeros(len(k), int)
    for q in range(len(k)):
        j = j5[q]
        if j < bw + 2: continue
        b, tt, se = kfit(x5[j - bw + 1:j + 1]); bt = b / 0.1
        if tau > 0 and tt != 0: seT = abs(bt / tt); bt *= tau * tau / (tau * tau + seT * seT)
        dd = int(np.sign(bt)) if abs(bt) >= 0.5 else 0
        if dd != 0 and tgate > 0 and abs(tt) < tgate: dd = 0
        dirs[q] = dd
    return dirs
GRID = {"A0 ширина 20 (умолчание)": run(), "A1 t-шлюз t ≥ 2": run(tgate=2.0), "A2 Э45 сжатие τ = 0,5": run(tau=0.5), "A3 ширина 40": run(bw=40)}
out, mats = {"база": {"$ на сделку": round(float((R * S).mean()), 2)}}, {}; days = lab.time.dt.tz_convert("Europe/Berlin").dt.date.values
for name, dirs in GRID.items():
    ok = (dirs == d) | (dirs == 0); pp, cq = R[ok], R[~ok]; wp, wc = int((pp > 0).sum()), int((cq > 0).sum())
    xs = np.random.default_rng(1).beta(1 + wp, 1 + len(pp) - wp, 200000) > np.random.default_rng(2).beta(1 + wc, 1 + len(cq) - wc, 200000)
    yr = pd.Series(R * S).groupby(lab.time.dt.year).apply(lambda s_: s_[ok[s_.index]].mean() - s_[~ok[s_.index]].mean())
    out[name] = {"пропущено": f"{ok.mean():.1%}", "точн. пр./отс.": f"{wp/len(pp):.3f}/{wc/max(1,len(cq)):.3f}", "P": round(float(xs.mean()), 3),
                 "$ пр./отс.": f"{(pp*S).mean():+.2f}/{(cq*S).mean():+.2f}", "годы": "".join("+" if v > 0 else "−" for v in yr.values)}
    mats[name] = pd.Series(np.where(ok, R * S, 0.0)).groupby(days).sum()
M = pd.DataFrame(mats).fillna(0).values; srs = M.mean(0) / M.std(0); bi = int(np.argmax(srs))
out["PBO"] = eng.pbo_cscv(M, S=10); out["DSR (38 испытаний)"] = eng.deflated_sharpe(float(srs[bi]), float(np.var(srs)), 38, len(M), float(pd.Series(M[:, bi]).skew()), float(pd.Series(M[:, bi]).kurt() + 3))[0]
json.dump(out, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
for kx, v in out.items(): print(kx, "→", v)
