#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_BT_DualBreakout_S021.py — контрольный бэктест пробоя диапазона двух сессий
Версия: DZ_BT_DualBreakout_S021-v1.0 (2026-09-22)

Назначение: честная проверка правил исследования GC 2007–2025 на минутных данных.
Один скрипт для обоих профилей: --profile chicago | berlin.

РЕШЕНИЯ ПО ВОПРОСАМ, ВЫЗВАВШИМ СОМНЕНИЯ
  1. Повторный вход разрешён, но ЧЕСТНО. После выхода стоп-ордер взводится снова
     только когда бар закрылся по входную сторону уровня: стоп на покупку биржа
     примет лишь выше рынка. Ложный вынос с выходом в безубыток и последующий
     истинный пробой дают две сделки. Дефект прежних скриптов — не число входов, а
     ЦЕНА: они записывали повторный вход по уровню, когда рынок был далеко за ним;
     на случайном блуждании это давало PF 7.4 из чистого шума.
  2. Вход при разрыве — по открытию бара, если бар открылся за уровнем.
  3. Стоп при разрыве — по открытию бара. Убыток может превысить стоп.
  4. Порядок событий внутри бара — ХУДШИЙ для позиции: стоп проверяется по уровню,
     действовавшему на начало бара; безубыток и трейлинг, подтянутые максимумом
     бара, начинают действовать со следующего бара. На баре входа безубыток не
     включается, а касание стопа засчитывается. Бары, где порядок имел значение,
     считаются отдельно (AmbiguousBars).
  5. Формат даты — определяется по данным: каждый кандидат проверяется на
     монотонность времени по всему файлу. Никакого dayfirst наугад.
  6. Разметка бара открытием или закрытием — определяется по открытию Globex в 17:00
     по Чикаго: при разметке по открытию бар 17:00 существует, по закрытию — нет.
  7. Пояс исходных данных — America/Chicago (подтверждено). Окна профиля
     применяются в поясе профиля. Старшие серии 15M и 4H строятся ВСЕГДА по
     биржевому времени Чикаго с якорем начала сессии 17:00 — так строит бары
     NinjaTrader по шаблону торговых часов CME, независимо от пояса экрана.
  8. Снимки 15M и 4H — только бары, закрытые СТРОГО ДО начала окна сигналов:
     время закрытия не позже начала окна минус одна минута.
  9. Вечернее направление — тренд дня (закрытие 14:30 против открытия 07:00), как в
     исследовании. Без тихой подмены трендом 4H: отсутствие данных блокирует сессию.
 10. Издержки — комиссия за круг и проскальзывание на каждом рыночном и стоповом
     исполнении, в тиках, настраиваемо.
 11. Контроль — перестановочный тест. Минутные приращения перемешиваются внутри
     каждого дня многократно (--control-runs). Это уничтожает внутридневную
     предсказуемость, сохраняя волатильность, форму баров и дневные изменения.
     Два вывода: медиана PF на перемешанных данных около единицы — метод сам не
     производит преимущества; p-значение — доля перемешиваний с PF не ниже
     основного: не выше 0.05 — внутридневная структура даёт значимое преимущество.
     Фиксированный порог отвергнут: при стопе 200 и редких больших убытках разброс
     PF на сотнях сделок так велик, что порог даёт ложные тревоги на чистом шуме.

ЗАПУСК
  python DZ_BT_DualBreakout_S021.py --data gc-1m.csv --profile chicago --out results
  python DZ_BT_DualBreakout_S021.py --data gc-1m.csv --profile berlin  --out results

