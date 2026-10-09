#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_NT_ModelBacktest.py — модельный бэктест, максимально близкий к Strategy Analyzer
NinjaTrader 8, с худшим вариантом там, где путь цены внутри свечи неизвестен.  v1.0

ПРАВИЛА
  Решения — только на закрытом баре (Calculate.OnBarClose). Ордер, поданный на закрытии
  бара k, работает с бара k+1.

  Из руководства NinjaTrader, раздел 12.4.5 «Historical Order Backfill Logic» — как есть:
    рыночный  по открытию бара, с проскальзыванием
    стоп      по уровню; если бар открылся за уровнем — по открытию; с проскальзыванием
    лимит     по цене лимита
    путь бара два возможных: O→H→L→C либо O→L→H→C

  ХУДШИЙ ВАРИАНТ там, где руководство правила не раскрывает:
    лимит      исполняется только при ПРОБОЕ цены, касания мало.
    путь бара  неблагоприятное событие внутри свечи наступает раньше благоприятного:
               сначала движение против позиции; при ожидании входа — вход, затем к стопу.
    бар входа  стоп, выставленный входом, действует сразу; цель — со следующего бара.

  Каждый бар, где путь изменил результат, записывается в журнал неоднозначностей
  с разницей капитала между путями: это цена незнания внутрибарной истории.

ЗАПУСК
  python DZ_NT_ModelBacktest.py --data mgc_export.txt --instrument MGC \
         --params '{"Fast":10,"Slow":25,"StopTicks":40,"TargetTicks":80}' --slippage 1

