#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_MS_Market_S021.py — иерархическая разметка структуры рынка, v1.0 (2026-10-04)

ТЗ «Иерархическая разметка структуры рынка v2» + дополнения руководителя: параллельная разметка
стационарных и нестационарных участков, реестр участков, предвестники переходов, внутридневной
путь, активные дни и окна, тонкий рынок. Обучение 2015–2018; 2022–2025 — только проверка, в этом
скрипте не трогается.

ПРИНЦИПЫ ПРОЕКТА, ВСТРОЕННЫЕ В КОД
  • Данные — сертифицированный кэш M1 (UTC, нс, время открытия бара). Старшие таймфреймы — той же
    функцией, что у очистителя v2 и NinjaTrader: от начала сессии 17:00 Чикаго (постулат П7).
  • Нет заглядывания. Экстремум считается известным на закрытии N-го бара после него; метка старшего
    таймфрейма действует с момента закрытия подтверждающего бара, а не с его открытия; минутка в момент t
    получает только то, что было известно к t. Команда selftest доказывает это измерением:
    разметка на усечённых данных обязана совпасть с разметкой на полных везде до среза.
  • Окна — по реальным барам, не по астрономическому времени: пятница и воскресенье не склеиваются.
  • Единицы: тик 0,1, стоимость тика 1 $ (MGC); объём — GC, прокси.
  • Пояса: данные UTC, торговый день CME по якорю 17:00 Чикаго, отчёты по Берлину.

РАЗМЕТКА (этап 2 ТЗ), для каждого ТФ 1, 5, 15, 30, 45, 60, 120, 240 минут
  SH/SL — экстремум High/Low в окне N баров до и N после; подтверждение — закрытие бара i+N.
  HH/HL/LL/LH — сравнение с предыдущим ПОДТВЕРЖДЁННЫМ экстремумом того же типа, в порядке
  подтверждения. Тренд: LONG от LL до нового HH, SHORT от HH до нового LL. Фаза: после HH в LONG —
  PULLBACK до HL, от HL — IMPULSE до HH; зеркально в SHORT. LH в LONG и HL в SHORT тренд не меняют.

СОСТОЯНИЯ РЯДА (дополнение), для каждого ТФ, причинно, окно W баров, метка с закрытия бара
  S — стационарный: DF-тест отвергает единичный корень (t < −2,86 — критическое значение 5 %
      Маккиннона для n > 100 с константой); эталон — Чан гл. 2 (ADF, Хёрст, variance ratio, полураспад).
  T+ / T− — нестационарный с наклоном: |t| наклона прямой по времени ≥ 2 и VR(q) z ≥ 1,96 (персистентность).
  W — нестационарный без наклона: неотличим от блуждания.
  Реестр участков: пробеги состояний и ноги между экстремумами, у каждого — ход в цене и тиках,
  наклон, R², эффективность хода, DF-t, VR-z, Хёрст (R/S, поправка Анис–Ллойда, как в MOD10), полураспад,
  экстремумы, MFE/MAE, идеальный и реализуемый PnL.

ЭКСПЕРИМЕНТЫ, выключены
  Э54 --confirm cusum --cusum-h H: подтверждение экстремума не N барами, а откатом на H·σ от него
      (AFML 2.5.2.1, с. 39: событие — после накопленного сдвига, не по таймеру).
  Э55 --trend-scan: наклон состояния — по окну с наибольшим |t| среди L = 8…W (MLAM 5.4), а не по W.

КОМАНДЫ
  label      --npz MGC_M1.npz [--volume-nt папка_импорта] --start 2015-01-01 --end 2019-01-01 --out ms/train
  profile    --out ms/train          внутридневной путь, дни недели, часы по Берлину, тонкий рынок
  transitions --out ms/train         предвестники переходов между состояниями
  selftest   --npz ... --start ... --end ... --cut 2017-06-01   доказательство отсутствия заглядывания
