#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_PORT_Chains_S021.py — перенос вычислительных ядер модулей на Python и измерение эстафетных
связок на реальных данных, v1.0 (2026-10-04)

СТАТУС. Это ПЕРЕНОС ядер C#-модулей v1.17 (структура PAC, адаптивное ядро MOD9, Лоренц MOD11, рычаг
MOD14, канал Калмана MOD13) формула в формулу по исходникам. Тождество с NinjaTrader НЕ доказано:
паритет проверяется командой parity-dump на вашей машине против журнала [T13]. До паритета каждое
число — «гипотеза, требует теста на машине пользователя». Вторая реализация логики допускается
только с перекрёстной сверкой (протокол доверия, раздел 6) — она здесь встроена, а не обещана.

КОНФИГУРАЦИЯ ЦЕПОЧКИ (слоты по карте эстафеты, остальные настройки — умолчания модулей):
  серия исполнения M5; структура: младший M5, старший M15; ядро MOD9 — M15; Лоренц — M5 (окно 2000,
  K = 16, шаг 4, горизонт 4); рычаг — свеча M5, кластеры из M1; Калман — младший M1, текущий M5,
  старший M60; направление по старшему, сопровождение по текущему.
  Порядок тактов NinjaTrader: при равной метке первой обрабатывается основная серия, поэтому при
  решении на закрытии M5 в момент t старшие серии видны только с закрытием < t, текущая — ≤ t.

ИСПОЛНЕНИЕ: рынок по открытию следующего бара, проскальзывание 1 тик, стоп [E03] 40 тиков по худшему
пути (касание на баре входа — выбит), окна входов и закрытие 22:30 по Берлину — умолчания [MOD3],
комиссия 0,44 $ за круг. Одна позиция за раз.

ЭКСПЕРИМЕНТЫ (цепочки в выдаче run)
  Э58 цепочка E2: сопровождение по старшему каналу M60 вместо текущего M5 — гипотеза, что стоп по нижней
      границе канала M5 с отступом 2 тика слишком тесен (в модуле — выбор [C1x] EscortTf = Higher).
  Э59 --meta-horizon N: вертикальный барьер мета-разметки N баров (по умолчанию 60, как [T29]); с N = 4 метка
      совпадает по горизонту с меткой Лоренца — проверка, не расходятся ли фильтр и разметка по горизонту.

КОМАНДЫ
  run          --npz M1.npz --volume-nt папка --start 2015-01-01 --end 2019-01-01 --out ms/chains
  parity-dump  те же аргументы, --days 2 — состояния модулей по барам для сверки с [T13]
