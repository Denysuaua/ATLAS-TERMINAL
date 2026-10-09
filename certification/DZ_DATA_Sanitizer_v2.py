# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_DATA_Sanitizer_v2.py — загрузка кэша и старшие таймфреймы, v2.0 (2026-10-04)

ЗАЧЕМ ВТОРАЯ ВЕРСИЯ, А НЕ ПРАВКА ПЕРВОЙ. Сертификат данных хранит отпечаток очистителя:
правка DZ_DATA_Sanitizer.py сделала бы недействительным сертификат MGC, на котором
посчитаны все 13 148 испытаний реестра. Первая версия остаётся неизменной и проверяет
старые данные; новые сертифицируются этой.

ЧТО ИСПРАВЛЕНО. В v1 параметр anchor_hours принимался, но не использовался: бары 4H
начинались от полуночи UTC (00:00, 04:00 … 20:00 UTC), а NinjaTrader по шаблону CME и
эталон пробоя строят их от начала сессии 17:00 по Чикаго. Здесь формула эталона
(DZ_BT_DualBreakout_S021.build_htf): начало бара = floor(местное время − 17 ч, N мин) + 17 ч
в поясе America/Chicago; закрытие — плановое, начало + N минут. Совпадение с эталоном
проверяет DZ_DATA_Check_S021.py htf-selftest — вторая реализация одной логики допустима
только с перекрёстной сверкой.

ИЗВЕСТНОЕ ОГРАНИЧЕНИЕ. Последний бар перед перерывом 16:00–17:00 получает плановое
закрытие 17:00, а NinjaTrader закрывает его по концу сессии в 16:00. Для снимков «строго
до окна» плановое закрытие консервативно: раньше срока бар не используется.

ЭКСПЕРИМЕНТ — долларовые бары (AFML, гл. 2, с. 27–28): бар закрывается, когда
накопленный оборот цена × объём × стоимость пункта достигает порога. Из минуток это
приближение: бар не может быть короче минуты.
==========================================================================================
"""
import numpy as np
import pandas as pd

VERSION = "DZ_DATA_Sanitizer-v2.0 (2026-10-04)"
TZ_EXCHANGE = "America/Chicago"


def load_clean(path):
    """Кэш движка (t) или сертифицированные массивы (t_open); объём — если есть, иначе нули."""
    z = np.load(path, allow_pickle=False)
    t = pd.to_datetime(z["t"] if "t" in z.files else z["t_open"], unit="ns", utc=True)
    return pd.DataFrame({
        "o": z["o"], "h": z["h"], "l": z["l"], "c": z["c"],
        "v": z["v"] if "v" in z.files else np.zeros(len(t)),
    }, index=t)


def resample(df, minutes, anchor_hours=17):
    """
    Старшие бары от начала сессии в биржевом времени Чикаго. Объём — сумма минуток.
    Индекс и столбец open_utc — время открытия в UTC; close_utc — плановое закрытие.
    """
    ct = df.index.tz_convert(TZ_EXCHANGE).tz_localize(None)
    shift = pd.Timedelta(hours=anchor_hours)
    start = (ct - shift).floor(f"{minutes}min") + shift
    g = pd.DataFrame({"o": df.o.values, "h": df.h.values, "l": df.l.values, "c": df.c.values,
                      "v": df.v.values if "v" in df else np.zeros(len(df))}, index=start).groupby(level=0)
    b = pd.DataFrame({"o": g.o.first(), "h": g.h.max(), "l": g.l.min(), "c": g.c.last(), "v": g.v.sum()})
    open_loc = pd.DatetimeIndex(b.index).tz_localize(TZ_EXCHANGE, ambiguous="NaT", nonexistent="NaT")
    close_loc = pd.DatetimeIndex(b.index + pd.Timedelta(minutes=minutes)).tz_localize(
        TZ_EXCHANGE, ambiguous="NaT", nonexistent="NaT")
    b["open_utc"] = open_loc.tz_convert("UTC")
    b["close_utc"] = close_loc.tz_convert("UTC")
    b = b.dropna(subset=["open_utc", "close_utc"])
    b.index = pd.DatetimeIndex(b["open_utc"])
    return b


def dollar_bars(df, usd_per_bar, point_value):
    """Э8: долларовые бары из минуток. Минутка с нулевым объёмом оборота не добавляет."""
    usd = (df.c.values * np.maximum(df.v.values, 0.0) * point_value).astype(float)
    cum = np.cumsum(usd)
    bar = np.floor((cum - 1e-9) / float(usd_per_bar)).astype(np.int64)
    g = pd.DataFrame({"o": df.o.values, "h": df.h.values, "l": df.l.values, "c": df.c.values,
                      "v": df.v.values, "t": df.index.values}, index=bar).groupby(level=0)
    out = pd.DataFrame({"o": g.o.first(), "h": g.h.max(), "l": g.l.min(), "c": g.c.last(),
                        "v": g.v.sum(), "open_utc": g.t.first(), "last_minute_open_utc": g.t.last()})
    return out.reset_index(drop=True)
