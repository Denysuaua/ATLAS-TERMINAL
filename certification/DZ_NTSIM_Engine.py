#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_NTSIM_Engine.py — локальная среда бэктеста по правилам исполнения NinjaTrader 8, v1.0

ЭТАЛОН ПРАВИЛ — руководство NinjaTrader 8, раздел 12.4.5 «Historical Order Backfill Logic»:
  «The algorithm fills historical orders using the same set of logic in both scenarios»
  (Strategy Analyzer и исторические ордера живой стратегии). Бар проходится тремя отрезками:
  открытие → первый экстремум → второй экстремум → закрытие, в зависимости от того,
  «moved up first» или «moved down first». Для каждого отрезка:
    рыночный  — по началу отрезка (на первом — открытие), с проскальзыванием;
    стоп      — по уровню, либо по началу отрезка, если цена уже за уровнем (разрыв),
                с проскальзыванием;
    лимит     — «set the fill price to the current order's Limit price»; с включённым
                «Fill Limit Orders on Touch» при касании — по открытию бара.

ЧЕГО РУКОВОДСТВО НЕ ГОВОРИТ, и что поэтому КАЛИБРУЕТСЯ, а не угадывается:
  правило «куда бар двинулся сначала»        --first-move closer | closeopen
  требуется ли пробой лимита или хватает касания --limit through | touch
  исполняются ли выходы на баре входа        сейчас — нет; проверяется калибровкой
Калибровка — командой calibrate на выгрузке сделок Strategy Analyzer.