==========================================================================================
"""
import argparse, importlib.util, json, math, os, sys, time
import numpy as np
import pandas as pd

VERSION = "DZ_PORT_Chains_S021-v1.0 (2026-10-04)"
HERE = os.path.dirname(os.path.abspath(__file__))
TICK = 0.1; TICK_USD = 1.0; COST_RT = 0.44; SLIP = 1
TZB = "Europe/Berlin"


def ms():
    s = importlib.util.spec_from_file_location("dz_ms", os.path.join(HERE, "DZ_MS_Market_S021.py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def log(m): print(time.strftime("%H:%M:%S"), m, flush=True)


# ============================================================== PAC (DZ_SW_Mod_Pac_S021 v1.4)
class PacState:
    def __init__(self, k):
        self.k = k; self.last_h = math.nan; self.last_h_bar = -1; self.prev_h = math.nan
        self.last_l = math.nan; self.last_l_bar = -1; self.prev_l = math.nan
        self.trend = 0; self.h_broken = False; self.l_broken = False


def pac_series(h, l, c, k_int=3, k_sw=10, higher=False, permit=None):
    """События структуры по барам серии: список (bar, scope, event, dir, conf, rank). Пивот: строго > слева, ≥ справа.
    Пробой — по закрытию; оба экстремума одним баром — события нет."""
    n = len(c); out = [[] for _ in range(n)]
    for scope, k in (("int", k_int), ("sw", k_sw)):
        st = PacState(k)
        for i in range(n):
            # пивоты: центр = бар i−k, окно i−2k … i
            if i >= 2 * k:
                cI = i - k; hC, lC = h[cI], l[cI]
                isH = isL = True
                for j in range(1, k + 1):
                    hL, hR, lL, lR = h[cI - j], h[cI + j], l[cI - j], l[cI + j]
                    if hC <= hL or hC < hR: isH = False
                    if lC >= lL or lC > lR: isL = False
                    if not isH and not isL: break
                if isH and cI != st.last_h_bar:
                    st.prev_h = st.last_h; st.last_h = hC; st.last_h_bar = cI; st.h_broken = False
                if isL and cI != st.last_l_bar:
                    st.prev_l = st.last_l; st.last_l = lC; st.last_l_bar = cI; st.l_broken = False
            probe = c[i]
            up = (not math.isnan(st.last_h)) and (not st.h_broken) and probe > st.last_h
            dn = (not math.isnan(st.last_l)) and (not st.l_broken) and probe < st.last_l
            if up and dn:
                st.h_broken = st.l_broken = True; continue
            if up:
                st.h_broken = True
                if st.trend == 0: st.trend = 1; continue
                ev = "BOS" if st.trend > 0 else ("CHOCH+" if (not math.isnan(st.prev_h) and probe > st.prev_h) else "CHOCH")
                st.trend = 1
                out[i].append((scope, ev, 1))
            if dn:
                st.l_broken = True
                if st.trend == 0: st.trend = -1; continue
                ev = "BOS" if st.trend < 0 else ("CHOCH+" if (not math.isnan(st.prev_l) and probe < st.prev_l) else "CHOCH")
                st.trend = -1
                out[i].append((scope, ev, -1))
    return out


CONF = {"BOS": 0.40, "CHOCH": 0.65, "CHOCH+": 0.85}
RANK = {"BOS": 100, "CHOCH": 200, "CHOCH+": 300}


def pac_candidates(ev_low, ev_high_map, n_exec):
    """Сильнейшее допущенное событие на такте исполнения: младший — все шесть, старший — три свинговых."""
    cand = {}
    for i in range(n_exec):
        best = None
        for (scope, ev, d) in ev_low[i]:
            rank = RANK[ev] + (20 if scope == "sw" else 0); conf = CONF[ev]
            if best is None or rank > best[0]: best = (rank, d, conf, f"МЛ {scope} {ev}")
        for (scope, ev, d) in ev_high_map.get(i, []):
            if scope != "sw": continue
            rank = RANK[ev] + 40 + 20; conf = CONF[ev] + 0.10
            if best is None or rank > best[0]: best = (rank, d, conf, f"СТ {scope} {ev}")
        if best: cand[i] = best
    return cand


# ============================================================== MOD9 (SwAdaptiveKernelEngine)
def kernel_fit(y, hb):
    """Епанечников, локальная прямая, x = −i; возвращает (alpha, beta, t)."""
    i = np.arange(hb); u = i / hb; w = np.where(u < 1, 1 - u * u, 0.0)
    x = -i.astype(float); yy = y[:hb]
    s0 = w.sum(); s1 = (w * x).sum(); s2 = (w * x * x).sum(); t0 = (w * yy).sum(); t1 = (w * x * yy).sum()
    d = s0 * s2 - s1 * s1
    if s0 <= 0 or d <= 1e-12 * s0 * s0: return t0 / s0, math.nan, 0.0
    a = (t0 * s2 - t1 * s1) / d; b = (s0 * t1 - s1 * t0) / d
    r = yy - (a + b * x); rss = (w * r * r).sum(); cc = ((w * (s0 * x - s1) / d) ** 2).sum()
    se = math.sqrt(max(0.0, rss / s0 * cc)); return a, b, (b / se if se > 0 else 0.0)


def kernel_series(h, l, c, bw=20, adapt=True, thr=0.5):
    """Направление ядра на каждом закрытии бара своей серии: +1/−1/0 по |наклон| ≥ 0,5 тика/бар."""
    n = len(c); dirs = np.zeros(n, np.int8); slope = np.full(n, np.nan)
    tr = np.empty(n); tr[0] = h[0] - l[0]
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    for i in range(n):
        if i < 20: continue
        hb = bw
        if adapt:
            atr5 = tr[i - 4:i + 1].mean(); atr20 = tr[i - 19:i + 1].mean()
            ratio = atr20 / atr5 if atr5 > 0 else 1.0
            hb = int(round(bw * max(0.5, min(2.0, ratio))))
        hb = max(3, hb)
        if i + 1 < hb: continue
        y = c[i::-1][:hb]
        a, b, t = kernel_fit(y, hb)
        if math.isnan(b): continue
        s = b / TICK; slope[i] = s
        dirs[i] = int(np.sign(s)) if abs(s) >= thr else 0
    return dirs, slope


# ============================================================== MOD11 (Lorentzian)
def yj(x, lam):
    x = np.asarray(x, float); out = np.empty_like(x)
    pos = x >= 0
    if abs(lam) < 1e-9: out[pos] = np.log(x[pos] + 1)
    else: out[pos] = ((x[pos] + 1) ** lam - 1) / lam
    if abs(lam - 2) < 1e-9: out[~pos] = -np.log(1 - x[~pos])
    else: out[~pos] = -((1 - x[~pos]) ** (2 - lam) - 1) / (2 - lam)
    return out


def yj_fit(x):
    """Золотое сечение по λ ∈ [−2, 2], 30 итераций — как в модуле."""
    def ll(l):
        y = yj(x, l); v = ((y - y.mean()) ** 2).mean()
        j = (np.sign(x) * np.log(np.abs(x) + 1)).sum()
        return -0.5 * len(x) * math.log(v) + (l - 1) * j if v > 0 else -math.inf
    lo, hi, gr = -2.0, 2.0, 0.6180339887
    x1 = hi - gr * (hi - lo); x2 = lo + gr * (hi - lo); f1 = ll(x1); f2 = ll(x2)
    for _ in range(30):
        if f1 < f2: lo = x1; x1 = x2; f1 = f2; x2 = lo + gr * (hi - lo); f2 = ll(x2)
        else: hi = x2; x2 = x1; f2 = f1; x1 = hi - gr * (hi - lo); f1 = ll(x1)
    return 0.5 * (lo + hi)


def lorentz_series(h, l, c, v, lookback=2000, K=16, stride=4, H=4, vote_thr=0.5, refit=100, fitwin=500, q=0.01, r=1.0):
    n = len(c); F = 5; raw = np.full((n, F), np.nan)
    atr = math.nan; prev = math.nan; rsiN = 0; rsiUp = rsiDn = 0.0; kx = math.nan; kv = 0.0; p00 = p01 = p11 = 0.0
    volring = np.zeros(20); tpv = np.zeros(20); vi = 0; vcnt = 0
    for i in range(n):
        hh, ll, cc, vv = h[i], l[i], c[i], v[i]
        tr = hh - ll if math.isnan(prev) else max(hh - ll, abs(hh - prev), abs(ll - prev))
        atr = tr if math.isnan(prev) else atr + (tr - atr) / 14.0
        chg = 0.0 if math.isnan(prev) else cc - prev
        rsiN += 1; rsiUp += ((chg if chg > 0 else 0) - rsiUp) / min(14, rsiN); rsiDn += ((-chg if chg < 0 else 0) - rsiDn) / min(14, rsiN)
        rsi = 100 - 100 / (1 + rsiUp / rsiDn) if rsiDn > 0 else 100.0
        if math.isnan(kx): kx = cc; kv = 0.0
        else:
            xp = kx + kv; a00 = p00 + 2 * p01 + p11 + q; a01 = p01 + p11; a11 = p11 + q
            s = a00 + r; g0 = a00 / s; g1 = a01 / s; e = cc - xp
            kx = xp + g0 * e; kv = kv + g1 * e; p00 = (1 - g0) * a00; p01 = (1 - g0) * a01; p11 = a11 - g1 * a01
        volring[vi] = vv; tpv[vi] = vv * (hh + ll + cc) / 3.0; vi = (vi + 1) % 20; vcnt = min(20, vcnt + 1)
        vs = volring[:vcnt].sum(); tps = tpv[:vcnt].sum()
        vdens = vv / (vs / vcnt) if vs > 0 else 1.0; com = tps / vs if vs > 0 else cc
        prev = cc; a = atr if atr > 0 else 1e-9
        raw[i] = (atr / cc, kv / a, rsi, vdens, (cc - com) / a)
    # нормализация: рефит каждые refit баров на окне fitwin; Z по текущим параметрам
    dirs = np.zeros(n, np.int8); strength = np.zeros(n)
    pre_mu = pre_sd = post_mu = post_sd = lam = None; since = refit; ready = False
    Zcache = None
    for i in range(n):
        if i < 22: continue
        since += 1
        if (since >= refit or not ready) and i + 1 >= 50:
            w = raw[max(0, i + 1 - fitwin):i + 1]
            pre_mu = w.mean(0); pre_sd = w.std(0, ddof=1); pre_sd[~(pre_sd > 0)] = 1
            lam = np.array([yj_fit((w[:, f] - pre_mu[f]) / pre_sd[f]) for f in range(F)])
            post = np.column_stack([yj((w[:, f] - pre_mu[f]) / pre_sd[f], lam[f]) for f in range(F)])
            post_mu = post.mean(0); post_sd = post.std(0, ddof=1); post_sd[~(post_sd > 0)] = 1
            ready = True; since = 0
            # Z всего ряда по параметрам этого рефита: решение на баре j берёт только строки ≤ j,
            # параметры подогнаны на окне до i ≤ j — заглядывания нет; пересчёт при каждом рефите.
            Zcache = np.column_stack([(yj((raw[:, f] - pre_mu[f]) / pre_sd[f], lam[f]) - post_mu[f]) / post_sd[f] for f in range(F)])
        if not ready: continue
        q0 = Zcache[i]
        backs = np.arange(H, min(i, lookback) + 1, max(1, stride))
        if len(backs) < 1: continue
        idx = i - backs
        d = np.log1p(np.abs(Zcache[idx] - q0)).sum(1)
        lab = np.where(c[idx + H] > c[idx], 1, -1)          # исход соседа известен: back ≥ H
        take = np.argsort(d, kind="stable")[:K]
        vote = lab[take].sum(); sw = len(take)
        st = abs(vote) / sw if sw else 0
        dirs[i] = int(np.sign(vote)) if st >= vote_thr else 0; strength[i] = st
    return dirs, strength


# ============================================================== MOD14 (Lever)
def lever_series(m5, m1, clusters=10, min_h=4, smooth=3, scale_win=50, vote_z=0.5, warm=50):
    """Баланс свечи M5 по профилю из M1 (объём равномерно по тикам бара). Состояние Up/Down/Middle."""
    n = len(m5); bal = np.full(n, np.nan); W = np.full(n, np.nan)
    m1_open = m1["open_utc"].to_numpy("datetime64[ns]"); m1h = m1["h"].to_numpy(float); m1l = m1["l"].to_numpy(float); m1v = m1["v"].to_numpy(float)
    co = m5["open_utc"].to_numpy("datetime64[ns]"); ce = m5["close_utc"].to_numpy("datetime64[ns]")
    lo_i = np.searchsorted(m1_open, co, "left"); hi_i = np.searchsorted(m1_open, ce, "left")
    H = m5["h"].to_numpy(float); L = m5["l"].to_numpy(float); O = m5["o"].to_numpy(float); C = m5["c"].to_numpy(float)
    for i in range(n):
        kL = int(round(L[i] / TICK)); kH = int(round(H[i] / TICK)); nlev = kH - kL + 1
        if nlev < max(2, min_h) or nlev > 5000: continue
        w = np.zeros(nlev); Wt = 0.0
        for j in range(lo_i[i], hi_i[i]):
            a = int(round(m1l[j] / TICK)); b = int(round(m1h[j] / TICK)); vv = m1v[j]
            if b < a: a, b = b, a
            m = b - a + 1
            if m <= 0 or not (vv > 0): continue
            ww = vv / m
            a0 = max(a, kL); b0 = min(b, kH)
            if b0 >= a0: w[a0 - kL:b0 - kL + 1] += ww; Wt += ww * (b0 - a0 + 1)
        if not Wt > 0: continue
        g = (H[i] + L[i]) / 2.0; armUp = max(H[i] - g, TICK); armDn = max(g - L[i], TICK)
        arm = lambda p: (p - g) / armUp if p >= g else (p - g) / armDn
        half = Wt / 2.0; cum = 0.0; p50 = H[i]
        for j in range(nlev):
            if w[j] > 0 and cum + w[j] >= half: p50 = (kL + j) * TICK - TICK / 2.0 + TICK * (half - cum) / w[j]; break
            cum += w[j]
        nc = max(1, min(max(2, clusters), nlev)); dens = np.zeros(nc); cen = np.zeros(nc); cnt = np.zeros(nc)
        for b in range(nc):
            a0 = b * nlev // nc; a1 = (b + 1) * nlev // nc - 1
            cnt[b] = a1 - a0 + 1; dens[b] = w[a0:a1 + 1].sum() / cnt[b]; cen[b] = (kL + (a0 + a1) / 2.0) * TICK
        md = np.median(dens); num = den = 0.0
        for b in range(nc):
            e = max(0.0, dens[b] - md) * cnt[b]; d = arm(cen[b]); num += e * d; den += e * abs(d)
        lever = num / den if den > 0 else 0.0
        bal[i] = 0.5 * (lever + arm(p50)); W[i] = Wt
    state = np.zeros(n, np.int8); z = np.full(n, np.nan)
    hist_b, hist_w = [], []
    for i in range(n):
        if math.isnan(bal[i]): continue
        hist_b.append(bal[i]); hist_w.append(W[i])
        if len(hist_b) < warm: continue
        tb = np.array(hist_b[-smooth:]); tw = np.array(hist_w[-smooth:])
        order = np.argsort(tb); cw = np.cumsum(tw[order]); sm = tb[order][np.searchsorted(cw, cw[-1] / 2.0)]
        tail = np.array(hist_b[-scale_win:]); mad = np.median(np.abs(tail - np.median(tail)))
        sc = max(0.02, 1.4826 * mad); zz = sm / sc; z[i] = zz
        state[i] = 1 if zz >= vote_z else (-1 if zz <= -vote_z else 0)
    return state, z


# ============================================================== MOD13 (Kalman track)
class KTrack:
    def __init__(self, period, wmin, wmax, k=2.0, confirm=5, warm_periods=3, flat_tilt=0.4, sym=0.3, trend_z=3.0, trend_tilt=0.6, comp=0.75, exp=1.35):
        a = 2.0 / (period + 1.0); b = 2.0 * (2.0 - a) - 4.0 * math.sqrt(1.0 - a); lam = b / math.sqrt(1.0 - a)
        self.lam2 = lam * lam; self.nisA = a; self.forget = 0.97; self.rMin = (0.25 * TICK) ** 2; self.k = k
        self.flat_tilt = flat_tilt; self.sym = sym; self.trend_z = trend_z; self.trend_tilt = trend_tilt; self.comp = comp; self.exp = exp
        self.warm = max(10, warm_periods * period); self.confirm = confirm
        self.wmin, self.wmax = max(3, min(wmin, wmax)), max(wmin, wmax); self.lf = float(self.wmax); self.wlen = self.wmax
        self.n = 0; self.steps = 0; self.boot = []; self.closes = []; self.resid = []; self.uppers = []; self.lowers = []; self.widths = []
        self.smoothed = False; self.in_range = False; self.flat_streak = 0; self.ready = False; self.state = "W"
        self.level = self.upper = self.lower = self.prev_upper = self.prev_lower = math.nan
        self.zS = self.tiltS = self.tuS = self.tlS = self.imbS = 0.0; self.x1 = 0.0
    @staticmethod
    def ols_slope(arr, m):
        y = np.array(arr[-m:][::-1]); x = -np.arange(len(y), dtype=float)
        if len(y) < 3: return 0.0
        xm, ym = x.mean(), y.mean(); d = ((x - xm) ** 2).sum()
        return ((x - xm) * (y - ym)).sum() / d if d > 0 else 0.0
    def update(self, z, hi, lo):
        self.closes.append(z)
        cl = self.closes
        if len(cl) > self.wmax:
            net = abs(cl[-1] - cl[-1 - self.wmax]); path = sum(abs(cl[-1 - i] - cl[-2 - i]) for i in range(self.wmax))
            er = net / path if path > 0 else 0.0; target = self.wmin + (self.wmax - self.wmin) * (1.0 - er)
            self.lf += 0.2 * (target - self.lf); self.wlen = max(self.wmin, min(self.wmax, int(round(self.lf))))
        else: self.wlen = max(self.wmin, min(self.wmax, len(cl) - 1))
        if self.n < 5:
            self.boot.append(z); self.n += 1
            if self.n == 5:
                acc = sum((self.boot[i] - self.boot[i - 1]) ** 2 for i in range(1, 5)); self.r = max(acc / 4.0, self.rMin)
                self.x0 = z; self.x1 = (self.boot[4] - self.boot[0]) / 4.0; self.p00 = 10 * self.r; self.p01 = 0.0; self.p11 = self.r; self.s = self.p00 + self.r
            self.ready = False; self.state = "W"; return
        q = self.lam2 * self.r
        a00 = self.p00 + 2 * self.p01 + self.p11 + q / 4.0; a01 = self.p01 + self.p11 + q / 2.0; a11 = self.p11 + q
        xp0 = self.x0 + self.x1; xp1 = self.x1; nu = z - xp0; sv = a00 + self.r; k0 = a00 / sv; k1 = a01 / sv
        self.x0 = xp0 + k0 * nu; self.x1 = xp1 + k1 * nu
        self.p00 = max(1e-18, (1 - k0) * a00); self.p01 = (1 - k0) * a01; self.p11 = max(1e-18, a11 - k1 * a01); self.s = sv
        self.steps += 1; dsh = (1 - self.forget) / (1 - self.forget ** (self.steps + 1))
        self.r = max((1 - dsh) * self.r + dsh * (nu * nu - a00), self.rMin); self.n += 1
        self.resid.append(z - self.x0)
        Lw = min(self.wlen, len(self.resid))
        if Lw < 3: self.ready = False; self.state = "W"; return
        rr = np.array(self.resid[-Lw:][::-1]); u = np.arange(Lw) / (Lw / 2.0); w = np.exp(-0.5 * u * u)
        W = w.sum(); U2 = (w * rr * rr * (rr > 0)).sum(); D2 = (w * rr * rr * (rr <= 0)).sum()
        dup, ddn = math.sqrt(U2 / W), math.sqrt(D2 / W); imb = (dup - ddn) / (dup + ddn) if dup + ddn > 0 else 0.0
        hu = max(TICK, self.k * math.sqrt(2.0) * dup); hd = max(TICK, self.k * math.sqrt(2.0) * ddn)
        self.prev_level, self.prev_upper, self.prev_lower = self.level, self.upper, self.lower
        self.level = self.x0; self.upper = self.x0 + hu; self.lower = self.x0 - hd; width = self.upper - self.lower
        self.uppers.append(self.upper); self.lowers.append(self.lower); self.widths.append(width)
        lw = min(len(self.widths), self.wmax); sw_ = max(1.0, lw / 2.0); uu = np.arange(lw) / sw_; ww = np.exp(-0.5 * uu * uu)
        swd = (ww * np.array(self.widths[-lw:][::-1])).sum(); ratio = width / (swd / ww.sum()) if swd > 0 else 1.0
        m = max(5, Lw // 2); wd = max(width, 2 * TICK)
        tilt = self.x1 * Lw / wd; tu = self.ols_slope(self.uppers, m) * m / wd; tl = self.ols_slope(self.lowers, m) * m / wd; sz = self.x1 / math.sqrt(self.p11)
        if not self.smoothed: self.zS, self.tiltS, self.tuS, self.tlS, self.imbS = sz, tilt, tu, tl, imb; self.smoothed = True
        else:
            A = 0.3; self.zS += A * (sz - self.zS); self.tiltS += A * (tilt - self.tiltS); self.tuS += A * (tu - self.tuS); self.tlS += A * (tl - self.tlS); self.imbS += A * (imb - self.imbS)
        zf = self.trend_z / 2.0; tb = 1.25 * self.flat_tilt
        flat = abs(self.zS) < zf and abs(self.tiltS) < self.flat_tilt and abs(self.tuS) < tb and abs(self.tlS) < tb and abs(self.tuS - self.tlS) < tb and abs(self.imbS) < self.sym
        self.flat_streak = self.flat_streak + 1 if flat else 0
        ready = self.n >= self.warm and len(self.resid) >= self.wmin
        trend = abs(self.zS) >= self.trend_z and abs(self.tiltS) >= self.trend_tilt
        if self.in_range:
            up = (not math.isnan(self.prev_upper)) and z > self.prev_upper; dn = (not math.isnan(self.prev_lower)) and z < self.prev_lower
            if up or dn or trend: self.in_range = False; self.flat_streak = 0
        elif ready and self.flat_streak >= self.confirm: self.in_range = True
        self.ready = ready
        self.state = "W" if not ready else ("R" if self.in_range else ("T+" if trend and self.x1 > 0 else ("T-" if trend else "U")))
    @property
    def zflat(self): return self.trend_z / 2.0
    @property
    def corridor(self): return (self.tuS + self.tlS) / 2.0


def kalman_tracks(bars, period, wmin, wmax, confirm):
    t = KTrack(period, wmin, wmax, confirm=confirm); n = len(bars)
    st = np.empty(n, dtype=object); lower = np.full(n, np.nan); upper = np.full(n, np.nan); zS = np.full(n, np.nan); cor = np.full(n, np.nan); ready = np.zeros(n, bool)
    h = bars["h"].to_numpy(float); l = bars["l"].to_numpy(float); c = bars["c"].to_numpy(float)
    for i in range(n):
        t.update(c[i], h[i], l[i]); st[i] = t.state; lower[i] = t.lower; upper[i] = t.upper; zS[i] = t.zS; cor[i] = t.corridor; ready[i] = t.ready
    return st, lower, upper, zS, cor, ready, t.zflat


# ============================================================== оркестровка
def latest_before(src_close, dst_time, strict=True):
    """Индекс последнего бара источника с close < t (strict) или ≤ t."""
    pos = np.searchsorted(src_close, dst_time, side="left" if strict else "right") - 1
    return pos


def simulate(m5, cand, filt_ok, escort, hard_close_min, win1, win2, entries_until, stop_ticks=40, name=""):
    """Одна позиция за раз; вход по открытию следующего бара; стоп по худшему пути; закрытие 22:30 по Берлину."""
    o = m5["o"].to_numpy(float); h = m5["h"].to_numpy(float); l = m5["l"].to_numpy(float); c = m5["c"].to_numpy(float)
    be = pd.DatetimeIndex(m5["close_utc"]).tz_convert(TZB); tod = (be.hour * 60 + be.minute).to_numpy(); wd = be.dayofweek.to_numpy()
    n = len(o); trades = []; pos = 0; i = 0
    while i < n - 2:
        if pos == 0:
            if i in cand and filt_ok[i] and wd[i] < 5 and ((win1[0] <= tod[i] < win1[1]) or (win2[0] <= tod[i] < win2[1])) and tod[i] < entries_until:
                d = cand[i][1]; ent = o[i + 1] + d * SLIP * TICK; stop = ent - d * stop_ticks * TICK
                mfe = 0.0; mae = 0.0; j = i + 1; exit_px = None; reason = ""; k = j; against = 0
                while k < n:
                    # стоп по худшему пути (на баре входа тоже)
                    if (d > 0 and l[k] <= stop) or (d < 0 and h[k] >= stop):
                        exit_px = (min(o[k], stop) if d > 0 else max(o[k], stop)); exit_px -= d * SLIP * TICK; reason = "стоп"; break
                    mfe = max(mfe, (h[k] - ent) if d > 0 else (ent - l[k])); mae = max(mae, (ent - l[k]) if d > 0 else (h[k] - ent))
                    if tod[k] >= hard_close_min or wd[k] != wd[j]:
                        exit_px = o[k] - d * SLIP * TICK if k > j else c[k] - d * SLIP * TICK; reason = "22:30"; break
                    if escort is not None:
                        new_stop, flip = escort(k, d, stop)
                        if new_stop is not None and ((d > 0 and new_stop > stop) or (d < 0 and new_stop < stop)): stop = new_stop
                        if flip:
                            against += 1
                            if against >= 2 and k + 1 < n: exit_px = o[k + 1] - d * SLIP * TICK; reason = "наклон"; k += 1; break
                        else: against = 0
                    k += 1
                if exit_px is None: exit_px = c[n - 1]; reason = "конец"; k = n - 1
                pnl = (exit_px - ent) * d / TICK * TICK_USD - COST_RT
                trades.append({"chain": name, "entry_bar": i + 1, "exit_bar": k, "dir": d, "entry": ent, "exit": exit_px, "pnl_usd": pnl,
                               "mfe_ticks": mfe / TICK, "mae_ticks": mae / TICK, "bars": k - i, "reason": reason, "time_utc": m5["close_utc"].iloc[i]})
                i = k + 1; continue
        i += 1
    return pd.DataFrame(trades)


def summarize(tr):
    if len(tr) == 0: return {"n": 0}
    w = tr[tr.pnl_usd > 0].pnl_usd.sum(); lo = -tr[tr.pnl_usd < 0].pnl_usd.sum()
    wins = tr[tr.pnl_usd > 0]
    cap_w = float((wins.pnl_usd / (wins.mfe_ticks * TICK_USD).replace(0, np.nan)).median()) if len(wins) else np.nan
    cap_total = float(tr.pnl_usd.sum() / max(1e-9, (tr.mfe_ticks * TICK_USD).sum()))
    return {"n": int(len(tr)), "pnl_sum": round(float(tr.pnl_usd.sum()), 1), "pnl_mean": round(float(tr.pnl_usd.mean()), 2), "pf": round(float(w / lo), 3) if lo > 0 else float("inf"),
            "win": round(float((tr.pnl_usd > 0).mean()), 3), "mfe_med": round(float(tr.mfe_ticks.median()), 1), "mae_med": round(float(tr.mae_ticks.median()), 1),
            "capture_winners_med": round(cap_w, 3), "capture_total": round(cap_total, 3), "reasons": {k: int(v) for k, v in tr.reason.value_counts().items()}}


def cmd_run(a):
    M = ms(); t0 = time.time()
    m1 = M.load_npz(a.npz); m1 = m1[(m1.index >= pd.Timestamp(a.start, tz="UTC")) & (m1.index < pd.Timestamp(a.end, tz="UTC"))]
    if a.volume_nt:
        nt = M.load_nt_volume(a.volume_nt, a.start, a.end); j = m1.join(nt[["v"]], how="left", rsuffix="_nt"); m1["v"] = j["v_nt"].fillna(0.0).to_numpy()
    bars = M.resample_all(m1, [5, 15, 60]); m1b = bars[1].reset_index(drop=True)
    m5 = bars[5].reset_index(drop=True); m15 = bars[15].reset_index(drop=True); m60 = bars[60].reset_index(drop=True)
    log(f"бары: M1 {len(m1b):,}, M5 {len(m5):,}, M15 {len(m15):,}, M60 {len(m60):,}")
    c5 = pd.DatetimeIndex(m5["close_utc"]).to_numpy("datetime64[ns]"); c15 = pd.DatetimeIndex(m15["close_utc"]).to_numpy("datetime64[ns]"); c60 = pd.DatetimeIndex(m60["close_utc"]).to_numpy("datetime64[ns]")
    # --- PAC: младший M5 (≤ t), старший M15 (< t)
    ev5 = pac_series(m5["h"].to_numpy(float), m5["l"].to_numpy(float), m5["c"].to_numpy(float))
    ev15 = pac_series(m15["h"].to_numpy(float), m15["l"].to_numpy(float), m15["c"].to_numpy(float), higher=True)
    pos15 = latest_before(c15, c5, strict=True)
    ev_high_map = {}
    seen = set()
    for i in range(len(m5)):
        p = pos15[i]
        if p >= 0 and p not in seen and ev15[p]:
            # событие старшего ТФ отправляется на первом такте исполнения после закрытия его бара
            ev_high_map[i] = ev15[p]; seen.add(p)
    cand = pac_candidates(ev5, ev_high_map, len(m5))
    log(f"PAC: кандидатов {len(cand):,} ({len(cand)/len(m5):.2%} баров M5), {time.time()-t0:.0f} с")
    # --- MOD9 на M15 (< t)
    kd15, ks15 = kernel_series(m15["h"].to_numpy(float), m15["l"].to_numpy(float), m15["c"].to_numpy(float))
    ker_dir = np.where(pos15 >= 0, kd15[np.clip(pos15, 0, len(kd15) - 1)], 0)
    log(f"MOD9: доля баров с направлением {np.mean(ker_dir != 0):.2%}, {time.time()-t0:.0f} с")
    # --- MOD11 на M5 (≤ t)
    ld, ls = lorentz_series(m5["h"].to_numpy(float), m5["l"].to_numpy(float), m5["c"].to_numpy(float), m5["v"].to_numpy(float))
    log(f"MOD11: доля баров с перевесом {np.mean(ld != 0):.2%}, {time.time()-t0:.0f} с")
    # --- MOD14: свеча M5 из M1, финализация после закрытия → доступна с бара i+1
    lv_state, lv_z = lever_series(m5, m1b)
    lv_avail = np.r_[0, lv_state[:-1]]
    log(f"MOD14: доля Up/Down {np.mean(lv_avail != 0):.2%}, {time.time()-t0:.0f} с")
    # --- MOD13: направление по M60 (< t), сопровождение по M5 (≤ t)
    st60, lo60, up60, z60, cor60, rd60, zf = kalman_tracks(m60, 20, 30, 120, confirm=5)
    st5, lo5, up5, z5, cor5, rd5, zf5 = kalman_tracks(m5, 20, 30, 120, confirm=5)
    pos60 = latest_before(c60, c5, strict=True)
    k60 = np.where(pos60 >= 0, st60[np.clip(pos60, 0, len(st60) - 1)], "W")
    kal_dir = np.where(k60 == "T+", 1, np.where(k60 == "T-", -1, 0))
    log(f"MOD13: доля тренда по M60 {np.mean(kal_dir != 0):.2%}, {time.time()-t0:.0f} с")
    # --- вердикты фильтров на кандидатах: пропуск, если нейтраль или согласие; вето при противоположном направлении
    n5 = len(m5); cd = np.zeros(n5, np.int8)
    for i, v in cand.items(): cd[i] = v[1]
    def passes(fdir): return (fdir == 0) | (fdir == cd)
    F = {"MOD9": passes(ker_dir), "MOD11": passes(ld), "MOD14": passes(lv_avail), "MOD13": passes(kal_dir)}
    # --- мета-разметка Э32: вход по закрытию бара сигнала, цель = стоп, стоп 40, вертикаль 60 баров
    h = m5["h"].to_numpy(float); l = m5["l"].to_numpy(float); c = m5["c"].to_numpy(float)
    meta = {}
    for i, v in cand.items():
        d = v[1]; e = c[i]; up = e + (40 * TICK if d > 0 else 40 * TICK); dn = e - 40 * TICK
        lab = None
        for k in range(i + 1, min(n5, i + a.meta_horizon + 1)):
            hu, hd = h[k] >= up, l[k] <= dn
            if hu and hd: lab = 0; break
            if hu: lab = 1 if d > 0 else 0; break
            if hd: lab = 1 if d < 0 else 0; break
        if lab is None: lab = 1 if (c[min(n5 - 1, i + a.meta_horizon)] - e) * d > 0 else 0
        meta[i] = lab
    rows = []
    idx = np.array(sorted(meta)); labs = np.array([meta[i] for i in idx])
    for name, ok in F.items():
        p = ok[idx]
        passw = int(((labs == 1) & p).sum()); passl = int(((labs == 0) & p).sum()); cutw = int(((labs == 1) & ~p).sum()); cutl = int(((labs == 0) & ~p).sum())
        rows.append({"filter": name, "candidates": len(idx), "passed": passw + passl, "precision_pass": round(passw / max(1, passw + passl), 4),
                     "base_rate": round(float(labs.mean()), 4), "recall": round(passw / max(1, passw + cutw), 4), "cut": cutw + cutl, "cut_profitable": cutw})
    metaT = pd.DataFrame(rows); log("\n" + metaT.to_string(index=False))
    # --- цепочки: симуляция сделок
    win1 = (60, 8 * 60); win2 = (9 * 60 + 30, 18 * 60 + 30); until = 21 * 60 + 30; hard = 22 * 60 + 30
    allok = np.ones(n5, bool)
    def kal_escort(k, d, stop):
        if not rd5[k]: return None, False
        new = (lo5[k] - 2 * TICK) if d > 0 else (up5[k] + 2 * TICK)
        if d > 0 and new >= c[k]: new = None
        if d < 0 and new is not None and new <= c[k]: new = None
        flip = (z5[k] <= -zf5 and cor5[k] < 0) if d > 0 else (z5[k] >= zf5 and cor5[k] > 0)
        return new, flip
    # Э58: сопровождение по старшему каналу (EscortTf = Higher, M60) — реже обновляется, шире; в модуле это настройка [C1x]
    lo60m = np.where(pos60 >= 0, lo60[np.clip(pos60, 0, len(lo60) - 1)], np.nan); up60m = np.where(pos60 >= 0, up60[np.clip(pos60, 0, len(up60) - 1)], np.nan)
    rd60m = np.where(pos60 >= 0, rd60[np.clip(pos60, 0, len(rd60) - 1)], False)
    def kal_escort60(k, d, stop):
        if not rd60m[k] or math.isnan(lo60m[k]): return None, False
        new = (lo60m[k] - 2 * TICK) if d > 0 else (up60m[k] + 2 * TICK)
        if (d > 0 and new >= c[k]) or (d < 0 and new <= c[k]): new = None
        return new, False
    chains = {
        "A: PAC без фильтров, стоп 40 + 22:30": (allok, None),
        "E2 (Э58): PAC → сопровождение MOD13 по каналу M60": (allok, kal_escort60),
        "B: PAC ∧ MOD14 ∧ MOD11 (валидация)": (F["MOD14"] & F["MOD11"], None),
        "C: PAC ∧ MOD9 (ядро M15)": (F["MOD9"], None),
        "D: PAC ∧ MOD13-направление M60": (F["MOD13"], None),
        "E: PAC → сопровождение MOD13 (канал M5)": (allok, kal_escort),
        "F: PAC ∧ MOD14 ∧ MOD11 ∧ MOD9 → MOD13": (F["MOD14"] & F["MOD11"] & F["MOD9"], kal_escort),
        "G: PAC ∧ MOD9 ∧ MOD13-напр. → MOD13": (F["MOD9"] & F["MOD13"], kal_escort),
    }
    res = {}; alltr = []
    for name, (ok, esc) in chains.items():
        tr = simulate(m5, cand, ok, esc, hard, win1, win2, until, name=name)
        res[name] = summarize(tr); alltr.append(tr)
        log(f"{name}: {res[name]}")
    os.makedirs(a.out, exist_ok=True)
    pd.concat(alltr).to_csv(os.path.join(a.out, "chain_trades.csv"), sep=";", index=False, float_format="%.3f")
    metaT.to_csv(os.path.join(a.out, "meta_filters.csv"), sep=";", index=False)
    json.dump({"version": VERSION, "start": a.start, "end": a.end, "candidates": len(cand), "chains": res}, open(os.path.join(a.out, "chains_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
    log(f"готово, {time.time()-t0:.0f} с")


def main():
    ap = argparse.ArgumentParser(description=VERSION); sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "parity-dump"):
        p = sub.add_parser(name); p.add_argument("--npz", required=True); p.add_argument("--volume-nt"); p.add_argument("--start", default="2015-01-01"); p.add_argument("--end", default="2019-01-01"); p.add_argument("--out", default="ms/chains"); p.add_argument("--days", type=int, default=2); p.add_argument("--meta-horizon", type=int, default=60)
    a = ap.parse_args()
    if a.cmd == "parity-dump": a.end = str((pd.Timestamp(a.start) + pd.Timedelta(days=a.days)).date())
    cmd_run(a)


if __name__ == "__main__":
    main()
