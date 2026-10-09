"""Базовый класс баров, которые строятся по тикам (B04 гл.2, §2.3, с.25–32, PDF 52–59).

Тик — строка (date_time, price, volume). Бар закрывается по правилу подкласса;
незавершённые тики переносятся в следующий пакет, поэтому результат не зависит
от размера пакета (тест). Последний незавершённый бар в выход не попадает.

Столбцы выхода (как в каркасе): date_time — время последнего тика бара (для
баров времени — правая граница интервала), tick_num — сквозной номер
последнего тика, open, high, low, close, volume, cum_buy_volume — объём тиков
со знаком +1 по правилу тика, cum_ticks, cum_dollar_value — Σ price·volume.

Ссылки на источники — по каталогу библиотеки: B04 = AFML, страницы «печатная
(PDF)».
"""

from __future__ import annotations

import math
import numbers
import os
import sys
from collections import deque
from typing import Any, Iterable, Iterator

import numpy as np
import pandas as pd

from dz_afml.util.fast_ewma import ewma
from dz_afml.util.misc import crop_data_frame_in_batches

BAR_COLUMNS = ["date_time", "tick_num", "open", "high", "low", "close", "volume",
               "cum_buy_volume", "cum_ticks", "cum_dollar_value"]
TICK_COLUMNS = ["date_time", "price", "volume"]
_NO_WRITE = ("запись файлов библиотекой не выполняется (ТЗ, п.4): верните DataFrame "
             "и сохраните его сами")


def _crop_data_frame_in_batches(df: pd.DataFrame, chunksize: int) -> list[pd.DataFrame]:
    """Режет таблицу тиков на пакеты по chunksize строк.

    То же, что util.misc.crop_data_frame_in_batches: опись каркаса держит
    копию функции в base_bars. Статус: Недостаточно материалов (каркас не
    приложен; поведение однозначно из имени и проверено тестами).
    """
    return crop_data_frame_in_batches(df, chunksize)


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Real) or value < 1:
        raise ValueError(f"{name} должно быть числом >= 1")
    return int(value)


