#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_SA_Audit_S021.py — проверка оптимизации Strategy Analyzer, v1.0 (2026-10-04)

Читает журнал итераций, который коммутатор пишет в анализаторе при [T19]
(dz_export\\sa_runs\\sa_daily_*.csv: итерация, дата, результат, издержки, сделки, настройки),
строит матрицу «дни × итерации» и считает то же, что движок ПК для своих задач:
  DSR — дефлированный Шарп лучшей итерации по числу итераций (AFML с. 204–206);
  PBO — вероятность переподгонки по CSCV (AFML с. 155–156);
  порог «случайного лучшего» — ожидаемый максимум Шарпа без преимущества.
Формулы не переписаны: импортируются из DZ_OPT_Engine_S021.py — одна величина, один источник.

ЕДИНИЦА — день. Дни без сделок — нули: иначе Шарп завышается. Календарь — рабочие дни от
первой до последней даты журнала.

КОМИССИЯ. Trade.ProfitCurrency в руководстве NinjaTrader — «прибыль в валюте» (с. 2393);
включает ли она комиссию, не сказано. По умолчанию результат берётся как есть; при
--subtract-commission комиссия вычитается. Какой вариант верен — сверить один раз по
вкладке Trades анализатора и записать в журнал ревизии.

  python DZ_SA_Audit_S021.py --journal sa_daily_20261004.csv [--since 2026-10-04T12:00]
         [--registry trials_registry.csv --strategy SA_DualBreakout] [--out sa_audit.csv]
==========================================================================================
"""
import argparse, glob, importlib.util, math, os, sys
import numpy as np
import pandas as pd

VERSION = "DZ_SA_Audit_S021-v1.0 (2026-10-04)"
HERE = os.path.dirname(os.path.abspath(__file__))


def _engine():
    spec = importlib.util.spec_from_file_location("dz_engine", os.path.join(HERE, "DZ_OPT_Engine_S021.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def load(paths, subtract_commission):
    frames = [pd.read_csv(p, sep=";", dtype={"iteration": str, "date": str}) for p in paths]
    d = pd.concat(frames, ignore_index=True)
    d["profit"] = pd.to_numeric(d["profit"], errors="coerce").fillna(0.0)
    d["commission"] = pd.to_numeric(d["commission"], errors="coerce").fillna(0.0)
    d["net"] = d["profit"] - (d["commission"] if subtract_commission else 0.0)
    return d


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--journal", nargs="+", required=True, help="файлы sa_daily_*.csv или маска")
    ap.add_argument("--subtract-commission", action="store_true")
    ap.add_argument("--registry", default=None, help="дописать число итераций в реестр испытаний")
    ap.add_argument("--strategy", default="SA_DualBreakout")
    ap.add_argument("--task-id", default=None)
    ap.add_argument("--out", default="sa_audit.csv")
    ap.add_argument("--blocks", type=int, default=10, help="число блоков CSCV")
    a = ap.parse_args()

    paths = sorted({p for pat in a.journal for p in glob.glob(pat)})
    if not paths:
        sys.exit("журнал не найден")
    eng = _engine()
    d = load(paths, a.subtract_commission)
    iters = sorted(d["iteration"].unique())
    dated = d[d["date"].notna() & (d["date"].astype(str).str.len() >= 8)].copy()
    if dated.empty:
        sys.exit("в журнале нет ни одной сделки")
    dated["date"] = pd.to_datetime(dated["date"])
    days = pd.bdate_range(dated["date"].min(), dated["date"].max())
    M = np.zeros((len(days), len(iters)))
    pos = {k: i for i, k in enumerate(iters)}
    piv = dated.groupby(["date", "iteration"])["net"].sum()
    di = {dd: i for i, dd in enumerate(days)}
    for (dd, it), v in piv.items():
        if dd in di:
            M[di[dd], pos[it]] += v

    mu, sd = M.mean(0), M.std(0, ddof=1)
    sr = np.where(sd > 0, mu / np.where(sd > 0, sd, 1), np.nan)
    trades = d.groupby("iteration")["trades"].sum().reindex(iters).fillna(0).astype(int).values
    net = M.sum(0)
    best = int(np.nanargmax(sr))
    x = M[:, best]
    skew = float(pd.Series(x).skew()) if len(x) > 2 else 0.0
    kurt = float(pd.Series(x).kurt() + 3.0) if len(x) > 3 else 3.0
    n_trials = len(iters)
    if a.registry:
        tid = a.task_id or "SA_" + pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        n_trials = eng.registry_add(a.registry, tid, a.strategy, len(iters))
    dsr, sr0 = eng.deflated_sharpe(float(sr[best]), float(np.nanvar(sr)), n_trials, len(days), skew, kurt)
    pbo = eng.pbo_cscv(M, S=a.blocks) if len(iters) >= 2 else None

    rep = pd.DataFrame({"iteration": iters, "net": np.round(net, 2), "trades": trades,
                        "sharpe_daily": np.round(sr, 5)}).sort_values("sharpe_daily", ascending=False)
    params = d.drop_duplicates("iteration").set_index("iteration")["params"]
    rep["params"] = rep["iteration"].map(params)
    rep.to_csv(a.out, index=False, sep=";")

    print(f"{VERSION}")
    print(f"  журналов {len(paths)}, итераций {len(iters)}, дней {len(days)} ({days[0].date()} … {days[-1].date()})"
          f"{', комиссия вычтена' if a.subtract_commission else ''}")
    print(f"  лучшая итерация {iters[best]}: итог {net[best]:.2f}, сделок {trades[best]}, Шарп дневной {sr[best]:.4f}")
    print(f"  испытаний для DSR {n_trials}; порог «случайного лучшего» {sr0}; DSR {dsr}; PBO {pbo}")
    ok = dsr is not None and dsr >= 0.95 and pbo is not None and pbo <= 0.5
    print("  ИТОГ: " + ("преимущество подтверждено с учётом числа итераций" if ok
                        else "преимущество не доказано с учётом числа итераций и переподгонки"))
    print(f"  таблица итераций → {a.out}")


if __name__ == "__main__":
    main()
