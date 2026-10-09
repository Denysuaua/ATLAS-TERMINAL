#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_SYN_Test_S021.py — проверки ПК-стенда на синтетическом рынке, v1.0 (2026-10-04)

  pipeline  --raw syn_raw.txt --symbol SYN1     сырьё → кэш движка → сертификат (очиститель
            v2) → проверка сертификата → объём → старшие ТФ против эталона → цены кэша
            против сырья. Синтетика с пропавшими минутками, нулевым объёмом и переходами
            на летнее время — то, на чём ломаются загрузчики.
  reference --raw syn_raw.txt [--instrument MGC] [--qty 3]
            эталон пробоя на синтетике и 11 инвариантов каждой сделки: уровень от базы,
            исполнение по уровню или открытию на разрыве, флаг разрыва, проскальзывание и
            стоп от исполнения, касание уровня, худший порядок на баре входа, цена выхода по
            причине, результат в тиках, окно входа, сделки не перекрываются, MFE и MAE ≥ 0.
  noise     --instrument MGC --runs 20 --days 80        ЭКСПЕРИМЕНТ Э30
            контроль на чистом случайном блуждании без режимов и событий: преимущества нет
            по построению, и средний результат сделки в тиках обязан быть около
            −(проскальзывание входа + выхода). Заметно выше — эталон заглядывает в будущее
            или выгодно выбирает порядок цен внутри бара (AFML гл. 13; MLAM гл. 8).