class BaseBars:
    """Общая часть баров по тикам: чтение пакетами, правило тика, сборка строк.

    Входы конструктора:
        metric: что накапливается — 'cum_ticks', 'cum_volume',
            'cum_dollar_value' (для баров времени — None).
        batch_size: строк в пакете при чтении CSV и нарезке таблицы.

    Источник: B04 §2.3, с.25–32 (PDF 52–59): бары времени, тиков, объёма,
        денег; правило тика — §2.3.2.1, с.29 (PDF 56).
    Статус: Подтверждено по официальному учебнику.
    Причинность: бар собирается только из своих тиков; закрытие бара известно
        в момент его последнего тика (для баров времени — на правой границе).
    """

    METRICS = (None, "cum_ticks", "cum_volume", "cum_dollar_value",
               "tick_imbalance", "volume_imbalance", "dollar_imbalance",
               "tick_run", "volume_run", "dollar_run")

    def __init__(self, metric: str | None, batch_size: float = 2e7) -> None:
        if metric not in self.METRICS:
            raise ValueError(f"metric должен быть одним из {self.METRICS[1:]}")
        self.metric = metric
        self.batch_size = _positive_int(batch_size, "batch_size")
        self.prev_price: float | None = None
        self.prev_tick_rule = 0.0
        self.tick_num = 0
        self._pending: dict | None = None
        self._csv_header = False
        self._reset_cache()

    # --- чтение -----------------------------------------------------------
    def batch_run(self, file_path_or_df: Any, verbose: bool = True, to_csv: bool = False,
                  output_path: str | None = None) -> pd.DataFrame:
        """Строит бары по всему источнику пакетами и возвращает таблицу баров.

        Входы: file_path_or_df — DataFrame с тремя столбцами (время, цена,
            объём), список таких таблиц, путь к CSV или файловый объект;
            verbose — печатать номер пакета в stderr; to_csv, output_path —
            запись в файл не поддерживается (ValueError, ТЗ п.4).
        Выход: pd.DataFrame со столбцами BAR_COLUMNS.
        """
        if to_csv or output_path is not None:
            raise ValueError(_NO_WRITE)
        parts = []
        for number, batch in enumerate(self._batch_iterator(file_path_or_df), 1):
            if verbose:
                sys.stderr.write(f"пакет {number}: {len(batch)} строк\n")
            parts.append(self.run(batch))
        parts = [p for p in parts if len(p)]
        if not parts:
            return pd.DataFrame(columns=BAR_COLUMNS)
        return pd.concat(parts, ignore_index=True)

    def _batch_iterator(self, file_path_or_df: Any) -> Iterator[pd.DataFrame]:
        """Отдаёт пакеты тиков из таблицы, списка таблиц или CSV."""
        if isinstance(file_path_or_df, pd.DataFrame):
            if len(file_path_or_df):
                self._assert_csv(file_path_or_df.iloc[:1])
            yield from _crop_data_frame_in_batches(file_path_or_df, self.batch_size)
            return
        if isinstance(file_path_or_df, (list, tuple)):
            for frame in file_path_or_df:
                if len(frame):
                    self._assert_csv(frame.iloc[:1])
                yield from _crop_data_frame_in_batches(frame, self.batch_size)
            return
        first = self._read_first_row(file_path_or_df)
        self._assert_csv(first)
        source = file_path_or_df if hasattr(file_path_or_df, "read") else os.fspath(file_path_or_df)
        reader = pd.read_csv(source, header=0 if self._csv_header else None,
                             names=TICK_COLUMNS, chunksize=self.batch_size)
        yield from reader

    def _read_first_row(self, file_path: Any) -> pd.DataFrame:
        """Читает первую строку данных CSV; заголовок распознаётся по нечисловой цене."""
        source = file_path if hasattr(file_path, "read") else os.fspath(file_path)
        head = pd.read_csv(source, header=None, nrows=2)
        if hasattr(file_path, "seek"):
            file_path.seek(0)
        try:
            float(head.iloc[0, 1])
            self._csv_header = False
            first = head.iloc[:1]
        except (TypeError, ValueError):
            self._csv_header = True
            first = head.iloc[1:2]
        return first

    @staticmethod
    def _assert_csv(test_batch: pd.DataFrame) -> None:
        """Проверяет формат тиков: три столбца — время, цена, объём."""
        if test_batch.shape[1] != 3:
            raise ValueError("нужно ровно три столбца: date_time, price, volume")
        try:
            pd.to_datetime(test_batch.iloc[:, 0])
        except (TypeError, ValueError) as err:
            raise ValueError("первый столбец должен быть временем") from err
        for col, name in ((1, "price"), (2, "volume")):
            try:
                float(test_batch.iloc[0, col])
            except (TypeError, ValueError) as err:
                raise ValueError(f"столбец {name} должен быть числом") from err

    # --- расчёт -------------------------------------------------------------
    def run(self, data: pd.DataFrame) -> pd.DataFrame:
        """Строит бары по одному пакету тиков, продолжая состояние прошлых пакетов."""
        frame = data.copy()
        frame.columns = TICK_COLUMNS
        times = pd.DatetimeIndex(pd.to_datetime(frame["date_time"]))
        if len(times) > 1 and not times.is_monotonic_increasing:
            raise ValueError("время тиков не должно убывать")
        prices = frame["price"].to_numpy(dtype=np.float64)
        volumes = frame["volume"].to_numpy(dtype=np.float64)
        if not (np.all(np.isfinite(prices)) and np.all(np.isfinite(volumes))):
            raise ValueError("в ценах или объёмах есть пропуски")
        if (prices <= 0).any() or (volumes < 0).any():
            raise ValueError("цены должны быть > 0, объём >= 0")
        rows = self._extract_bars({"times": times, "prices": prices, "volumes": volumes})
        return pd.DataFrame(rows, columns=BAR_COLUMNS)

    def _extract_bars(self, data: dict) -> pd.DataFrame:
        raise NotImplementedError("определяется в подклассе")

    def _reset_cache(self) -> None:
        raise NotImplementedError("определяется в подклассе")

    def _update_high_low(self, price: Any) -> tuple[float, float]:
        """Обновляет максимум и минимум незавершённого бара ценой или массивом цен."""
        values = np.atleast_1d(np.asarray(price, dtype=np.float64))
        self.cache["high"] = max(self.cache.get("high", -np.inf), float(values.max()))
        self.cache["low"] = min(self.cache.get("low", np.inf), float(values.min()))
        return self.cache["high"], self.cache["low"]

    def _create_bars(self, date_time: Any, price: float, high_price: float, low_price: float,
                     bars_list: list) -> None:
        """Добавляет в bars_list строку бара из накопленного кэша и цены закрытия."""
        bars_list.append([date_time, self.tick_num, self.cache["open"], high_price, low_price, price,
                          self.cache["volume"], self.cache["buy_volume"], self.cache["ticks"],
                          self.cache["dollar"]])

    def _apply_tick_rule(self, price: Any) -> np.ndarray:
        """Правило тика: знак изменения цены, при нулевом изменении — прошлый знак.

        Источник: B04 §2.3.2.1, с.29 (PDF 56): b_t = b_{t−1} при Δp_t = 0,
            иначе |Δp_t|/Δp_t. Граничное значение переносится между пакетами;
            для самого первого тика ряда знак 0.
        Статус: Подтверждено по официальному учебнику.
        """
        prices = np.atleast_1d(np.asarray(price, dtype=np.float64))
        if prices.size == 0:
            return np.empty(0)
        start = prices[0] if self.prev_price is None else self.prev_price
        signs = np.sign(np.diff(np.r_[start, prices]))
        last = np.where(signs != 0, np.arange(signs.size), -1)
        np.maximum.accumulate(last, out=last)
        filled = np.where(last >= 0, signs[np.maximum(last, 0)], self.prev_tick_rule)
        self.prev_price = float(prices[-1])
        self.prev_tick_rule = float(filled[-1])
        return filled

    def _get_imbalance(self, price: Any, signed_tick: Any, volume: Any) -> np.ndarray:
        """Дисбаланс тика по метрике бара: b_t, b_t·v_t или b_t·p_t·v_t (B04, с.29–30)."""
        signed = np.asarray(signed_tick, dtype=np.float64)
        if self.metric is None or self.metric.startswith(("cum_ticks", "tick_")):
            return signed
        if self.metric.startswith(("cum_volume", "volume_")):
            return signed * np.asarray(volume, dtype=np.float64)
        return signed * np.asarray(volume, dtype=np.float64) * np.asarray(price, dtype=np.float64)

    # --- общие помощники подклассов ---------------------------------------------
    def _with_pending(self, data: dict) -> dict:
        """Добавляет к пакету тики незавершённого бара из прошлого пакета."""
        signs = self._apply_tick_rule(data["prices"])
        merged = {"times": data["times"], "prices": data["prices"], "volumes": data["volumes"],
                  "signs": signs, "first_num": self.tick_num + 1}
        self.tick_num += len(data["prices"])
        if self._pending is not None and len(self._pending["prices"]):
            p = self._pending
            merged = {"times": p["times"].append(data["times"]),
                      "prices": np.r_[p["prices"], data["prices"]],
                      "volumes": np.r_[p["volumes"], data["volumes"]],
                      "signs": np.r_[p["signs"], signs], "first_num": p["first_num"]}
        return merged

    def _rows_from_segments(self, merged: dict, ends: np.ndarray, labels: Any = None) -> list:
        """Строки баров по отрезкам тиков [start, end]; остаток уходит в _pending."""
        prices, volumes, signs = merged["prices"], merged["volumes"], merged["signs"]
        stop = int(ends[-1]) + 1 if len(ends) else 0
        rest = slice(stop, None)
        self._pending = {"times": merged["times"][rest], "prices": prices[rest],
                         "volumes": volumes[rest], "signs": signs[rest],
                         "first_num": merged["first_num"] + stop}
        if not len(ends):
            return []
        starts = np.r_[0, ends[:-1] + 1]
        p, v = prices[:stop], volumes[:stop]
        high = np.maximum.reduceat(p, starts)
        low = np.minimum.reduceat(p, starts)
        vol = np.add.reduceat(v, starts)
        buy = np.add.reduceat(np.where(signs[:stop] > 0, v, 0.0), starts)
        dollar = np.add.reduceat(p * v, starts)
        times = merged["times"][ends] if labels is None else labels
        nums = merged["first_num"] + ends
        return [[times[k], int(nums[k]), p[starts[k]], high[k], low[k], p[ends[k]], vol[k], buy[k],
                 int(ends[k] - starts[k] + 1), dollar[k]] for k in range(len(ends))]