==========================================================================================
"""
import argparse, glob, importlib.util, json, math, os, sys, time
import numpy as np
import pandas as pd

VERSION = "DZ_MS_Market_S021-v1.0 (2026-10-04)"
HERE = os.path.dirname(os.path.abspath(__file__))
TZ_EX = "America/Chicago"
TZ_REP = "Europe/Berlin"
TICK = 0.1
TICK_USD = 1.0
COST_RT_USD = 0.44           # комиссия за круг, паспорт MGC
SLIP_TICKS = 1.0             # проскальзывание на каждом исполнении, паспорт MGC
TFS = [1, 5, 15, 30, 45, 60, 120, 240]
SW = {0: "", 1: "HH", 2: "HL", 3: "LL", 4: "LH", 5: "H", 6: "L"}
TR = {0: "", 1: "LONG", -1: "SHORT"}
PH = {0: "", 1: "IMPULSE", 2: "PULLBACK"}
ST = {0: "", 1: "S", 2: "T+", 3: "T-", 4: "W"}


def log(m):
    print(time.strftime("%H:%M:%S"), m, flush=True)


# ---------------------------------------------------------------- 1. данные
def load_npz(path):
    z = np.load(path, allow_pickle=False)
    t = pd.to_datetime(z["t_open"] if "t_open" in z.files else z["t"], unit="ns", utc=True)
    df = pd.DataFrame({"o": z["o"], "h": z["h"], "l": z["l"], "c": z["c"],
                       "v": z["v"] if "v" in z.files else np.zeros(len(t))}, index=t)
    return df


def load_raw(path):
    """Формат ТЗ: Date Time O H L C V без заголовка, разделитель таб/пробел; формат даты — по монотонности."""
    d = pd.read_csv(path, sep=None, engine="python", header=None, names=["d", "t", "o", "h", "l", "c", "v"], dtype={"d": str, "t": str})
    best = None
    for fmt in ("%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y%m%d %H%M%S", "%Y-%m-%d %H:%M:%S"):
        try:
            ts = pd.to_datetime(d["d"] + " " + d["t"], format=fmt)
        except Exception:
            continue
        if ts.is_monotonic_increasing:
            best = ts; break
    if best is None:
        sys.exit("формат даты не определён по монотонности времени")
    utc = best.dt.tz_localize(TZ_EX, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    df = d[["o", "h", "l", "c", "v"]].astype(float); df.index = utc
    return df[~df.index.isna()]


def load_nt_volume(folder, start, end):
    """Файлы импорта NinjaTrader yyyyMMdd HHmmss;O;H;L;C;V в чикагском времени — только для объёма."""
    frames = []
    for p in sorted(glob.glob(os.path.join(folder, "*", "GC*.Last.txt"))):
        y = os.path.basename(os.path.dirname(p))
        if not y.isdigit() or not (int(start[:4]) <= int(y) <= int(end[:4])):
            continue
        d = pd.read_csv(p, sep=";", header=None, names=["ts", "o", "h", "l", "c", "v"], dtype={"ts": str})
        loc = pd.to_datetime(d["ts"], format="%Y%m%d %H%M%S")
        d.index = loc.dt.tz_localize(TZ_EX, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
        frames.append(d[~d.index.isna()])
    if not frames:
        return None
    return pd.concat(frames)


def trading_day(idx_utc):
    t = pd.DatetimeIndex(idx_utc).tz_convert(TZ_EX) + pd.Timedelta(hours=7)
    return pd.DatetimeIndex(t.tz_localize(None).normalize())


def fill_gaps(m1):
    """ТЗ 3.1: пропущенные минуты ВНУТРИ торгового дня — цена ffill (плоский бар), объём 0.
    Перерыв 16:00–17:00 Чикаго и выходные — граница дня, не заполняются."""
    td = trading_day(m1.index)
    full = []
    for day, g in m1.groupby(td):
        rng = pd.date_range(g.index[0], g.index[-1], freq="1min", tz="UTC")
        if len(rng) == len(g):
            full.append(g); continue
        r = g.reindex(rng)
        prev = r["c"].ffill()
        miss = r["o"].isna()
        for col in ("o", "h", "l", "c"):
            r.loc[miss, col] = prev[miss]
        r.loc[miss, "v"] = 0.0
        r["filled"] = miss.astype(np.int8)
        full.append(r)
    out = pd.concat(full)
    if "filled" not in out:
        out["filled"] = np.int8(0)
    out["filled"] = out["filled"].fillna(0).astype(np.int8)
    return out


def sanitizer():
    s = importlib.util.spec_from_file_location("dz_san", os.path.join(HERE, "DZ_DATA_Sanitizer_v2.py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def resample_all(m1, tfs):
    san = sanitizer()
    out = {1: m1.assign(open_utc=m1.index, close_utc=m1.index + pd.Timedelta(minutes=1))}
    for tf in tfs:
        if tf == 1:
            continue
        b = san.resample(m1[["o", "h", "l", "c", "v"]], tf, 17)
        out[tf] = b
    return out


# ---------------------------------------------------------------- 2. экстремумы и структура
def swings(h, l, n):
    """SH: High максимален в окне N до и N после (слева ≥, справа строго >); SL зеркально. Возвращает индексы."""
    hs, ls = pd.Series(h), pd.Series(l)
    back_max = hs.rolling(n, min_periods=n).max().shift(1)
    fwd_max = hs[::-1].rolling(n, min_periods=n).max().shift(1)[::-1]
    back_min = ls.rolling(n, min_periods=n).min().shift(1)
    fwd_min = ls[::-1].rolling(n, min_periods=n).min().shift(1)[::-1]
    sh = np.where((hs >= back_max) & (hs > fwd_max))[0]
    sl = np.where((ls <= back_min) & (ls < fwd_min))[0]
    return sh, sl


def confirm_cusum(bars, idx, kind, h_sigma):
    """Э54: подтверждение откатом на H·σ от экстремума (σ — EWM std минутных/барных доходностей, 100)."""
    c = bars["c"].to_numpy(float); hi = bars["h"].to_numpy(float); lo = bars["l"].to_numpy(float)
    r = pd.Series(np.diff(c, prepend=c[0]))
    sig = r.ewm(span=100, min_periods=20).std().to_numpy(float)
    out = np.full(len(idx), -1, dtype=np.int64)
    for k, i in enumerate(idx):
        thr = h_sigma * (sig[i] if not np.isnan(sig[i]) else np.nanmedian(sig))
        if kind == "H":
            j = np.argmax(hi[i] - lo[i + 1:] >= thr) if i + 1 < len(c) else 0
            ok = i + 1 < len(c) and (hi[i] - lo[i + 1:]).max() >= thr
        else:
            j = np.argmax(hi[i + 1:] - lo[i] >= thr) if i + 1 < len(c) else 0
            ok = i + 1 < len(c) and (hi[i + 1:] - lo[i]).max() >= thr
        out[k] = i + 1 + j if ok else -1
    return out


def structure(bars, n, confirm="bars", cusum_h=3.0):
    """События в порядке подтверждения; тренд и фаза по ТЗ 4.3. valid_from — закрытие подтверждающего бара."""
    h = bars["h"].to_numpy(float); l = bars["l"].to_numpy(float)
    sh, sl = swings(h, l, n)
    close_utc = pd.DatetimeIndex(bars["close_utc"]); open_utc = pd.DatetimeIndex(bars["open_utc"])
    if confirm == "cusum":
        ch, cl = confirm_cusum(bars, sh, "H", cusum_h), confirm_cusum(bars, sl, "L", cusum_h)
        sh, ch = sh[ch >= 0], ch[ch >= 0]; sl, cl = sl[cl >= 0], cl[cl >= 0]
    else:
        ch, cl = sh + n, sl + n
        keep = ch < len(bars); sh, ch = sh[keep], ch[keep]
        keep = cl < len(bars); sl, cl = sl[keep], cl[keep]
    ev = pd.DataFrame({"bar": np.r_[sh, sl], "kind": np.r_[np.full(len(sh), "H"), np.full(len(sl), "L")],
                       "price": np.r_[h[sh], l[sl]], "conf_bar": np.r_[ch, cl]})
    ev["time"] = open_utc[ev["bar"].to_numpy()]
    ev["valid_from"] = close_utc[ev["conf_bar"].to_numpy()]
    ev = ev.sort_values(["valid_from", "bar"], kind="mergesort").reset_index(drop=True)
    sw = np.zeros(len(ev), np.int8); trend = np.zeros(len(ev), np.int8); phase = np.zeros(len(ev), np.int8)
    anchor_time = np.full(len(ev), np.datetime64("NaT"), "datetime64[ns]")
    times = ev["time"].to_numpy("datetime64[ns]")
    last_h = last_l = np.nan; t = 0; ph = 0
    last_hh_time = last_ll_time = None
    kinds = ev["kind"].to_numpy(); prices = ev["price"].to_numpy(float)
    for i in range(len(ev)):
        k, p = kinds[i], prices[i]
        if k == "H":
            code = 5 if np.isnan(last_h) else (1 if p > last_h else 4)       # H / HH / LH
            last_h = p
            if code == 1:
                if t != 1: anchor_time[i] = last_ll_time if last_ll_time is not None else times[i]
                t = 1; ph = 2; last_hh_time = times[i]
            elif code == 4 and t == -1:
                ph = 1
        else:
            code = 6 if np.isnan(last_l) else (3 if p < last_l else 2)       # L / LL / HL
            last_l = p
            if code == 3:
                if t != -1: anchor_time[i] = last_hh_time if last_hh_time is not None else times[i]
                t = -1; ph = 2; last_ll_time = times[i]
            elif code == 2 and t == 1:
                ph = 1
        sw[i], trend[i], phase[i] = code, t, ph
    ev["swing"] = sw; ev["trend"] = trend; ev["phase"] = phase; ev["anchor_time"] = anchor_time
    return ev


def project(ev, minute_open, col):
    """Метка = последнее событие с valid_from ≤ время открытия минутки."""
    vf = ev["valid_from"].to_numpy("datetime64[ns]")
    pos = np.searchsorted(vf, minute_open.to_numpy("datetime64[ns]"), side="right") - 1
    vals = ev[col].to_numpy()
    out = np.where(pos >= 0, vals[np.clip(pos, 0, len(vals) - 1)], 0)
    return out.astype(np.int8)


# ---------------------------------------------------------------- 3. статистики окон и участков
def roll_df_t(y, w):
    """DF-статистика Δy = a + ρ·y₋₁ + e на окне w (без лагов), векторно через скользящие суммы."""
    y = pd.Series(y, dtype=float)
    dy = y.diff(); x = y.shift(1)
    n = w                      # в каждом окне ровно w пар (x, Δy); первое окно с NaN отбрасывается само
    sx, sy = x.rolling(w).sum(), dy.rolling(w).sum()
    sxx, sxy, syy = (x * x).rolling(w).sum(), (x * dy).rolling(w).sum(), (dy * dy).rolling(w).sum()
    den = n * sxx - sx * sx
    rho = (n * sxy - sx * sy) / den
    a = (sy - rho * sx) / n
    sse = syy - a * sy - rho * sxy
    s2 = sse / (n - 2)
    se = np.sqrt(s2 * n / den)
    return (rho / se).to_numpy(float), rho.to_numpy(float)


def roll_slope_t(y, w):
    """t-статистика наклона прямой y ~ a + b·k, k = 0…w−1, векторно."""
    y = pd.Series(y, dtype=float)
    k = np.arange(len(y), dtype=float)
    sk = w * (w - 1) / 2.0; skk = (w - 1) * w * (2 * w - 1) / 6.0
    sy = y.rolling(w).sum(); syy = (y * y).rolling(w).sum()
    sky_glob = (pd.Series(k) * y).rolling(w).sum()
    k0 = pd.Series(k) - (w - 1)
    sky = sky_glob - k0 * sy
    den = w * skk - sk * sk
    b = (w * sky - sk * sy) / den
    a = (sy - b * sk) / w
    sse = syy - a * sy - b * sky
    s2 = sse / (w - 2)
    se = np.sqrt(s2 * w / den)
    return (b / se).to_numpy(float), b.to_numpy(float)


def roll_vr_z(y, w, q=4):
    """Lo–MacKinlay VR(q) на окне w: z = (VR−1)/√(2(2q−1)(q−1)/(3q·n)) — однородная дисперсия."""
    y = pd.Series(y, dtype=float)
    r = y.diff()
    rq = y.diff(q)
    n = w
    v1 = (r * r).rolling(w).sum() / n - (r.rolling(w).sum() / n) ** 2
    vq = (rq * rq).rolling(w).sum() / n - (rq.rolling(w).sum() / n) ** 2
    vr = vq / (q * v1)
    z = (vr - 1) / np.sqrt(2 * (2 * q - 1) * (q - 1) / (3.0 * q * n))
    return z.to_numpy(float), vr.to_numpy(float)


def hurst_rs(r):
    """R/S на масштабах N, N/2, N/4… ≥ 8 с поправкой Анис–Ллойда (как MOD10); H = 0,5 + наклон."""
    r = np.asarray(r, float); n = len(r)
    if n < 32 or np.nanstd(r) == 0:
        return np.nan
    xs, ys = [], []
    m = n
    while m >= 8:
        k = n // m
        vals = []
        for b in range(k):
            seg = r[b * m:(b + 1) * m]
            z = np.cumsum(seg - seg.mean())
            rs = (z.max() - z.min()) / (seg.std(ddof=1) if seg.std(ddof=1) > 0 else np.nan)
            if not np.isnan(rs): vals.append(rs)
        if vals:
            # ожидание R/S для независимых приращений (Анис–Ллойд, поправка Петерса)
            if m > 340:
                e = ((m - 0.5) / m) * (1 / math.sqrt(math.pi * m / 2)) * sum(math.sqrt((m - i) / i) for i in range(1, m))
            else:
                e = ((m - 0.5) / m) * (math.gamma((m - 1) / 2) / (math.sqrt(math.pi) * math.gamma(m / 2))) * sum(math.sqrt((m - i) / i) for i in range(1, m))
            xs.append(math.log(m)); ys.append(math.log(np.mean(vals)) - math.log(e))
        m //= 2
    if len(xs) < 2:
        return np.nan
    slope = np.polyfit(xs, ys, 1)[0]
    return 0.5 + slope


def seg_stats(c, direction=0):
    """Статистики участка по закрытиям: наклон (тик/бар), t, R², эффективность хода, DF-t, VR-z, Хёрст, полураспад."""
    c = np.asarray(c, float); n = len(c)
    out = {"n": n}
    if n < 4:
        return out
    k = np.arange(n, dtype=float)
    b, a = np.polyfit(k, c, 1)
    fit = a + b * k; sse = ((c - fit) ** 2).sum(); sst = ((c - c.mean()) ** 2).sum()
    se = math.sqrt(sse / (n - 2) / ((k - k.mean()) ** 2).sum()) if n > 2 and sse > 0 else np.nan
    out["slope_ticks_per_bar"] = b / TICK
    out["slope_t"] = b / se if se and not np.isnan(se) and se > 0 else np.nan
    out["r2"] = 1 - sse / sst if sst > 0 else np.nan
    d = np.diff(c)
    out["efficiency"] = abs(c[-1] - c[0]) / np.abs(d).sum() if np.abs(d).sum() > 0 else np.nan
    out["vol_ticks"] = d.std(ddof=1) / TICK if n > 2 else np.nan
    # DF и полураспад: Δc = α + ρ·c₋₁
    if n >= 8 and np.isfinite(c).all() and np.std(c[:-1]) > 0:
        x = c[:-1] - c[:-1].mean(); dy = d          # центрирование: обусловленность при ценах ~1000
        X = np.column_stack([np.ones(len(x)), x])
        try:
            beta, res, _, _ = np.linalg.lstsq(X, dy, rcond=None)
            resid = dy - X @ beta; s2 = (resid @ resid) / max(1, len(x) - 2)
            cov = s2 * np.linalg.pinv(X.T @ X)
        except np.linalg.LinAlgError:
            return out
        rho = beta[1]; se_rho = math.sqrt(cov[1, 1]) if cov[1, 1] > 0 else np.nan
        out["df_t"] = rho / se_rho if se_rho and se_rho > 0 else np.nan
        out["half_life_bars"] = -math.log(2) / rho if rho < 0 else np.inf
        if n >= 16:
            q = 4; r1 = d; rq = c[q:] - c[:-q]
            v1 = r1.var(); vq = rq.var()
            vr = vq / (q * v1) if v1 > 0 else np.nan
            out["vr4"] = vr
            out["vr4_z"] = (vr - 1) / math.sqrt(2 * (2 * q - 1) * (q - 1) / (3.0 * q * n)) if not np.isnan(vr) else np.nan
        out["hurst"] = hurst_rs(d) if n >= 32 else np.nan
    return out


def state_series(bars, w, trend_scan=False):
    """Причинное состояние ряда на окне w: S / T+ / T− / W; метка действует с закрытия бара."""
    c = bars["c"].to_numpy(float)
    df_t, _ = roll_df_t(c, w)
    if trend_scan:
        best_t = np.full(len(c), np.nan); best_b = np.full(len(c), np.nan)
        for L in range(8, w + 1):
            t_l, b_l = roll_slope_t(c, L)
            take = np.isnan(best_t) | (np.abs(t_l) > np.abs(best_t))
            best_t = np.where(take, t_l, best_t); best_b = np.where(take, b_l, best_b)
        sl_t, sl_b = best_t, best_b
    else:
        sl_t, sl_b = roll_slope_t(c, w)
    vr_z, vr = roll_vr_z(c, w)
    st = np.zeros(len(c), np.int8)
    ok = ~np.isnan(df_t) & ~np.isnan(sl_t) & ~np.isnan(vr_z)
    stat = ok & (df_t < -2.86)
    trend_up = ok & ~stat & (sl_t >= 2.0) & (vr_z >= 1.96)
    trend_dn = ok & ~stat & (sl_t <= -2.0) & (vr_z >= 1.96)
    walk = ok & ~stat & ~trend_up & ~trend_dn
    st[stat] = 1; st[trend_up] = 2; st[trend_dn] = 3; st[walk] = 4
    return st, df_t, sl_t, sl_b, vr_z


def runs(values, times_open, times_close, tf):
    """Пробеги одинаковых состояний → участки."""
    v = np.asarray(values); n = len(v)
    if n == 0: return pd.DataFrame()
    change = np.r_[True, v[1:] != v[:-1]]
    starts = np.where(change)[0]; ends = np.r_[starts[1:] - 1, n - 1]
    return pd.DataFrame({"tf": tf, "state": v[starts], "start_bar": starts, "end_bar": ends,
                         "start_open_utc": times_open[starts], "end_close_utc": times_close[ends]})


# ---------------------------------------------------------------- 4. команды
def cmd_label(a):
    t0 = time.time()
    m1 = load_npz(a.npz) if a.npz else load_raw(a.raw)
    m1 = m1[(m1.index >= pd.Timestamp(a.start, tz="UTC")) & (m1.index < pd.Timestamp(a.end, tz="UTC"))]
    log(f"M1 загружено: {len(m1):,} минуток {m1.index[0]} … {m1.index[-1]}")
    vol_src = "сертифицированный кэш"
    if a.volume_nt:
        nt = load_nt_volume(a.volume_nt, a.start, a.end)
        if nt is not None:
            j = m1.join(nt[["o", "h", "l", "c", "v"]], how="left", rsuffix="_nt")
            same = (np.abs(j["c"] - j["c_nt"]) < 1e-9) & (np.abs(j["h"] - j["h_nt"]) < 1e-9)
            log(f"объём из файлов импорта: совпадение цен {same.mean():.6f} на {int(same.sum()):,} минутках")
            m1["v"] = j["v_nt"].fillna(0.0).to_numpy()
            vol_src = "файлы импорта NinjaTrader (цены совпали с сертификатом)"
    filled = 0
    if a.fill_gaps:
        n0 = len(m1); m1 = fill_gaps(m1); filled = int(m1["filled"].sum())
        log(f"пропуски внутри дня заполнены: {filled:,} минуток ({filled / max(1, len(m1)):.3%}), было {n0:,} стало {len(m1):,}")
    else:
        m1["filled"] = np.int8(0)
    tfs = [int(x) for x in a.tfs]
    bars = resample_all(m1, tfs)
    os.makedirs(a.out, exist_ok=True)
    minute_open = m1.index
    labels = {}
    events_all, legs_all, trends_all, states_all = [], [], [], []
    for tf in tfs:
        b = bars[tf].reset_index(drop=True)
        n = max(2, int(round(a.n * (a.n_scale ** tfs.index(tf)))) if a.n_scale != 1.0 else a.n)
        ev = structure(b, n, a.confirm, a.cusum_h)
        ev["tf"] = tf; ev["n"] = n
        for col in ("swing", "trend", "phase"):
            labels[f"{tf}m_{col}"] = project(ev, minute_open, col)
        # ноги между экстремумами в порядке появления
        o = ev.sort_values("bar").reset_index(drop=True)
        c = b["c"].to_numpy(float); hi = b["h"].to_numpy(float); lo = b["l"].to_numpy(float)
        for i in range(len(o) - 1):
            i0, i1 = int(o.loc[i, "bar"]), int(o.loc[i + 1, "bar"])
            if i1 <= i0: continue
            p0, p1 = float(o.loc[i, "price"]), float(o.loc[i + 1, "price"])
            d = 1 if p1 > p0 else -1
            seg = c[i0:i1 + 1]
            s = seg_stats(seg)
            mfe = (hi[i0:i1 + 1].max() - p0) if d > 0 else (p0 - lo[i0:i1 + 1].min())
            mae = (p0 - lo[i0:i1 + 1].min()) if d > 0 else (hi[i0:i1 + 1].max() - p0)
            ticks = (p1 - p0) * d / TICK
            legs_all.append({"tf": tf, "from_kind": o.loc[i, "kind"], "to_kind": o.loc[i + 1, "kind"],
                             "from_swing": SW[int(o.loc[i, "swing"])], "to_swing": SW[int(o.loc[i + 1, "swing"])],
                             "start_utc": o.loc[i, "time"], "end_utc": o.loc[i + 1, "time"], "known_at_utc": o.loc[i + 1, "valid_from"],
                             "direction": d, "start_price": p0, "end_price": p1, "move_abs": abs(p1 - p0), "move_ticks": ticks,
                             "bars": i1 - i0, "minutes": (i1 - i0) * tf, "mfe_ticks": mfe / TICK, "mae_ticks": mae / TICK,
                             "pnl_ideal_usd": ticks * TICK_USD - COST_RT_USD - 2 * SLIP_TICKS * TICK_USD,
                             **{k: v for k, v in s.items()}})
        # трендовые участки: от подтверждения HH (LL) до подтверждения противоположного флипа
        flips = ev[(ev["swing"] == 1) | (ev["swing"] == 3)].reset_index(drop=True)
        cur = None
        for i in range(len(flips)):
            tr_ = int(flips.loc[i, "trend"])
            if cur is None or cur["trend"] != tr_:
                if cur is not None:
                    cur["end_valid_utc"] = flips.loc[i, "valid_from"]; cur["end_conf_bar"] = int(flips.loc[i, "conf_bar"]); trends_all.append(cur)
                cur = {"tf": tf, "trend": TR[tr_], "start_valid_utc": flips.loc[i, "valid_from"], "start_conf_bar": int(flips.loc[i, "conf_bar"]),
                       "anchor_utc": flips.loc[i, "anchor_time"], "legs": 0}
            cur["legs"] += 1
        if cur is not None:
            cur["end_valid_utc"] = pd.NaT; cur["end_conf_bar"] = len(b) - 1; trends_all.append(cur)
        for tdict in [x for x in trends_all if x["tf"] == tf and "stats" not in x]:
            i0, i1 = tdict["start_conf_bar"], tdict["end_conf_bar"]
            seg = c[i0:i1 + 1]; s = seg_stats(seg)
            dirn = 1 if tdict["trend"] == "LONG" else -1
            move = (c[i1] - c[i0]) * dirn
            tdict.update({"bars": i1 - i0, "minutes": (i1 - i0) * tf, "entry_close": c[i0], "exit_close": c[i1],
                          "move_ticks_realized": move / TICK, "pnl_realized_usd": move / TICK * TICK_USD - COST_RT_USD - 2 * SLIP_TICKS * TICK_USD,
                          "max_high": hi[i0:i1 + 1].max(), "min_low": lo[i0:i1 + 1].min(),
                          "mfe_ticks": ((hi[i0:i1 + 1].max() - c[i0]) if dirn > 0 else (c[i0] - lo[i0:i1 + 1].min())) / TICK,
                          "mae_ticks": ((c[i0] - lo[i0:i1 + 1].min()) if dirn > 0 else (hi[i0:i1 + 1].max() - c[i0])) / TICK,
                          **s, "stats": 1})
        # состояния ряда
        w = a.state_window
        st, df_t, sl_t, sl_b, vr_z = state_series(b, w, a.trend_scan)
        st_ev = pd.DataFrame({"valid_from": pd.DatetimeIndex(b["close_utc"]), "state": st})
        st_ev = st_ev[np.r_[True, st[1:] != st[:-1]]]
        labels[f"{tf}m_state"] = project(st_ev.rename(columns={"state": "state"}), minute_open, "state")
        rr = runs(st, pd.DatetimeIndex(b["open_utc"]).to_numpy(), pd.DatetimeIndex(b["close_utc"]).to_numpy(), tf)
        rows = []
        for r in rr.itertuples(index=False):
            i0, i1 = int(r.start_bar), int(r.end_bar)
            if r.state == 0: continue
            seg = c[i0:i1 + 1]; s = seg_stats(seg)
            dirn = 1 if r.state == 2 else (-1 if r.state == 3 else 0)
            move = c[i1] - c[i0]
            rows.append({"tf": tf, "state": ST[int(r.state)], "start_open_utc": r.start_open_utc, "end_close_utc": r.end_close_utc,
                         "bars": i1 - i0 + 1, "minutes": (i1 - i0 + 1) * tf, "start_close": c[i0], "end_close": c[i1],
                         "move_abs": abs(move), "move_ticks": move / TICK, "range_ticks": (hi[i0:i1 + 1].max() - lo[i0:i1 + 1].min()) / TICK,
                         "max_high": hi[i0:i1 + 1].max(), "min_low": lo[i0:i1 + 1].min(),
                         "pnl_hold_direction_usd": (move * dirn / TICK * TICK_USD - COST_RT_USD - 2 * SLIP_TICKS * TICK_USD) if dirn else np.nan,
                         "df_t_at_start": df_t[i0], "slope_t_at_start": sl_t[i0], "vr_z_at_start": vr_z[i0], **s})
        states_all.extend(rows)
        ev["swing_txt"] = ev["swing"].map(SW); ev["trend_txt"] = ev["trend"].map(TR); ev["phase_txt"] = ev["phase"].map(PH)
        events_all.append(ev)
        log(f"ТФ {tf}m: баров {len(b):,}, N={n}, экстремумов {len(ev):,}, участков состояний {len(rows):,}, {time.time() - t0:.0f} с")
    # выгрузка
    lab = pd.DataFrame(labels, index=minute_open)
    out = m1[["o", "h", "l", "c", "v", "filled"]].join(lab)
    np.savez_compressed(os.path.join(a.out, "minutes_labeled.npz"), t_open=out.index.asi8, **{k: out[k].to_numpy() for k in out.columns})
    sample = out.loc[out.index[:3 * 1440]].copy()
    for tf in tfs:
        sample[f"{tf}m_swing"] = sample[f"{tf}m_swing"].map(SW); sample[f"{tf}m_trend"] = sample[f"{tf}m_trend"].map(TR)
        sample[f"{tf}m_phase"] = sample[f"{tf}m_phase"].map(PH); sample[f"{tf}m_state"] = sample[f"{tf}m_state"].map(ST)
    sample.to_csv(os.path.join(a.out, "minutes_labeled_sample.csv"), sep=";", float_format="%.4f")
    pd.concat(events_all).to_csv(os.path.join(a.out, "swings_events.csv"), sep=";", index=False)
    pd.DataFrame(legs_all).to_csv(os.path.join(a.out, "registry_legs.csv"), sep=";", index=False, float_format="%.4f")
    pd.DataFrame([{k: v for k, v in t.items() if k != "stats"} for t in trends_all]).to_csv(os.path.join(a.out, "registry_trends.csv"), sep=";", index=False, float_format="%.4f")
    pd.DataFrame(states_all).to_csv(os.path.join(a.out, "registry_states.csv"), sep=";", index=False, float_format="%.4f")
    manifest = {"script": VERSION, "npz": a.npz, "raw": a.raw, "start": a.start, "end": a.end, "minutes": int(len(out)), "filled_minutes": filled,
                "volume_source": vol_src, "n": a.n, "n_scale": a.n_scale, "confirm": a.confirm, "cusum_h": a.cusum_h,
                "state_window": a.state_window, "trend_scan": a.trend_scan, "tfs": tfs, "tick": TICK, "tick_usd": TICK_USD,
                "costs": {"round_turn_usd": COST_RT_USD, "slippage_ticks_per_fill": SLIP_TICKS},
                "columns": list(out.columns), "codes": {"swing": SW, "trend": TR, "phase": PH, "state": ST}}
    json.dump(manifest, open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
    log(f"готово: {a.out}, {time.time() - t0:.0f} с")


def load_labeled(out):
    z = np.load(os.path.join(out, "minutes_labeled.npz"), allow_pickle=False)
    idx = pd.to_datetime(z["t_open"], unit="ns", utc=True)
    return pd.DataFrame({k: z[k] for k in z.files if k != "t_open"}, index=idx)


def cmd_profile(a):
    d = load_labeled(a.out)
    d = d[d["filled"] == 0]
    td = trading_day(d.index)
    ct = d.index.tz_convert(TZ_EX); be = d.index.tz_convert(TZ_REP)
    minute_of_session = ((ct.hour * 60 + ct.minute) - 17 * 60) % 1440
    sess_open = d.groupby(td)["o"].transform("first")
    d = d.assign(trading_day=td, mos=minute_of_session, berlin_hour=be.hour, wd=pd.DatetimeIndex(td).dayofweek,
                 dev_ticks=(d["c"] - sess_open) / TICK, absret_ticks=np.abs(d["c"].diff()) / TICK, range_ticks=(d["h"] - d["l"]) / TICK)
    # внутридневной путь (минута сессии от 17:00 Чикаго)
    path = d.groupby("mos").agg(dev_mean=("dev_ticks", "mean"), dev_median=("dev_ticks", "median"), absret_mean=("absret_ticks", "mean"),
                                range_mean=("range_ticks", "mean"), vol_mean=("v", "mean"), minutes=("c", "size"))
    path["berlin_time_winter"] = [(pd.Timestamp("2000-01-01 17:00") + pd.Timedelta(minutes=int(m)) + pd.Timedelta(hours=7)).strftime("%H:%M") for m in path.index]
    path.to_csv(os.path.join(a.out, "profile_intraday_path.csv"), sep=";", float_format="%.3f")
    # дни недели (по торговому дню CME)
    daily = d.groupby("trading_day").agg(range_ticks=("h", lambda x: 0), vol=("v", "sum"), absret=("absret_ticks", "sum"), n=("c", "size"), hi=("h", "max"), lo=("l", "min"))
    daily["range_ticks"] = (daily["hi"] - daily["lo"]) / TICK
    daily["wd"] = pd.DatetimeIndex(daily.index).dayofweek
    wd = daily.groupby("wd").agg(days=("n", "size"), range_ticks_mean=("range_ticks", "mean"), range_ticks_median=("range_ticks", "median"),
                                 vol_mean=("vol", "mean"), path_ticks_mean=("absret", "mean"), minutes_mean=("n", "mean"))
    wd.index = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][:len(wd)] if len(wd) <= 7 else wd.index
    wd.to_csv(os.path.join(a.out, "profile_weekdays.csv"), sep=";", float_format="%.2f")
    # часы по Берлину
    hr = d.groupby("berlin_hour").agg(minutes=("c", "size"), vol_per_min=("v", "mean"), absret_mean=("absret_ticks", "mean"),
                                      range_mean=("range_ticks", "mean"), zero_vol_share=("v", lambda x: float((x <= 0).mean())))
    med = hr["vol_per_min"].median()
    hr["thin"] = hr["vol_per_min"] < a.thin_share * med
    hr["activity_rank"] = hr["vol_per_min"].rank(ascending=False).astype(int)
    hr.to_csv(os.path.join(a.out, "profile_berlin_hours.csv"), sep=";", float_format="%.3f")
    # часы × день недели
    hw = d.groupby(["wd", "berlin_hour"]).agg(vol_per_min=("v", "mean"), absret_mean=("absret_ticks", "mean")).reset_index()
    hw.to_csv(os.path.join(a.out, "profile_hours_by_weekday.csv"), sep=";", index=False, float_format="%.3f")
    log("профили записаны")


def cmd_transitions(a):
    d = load_labeled(a.out)
    be = d.index.tz_convert(TZ_REP)
    td = trading_day(d.index)
    rows = []
    for tf in a.tfs:
        col = f"{int(tf)}m_state"
        if col not in d: continue
        st = d[col].to_numpy(np.int8)
        ch = np.where(np.r_[False, (st[1:] != st[:-1]) & (st[1:] > 0) & (st[:-1] > 0)])[0]
        k = a.lookback
        absret = np.abs(np.diff(d["c"].to_numpy(float), prepend=np.nan)) / TICK
        vol = d["v"].to_numpy(float); rng = (d["h"] - d["l"]).to_numpy(float) / TICK
        base_absret, base_vol, base_rng = np.nanmean(absret), np.nanmean(vol), np.nanmean(rng)
        for i in ch:
            if i < 4 * k: continue
            pre, far = slice(i - k, i), slice(i - 4 * k, i - k)
            rows.append({"tf": int(tf), "from": ST[int(st[i - 1])], "to": ST[int(st[i])], "time_utc": d.index[i],
                         "berlin_hour": int(be[i].hour), "weekday": int(pd.Timestamp(td[i]).dayofweek),
                         "absret_ratio_pre_vs_far": np.nanmean(absret[pre]) / max(1e-9, np.nanmean(absret[far])),
                         "vol_ratio_pre_vs_far": np.nanmean(vol[pre]) / max(1e-9, np.nanmean(vol[far])),
                         "range_ratio_pre_vs_far": np.nanmean(rng[pre]) / max(1e-9, np.nanmean(rng[far])),
                         "absret_pre_vs_base": np.nanmean(absret[pre]) / base_absret})
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(a.out, "transitions.csv"), sep=";", index=False, float_format="%.4f")
    if len(t):
        s = t.groupby(["tf", "from", "to"]).agg(n=("time_utc", "size"), absret_ratio=("absret_ratio_pre_vs_far", "median"),
                                                 vol_ratio=("vol_ratio_pre_vs_far", "median"), range_ratio=("range_ratio_pre_vs_far", "median"),
                                                 absret_vs_base=("absret_pre_vs_base", "median"))
        s.to_csv(os.path.join(a.out, "transitions_summary.csv"), sep=";", float_format="%.3f")
        hh = t.groupby(["tf", "berlin_hour"]).size().unstack(fill_value=0)
        hh.to_csv(os.path.join(a.out, "transitions_by_berlin_hour.csv"), sep=";")
    log(f"переходов {len(t):,}; сводки записаны")


def cmd_selftest(a):
    """Разметка на полных данных против разметки на данных, усечённых датой среза: до среза — байт в байт."""
    import copy, tempfile
    cut = pd.Timestamp(a.cut, tz="UTC")
    full = copy.copy(a); full.out = tempfile.mkdtemp()
    part = copy.copy(a); part.out = tempfile.mkdtemp(); part.end = a.cut
    cmd_label(full); cmd_label(part)
    F = load_labeled(full.out); P = load_labeled(part.out)
    F = F[F.index < cut]
    cols = [c for c in F.columns if c.endswith(("_swing", "_trend", "_phase", "_state"))]
    bad = {}
    for c in cols:
        x, y = F[c].to_numpy(), P[c].reindex(F.index).to_numpy()
        diff = int((x != y).sum()); bad[c] = diff
    worst = max(bad.values()) if bad else 0
    print("ПРОВЕРКА ЗАГЛЯДЫВАНИЯ:", "ПРОЙДЕНА — метки до среза совпадают во всех столбцах" if worst == 0 else f"ПРОВАЛ — расхождений: {bad}")
    print({k: v for k, v in bad.items() if v})
    return worst == 0


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)
    def common(p):
        p.add_argument("--npz"); p.add_argument("--raw"); p.add_argument("--volume-nt")
        p.add_argument("--start", default="2015-01-01"); p.add_argument("--end", default="2019-01-01")
        p.add_argument("--out", default="ms/train")
        p.add_argument("--n", type=int, default=5, help="N баров до и после экстремума")
        p.add_argument("--n-scale", type=float, default=1.0, help="масштаб N по ТФ: N_tf = N·scale^k")
        p.add_argument("--tfs", nargs="*", default=[str(x) for x in TFS])
        p.add_argument("--fill-gaps", action="store_true", default=True); p.add_argument("--no-fill-gaps", dest="fill_gaps", action="store_false")
        p.add_argument("--state-window", type=int, default=64)
        p.add_argument("--confirm", choices=["bars", "cusum"], default="bars"); p.add_argument("--cusum-h", type=float, default=3.0)
        p.add_argument("--trend-scan", action="store_true", default=False)
    l = sub.add_parser("label"); common(l)
    s = sub.add_parser("selftest"); common(s); s.add_argument("--cut", required=True)
    pr = sub.add_parser("profile"); pr.add_argument("--out", default="ms/train"); pr.add_argument("--thin-share", type=float, default=0.3)
    tr = sub.add_parser("transitions"); tr.add_argument("--out", default="ms/train"); tr.add_argument("--tfs", nargs="*", default=[str(x) for x in TFS]); tr.add_argument("--lookback", type=int, default=30)
    a = ap.parse_args()
    if a.cmd == "label": cmd_label(a)
    elif a.cmd == "selftest": sys.exit(0 if cmd_selftest(a) else 1)
    elif a.cmd == "profile": cmd_profile(a)
    else: cmd_transitions(a)


if __name__ == "__main__":
    main()