СТРАТЕГИИ — классы с методом on_bar_update() и API управляемого подхода NinjaScript.
Первая — SampleMACrossOver, копия встроенной @SampleMACrossOver: однозначная логика,
пригодная для проверки паритета исполнения до переноса собственных стратегий.
==========================================================================================
"""
import argparse, importlib.util, json, os, sys
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

VERSION = "DZ_NTSIM_Engine-v1.1 (2026-09-27)"


# ======================================================================================
# 1. ДАННЫЕ: нетребовательная загрузка
# ======================================================================================

def _load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def detect_source_tz(naive, candidates=("America/Chicago", "UTC", "America/New_York", "Europe/Berlin")):
    """
    ЭКСПЕРИМЕНТ. Пояс исходных меток по подписи рынка CME: в поясе Чикаго бары 17:00–17:01
    (открытие Globex) есть каждый будний вечер, а в перерыве 16:15–16:45 баров нет.
    Выбирается пояс, где эта подпись выражена сильнее всего. Для рынков вне CME — задать явно.
    """
    best, score_best, rep = None, -1e9, {}
    for tz in candidates:
        loc = pd.DatetimeIndex(naive).tz_localize(tz, ambiguous="NaT", nonexistent="NaT").dropna()
        ct = loc.tz_convert("America/Chicago")
        wd = ct.dayofweek <= 3; hm = ct.hour * 100 + ct.minute
        reopen = int(((hm >= 1700) & (hm <= 1701) & wd).sum())
        halt = int(((hm >= 1615) & (hm < 1645) & wd).sum())
        s = reopen - 10 * halt
        rep[tz] = {"reopen_bars": reopen, "halt_bars": halt}
        if s > score_best:
            best, score_best = tz, s
    return best, rep


def load_bars(path, src_tz, bar_label, ref_path):
    """
    Любой из форматов: .npz/.parquet из DZ_DATA_Sanitizer; CSV с заголовком или без, с
    разделителем «;», «,» или табуляцией, с датой и временем в одном поле или в двух —
    включая формат выгрузки NinjaTrader «yyyyMMdd HHmmss;O;H;L;C;V». Разбор даты — функции
    эталона DZ_BT (по монотонности времени, без dayfirst наугад).
    Возвращает бары с индексом UTC по времени ОТКРЫТИЯ бара, столбцы o h l c v.
    """
    if path.endswith((".npz", ".parquet")):
        san = _load_mod(os.path.join(os.path.dirname(ref_path) or ".", "DZ_DATA_Sanitizer.py"), "dz_san")
        return san.load_clean(path), {"source": "cache"}
    ref = _load_mod(ref_path, "dz_ref")
    stamp, df = ref.read_raw(path)
    fmt, _ = ref.detect_date_format(stamp, "auto")
    naive = pd.to_datetime(stamp, format=fmt, errors="coerce")
    num = lambda c: pd.to_numeric(df[c], errors="coerce") if c in df.columns else pd.Series(0.0, index=df.index)
    d = pd.DataFrame({"ts": naive, "o": num("Open"), "h": num("High"), "l": num("Low"), "c": num("Close"), "v": num("Volume")}).dropna(subset=["ts", "o", "h", "l", "c"])
    info = {"date_format": fmt}
    if src_tz == "auto":
        src_tz, info["tz_detection"] = detect_source_tz(d.ts)
    loc = pd.DatetimeIndex(d.ts).tz_localize(src_tz, ambiguous="NaT", nonexistent="NaT")
    d = d[~loc.isna()]; loc = loc[~loc.isna()]
    if bar_label == "auto":
        bar_label, info["label_evidence"] = ref.detect_bar_label(loc.tz_convert("America/Chicago").tz_localize(None), "auto")
    utc = loc.tz_convert("UTC") - (pd.Timedelta(minutes=1) if bar_label == "close" else pd.Timedelta(0))
    out = d.drop(columns="ts").set_index(pd.DatetimeIndex(utc, name="t")).sort_index()
    out = out[~out.index.duplicated(keep="first")]
    info.update({"src_tz": src_tz, "bar_label": bar_label, "bars": len(out)})
    return out, info


# ======================================================================================
# 2. ОРДЕРА И ПОЗИЦИЯ
# ======================================================================================

@dataclass
class Order:
    oid: int
    name: str
    side: int              # +1 покупка, −1 продажа
    kind: str              # market | stop | limit
    qty: int
    price: float = float("nan")
    is_entry: bool = True
    from_entry: str = ""
    submitted_bar: int = 0
    touched_bar: int = -1  # бар последнего подтверждения стратегией (isLiveUntilCancelled = false)


@dataclass
class Position:
    side: int = 0
    qty: int = 0
    avg: float = 0.0
    name: str = ""
    entry_time: object = None
    entry_bar: int = -1
    hi: float = float("-inf")
    lo: float = float("inf")


# ======================================================================================
# 3. СТРАТЕГИЯ: API управляемого подхода
# ======================================================================================

class Strategy:
    """База стратегии. Методы повторяют имена NinjaScript; вызываются из on_bar_update()."""
    params = {}

    def __init__(self, **kw):
        self.p = dict(self.params); self.p.update(kw)

    # --- доступ к барам: i баров назад, как Close[i] ---
    def Close(self, i=0): return self._e.c[self._e.k - i]
    def Open(self, i=0): return self._e.o[self._e.k - i]
    def High(self, i=0): return self._e.h[self._e.k - i]
    def Low(self, i=0): return self._e.l[self._e.k - i]
    @property
    def CurrentBar(self): return self._e.k
    @property
    def Position(self): return self._e.pos

    def SMA(self, period, i=0):
        k = self._e.k - i
        return float(np.mean(self._e.c[k - period + 1:k + 1])) if k >= period - 1 else float("nan")

    # --- ордера ---
    def EnterLong(self, qty=1, name="Long"): self._e.submit(name, +1, "market", qty, is_entry=True)
    def EnterShort(self, qty=1, name="Short"): self._e.submit(name, -1, "market", qty, is_entry=True)
    def EnterLongStopMarket(self, qty, price, name="Long"): self._e.submit(name, +1, "stop", qty, price, True)
    def EnterShortStopMarket(self, qty, price, name="Short"): self._e.submit(name, -1, "stop", qty, price, True)
    def EnterLongLimit(self, qty, price, name="Long"): self._e.submit(name, +1, "limit", qty, price, True)
    def EnterShortLimit(self, qty, price, name="Short"): self._e.submit(name, -1, "limit", qty, price, True)
    # Выходы: qty = 0 — вся позиция; иначе частичный выход, остаток позиции живёт дальше.
    def ExitLong(self, qty=0, name="Exit"): self._e.submit(name, -1, "market", qty, is_entry=False)
    def ExitShort(self, qty=0, name="Exit"): self._e.submit(name, +1, "market", qty, is_entry=False)
    def ExitLongLimit(self, qty, price, name="Exit limit"): self._e.submit(name, -1, "limit", qty, price, False)
    def ExitShortLimit(self, qty, price, name="Exit limit"): self._e.submit(name, +1, "limit", qty, price, False)
    def ExitLongStopMarket(self, qty, price, name="Exit stop"): self._e.submit(name, -1, "stop", qty, price, False)
    def ExitShortStopMarket(self, qty, price, name="Exit stop"): self._e.submit(name, +1, "stop", qty, price, False)
    def SetStopLoss(self, ticks=None, price=None): self._e.stop_spec = ("ticks", ticks) if ticks else ("price", price)
    def SetProfitTarget(self, ticks=None, price=None): self._e.target_spec = ("ticks", ticks) if ticks else ("price", price)

    def on_bar_update(self):
        raise NotImplementedError


class SampleMACrossOver(Strategy):
    """
    Копия встроенной @SampleMACrossOver NinjaTrader:
      if (CrossAbove(SMA(Fast), SMA(Slow), 1)) EnterLong();
      else if (CrossBelow(SMA(Fast), SMA(Slow), 1)) EnterShort();
    Проверяйте в Strategy Analyzer с теми же Fast и Slow — это первый тест паритета.
    """
    params = {"Fast": 10, "Slow": 25, "StopTicks": 0, "TargetTicks": 0}

    def on_bar_update(self):
        if self.CurrentBar < self.p["Slow"]:
            return
        if self.p["StopTicks"]: self.SetStopLoss(ticks=self.p["StopTicks"])
        if self.p["TargetTicks"]: self.SetProfitTarget(ticks=self.p["TargetTicks"])
        f0, s0 = self.SMA(self.p["Fast"]), self.SMA(self.p["Slow"])
        f1, s1 = self.SMA(self.p["Fast"], 1), self.SMA(self.p["Slow"], 1)
        if f1 <= s1 and f0 > s0:
            self.EnterLong(name="MA cross up")
        elif f1 >= s1 and f0 < s0:
            self.EnterShort(name="MA cross down")


STRATEGIES = {"SampleMACrossOver": SampleMACrossOver}


# ======================================================================================
# 4. ДВИЖОК: исторический алгоритм исполнения NinjaTrader
# ======================================================================================

@dataclass
class SimConfig:
    qty: int = 1
    slippage_ticks: float = 0.0
    first_move: str = "closer"     # closer — ближний к открытию экстремум первым; closeopen — по знаку C−O
    limit: str = "through"         # through — лимит требует пробоя; touch — хватает касания
    exit_on_session_close: bool = True
    entries_per_direction: int = 1


class Engine:
    def __init__(self, bars, inst, strategy, cfg):
        self.b, self.inst, self.s, self.cfg = bars, inst, strategy, cfg
        self.o, self.h, self.l, self.c = (bars[x].to_numpy(float) for x in "ohlc")
        self.t = bars.index
        self.tick = inst["tick"]
        self.pv = inst["point_value"]
        self.comm = inst.get("commission_per_side", 0.0)
        self.working, self.trades, self.ledger = [], [], []
        self.pos = Position()
        self.stop_spec = self.target_spec = None
        self.k, self._oid = 0, 0
        loc = self.t.tz_convert(inst["tz"])
        close_hm = int(inst["session_close"].replace(":", ""))
        # Время — явно в наносекундах: урок дефекта Д-23.
        tns = pd.DatetimeIndex(self.t).as_unit("ns").asi8 if hasattr(self.t, "as_unit") else self.t.asi8
        nxt = np.r_[tns[1:], tns[-1] + 10 ** 12]
        gap = (nxt - tns) > 30 * 60 * 10 ** 9
        end_hm = (loc + pd.Timedelta(minutes=1)).hour * 100 + (loc + pd.Timedelta(minutes=1)).minute
        # Последний бар сессии: следующий бар далеко либо бар заканчивается на закрытии сессии.
        self.session_last = gap | (end_hm == close_hm)
        strategy._e = self

    # --- подача ордеров из стратегии ---
    def submit(self, name, side, kind, qty, price=float("nan"), is_entry=True):
        # Повторная подача того же ордера обновляет его, а не плодит новый.
        same = [w for w in self.working if w.is_entry == is_entry and w.side == side and w.kind == kind
                and (is_entry or w.name == name) and w.touched_bar < 10 ** 12]
        if same:
            same[0].price, same[0].touched_bar = price, self.k
            if qty:
                same[0].qty = qty
            return
        if is_entry and self.pos.side == side and self.pos.qty >= self.cfg.entries_per_direction * max(1, qty or self.cfg.qty):
            return                                  # EntriesPerDirection
        self._oid += 1
        # Для выхода qty = 0 означает «вся позиция»; прежде подставлялся объём по умолчанию,
        # и ExitLong() на позиции в 3 контракта закрывал только один.
        self.working.append(Order(self._oid, name, side, kind, (qty or self.cfg.qty) if is_entry else qty, price,
                                  is_entry, submitted_bar=self.k, touched_bar=self.k))

    # --- модель пути внутри бара ---
    def _path(self, k):
        o, h, l, c = self.o[k], self.h[k], self.l[k], self.c[k]
        up = (h - o) <= (o - l) if self.cfg.first_move == "closer" else c >= o
        return ([(o, h), (h, l), (l, c)] if up else [(o, l), (l, h), (h, c)]), up

    def _fill_price(self, od, a, b, k, first_seg):
        lo, hi = min(a, b), max(a, b)
        if od.kind == "market":
            px = a if first_seg else None
            if px is None:
                return None
        elif od.kind == "stop":
            if od.side > 0:
                px = a if a >= od.price else (od.price if hi >= od.price else None)
            else:
                px = a if a <= od.price else (od.price if lo <= od.price else None)
            if px is None:
                return None
        else:                                        # limit
            hit = (lo <= od.price if self.cfg.limit == "touch" else lo < od.price) if od.side > 0 else \
                  (hi >= od.price if self.cfg.limit == "touch" else hi > od.price)
            if not hit:
                return None
            return od.price                          # руководство: «the current order's Limit price»
        # проскальзывание — рыночным и стоповым, не выходя за пределы бара
        slip = self.cfg.slippage_ticks * self.tick * od.side
        return min(max(px + slip, self.l[k]), self.h[k])

    def _process_bar(self, k):
        segs, up = self._path(k)
        live = [w for w in self.working]
        filled_ids = set()
        for si, (a, b) in enumerate(segs):
            # Очерёдность по пути цены: рыночный — в начале отрезка, стоп и лимит — по
            # расстоянию от начала отрезка. Прежде — в порядке списка, и стоп мог исполниться
            # раньше рыночного разворота на открытии.
            ordered = sorted(live, key=lambda od: -1.0 if od.kind == "market" else (
                0.0 if od.kind == "stop" and ((od.side > 0 and a >= od.price) or (od.side < 0 and a <= od.price))
                else abs(od.price - a)))
            for od in ordered:
                if od.oid in filled_ids:
                    continue
                if od.is_entry is False and self.pos.side == 0:
                    continue
                px = self._fill_price(od, a, b, k, si == 0)
                if px is None:
                    continue
                filled_ids.add(od.oid)
                if si > 0 and od.kind != "market":
                    self.ledger.append({"bar": str(self.t[k]), "order": od.name, "segment": si, "moved_up_first": up})
                self._execute(od, px, k)
        self.working = [w for w in self.working if w.oid not in filled_ids]

    def _execute(self, od, px, k):
        if od.is_entry:
            if self.pos.side == -od.side:            # разворот: сначала закрыть
                self._close(px, k, "Close position")
            if self.pos.side == 0:
                self.pos = Position(od.side, od.qty, px, od.name, self.t[k], k, px, px)
                self._arm_exits(k)
        else:
            if self.pos.side != 0 and od.side == -self.pos.side:
                self._reduce(px, k, od.name, od.qty)

    def _arm_exits(self, k):
        """Стоп и цель выставляются от цены исполнения, как SetStopLoss/SetProfitTarget в тиках."""
        self.working = [w for w in self.working if w.is_entry]
        side, avg = self.pos.side, self.pos.avg
        for spec, kind, nm in ((self.stop_spec, "stop", "Stop loss"), (self.target_spec, "limit", "Profit target")):
            if not spec:
                continue
            mode, v = spec
            if mode == "ticks":
                price = avg - side * v * self.tick if kind == "stop" else avg + side * v * self.tick
            else:
                price = v
            self._oid += 1
            self.working.append(Order(self._oid, nm, -side, kind, self.pos.qty, price, False,
                                      submitted_bar=k, touched_bar=10 ** 12))

    def _close(self, px, k, reason):
        self._reduce(px, k, reason, 0)

    def _reduce(self, px, k, reason, qty):
        """
        Выход объёмом qty (0 — вся позиция). Четыре действия, и все обязательны:
          1. запись сделки на ВЫШЕДШИЙ объём — так Strategy Analyzer показывает частичные
             исполнения отдельными строками;
          2. уменьшение объёма позиции; средняя цена остатка НЕ меняется;
          3. защитные ордера — на объём остатка, иначе стоп закрыл бы больше, чем осталось;
          4. при нулевом остатке — сброс позиции и снятие всех ордеров выхода.
        """
        p = self.pos
        q = p.qty if (not qty or qty >= p.qty) else qty
        gross = (px - p.avg) * p.side * q * self.pv
        comm = 2 * self.comm * q
        self.trades.append({
            "EntryTimeUTC": str(p.entry_time), "ExitTimeUTC": str(self.t[k]), "Direction": p.side, "Qty": q,
            "EntryPrice": p.avg, "ExitPrice": px, "EntryName": p.name, "ExitName": reason,
            "GrossCurrency": round(gross, 2), "Commission": round(comm, 2), "NetCurrency": round(gross - comm, 2),
            "GrossTicks": round((px - p.avg) * p.side / self.tick, 2),
            "MAE_Ticks": round(max(0.0, (p.avg - p.lo) if p.side > 0 else (p.hi - p.avg)) / self.tick, 1),
            "MFE_Ticks": round(max(0.0, (p.hi - p.avg) if p.side > 0 else (p.avg - p.lo)) / self.tick, 1),
            "BarsHeld": k - p.entry_bar})
        p.qty -= q
        if p.qty <= 0:
            self.working = [w for w in self.working if w.is_entry]
            self.pos = Position()
        else:
            for w in self.working:
                if not w.is_entry and w.touched_bar >= 10 ** 12:
                    w.qty = p.qty

    def run(self):
        n = len(self.c)
        for k in range(n):
            self.k = k
            # Ордера, не подтверждённые на прошлом баре, снимаются (isLiveUntilCancelled = false).
            # Входы и выходы стратегии, не подтверждённые на прошлом баре, снимаются
            # (isLiveUntilCancelled = false). Защитные ордера помечены как вечные.
            self.working = [w for w in self.working if w.touched_bar >= k - 1]
            # Выходы, выставленные при входе на этом баре, в обработку этого бара не попадают:
            # набор ордеров фиксируется на начало бара. Исполнение выхода на баре входа не
            # моделируется — это предположение, проверяемое калибровкой.
            self._process_bar(k)
            if self.pos.side != 0:
                self.pos.hi = max(self.pos.hi, self.h[k]); self.pos.lo = min(self.pos.lo, self.l[k])
            if self.cfg.exit_on_session_close and self.pos.side != 0 and self.session_last[k]:
                self._close(self.c[k], k, "Exit on session close")
            self.s.on_bar_update()
        if self.pos.side != 0:
            self._close(self.c[-1], n - 1, "Data end")
        return pd.DataFrame(self.trades)


# ======================================================================================
# 5. ИТОГ И КАЛИБРОВКА
# ======================================================================================

def perf(tr):
    if len(tr) == 0:
        return {"Trades": 0}
    net = tr.NetCurrency.to_numpy(float); w, l = net[net > 0], net[net < 0]
    eq = np.cumsum(net); dd = float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max())
    return {"Trades": len(net), "NetProfit": round(float(net.sum()), 2), "GrossProfit": round(float(w.sum()), 2),
            "GrossLoss": round(float(l.sum()), 2), "Commission": round(float(tr.Commission.sum()), 2),
            "ProfitFactor": round(float(w.sum() / -l.sum()), 3) if len(l) else None, "MaxDrawdown": round(-dd, 2),
            "WinRatePct": round(100 * len(w) / len(net), 2)}


def apply_task(a, ap):
    """
    Файл задачи Excel: значения ячеек → параметры запуска. Явно заданный ключ командной
    строки имеет приоритет над файлом. Неизвестные ключи сообщаются, а не пропускаются молча.
    """
    if not getattr(a, "task", None):
        return a
    task = json.load(open(a.task, encoding="utf-8"))
    unknown = []
    for k, v in task.items():
        key = k.replace("-", "_")
        if not hasattr(a, key):
            unknown.append(k); continue
        if getattr(a, key) == ap.get_default(key):
            setattr(a, key, json.dumps(v, ensure_ascii=False) if key == "params" and not isinstance(v, str) else v)
    if unknown:
        print(f"ВНИМАНИЕ: в задаче неизвестные ключи {unknown} — проигнорированы")
    return a


def run_once(a, bars, inst, **over):
    cfg = SimConfig(qty=a.qty, slippage_ticks=a.slippage, first_move=over.get("first_move", a.first_move),
                    limit=over.get("limit", a.limit),
                    exit_on_session_close=not a.no_session_exit)
    params = json.loads(a.params) if a.params else {}
    strat = STRATEGIES[a.strategy](**params)
    eng = Engine(bars, inst, strat, cfg)
    return eng.run(), eng.ledger


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("cmd", choices=["run", "calibrate"])
    ap.add_argument("--task", help="файл задачи task.json от Excel")
    ap.add_argument("--data"); ap.add_argument("--instrument")
    ap.add_argument("--instruments", default="DZ_NTSIM_Instruments.json")
    ap.add_argument("--ref", default="DZ_BT_DualBreakout_S021.py")
    ap.add_argument("--src-tz", default="auto"); ap.add_argument("--bar-label", default="auto")
    ap.add_argument("--strategy", default="SampleMACrossOver"); ap.add_argument("--params", default="")
    ap.add_argument("--qty", type=int, default=1); ap.add_argument("--slippage", type=float, default=0.0)
    ap.add_argument("--first-move", default="closer"); ap.add_argument("--limit", default="through")
    ap.add_argument("--no-session-exit", action="store_true")
    ap.add_argument("--start"); ap.add_argument("--end")
    ap.add_argument("--nt-trades", help="выгрузка сделок Strategy Analyzer — для calibrate")
    ap.add_argument("--out", default="ntsim")
    a = apply_task(ap.parse_args(), ap)
    if not a.data or not a.instrument:
        sys.exit("нужны --data и --instrument — в командной строке или в task.json")

    inst = json.load(open(a.instruments, encoding="utf-8"))[a.instrument]
    if not inst.get("verified_in_nt"):
        print(f"ВНИМАНИЕ: параметры {a.instrument} не сверены с Instrument Manager NinjaTrader")
    bars, info = load_bars(a.data, a.src_tz, a.bar_label, a.ref)
    if a.start: bars = bars[bars.index >= pd.Timestamp(a.start, tz="UTC")]
    if a.end: bars = bars[bars.index <= pd.Timestamp(a.end, tz="UTC")]
    print(f"[данные] {info}")

    if a.cmd == "run":
        tr, ledger = run_once(a, bars, inst)
        tr.to_csv(a.out + "_trades.csv", index=False)
        pd.DataFrame(ledger).to_csv(a.out + "_ambiguity.csv", index=False)
        print(f"[итог] {perf(tr)} | исполнений, зависящих от порядка внутри бара: {len(ledger)}")
        return

    # ЭКСПЕРИМЕНТ. Калибровка неизвестных правил по выгрузке Strategy Analyzer.
    opt = _load_mod(os.path.join(os.path.dirname(a.ref) or ".", "DZ_OPT_Engine_S021.py"), "dz_opt")
    rows = []
    for fm in ("closer", "closeopen"):
        for lim in ("through", "touch"):
            tr, _ = run_once(a, bars, inst, first_move=fm, limit=lim)
            f = f"{a.out}_{fm}_{lim}_trades.csv"
            tr.rename(columns={"NetCurrency": "NetUSD", "EntryPrice": "EntryPriceWithSlip", "ExitPrice": "ExitPriceWithSlip"}).to_csv(f, index=False)
            ok, cnt = opt.parity(a.nt_trades, f, "Europe/Berlin", 1.0, 0.005, f.replace("_trades", "_parity"))
            rows.append({"first_move": fm, "limit": lim, "matched": cnt.get("СОВПАДАЕТ", 0), **cnt})
    res = pd.DataFrame(rows).sort_values("matched", ascending=False)
    print(res.to_string(index=False))
    print(f"[калибровка] ближе всего к NinjaTrader: first_move={res.iloc[0].first_move}, limit={res.iloc[0].limit}")


if __name__ == "__main__":
    main()