# ---------------------------------------------------------------------------
# Бары по информации: дисбаланс и серии (B04 §2.3.2, с.29–32, PDF 56–59)
# ---------------------------------------------------------------------------
def _open_cache(cache: dict, price: float) -> None:
    if not cache:
        cache.update(open=price, high=price, low=price, volume=0.0, buy_volume=0.0, ticks=0, dollar=0.0)


def _add_tick(cache: dict, price: float, volume: float, sign: float) -> None:
    if price > cache["high"]:
        cache["high"] = price
    if price < cache["low"]:
        cache["low"] = price
    cache["volume"] += volume
    if sign > 0:
        cache["buy_volume"] += volume
    cache["ticks"] += 1
    cache["dollar"] += price * volume


class BaseImbalanceBars(BaseBars):
    """Общая часть баров дисбаланса: тиков (TIB), объёма (VIB), денег (DIB).

    Что делает: θ_T = Σ b_t·x_t, где x_t = 1, v_t или p_t·v_t, b_t — правило тика.
    Бар закрывается на первом T, при котором |θ_T| ≥ E0[T]·|E0[b_t·x_t]|.
    E0[b_t·x_t] — EWM-среднее b_t·x_t последних min(n, expected_imbalance_window)
    тиков; до прогрева (exp_num_ticks_init тиков) бар закрыться не может.
    E0[T] задаёт подкласс: EMA — EWM-среднее длин прошлых баров, Const — число.

    Входы: metric — 'tick_imbalance', 'volume_imbalance', 'dollar_imbalance';
        batch_size; expected_imbalance_window; exp_num_ticks_init — прогрев и
        начальное E0[T]; analyse_thresholds — сохранять пороги по каждому тику
        (bars_thresholds); min_expected_imbalance — ЭКСПЕРИМЕНТ E8: нижняя
        граница |E0[b_t·x_t]| (по умолчанию нет).
    Источник: B04 §2.3.2.1–2.3.2.2, с.29–31 (PDF 56–58).
    Статус: Подтверждено по официальному учебнику.
    На минутках GC неприменимо без тиков: знак сделки по правилу тика
        определяется только по последовательным сделкам.
    Причинность: пороги бара считаются только по тикам прошлых баров (тест).
    """

    _KINDS = ("tick_imbalance", "volume_imbalance", "dollar_imbalance")

    def __init__(self, metric: str, batch_size: float, expected_imbalance_window: int,
                 exp_num_ticks_init: int, analyse_thresholds: bool,
                 min_expected_imbalance: float | None = None) -> None:
        if metric not in self._KINDS:
            raise ValueError(f"metric — одно из {self._KINDS}")
        self.expected_imbalance_window = _positive_int(expected_imbalance_window, "expected_imbalance_window")
        self.exp_num_ticks_init = _positive_int(exp_num_ticks_init, "exp_num_ticks_init")
        if min_expected_imbalance is not None and not (isinstance(min_expected_imbalance, numbers.Real)
                                                       and min_expected_imbalance > 0):
            raise ValueError("min_expected_imbalance — число > 0 или None")
        self.min_expected_imbalance = min_expected_imbalance
        self.analyse_thresholds = bool(analyse_thresholds)
        self.num_ticks_bar: list = []
        self.bars_thresholds: list = []
        self._imbalances: deque = deque(maxlen=max(self.expected_imbalance_window, self.exp_num_ticks_init))
        self._seen = 0
        self.thresholds = {"cum_theta": 0.0, "expected_imbalance": math.nan,
                           "exp_num_ticks": float(self.exp_num_ticks_init)}
        super().__init__(metric, batch_size)

    def _reset_cache(self) -> None:
        """Сбрасывает накопления незавершённого бара (пороги остаются)."""
        self.cache = {}
        self._pending = None
        if hasattr(self, "thresholds"):
            self.thresholds["cum_theta"] = 0.0

    def _get_expected_imbalance(self, window: int) -> float:
        """E0[b_t·x_t]: EWM-среднее (span = k) последних k = min(n, window) значений; до прогрева NaN."""
        if self._seen < self.exp_num_ticks_init or not self._imbalances:
            return math.nan
        values = np.asarray(self._imbalances, dtype=np.float64)
        k = min(len(values), int(window))
        expected = float(ewma(values[-k:], k)[-1])
        floor = self.min_expected_imbalance
        if floor is not None and abs(expected) < floor:
            expected = math.copysign(floor, expected) if expected != 0 else floor
        return expected

    def _get_exp_num_ticks(self) -> float:
        raise NotImplementedError("определяется в подклассе")

    def _extract_bars(self, data: dict) -> list:
        """Проходит тики по одному: накапливает θ и закрывает бар по порогу книги."""
        times, prices, volumes = data["times"], data["prices"], data["volumes"]
        signs = self._apply_tick_rule(prices)
        imbalances = self._get_imbalance(prices, signs, volumes)
        rows: list = []
        th = self.thresholds
        for i in range(len(prices)):
            price, volume, sign, imb = float(prices[i]), float(volumes[i]), float(signs[i]), float(imbalances[i])
            self.tick_num += 1
            _open_cache(self.cache, price)
            _add_tick(self.cache, price, volume, sign)
            self._imbalances.append(imb)
            self._seen += 1
            th["cum_theta"] += imb
            if math.isnan(th["expected_imbalance"]) and self._seen >= self.exp_num_ticks_init:
                th["expected_imbalance"] = self._get_expected_imbalance(self.expected_imbalance_window)
            if self.analyse_thresholds:
                self.bars_thresholds.append({"timestamp": times[i], "cum_theta": th["cum_theta"],
                                             "expected_imbalance": th["expected_imbalance"],
                                             "exp_num_ticks": th["exp_num_ticks"]})
            expected = th["expected_imbalance"]
            if not math.isnan(expected) and abs(th["cum_theta"]) >= th["exp_num_ticks"] * abs(expected):
                self._create_bars(times[i], price, self.cache["high"], self.cache["low"], rows)
                self.num_ticks_bar.append(self.cache["ticks"])
                th["exp_num_ticks"] = self._get_exp_num_ticks()
                th["expected_imbalance"] = self._get_expected_imbalance(self.expected_imbalance_window)
                self._reset_cache()
        return rows