Использует загрузку данных, реестр инструментов и API стратегий DZ_NTSIM_Engine.py —
один источник, без второй реализации.
==========================================================================================
"""
import argparse, copy, importlib.util, json, os, sys
import numpy as np
import pandas as pd

VERSION = "DZ_NT_ModelBacktest-v1.1 (2026-09-27)"
HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("dz_ntsim", os.path.join(HERE, "DZ_NTSIM_Engine.py"))
E = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(E)


class WorstCaseEngine(E.Engine):

    # ---------- состояние бара: снимок и восстановление ----------
    def _snap(self):
        return (copy.deepcopy(self.pos), [copy.copy(w) for w in self.working],
                len(self.trades), len(self.ledger), self._oid)

    def _restore(self, s):
        self.pos = copy.deepcopy(s[0]); self.working = [copy.copy(w) for w in s[1]]
        del self.trades[s[2]:]; del self.ledger[s[3]:]; self._oid = s[4]

    def _equity(self, k, n0):
        realized = sum(t["NetCurrency"] for t in self.trades[n0:])
        unreal = (self.c[k] - self.pos.avg) * self.pos.side * self.pos.qty * self.pv if self.pos.side else 0.0
        return realized + unreal

    # ---------- один путь бара ----------
    def _run_path(self, k, up, same_bar_exit=True):
        o, h, l, c = self.o[k], self.h[k], self.l[k], self.c[k]
        segs = [(o, h), (h, l), (l, c)] if up else [(o, l), (l, h), (h, c)]
        for si, (a, b) in enumerate(segs):
            cur = a
            while True:
                # Исполняется ордер, до которого цена доходит ПЕРВЫМ: рыночный — в начале
                # отрезка; стоп и лимит — по расстоянию от текущей точки пути. При равенстве —
                # неблагоприятный первым. Прежде ордера брались в порядке списка, и стоп мог
                # исполниться раньше рыночного разворота, стоявшего на открытии.
                best = None
                for od in self.working:
                    if not od.is_entry and self.pos.side == 0:
                        continue
                    if not od.is_entry and od.submitted_bar == k and od.kind == "limit":
                        continue          # цель, выставленная входом этого бара: благоприятное не засчитывается
                    px = self._fill_price(od, cur, b, k, si == 0 and cur == a)
                    if px is None:
                        continue
                    if od.kind == "market":
                        dist = -1.0
                    elif od.kind == "stop" and ((od.side > 0 and cur >= od.price) or (od.side < 0 and cur <= od.price)):
                        dist = 0.0
                    else:
                        dist = abs(od.price - cur)
                    pri = 0 if od.kind == "market" else (1 if (not od.is_entry and od.kind == "stop") else 2)
                    if best is None or (dist, pri) < best[0]:
                        best = ((dist, pri), od, px)
                if best is None:
                    break
                _, od, px = best
                self.working.remove(od)
                self._execute(od, px, k)     # вход ставит стоп и цель — они действуют сразу
                # Следующий ордер отрезка считается от точки исполнения, но не за пределами отрезка.
                cur = min(max(px, min(a, b)), max(a, b))

    # ---------- бар: неблагоприятное событие внутри свечи — раньше благоприятного ----------
    def _process_bar(self, k):
        """
        Худший вариант определяется по СОБЫТИЯМ, а не по капиталу на закрытии бара.
        Критерий по капиталу близорук: отказ от выхода на баре входа делает капитал на
        закрытии хуже, но спасает сделку на следующем баре — проверка это показала.
          позиция длинная на начало бара  → путь O→L→H→C: сначала против позиции
          позиция короткая                → O→H→L→C
          вне рынка, ждёт вход на покупку → O→H→L→C: вход, затем вниз к стопу
          вне рынка, ждёт вход на продажу → O→L→H→C
          ждёт входы в обе стороны        → оба пути, принимается худший капитал на закрытии
        Стоп, выставленный входом, действует уже на баре входа; цель — нет.
        """
        if self.pos.side == 0 and not self.working:
            return
        side = self.pos.side
        mk = [w for w in self.working if w.is_entry and w.kind == "market"]
        if mk:
            side = mk[0].side                          # рыночный вход исполнится по открытию
        if side > 0:
            paths = [False]
        elif side < 0:
            paths = [True]
        else:
            sides = {w.side for w in self.working if w.is_entry}
            paths = [True] if sides == {1} else [False] if sides == {-1} else [True, False]

        s0 = self._snap(); n0 = len(self.trades)
        res = {}
        for up in (True, False):                       # оба пути — для журнала цены незнания
            self._restore(s0); self._run_path(k, up); res[up] = (self._equity(k, n0), self._snap())
        pick = min(paths, key=lambda u: res[u][0])
        self._restore(res[pick][1])
        if abs(res[True][0] - res[False][0]) > 1e-9:
            self.ledger.append({"bar_utc": str(self.t[k]), "assumed_up_first": pick,
                                "equity_assumed": round(res[pick][0], 2), "equity_other": round(res[not pick][0], 2),
                                "cost_of_ignorance": round(abs(res[True][0] - res[False][0]), 2)})


# ======================================================================================
# ИТОГ В СТРУКТУРЕ ВКЛАДКИ «СВОДКА» STRATEGY ANALYZER
# ======================================================================================

def nt_summary(tr, bars):
    if len(tr) == 0:
        return {"Всего сделок": 0}
    net = tr.NetCurrency.to_numpy(float); gross = tr.GrossCurrency.to_numpy(float)
    win, loss, even = net[net > 0], net[net < 0], net[net == 0]
    eq = np.cumsum(net); dd = float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max())
    cw = cl = mw = ml = 0
    for v in net:
        cw, cl = (cw + 1, 0) if v > 0 else ((0, cl + 1) if v < 0 else (0, 0))
        mw, ml = max(mw, cw), max(ml, cl)
    days = max(1.0, (bars.index[-1] - bars.index[0]).total_seconds() / 86400)
    gp, gl = float(gross[gross > 0].sum()), float(gross[gross < 0].sum())
    return {
        "Чистая прибыль": round(float(net.sum()), 2),
        "Валовая прибыль (до комиссии)": round(gp, 2),
        "Валовой убыток (до комиссии)": round(gl, 2),
        "Комиссия": round(float(tr.Commission.sum()), 2),
        "Фактор прибыли (по валовым)": round(gp / -gl, 3) if gl < 0 else None,
        "Макс. просадка (по закрытым сделкам)": round(-dd, 2),
        "Всего сделок": int(len(net)),
        "Процент прибыльных": round(100 * len(win) / len(net), 2),
        "Прибыльных / убыточных / в ноль": f"{len(win)} / {len(loss)} / {len(even)}",
        "Средняя сделка": round(float(net.mean()), 2),
        "Средняя прибыльная": round(float(win.mean()), 2) if len(win) else None,
        "Средняя убыточная": round(float(loss.mean()), 2) if len(loss) else None,
        "Отношение ср. прибыльной к ср. убыточной": round(float(win.mean() / -loss.mean()), 3) if len(win) and len(loss) else None,
        "Макс. прибыльных подряд": mw, "Макс. убыточных подряд": ml,
        "Крупнейшая прибыльная": round(float(net.max()), 2), "Крупнейшая убыточная": round(float(net.min()), 2),
        "Сделок в день": round(len(net) / days, 3),
        "Средняя длительность, баров": round(float(tr.BarsHeld.mean()), 1),
        "Среднее MAE, тиков": round(float(tr.MAE_Ticks.mean()), 2),
        "Среднее MFE, тиков": round(float(tr.MFE_Ticks.mean()), 2),
    }


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--task", help="файл задачи task.json от Excel")
    ap.add_argument("--data"); ap.add_argument("--instrument")
    ap.add_argument("--limit", default="through", choices=["through", "touch"],
                    help="through — лимит только при пробое (стресс-тест); touch — при касании")
    ap.add_argument("--instruments", default=os.path.join(HERE, "DZ_NTSIM_Instruments.json"))
    ap.add_argument("--ref", default=os.path.join(HERE, "DZ_BT_DualBreakout_S021.py"))
    ap.add_argument("--src-tz", default="auto"); ap.add_argument("--bar-label", default="auto")
    ap.add_argument("--strategy", default="SampleMACrossOver"); ap.add_argument("--params", default="")
    ap.add_argument("--qty", type=int, default=1); ap.add_argument("--slippage", type=float, default=0.0)
    ap.add_argument("--no-session-exit", action="store_true")
    ap.add_argument("--start"); ap.add_argument("--end"); ap.add_argument("--out", default="model")
    a = E.apply_task(ap.parse_args(), ap)
    if not a.data or not a.instrument:
        sys.exit("нужны --data и --instrument — в командной строке или в task.json")

    inst = json.load(open(a.instruments, encoding="utf-8"))[a.instrument]
    if not inst.get("verified_in_nt"):
        print(f"ВНИМАНИЕ: параметры {a.instrument} не сверены с Instrument Manager NinjaTrader")
    bars, info = E.load_bars(a.data, a.src_tz, a.bar_label, a.ref)
    if a.start: bars = bars[bars.index >= pd.Timestamp(a.start, tz="UTC")]
    if a.end: bars = bars[bars.index <= pd.Timestamp(a.end, tz="UTC")]

    cfg = E.SimConfig(qty=a.qty, slippage_ticks=a.slippage, limit=a.limit,
                      exit_on_session_close=not a.no_session_exit)
    strat = E.STRATEGIES[a.strategy](**(json.loads(a.params) if a.params else {}))
    eng = WorstCaseEngine(bars, inst, strat, cfg)
    tr = eng.run()

    tr.to_csv(a.out + "_trades.csv", index=False)
    led = pd.DataFrame(eng.ledger); led.to_csv(a.out + "_ambiguity.csv", index=False)
    summ = nt_summary(tr, bars)
    summ["Баров, где путь внутри свечи изменил результат"] = int(len(led))
    summ["Цена незнания пути, всего"] = round(float(led.cost_of_ignorance.sum()), 2) if len(led) else 0.0
    with open(a.out + "_summary.json", "w", encoding="utf-8") as f:
        json.dump({"engine": VERSION, "data": info, "params": vars(a), "summary": summ}, f, ensure_ascii=False, indent=2, default=str)
    print(f"[данные] пояс {info.get('src_tz')}, разметка {info.get('bar_label')}, баров {len(bars):,}")
    for k, v in summ.items():
        print(f"  {k:46} {v}")


if __name__ == "__main__":
    main()