ТРЕБОВАНИЯ: Python 3.9+, pandas 1.5+, numpy.
==========================================================================================
"""
import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import time as dtime

import numpy as np
import pandas as pd

VERSION = "DZ_BT_DualBreakout_S021-v1.0 (2026-09-22)"
TZ_SOURCE = "America/Chicago"
TZ_EXCHANGE = "America/Chicago"
PROFILE_TZ = {"chicago": "America/Chicago", "berlin": "Europe/Berlin"}
NS_MIN = 60 * 1_000_000_000


def _ns(idx):
    """
    Целые НАНОСЕКУНДЫ независимо от разрешения индекса. В pandas 2.x разбор строк может
    дать микросекунды, и asi8 тогда возвращает микросекунды. Прежде это ломало молча:
    вычитание NS_MIN отнимало не минуту, а 16,7 часа, и снимки 15M и 4H брались с баров,
    закрытых почти за сутки до окна; pd.Timestamp(целое) показывал 1970 год.
    """
    idx = pd.DatetimeIndex(idx)
    return idx.as_unit("ns").asi8 if hasattr(idx, "as_unit") else idx.asi8

SESSIONS = {
    "MORNING": dict(base=(dtime(6, 0), dtime(7, 0)), window=(dtime(7, 0), dtime(10, 0)),
                    exit=dtime(14, 30), trail_key="trail_morning_ticks"),
    "EVENING": dict(base=(dtime(17, 0), dtime(18, 0)), window=(dtime(18, 0), dtime(20, 0)),
                    exit=dtime(21, 30), trail_key="trail_evening_ticks"),
}

DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y%m%d %H%M%S", "%Y%m%d %H:%M:%S", "%Y%m%d %H%M",
    "%Y%m%d %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
    "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M",
    "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %I:%M %p",
]


@dataclass
class Params:
    profile: str = "chicago"
    tick: float = 0.1
    usd_per_tick: float = 3.0            # 3 MGC по 1 доллару за тик
    commission_rt_usd: float = 1.32      # комиссия за круг на весь объём
    slip_entry_ticks: float = 1.0
    slip_exit_ticks: float = 1.0         # стоп и выход по времени — рыночные исполнения
    stop_ticks: float = 200.0
    be_trigger_ticks: float = 15.0
    be_offset_ticks: float = 1.0
    trail_morning_ticks: float = 15.0
    trail_evening_ticks: float = 10.0
    min_range_ticks: float = 15.0
    max_range_ticks: float = 45.0
    min_base_bars: int = 50              # из 60: меньше — данные неполны, сессия пропускается
    atr_fast: int = 20
    atr_slow: int = 40
    flat_threshold: float = 0.85
    trend_bars: int = 10
    h4_anchor: str = "session"           # session — 17:00 CT, как NinjaTrader; midnight — от полуночи
    evening_dir: str = "daytrend"        # daytrend | h4 | both
    bar_label: str = "auto"              # auto | open | close
    date_format: str = "auto"
    max_entries_per_session: int = 0    # 0 — без ограничения
    control_runs: int = 20              # число перемешиваний; 0 — без контроля
    seed: int = 20260922


# ======================================================================================
# 1. ЗАГРУЗКА И ПРОВЕРКА ДАННЫХ
# ======================================================================================

def sha256_of(path, limit=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def read_raw(path):
    """Чтение с автоопределением разделителя и заголовка. Все поля — строки."""
    head = pd.read_csv(path, sep=None, engine="python", header=None, dtype=str, nrows=3)
    first = " ".join(str(x) for x in head.iloc[0].tolist()).lower()
    has_header = any(k in first for k in ("date", "time", "open", "close", "datum"))
    df = pd.read_csv(path, sep=None, engine="python", header=0 if has_header else None, dtype=str)
    cols = [str(c).strip().strip("<>").lower() for c in df.columns]

    if has_header:
        m = {}
        for c, orig in zip(cols, df.columns):
            if c in ("date", "datum"): m[orig] = "Date"
            elif c in ("time", "zeit"): m[orig] = "Time"
            elif c in ("datetime", "timestamp", "date_time"): m[orig] = "DateTime"
            elif c in ("open", "o"): m[orig] = "Open"
            elif c in ("high", "h"): m[orig] = "High"
            elif c in ("low", "l"): m[orig] = "Low"
            elif c in ("close", "c", "last"): m[orig] = "Close"
            elif c in ("volume", "vol", "v"): m[orig] = "Volume"
        df = df.rename(columns=m)
    else:
        # Без заголовка: дата и время раздельно, если второе поле похоже на время.
        second = str(df.iloc[0, 1])
        if ":" in second or (second.isdigit() and len(second) in (4, 6)):
            names = ["Date", "Time", "Open", "High", "Low", "Close", "Volume"]
        else:
            names = ["DateTime", "Open", "High", "Low", "Close", "Volume"]
        df.columns = names[:df.shape[1]] + [f"X{i}" for i in range(df.shape[1] - len(names))]

    if "DateTime" in df.columns:
        stamp = df["DateTime"].astype(str).str.strip()
    else:
        stamp = df["Date"].astype(str).str.strip() + " " + df["Time"].astype(str).str.strip()
    return stamp, df


def detect_date_format(stamp, forced):
    """
    Формат выбирается по данным. Кандидат обязан разобрать почти все строки и дать
    монотонное время в порядке файла. Неверный порядок дня и месяца на минутных
    данных немедленно даёт скачки назад, поэтому монотонность его отсекает.
    """
    if forced != "auto":
        return forced, {"forced": True}
    sample = stamp.iloc[: min(len(stamp), 50000)]
    survivors = []
    for fmt in DATE_FORMATS:
        p = pd.to_datetime(sample, format=fmt, errors="coerce")
        if p.notna().mean() >= 0.999:
            survivors.append(fmt)
    if not survivors:
        raise SystemExit("ОШИБКА: формат даты не распознан. Укажите --date-format.")
    report = {}
    best, best_score = None, -1.0
    for fmt in survivors:
        p = pd.to_datetime(stamp, format=fmt, errors="coerce")
        ok = p.notna().mean()
        v = p.dropna().values.astype("int64")
        mono = float((np.diff(v) >= 0).mean()) if len(v) > 1 else 0.0
        score = ok * mono
        report[fmt] = {"parsed": round(float(ok), 6), "monotonic": round(mono, 6)}
        if score > best_score:
            best, best_score = fmt, score
    if report[best]["monotonic"] < 0.999:
        raise SystemExit(f"ОШИБКА: ни один формат не даёт монотонного времени: {report}")
    return best, report


def detect_bar_label(local_ct_naive, forced):
    """
    Разметка по открытию или по закрытию — по открытию Globex в 17:00 по Чикаго.
    По открытию: бары 17:00 и 17:01 существуют оба. По закрытию: первый бар 17:01,
    бара 17:00 нет. Сравниваются только будни с понедельника по четверг.
    """
    wd = local_ct_naive.dayofweek
    hm = local_ct_naive.hour * 100 + local_ct_naive.minute
    mask = (wd <= 3)
    n1700 = int(((hm == 1700) & mask).sum())
    n1701 = int(((hm == 1701) & mask).sum())
    evidence = {"bars_at_17:00": n1700, "bars_at_17:01": n1701}
    if forced != "auto":
        return forced, evidence
    if n1701 == 0:
        raise SystemExit("ОШИБКА: нет баров 17:01 по Чикаго — пояс данных не Чикаго? Укажите --bar-label.")
    ratio = n1700 / n1701
    evidence["ratio"] = round(ratio, 4)
    if ratio > 0.8:
        return "open", evidence
    if ratio < 0.2:
        return "close", evidence
    raise SystemExit(f"ОШИБКА: разметка бара неоднозначна {evidence}. Укажите --bar-label.")


def load_m1(path, p, log):
    stamp, df = read_raw(path)
    rows_read = len(df)
    fmt, fmt_report = detect_date_format(stamp, p.date_format)
    ts = pd.to_datetime(stamp, format=fmt, errors="coerce")

    out = pd.DataFrame({
        "ts": ts,
        "o": pd.to_numeric(df["Open"], errors="coerce"),
        "h": pd.to_numeric(df["High"], errors="coerce"),
        "l": pd.to_numeric(df["Low"], errors="coerce"),
        "c": pd.to_numeric(df["Close"], errors="coerce"),
    })
    bad_parse = int(out.isna().any(axis=1).sum())
    out = out.dropna()

    bad_ohlc_mask = (out.h < out.l) | (out.o > out.h) | (out.o < out.l) | (out.c > out.h) | (out.c < out.l) | (out.l <= 0)
    bad_ohlc = int(bad_ohlc_mask.sum())
    out = out[~bad_ohlc_mask]

    # Пояс источника — Чикаго. Смены времени в Чикаго приходятся на воскресенье 02:00,
    # когда биржа закрыта, поэтому неоднозначных меток быть не должно. Они считаются.
    idx = pd.DatetimeIndex(out.ts)
    loc = idx.tz_localize(TZ_SOURCE, ambiguous="NaT", nonexistent="NaT")
    dst_nat = int(loc.isna().sum())
    out = out[~loc.isna()]
    loc = loc[~loc.isna()]

    label, label_ev = detect_bar_label(loc.tz_localize(None), p.bar_label)
    utc = loc.tz_convert("UTC")
    if label == "close":
        utc = utc - pd.Timedelta(minutes=1)   # внутри скрипта всё — по времени ОТКРЫТИЯ бара

    # Индекс ставится самим DatetimeIndex: .values отбросил бы часовой пояс.
    out = out.set_index(pd.DatetimeIndex(utc, name="t")).sort_index()
    if hasattr(out.index, "as_unit"):
        out.index = out.index.as_unit("ns")
    dup = int(out.index.duplicated().sum())
    out = out[~out.index.duplicated(keep="first")]

    step = np.diff(_ns(out.index)) / NS_MIN
    wd = out.index.tz_convert(TZ_SOURCE).dayofweek
    validation = {
        "rows_read": rows_read, "rows_used": int(len(out)),
        "dropped_unparsed": bad_parse, "dropped_bad_ohlc": bad_ohlc,
        "dropped_dst_nat": dst_nat, "dropped_duplicates": dup,
        "date_format": fmt, "date_format_report": fmt_report,
        "bar_label": label, "bar_label_evidence": label_ev,
        "median_step_min": float(np.median(step)) if len(step) else None,
        "saturday_bars": int((wd == 5).sum()),
        "first_bar_utc": str(out.index[0]), "last_bar_utc": str(out.index[-1]),
    }
    log(f"[данные] строк {rows_read:,}, использовано {len(out):,}, формат «{fmt}», разметка «{label}»")
    return out, validation


# ======================================================================================
# 2. СТАРШИЕ СЕРИИ: 15M И 4H ПО БИРЖЕВОМУ ВРЕМЕНИ ЧИКАГО
# ======================================================================================

def build_htf(m1, minutes, anchor_hours):
    """
    Бары старшего таймфрейма в биржевом времени Чикаго. Якорь 17:00 даёт границы
    4H в 17:00, 21:00, 01:00, 05:00, 09:00, 13:00 — как у NinjaTrader при шаблоне CME.
    Время закрытия — плановое: начало бара плюс длительность. Плановое закрытие не
    раньше фактического, поэтому снимок не может использовать бар раньше срока.
    """
    ct = m1.index.tz_convert(TZ_EXCHANGE).tz_localize(None)
    shift = pd.Timedelta(hours=anchor_hours)
    start = (ct - shift).floor(f"{minutes}min") + shift
    g = pd.DataFrame({"o": m1.o.values, "h": m1.h.values, "l": m1.l.values, "c": m1.c.values},
                     index=start).groupby(level=0)
    bars = pd.DataFrame({"o": g.o.first(), "h": g.h.max(), "l": g.l.min(), "c": g.c.last()})
    end_naive = bars.index + pd.Timedelta(minutes=minutes)
    end = pd.DatetimeIndex(end_naive).tz_localize(TZ_EXCHANGE, ambiguous="NaT", nonexistent="NaT")
    bars["close_utc"] = end.tz_convert("UTC")
    return bars.dropna(subset=["close_utc"])


def compute_normvol(b15, p):
    pc = b15.c.shift(1)
    tr = pd.concat([b15.h - b15.l, (b15.h - pc).abs(), (b15.l - pc).abs()], axis=1).max(axis=1)
    tr.iloc[0] = b15.h.iloc[0] - b15.l.iloc[0]
    fast = tr.rolling(p.atr_fast).mean()        # SMA, как в регламенте
    slow = tr.rolling(p.atr_slow).mean()
    return (fast / (slow + 1e-8)).values


def compute_slope(b4, p):
    ret = b4.c / b4.c.shift(1) - 1.0
    mean = ret.rolling(p.trend_bars).mean()
    std = ret.rolling(p.trend_bars).std(ddof=0)  # знак наклона от выбора ddof не зависит
    slope = mean / (std + 1e-8)
    return np.sign(slope).values                 # NaN там, где баров не хватает


def snapshot(close_ns, values, when_ns):
    """Последний бар, закрытый СТРОГО до начала окна: закрытие ≤ начала окна − 1 минута."""
    i = np.searchsorted(close_ns, when_ns - NS_MIN, side="right") - 1
    if i < 0:
        return np.nan, None
    return values[i], int(close_ns[i])


# ======================================================================================
# 3. СИМУЛЯЦИЯ СЕССИИ
# ======================================================================================

def local_to_utc_ns(dates, t, tz):
    naive = pd.to_datetime([f"{d} {t.strftime('%H:%M:%S')}" for d in dates])
    loc = pd.DatetimeIndex(naive).tz_localize(tz, ambiguous="NaT", nonexistent="NaT")
    return _ns(loc.tz_convert("UTC"))


def run_trade(k, direction, level, trail, x_ns, t, o, h, l, c, p):
    """
    Одна сделка от бара исполнения k. Возвращает запись и индекс бара выхода.
    Худший порядок событий внутри бара: стоп проверяется по уровню на начало бара;
    безубыток и трейлинг от максимума бара действуют со следующего бара; на баре
    входа касание стопа засчитывается, безубыток не включается.
    """
    tk = p.tick
    fill = max(level, o[k]) if direction > 0 else min(level, o[k])
    entry_gap = bool(fill != level)
    fill_x = fill + direction * p.slip_entry_ticks * tk
    stop = fill_x - direction * p.stop_ticks * tk

    def S(v):                       # знаковые координаты: короткая позиция отражается
        return direction * v
    sf, s_stop = S(fill), S(stop)
    peak, mfe, mae = sf, 0.0, 0.0
    be, be_t, amb = False, None, 0
    exit_px, exit_t, reason_x, exit_gap, e = None, None, None, False, None

    lo_k, hi_k = (l[k], h[k]) if direction > 0 else (-h[k], -l[k])
    mae, mfe = max(mae, sf - lo_k), max(mfe, hi_k - sf)
    if lo_k <= s_stop:
        exit_px, exit_t, reason_x, amb, e = s_stop, t[k], "STOP_ON_ENTRY_BAR", 1, k
    else:
        for j in range(k + 1, len(t)):
            if t[j] >= x_ns:
                exit_px, exit_t, reason_x, e = S(o[j]), t[j], "TIME_EXIT", j
                break
            lo, hi, op = (l[j], h[j], o[j]) if direction > 0 else (-h[j], -l[j], -o[j])
            if lo <= s_stop:
                exit_gap, exit_px, exit_t, e = bool(op < s_stop), min(s_stop, op), t[j], j
                reason_x = "TRAIL_STOP" if be and s_stop > sf + p.be_offset_ticks * tk + 1e-9 \
                    else ("BE_STOP" if be else "INITIAL_STOP")
                if hi > peak:
                    amb += 1                # новый максимум на баре выхода
                break
            peak = max(peak, hi)
            mfe, mae = max(mfe, peak - sf), max(mae, sf - lo)
            if not be and peak - sf >= p.be_trigger_ticks * tk - 1e-9:
                be, be_t = True, t[j]
                s_stop = max(s_stop, sf + p.be_offset_ticks * tk)
            if be:
                s_stop = max(s_stop, peak - trail * tk)
        if exit_px is None:
            exit_px, exit_t, reason_x, e = S(c[-1]), t[-1], "DATA_END", len(t) - 1

    exit_real = S(exit_px)
    exit_x = exit_real - direction * p.slip_exit_ticks * tk
    gross = round(direction * (exit_x - fill_x) / tk, 6)
    ts = lambda v: str(pd.Timestamp(v, tz="UTC"))
    return dict(Direction=direction, EntryLevel=level, EntryTimeUTC=ts(t[k]), EntryPrice=fill,
                EntryGap=entry_gap, EntryPriceWithSlip=fill_x, StopInitial=stop,
                BEArmedUTC=ts(be_t) if be_t else None, ExitTimeUTC=ts(exit_t), ExitPrice=exit_real,
                ExitPriceWithSlip=exit_x, ExitReason=reason_x, ExitGap=exit_gap,
                MFE_Ticks=round(mfe / tk, 1), MAE_Ticks=round(mae / tk, 1), GrossTicks=gross,
                CommissionUSD=p.commission_rt_usd, NetUSD=round(gross * p.usd_per_tick - p.commission_rt_usd, 2),
                BarsHeld=int(e - k), AmbiguousBars=amb), e


def simulate(m1, p, log, tag="MAIN"):
    tz = PROFILE_TZ[p.profile]
    tk = p.tick
    t = _ns(m1.index)
    o, h, l, c = m1.o.values, m1.h.values, m1.l.values, m1.c.values

    anchor = 17 if p.h4_anchor == "session" else 0
    b15 = build_htf(m1, 15, anchor)
    b4 = build_htf(m1, 240, anchor)
    nv_close, nv_val = _ns(b15.close_utc), compute_normvol(b15, p)
    sl_close, sl_val = _ns(b4.close_utc), compute_slope(b4, p)

    dates = sorted(set(m1.index.tz_convert(tz).date))
    ds = [str(d) for d in dates]
    bnd = {}
    for name, sp in SESSIONS.items():
        bnd[name] = {k: local_to_utc_ns(ds, v, tz) for k, v in
                     (("b0", sp["base"][0]), ("b1", sp["base"][1]), ("w0", sp["window"][0]),
                      ("w1", sp["window"][1]), ("x", sp["exit"]))}
    d0700 = local_to_utc_ns(ds, dtime(7, 0), tz)
    d1430 = local_to_utc_ns(ds, dtime(14, 30), tz)

    sessions, trades = [], []
    for di, D in enumerate(ds):
        # Тренд дня для вечера: открытие первого бара от 07:00, закрытие последнего до 14:30.
        i07 = np.searchsorted(t, d0700[di]); i1430 = np.searchsorted(t, d1430[di])
        day_open = o[i07] if i07 < len(t) and t[i07] < d1430[di] else np.nan
        day_close = c[i1430 - 1] if i1430 - 1 >= 0 and t[i1430 - 1] >= d0700[di] else np.nan

        for name, sp in SESSIONS.items():
            B = bnd[name]
            if min(B["b0"][di], B["w0"][di], B["x"][di]) < 0:
                continue
            b0, b1 = np.searchsorted(t, B["b0"][di]), np.searchsorted(t, B["b1"][di])
            w0, w1 = np.searchsorted(t, B["w0"][di]), np.searchsorted(t, B["w1"][di])
            nbase = b1 - b0
            rec = dict(Profile=p.profile, Session=name, SessionDate=D, BaseBars=int(nbase))
            if nbase == 0 and w1 - w0 == 0:
                continue                                      # биржа закрыта — сессии нет
            if nbase < p.min_base_bars:
                rec.update(Decision="BLOCKED", Reason="NO_BASE_DATA"); sessions.append(rec); continue

            bh, bl = h[b0:b1].max(), l[b0:b1].min()
            rt = round((bh - bl) / tk, 6)
            nv, nv_t = snapshot(nv_close, nv_val, B["w0"][di])
            s4, s4_t = snapshot(sl_close, sl_val, B["w0"][di])
            rec.update(BaseHigh=bh, BaseLow=bl, BaseTicks=rt,
                       NormVol=None if np.isnan(nv) else round(float(nv), 4),
                       NormVolBarCloseUTC=str(pd.Timestamp(nv_t, tz="UTC")) if nv_t else None,
                       Slope4H=None if np.isnan(s4) else int(s4),
                       Slope4HBarCloseUTC=str(pd.Timestamp(s4_t, tz="UTC")) if s4_t else None,
                       DayOpen0700=None if np.isnan(day_open) else day_open,
                       DayClose1430=None if np.isnan(day_close) else day_close)

            reason = None
            if rt < p.min_range_ticks: reason = "RANGE_LOW"
            elif rt > p.max_range_ticks: reason = "RANGE_HIGH"
            elif np.isnan(nv): reason = "NORMVOL_NOT_READY"
            elif nv < p.flat_threshold: reason = "FLAT"
            if reason is None:
                if name == "EVENING" and p.evening_dir in ("daytrend", "both"):
                    if np.isnan(day_open) or np.isnan(day_close):
                        reason = "DAYTREND_MISSING"
                    else:
                        dt_dir = 1 if day_close >= day_open else -1
                        if p.evening_dir == "both":
                            if np.isnan(s4) or s4 == 0: reason = "NO_TREND"
                            elif int(s4) != dt_dir: reason = "DIR_CONFLICT"
                            else: direction = dt_dir
                        else:
                            direction = dt_dir
                else:
                    if np.isnan(s4) or s4 == 0: reason = "NO_TREND"
                    else: direction = int(s4)
            if reason:
                rec.update(Decision="BLOCKED", Reason=reason); sessions.append(rec); continue

            rec["Direction"] = direction
            level = bh + tk if direction > 0 else bl - tk
            rec["EntryLevel"] = level

            # --- отложенный стоп-вход с честным повторным взводом ---
            # Первый ордер ставится к началу окна: бары базы закрылись внутри диапазона,
            # поэтому стоп на уровне заведомо по нужную сторону рынка. После выхода
            # ордер взводится снова, только когда бар ЗАКРЫЛСЯ по входную сторону
            # уровня, и работает со следующего бара. Бар выхода сам может стать баром
            # взвода. Повторный «вход по уровню» при рынке за уровнем невозможен.
            trail = getattr(p, sp["trail_key"])
            x_ns = B["x"][di]
            armed, reset_t, entry_no, st_tr = True, None, 0, []
            j = w0
            while j < w1:
                if not armed:
                    if (direction > 0 and c[j] < level) or (direction < 0 and c[j] > level):
                        armed, reset_t = True, t[j]
                    j += 1
                    continue
                if (direction > 0 and h[j] >= level) or (direction < 0 and l[j] <= level):
                    if p.max_entries_per_session and entry_no >= p.max_entries_per_session:
                        break
                    entry_no += 1
                    tr, e = run_trade(j, direction, level, trail, x_ns, t, o, h, l, c, p)
                    row = dict(Profile=p.profile, Session=name, SessionDate=D, EntryNo=entry_no,
                               ResetBarUTC=None if reset_t is None else str(pd.Timestamp(reset_t, tz="UTC")),
                               BaseHigh=bh, BaseLow=bl, BaseTicks=rt, NormVol=rec["NormVol"], Slope4H=rec["Slope4H"])
                    row.update(tr)
                    trades.append(row); st_tr.append(row)
                    armed, reset_t = False, None
                    j = e
                    continue
                j += 1

            if not st_tr:
                rec.update(Decision="NO_FILL", Reason="LEVEL_NOT_TOUCHED"); sessions.append(rec); continue
            rec.update(Decision="TRADED", Reason=st_tr[-1]["ExitReason"], Entries=len(st_tr),
                       NetUSD=round(sum(x["NetUSD"] for x in st_tr), 2))
            sessions.append(rec)

    log(f"[{tag}] сессий {len(sessions):,}, сделок {len(trades):,}")
    return pd.DataFrame(sessions), pd.DataFrame(trades)


# ======================================================================================
# 4. КОНТРОЛЬНЫЙ ПРОГОН НА ПЕРЕМЕШАННЫХ ДАННЫХ
# ======================================================================================

def permute_within_day(m1, seed):
    """
    Приращения баров относительно предыдущего закрытия перемешиваются внутри каждого
    дня. Сохраняются: распределение приращений, форма баров, дневные изменения,
    календарь. Уничтожается: порядок движений внутри дня — то, на чём стоит пробой.
    """
    rng = np.random.default_rng(seed)
    pc = m1.c.shift(1).fillna(m1.o.iloc[0]).values
    d = np.stack([m1.o.values - pc, m1.h.values - pc, m1.l.values - pc, m1.c.values - pc], axis=1)
    day = m1.index.tz_convert(TZ_EXCHANGE).tz_localize(None).normalize().values
    order = np.arange(len(d))
    starts = np.r_[0, np.flatnonzero(day[1:] != day[:-1]) + 1, len(d)]
    for a, b in zip(starts[:-1], starts[1:]):
        order[a:b] = a + rng.permutation(b - a)
    dp = d[order]
    close = m1.c.values[0] - d[0, 3] + np.cumsum(dp[:, 3])
    prev = np.r_[m1.c.values[0] - d[0, 3], close[:-1]]
    return pd.DataFrame({"o": prev + dp[:, 0], "h": prev + dp[:, 1], "l": prev + dp[:, 2],
                         "c": close}, index=m1.index)


# ======================================================================================
# 5. ПОКАЗАТЕЛИ И ПРОВЕРКИ ЦЕЛОСТНОСТИ
# ======================================================================================

def metrics(tr, p):
    if tr is None or len(tr) == 0:
        return {"Trades": 0}
    tr = tr.sort_values("ExitTimeUTC")
    net = tr.NetUSD.values.astype(float)
    wins, losses = net[net > 0], net[net < 0]
    gp, gl = float(wins.sum()), float(-losses.sum())
    eq = np.cumsum(net)
    dd = float((np.maximum.accumulate(np.r_[0.0, eq]) - np.r_[0.0, eq]).max())
    mw = ml = cw = cl = 0
    for v in net:
        if v > 0: cw += 1; cl = 0
        elif v < 0: cl += 1; cw = 0
        mw, ml = max(mw, cw), max(ml, cl)
    return {
        "Trades": int(len(net)), "WinRatePct": round(100 * len(wins) / len(net), 2),
        "StructuralWinRatePct": round(100 * p.stop_ticks / (p.stop_ticks + p.be_trigger_ticks), 2),
        "ProfitFactor": round(gp / gl, 3) if gl > 0 else None,
        "NetUSD": round(float(net.sum()), 2), "GrossProfitUSD": round(gp, 2), "GrossLossUSD": round(-gl, 2),
        "AvgTradeUSD": round(float(net.mean()), 2),
        "AvgWinUSD": round(float(wins.mean()), 2) if len(wins) else None,
        "AvgLossUSD": round(float(losses.mean()), 2) if len(losses) else None,
        "MaxDrawdownUSD": round(dd, 2), "MaxConsecWins": mw, "MaxConsecLosses": ml,
        "AvgMFE_Ticks": round(float(tr.MFE_Ticks.mean()), 2), "AvgMAE_Ticks": round(float(tr.MAE_Ticks.mean()), 2),
        "EntryGaps": int(tr.EntryGap.sum()), "ExitGaps": int(tr.ExitGap.sum()),
        "AmbiguousBarsTotal": int(tr.AmbiguousBars.sum()),
        "ExitReasons": {k: int(v) for k, v in tr.ExitReason.value_counts().items()},
    }


def integrity(sess, tr, p):
    """Инварианты, нарушение которых означает дефект скрипта, а не свойство рынка."""
    chk = {"reentry_only_after_reset": True, "no_overlapping_trades": True,
           "entry_not_better_than_level": True, "traded_sessions_match": True}
    if len(tr):
        g = tr.sort_values(["SessionDate", "Session", "EntryNo"])
        for _, grp in g.groupby(["SessionDate", "Session"]):
            prev_exit = None
            for r in grp.itertuples():
                if r.EntryNo > 1:
                    rb = r.ResetBarUTC
                    if rb is None or (isinstance(rb, float) and np.isnan(rb)) or not (rb >= prev_exit and r.EntryTimeUTC > rb):
                        chk["reentry_only_after_reset"] = False
                if prev_exit is not None and r.EntryTimeUTC < prev_exit:
                    chk["no_overlapping_trades"] = False
                prev_exit = r.ExitTimeUTC
        lg, sh = tr[tr.Direction > 0], tr[tr.Direction < 0]
        chk["entry_not_better_than_level"] = bool((lg.EntryPrice >= lg.EntryLevel - 1e-9).all()
                                                  and (sh.EntryPrice <= sh.EntryLevel + 1e-9).all())
        chk["traded_sessions_match"] = bool(int((sess.Decision == "TRADED").sum())
                                            == g.groupby(["SessionDate", "Session"]).ngroups)
    chk["all_passed"] = all(chk.values())
    return chk


def yearly(tr, p):
    if len(tr) == 0:
        return pd.DataFrame()
    tr = tr.assign(Year=tr.SessionDate.str[:4])
    rows = []
    for (y, s), g in tr.groupby(["Year", "Session"]):
        m = metrics(g, p)
        rows.append({"Year": y, "Session": s, **{k: v for k, v in m.items() if not isinstance(v, dict)}})
    return pd.DataFrame(rows)


# ======================================================================================
# 6. ЗАПУСК
# ======================================================================================

def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--data", required=True)
    ap.add_argument("--profile", choices=list(PROFILE_TZ), required=True)
    ap.add_argument("--out", default="results")
    for f, v in asdict(Params()).items():
        if f == "profile":
            continue
        typ = type(v)
        if typ is bool:
            ap.add_argument(f"--{f.replace('_', '-')}", type=lambda s: s.lower() in ("1", "true", "yes"), default=v)
        else:
            ap.add_argument(f"--{f.replace('_', '-')}", type=typ, default=v)
    a = ap.parse_args()
    p = Params(**{k: getattr(a, k) for k in asdict(Params()) if hasattr(a, k)})
    os.makedirs(a.out, exist_ok=True)

    def log(msg):
        print(msg, flush=True)

    log(VERSION)
    log(f"профиль {p.profile}, пояс окон {PROFILE_TZ[p.profile]}, старшие серии — Чикаго, якорь 4H {p.h4_anchor}")
    m1, val = load_m1(a.data, p, log)

    sess, tr = simulate(m1, p, log, "ОСНОВНОЙ")
    summary = {
        "script": VERSION, "profile": p.profile, "window_tz": PROFILE_TZ[p.profile],
        "htf_tz": TZ_EXCHANGE, "data_file": os.path.basename(a.data), "data_sha256": sha256_of(a.data),
        "params": asdict(p), "validation": val,
        "sessions": {k: int(v) for k, v in sess.Decision.value_counts().items()} if len(sess) else {},
        "block_reasons": {k: int(v) for k, v in sess[sess.Decision == "BLOCKED"].Reason.value_counts().items()} if len(sess) else {},
        "metrics": metrics(tr, p),
        "metrics_by_session": {s: metrics(g, p) for s, g in tr.groupby("Session")} if len(tr) else {},
        "metrics_by_entry": {"first_entry": metrics(tr[tr.EntryNo == 1], p),
                             "reentries": metrics(tr[tr.EntryNo > 1], p)} if len(tr) else {},
        "entries_per_traded_session": {int(k): int(v) for k, v in
                                       sess[sess.Decision == "TRADED"].Entries.value_counts().sort_index().items()} if len(tr) else {},
        "integrity": integrity(sess, tr, p),
    }

    if p.control_runs > 0:
        pfs, nets = [], []
        for i in range(p.control_runs):
            _, ctr = simulate(permute_within_day(m1, p.seed + i), p, lambda *_: None, "КОНТРОЛЬ")
            cm = metrics(ctr, p)
            if cm.get("ProfitFactor") is not None:
                pfs.append(cm["ProfitFactor"]); nets.append(cm["NetUSD"])
        main_pf = summary["metrics"].get("ProfitFactor")
        if pfs and main_pf is not None:
            arr = np.array(pfs)
            med = float(np.median(arr))
            pval = float((np.sum(arr >= main_pf) + 1) / (len(arr) + 1))
            if med > 1.15:
                verdict = "ВНИМАНИЕ: метод производит преимущество на перемешанных данных — результат недостоверен"
            elif pval <= 0.05:
                verdict = "преимущество статистически значимо: внутридневная структура даёт результат сверх шума"
            else:
                verdict = "преимущество не доказано: основной PF неотличим от перемешанных данных"
        else:
            med, pval, verdict = None, None, "НЕТ ДАННЫХ"
        summary["control"] = {
            "method": "permute_within_day", "runs": p.control_runs, "seed_first": p.seed,
            "pf_median": None if med is None else round(med, 3),
            "pf_p05": round(float(np.percentile(pfs, 5)), 3) if pfs else None,
            "pf_p95": round(float(np.percentile(pfs, 95)), 3) if pfs else None,
            "net_median_usd": round(float(np.median(nets)), 2) if nets else None,
            "main_pf": main_pf, "p_value": None if pval is None else round(pval, 4),
            "verdict": verdict,
        }
        log(f"[контроль] {p.control_runs} перемешиваний: медиана PF {summary['control']['pf_median']}, "
            f"диапазон 5–95% [{summary['control']['pf_p05']} … {summary['control']['pf_p95']}], "
            f"p-значение {summary['control']['p_value']}")
        log(f"[контроль] {verdict}")

    pre = os.path.join(a.out, p.profile)
    sess.to_csv(pre + "_sessions.csv", index=False)
    tr.to_csv(pre + "_trades.csv", index=False)
    yearly(tr, p).to_csv(pre + "_yearly.csv", index=False)
    with open(pre + "_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=lambda x: x.item() if hasattr(x, "item") else str(x))

    m = summary["metrics"]
    log(f"[итог] сделок {m.get('Trades')}, прибыльных {m.get('WinRatePct')}% "
        f"(структурно {m.get('StructuralWinRatePct')}%), PF {m.get('ProfitFactor')}, "
        f"чистыми {m.get('NetUSD')}, просадка {m.get('MaxDrawdownUSD')}")
    log(f"[целостность] {'все проверки пройдены' if summary['integrity']['all_passed'] else 'НАРУШЕНИЯ: ' + str(summary['integrity'])}")
    log(f"[файлы] {pre}_summary.json, _sessions.csv, _trades.csv, _yearly.csv")


if __name__ == "__main__":
    main()