Скрипт лежит рядом со скриптами стенда (certification) и вызывает их, ничего в них не меняя.
==========================================================================================
"""
import argparse, importlib.util, json, math, os, subprocess, sys, tempfile
from datetime import time as dtime
import numpy as np
import pandas as pd

VERSION = "DZ_SYN_Test_S021-v1.0 (2026-10-04)"
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def _mod(fname, name):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def _run(args):
    r = subprocess.run([PY] + args, cwd=HERE, capture_output=True, text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()
    return r.returncode, (tail[-1] if tail else "")


# ======================================================================================
# pipeline
# ======================================================================================

def pipeline(a):
    root = tempfile.mkdtemp(prefix="dzsyn_")
    raw = os.path.abspath(a.raw)
    cache = os.path.join(root, "syn.npz")
    import shutil; shutil.copy(raw, os.path.join(root, "syn.txt"))
    steps = []
    rc, t = _run(["DZ_OPT_Engine_S021.py", "cache", "--data", os.path.join(root, "syn.txt")]); steps.append(("кэш движка", rc, t))
    rc, t = _run(["DZ_CERT_Data.py", "certify", "--symbol", a.symbol, "--clean", cache, "--tick", str(a.tick),
                  "--point-value", str(a.point_value), "--root", root, "--note", "синтетика DZ_SYN"]); steps.append(("сертификат", rc, t))
    cert = os.path.join(root, a.symbol, f"{a.symbol}_DATA_CERTIFICATE.json")
    rc, t = _run(["DZ_CERT_Data.py", "verify", "--cert", cert]); steps.append(("проверка сертификата", rc, t))
    m1 = os.path.join(root, a.symbol, f"{a.symbol}_M1.npz")
    rc, t = _run(["DZ_DATA_Check_S021.py", "volume", "--npz", m1, "--max-zero-share", "0.01"]); steps.append(("объём", rc, t))
    rc, t = _run(["DZ_DATA_Check_S021.py", "htf-selftest", "--npz", m1]); steps.append(("старшие ТФ = эталон", rc, t))
    ref = _mod("DZ_BT_DualBreakout_S021.py", "ref")
    p = ref.Params(); p.tick = a.tick
    m, _ = ref.load_m1(raw, p, lambda *_: None)
    z = np.load(m1)
    same = len(m) == len(z["c"]) and np.allclose(m.c.values, z["c"]) and np.allclose(m.h.values, z["h"])
    steps.append(("цены сертификата = сырьё", 0 if same else 1, f"минуток {len(m):,}"))
    ok = all(rc == 0 for _, rc, _ in steps)
    for n, rc, t in steps:
        print(f"  {'пройдено' if rc == 0 else 'НЕ ПРОЙДЕНО':<13} {n}: {t[:150]}")
    print(f"{VERSION} · pipeline: {'ПРОЙДЕН' if ok else 'НЕ ПРОЙДЕН'} (папка {root})")
    return ok


# ======================================================================================
# reference — инварианты сделок эталона
# ======================================================================================

def check_trades(m1, trades, p, ref):
    tk = p.tick
    t = m1.index.as_unit("ns").asi8 if hasattr(m1.index, "as_unit") else m1.index.asi8
    o, h, l = m1.o.values, m1.h.values, m1.l.values
    pos = {v: i for i, v in enumerate(t)}
    tz = ref.PROFILE_TZ[p.profile]
    viol = {f"I{i}": 0 for i in range(1, 12)}
    first = {}
    prev_exit = {}
    eps = 1e-6
    for _, r in trades.iterrows():
        d = int(r.Direction)
        k = pos.get(pd.Timestamp(r.EntryTimeUTC).value)
        j = pos.get(pd.Timestamp(r.ExitTimeUTC).value)
        if k is None or j is None:
            viol["I10"] += 1; continue

        def bad(code, why):
            viol[code] += 1
            first.setdefault(code, f"{r.Session} {r.SessionDate} вход {r.EntryTimeUTC}: {why}")
        lvl = r.BaseHigh + tk if d > 0 else r.BaseLow - tk
        if abs(r.EntryLevel - lvl) > eps: bad("I1", f"уровень {r.EntryLevel} ≠ база ± тик {lvl}")
        fill = max(r.EntryLevel, o[k]) if d > 0 else min(r.EntryLevel, o[k])
        if abs(r.EntryPrice - fill) > eps: bad("I2", f"вход {r.EntryPrice} ≠ {fill}")
        if bool(r.EntryGap) != (abs(r.EntryPrice - r.EntryLevel) > eps): bad("I3", "флаг разрыва")
        if abs(r.EntryPriceWithSlip - (r.EntryPrice + d * p.slip_entry_ticks * tk)) > eps or \
           abs(r.StopInitial - (r.EntryPriceWithSlip - d * p.stop_ticks * tk)) > eps: bad("I4", "проскальзывание или стоп")
        if (d > 0 and h[k] < r.EntryLevel - eps) or (d < 0 and l[k] > r.EntryLevel + eps): bad("I5", "бар входа не касался уровня")
        hit = (d > 0 and l[k] <= r.StopInitial + eps) or (d < 0 and h[k] >= r.StopInitial - eps)
        if hit and r.ExitReason != "STOP_ON_ENTRY_BAR": bad("I6", "стоп на баре входа не засчитан")
        if not hit and r.ExitReason == "STOP_ON_ENTRY_BAR": bad("I6", "стоп на баре входа без касания")
        why = None
        if r.ExitReason == "STOP_ON_ENTRY_BAR":
            if abs(r.ExitPrice - r.StopInitial) > eps or j != k: why = "выход не по стопу на баре входа"
        elif r.ExitReason.endswith("_STOP"):
            if d > 0 and (r.ExitPrice > o[j] + eps or r.ExitPrice < l[j] - eps): why = "стоп вне бара"
            if d < 0 and (r.ExitPrice < o[j] - eps or r.ExitPrice > h[j] + eps): why = "стоп вне бара"
            if bool(r.ExitGap) and abs(r.ExitPrice - o[j]) > eps: why = "разрыв не по открытию"
        elif r.ExitReason == "TIME_EXIT":
            if abs(r.ExitPrice - o[j]) > eps: why = "выход по времени не по открытию"
        if why: bad("I7", why)
        g = round(d * (r.ExitPriceWithSlip - r.EntryPriceWithSlip) / tk, 6)
        if abs(g - r.GrossTicks) > 1e-4 or abs(r.ExitPriceWithSlip - (r.ExitPrice - d * p.slip_exit_ticks * tk)) > eps:
            bad("I8", f"результат {r.GrossTicks} ≠ {g}")
        sp = ref.SESSIONS[r.Session]
        lt = pd.Timestamp(r.EntryTimeUTC).tz_convert(tz).time()
        if not (sp["window"][0] <= lt < sp["window"][1]): bad("I9", f"вход {lt} вне окна")
        key = (r.Session, r.SessionDate)
        if key in prev_exit and pd.Timestamp(r.EntryTimeUTC) < prev_exit[key]: bad("I10", "сделки перекрываются")
        prev_exit[key] = pd.Timestamp(r.ExitTimeUTC)
        if r.MFE_Ticks < -eps or r.MAE_Ticks < -eps: bad("I11", "MFE или MAE < 0")
    return viol, first


def reference(a):
    ref = _mod("DZ_BT_DualBreakout_S021.py", "ref")
    ins = json.load(open(os.path.join(HERE, "DZ_INSTRUMENTS_S021.json"), encoding="utf-8"))["instruments"][a.instrument]
    p = ref.Params()
    p.tick = ins["tick"]; p.usd_per_tick = ins["tick_value_usd"] * a.qty
    m1, val = ref.load_m1(a.raw, p, lambda *_: None)
    sess, tr = ref.simulate(m1, p, lambda *_: None)
    if tr.empty:
        print(f"{VERSION} · reference: сделок нет — проверять нечего"); return False
    viol, first = check_trades(m1, tr, p, ref)
    names = {"I1": "уровень от базы", "I2": "исполнение входа", "I3": "флаг разрыва", "I4": "проскальзывание и стоп",
             "I5": "касание уровня", "I6": "худший порядок на баре входа", "I7": "цена выхода по причине",
             "I8": "результат в тиках", "I9": "окно входа", "I10": "сделки не перекрываются", "I11": "MFE и MAE"}
    print(f"{VERSION} · reference  {a.raw}")
    print(f"  минуток {len(m1):,}, сессий {len(sess)}, сделок {len(tr)}; причины выхода: "
          + ", ".join(f"{k} {v}" for k, v in tr.ExitReason.value_counts().items()))
    print(f"  разрывов входа {int(tr.EntryGap.sum())}, разрывов выхода {int(tr.ExitGap.sum())}, "
          f"неоднозначных баров {int(tr.AmbiguousBars.sum())}, итог {tr.NetUSD.sum():.2f}")
    for k, v in viol.items():
        print(f"  {'пройдено' if v == 0 else 'НАРУШЕНО':<10} {k} {names[k]}: {v}" + (f" — {first[k]}" if k in first else ""))
    ok = sum(viol.values()) == 0
    print("  ИТОГ: " + ("все сделки эталона соблюдают инварианты" if ok else "есть нарушения — эталон не годится для сверки"))
    return ok


# ======================================================================================
# noise — Э30
# ======================================================================================

def noise(a):
    ref = _mod("DZ_BT_DualBreakout_S021.py", "ref")
    gen = _mod("DZ_SYN_Market_S021.py", "gen")
    ins = gen.passport(a.instrument)
    gross, nets, n_tr = [], [], 0
    tmp = tempfile.mkdtemp(prefix="dznoise_")
    for seed in range(1, a.runs + 1):
        ns = argparse.Namespace(instrument=a.instrument, start="2025-01-06", days=a.days, seed=seed, scenario="calm",
                                price=None, ou=None, nt_name=None, passport=None, out=os.path.join(tmp, f"rw{seed}"))
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            gen.generate(ns)
        p = ref.Params(); p.tick = ins["tick"]; p.usd_per_tick = ins["tick_value_usd"] * a.qty
        m1, _ = ref.load_m1(ns.out + "_raw.txt", p, lambda *_: None)
        _, tr = ref.simulate(m1, p, lambda *_: None)
        if len(tr):
            gross += list(tr.GrossTicks.values); nets.append(tr.NetUSD.sum()); n_tr += len(tr)
    g = np.array(gross)
    expect = -(ref.Params().slip_entry_ticks + ref.Params().slip_exit_ticks)
    se = g.std(ddof=1) / math.sqrt(len(g)) if len(g) > 1 else float("nan")
    tstat = (g.mean() - expect) / se if se > 0 else float("nan")
    print(f"{VERSION} · noise: прогонов {a.runs} × {a.days} дней случайного блуждания, сделок {n_tr}")
    print(f"  средний результат сделки {g.mean():+.3f} тика (ожидание без преимущества {expect:+.1f}), "
          f"t = {tstat:+.2f}; прогонов в плюсе {sum(1 for x in nets if x > 0)} из {len(nets)}")
    ok = not (tstat > 3.0)
    print("  ИТОГ: " + ("фантомного преимущества нет — эталон не заглядывает в будущее" if ok
                        else "ФАНТОМНОЕ ПРЕИМУЩЕСТВО на шуме — искать заглядывание или выгодный порядок внутри бара"))
    return ok


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("pipeline"); pp.add_argument("--raw", required=True); pp.add_argument("--symbol", default="SYN1")
    pp.add_argument("--tick", type=float, default=0.1); pp.add_argument("--point-value", type=float, default=10.0)
    r = sub.add_parser("reference"); r.add_argument("--raw", required=True); r.add_argument("--instrument", default="MGC")
    r.add_argument("--qty", type=int, default=3)
    n = sub.add_parser("noise"); n.add_argument("--instrument", default="MGC"); n.add_argument("--runs", type=int, default=20)
    n.add_argument("--days", type=int, default=80); n.add_argument("--qty", type=int, default=3)
    a = ap.parse_args()
    ok = {"pipeline": pipeline, "reference": reference, "noise": noise}[a.cmd](a)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