class BaseRunBars(BaseBars):
    """Общая часть баров серий: тиков (TRB), объёма (VRB), денег (DRB).

    Что делает: θ_T = max(Σ_{b=1} x_t, Σ_{b=−1} x_t) — объём (или число тиков)
    каждой стороны без взаимозачёта. Бар закрывается на первом T, при котором
    θ_T ≥ E0[T]·max(P·E0[x|b=1], (1 − P)·E0[x|b=−1]). P — EWM-среднее доли
    покупок в прошлых барах (num_prev_bars), E0[x|b] — EWM-средние x покупок и
    продаж по последним min(n, expected_imbalance_window) тикам каждой стороны.
    До прогрева (exp_num_ticks_init тиков и хотя бы по одной сделке каждой
    стороны) бар закрыться не может; на прогреве P — доля покупок в баре.

    Входы: metric — 'tick_run', 'volume_run', 'dollar_run'; batch_size;
        num_prev_bars; expected_imbalance_window; exp_num_ticks_init;
        analyse_thresholds.
    Источник: B04 §2.3.2.3–2.3.2.4, с.31–32 (PDF 58–59).
    Статус: Подтверждено по официальному учебнику.
    На минутках GC неприменимо без тиков.
    Причинность: пороги бара считаются только по тикам прошлых баров (тест).
    """

    _KINDS = ("tick_run", "volume_run", "dollar_run")

    def __init__(self, metric: str, batch_size: float, num_prev_bars: int, expected_imbalance_window: int,
                 exp_num_ticks_init: int, analyse_thresholds: bool) -> None:
        if metric not in self._KINDS:
            raise ValueError(f"metric — одно из {self._KINDS}")
        self.num_prev_bars = _positive_int(num_prev_bars, "num_prev_bars")
        self.expected_imbalance_window = _positive_int(expected_imbalance_window, "expected_imbalance_window")
        self.exp_num_ticks_init = _positive_int(exp_num_ticks_init, "exp_num_ticks_init")
        self.analyse_thresholds = bool(analyse_thresholds)
        size = max(self.expected_imbalance_window, self.exp_num_ticks_init)
        self._buys: deque = deque(maxlen=size)
        self._sells: deque = deque(maxlen=size)
        self._seen = 0
        self.num_ticks_bar: list = []
        self.buy_ticks_proportion: list = []
        self.bars_thresholds: list = []
        self.thresholds = {"cum_theta_buy": 0.0, "cum_theta_sell": 0.0, "exp_imbalance_buy": math.nan,
                           "exp_imbalance_sell": math.nan, "exp_num_ticks": float(self.exp_num_ticks_init),
                           "exp_buy_ticks_proportion": math.nan, "buy_ticks_num": 0}
        super().__init__(metric, batch_size)

    def _reset_cache(self) -> None:
        """Сбрасывает накопления незавершённого бара (ожидания остаются)."""
        self.cache = {}
        self._pending = None
        if hasattr(self, "thresholds"):
            self.thresholds.update(cum_theta_buy=0.0, cum_theta_sell=0.0, buy_ticks_num=0)

    def _get_expected_imbalance(self, array: Any, window: int, warm_up: bool = False) -> float:
        """EWM-среднее (span = k) последних k = min(n, window) значений стороны; NaN на прогреве."""
        if (warm_up and self._seen < self.exp_num_ticks_init) or len(array) == 0:
            return math.nan
        values = np.asarray(array, dtype=np.float64)
        k = min(len(values), int(window))
        return float(ewma(values[-k:], k)[-1])

    def _get_exp_num_ticks(self) -> float:
        raise NotImplementedError("определяется в подклассе")

    def _extract_bars(self, data: dict) -> list:
        """Проходит тики по одному: копит объём каждой стороны и закрывает бар по порогу книги."""
        times, prices, volumes = data["times"], data["prices"], data["volumes"]
        signs = self._apply_tick_rule(prices)
        imbalances = self._get_imbalance(prices, signs, volumes)
        rows: list = []
        th = self.thresholds
        window = self.expected_imbalance_window
        for i in range(len(prices)):
            price, volume, sign, imb = float(prices[i]), float(volumes[i]), float(signs[i]), float(imbalances[i])
            self.tick_num += 1
            self._seen += 1
            _open_cache(self.cache, price)
            _add_tick(self.cache, price, volume, sign)
            if imb > 0:
                self._buys.append(imb)
                th["cum_theta_buy"] += imb
                th["buy_ticks_num"] += 1
            elif imb < 0:
                self._sells.append(-imb)
                th["cum_theta_sell"] += -imb
            if math.isnan(th["exp_imbalance_buy"]) or math.isnan(th["exp_imbalance_sell"]):
                th["exp_imbalance_buy"] = self._get_expected_imbalance(self._buys, window, warm_up=True)
                th["exp_imbalance_sell"] = self._get_expected_imbalance(self._sells, window, warm_up=True)
                if not (math.isnan(th["exp_imbalance_buy"]) or math.isnan(th["exp_imbalance_sell"])):
                    th["exp_buy_ticks_proportion"] = th["buy_ticks_num"] / self.cache["ticks"]
            if self.analyse_thresholds:
                self.bars_thresholds.append({"timestamp": times[i], **{k: th[k] for k in th}})
            share = th["exp_buy_ticks_proportion"]
            expected = max(th["exp_imbalance_buy"] * share, th["exp_imbalance_sell"] * (1.0 - share))
            theta = max(th["cum_theta_buy"], th["cum_theta_sell"])
            if not math.isnan(expected) and theta >= th["exp_num_ticks"] * expected:
                self._create_bars(times[i], price, self.cache["high"], self.cache["low"], rows)
                self.num_ticks_bar.append(self.cache["ticks"])
                self.buy_ticks_proportion.append(th["buy_ticks_num"] / self.cache["ticks"])
                th["exp_num_ticks"] = self._get_exp_num_ticks()
                recent = np.asarray(self.buy_ticks_proportion[-self.num_prev_bars:], dtype=np.float64)
                th["exp_buy_ticks_proportion"] = float(ewma(recent, self.num_prev_bars)[-1])
                th["exp_imbalance_buy"] = self._get_expected_imbalance(self._buys, window)
                th["exp_imbalance_sell"] = self._get_expected_imbalance(self._sells, window)
                self._reset_cache()
        return rows

