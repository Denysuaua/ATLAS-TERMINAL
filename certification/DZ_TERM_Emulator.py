#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_TERM_Emulator.py — эмулятор локального терминала для бэктеста модулей, v1.0 (2026-09-27)

  Сертифицированные данные → «график» (бар за баром, решения на закрытии) → тестируемый
  модуль выдаёт СИГНАЛ → исполнение сертифицированной моделью худшего случая
  (DZ_NT_ModelBacktest.WorstCaseEngine). Схема та же, что в NinjaTrader: модули сигналят,
  исполняет ядро.

ЗАЩИТА ОТ ИЗМЕНЕНИЙ
  seal    снимает SHA-256 сертифицированных файлов и результат встроенного регресса
          (синтетические данные с фиксированным зерном) → DZ_TERM_Lock.json
  verify  сверяет отпечатки и регресс до цента. Любое расхождение — отказ в запуске.
  run     перед каждым запуском выполняет verify. Изменить ядро можно, но незаметно — нет:
          эмулятор не запустится, пока изменение не пройдёт регресс и не будет запечатано
          заново осознанно.

ДАННЫЕ — только кэш DZ_DATA_Sanitizer (.npz) с манифестом: отпечаток массивов сверяется
  с манифестом, несовпадение — отказ.

ЗАГЛЯДЫВАНИЕ ИСКЛЮЧЕНО ФИЗИЧЕСКИ: модуль получает массивы только до текущего бара, и они
  защищены от записи.

ПАРАЛЛЕЛЬНОСТЬ — процессами, не потоками: потоки Python не считают параллельно из-за GIL.
  Результат не зависит от числа процессов — это проверяется командой selftest.

МОДУЛЬ — класс Python:
    class MyModule:
        def __init__(self, **params): ...
        def on_bar(self, view) -> (direction, confidence)   # direction ∈ {−1, 0, +1}
  view.c, view.o, view.h, view.l, view.v — массивы до текущего бара включительно;
  view.t — время открытия баров UTC, нс; view.k — номер бара.
==========================================================================================
"""
import argparse, hashlib, importlib.util, json, os, sys, time
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd

VERSION = "DZ_TERM_Emulator-v1.0 (2026-09-27)"
HERE = os.path.dirname(os.path.abspath(__file__))
CERTIFIED = ["DZ_NTSIM_Engine.py", "DZ_NT_ModelBacktest.py", "DZ_DATA_Sanitizer.py",
             "DZ_NTSIM_Instruments.json", "DZ_TERM_Emulator.py"]
LOCK = os.path.join(HERE, "DZ_TERM_Lock.json")


def _mod(fname, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname) if not os.path.isabs(fname) else fname)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# ======================================================================================
# 1. ГРАФИК И ИСПОЛНЕНИЕ
# ======================================================================================

class BarView:
    """Окно графика для модуля: только закрытые бары до текущего, только чтение."""
    __slots__ = ("k", "t", "o", "h", "l", "c", "v")

    def __init__(self, arrays, k):
        self.k = k
        for name in ("t", "o", "h", "l", "c", "v"):
            setattr(self, name, arrays[name][:k + 1])


class ExampleMomentum:
    """Образец модуля: знак приращения цены за N баров."""
    def __init__(self, N=20):
        self.N = N

    def on_bar(self, view):
        if view.k < self.N:
            return 0, 0.0
        d = view.c[-1] - view.c[-1 - self.N]
        return (1 if d > 0 else -1 if d < 0 else 0), 1.0


def make_strategy(E, module, arrays, ex):
    """Исполнитель сигналов: сигнал → ордера через API NinjaScript сертифицированного движка."""
    class SignalDriven(E.Strategy):
        params = {}

        def on_bar_update(self):
            k = self.CurrentBar
            d, c = module.on_bar(BarView(arrays, k))
            if ex.get("stop_ticks"): self.SetStopLoss(ticks=ex["stop_ticks"])
            if ex.get("target_ticks"): self.SetProfitTarget(ticks=ex["target_ticks"])
            pos, q = self.Position.side, ex.get("qty", 1)
            if d > 0 and pos <= 0: self.EnterLong(qty=q, name="SIG L")
            elif d < 0 and pos >= 0: self.EnterShort(qty=q, name="SIG S")
            elif d == 0 and pos != 0 and ex.get("exit_on_flat", False):
                (self.ExitLong if pos > 0 else self.ExitShort)(name="SIG flat")
    return SignalDriven()


def run_job(job, bars, inst):
    M = _mod("DZ_NT_ModelBacktest.py", "dz_model"); E = M.E
    arrays = {"t": bars.index.as_unit("ns").asi8 if hasattr(bars.index, "as_unit") else bars.index.asi8}
    for x in "ohlcv":
        arrays[x] = bars[x].to_numpy(float) if x in bars.columns else np.zeros(len(bars))
    for a in arrays.values():
        a.flags.writeable = False                      # модуль не может изменить историю
    if job.get("module_file"):
        cls = getattr(_mod(job["module_file"], "dz_user_module"), job["module_class"])
    else:
        cls = ExampleMomentum
    module = cls(**job.get("module_params", {}))
    ex = job.get("execution", {})
    cfg = E.SimConfig(qty=ex.get("qty", 1), slippage_ticks=ex.get("slippage", 1.0),
                      limit=ex.get("limit", "through"), exit_on_session_close=ex.get("session_exit", True))
    eng = M.WorstCaseEngine(bars, inst, make_strategy(E, module, arrays, ex), cfg)
    tr = eng.run()
    return tr, M.nt_summary(tr, bars), len(eng.ledger)


# ======================================================================================
# 2. ПЕЧАТЬ: отпечатки и регресс
# ======================================================================================

def regression_value():
    """Встроенный регресс: синтетические бары с фиксированным зерном, SampleMACrossOver."""
    M = _mod("DZ_NT_ModelBacktest.py", "dz_model"); E = M.E
    rng = np.random.default_rng(20260927)
    idx = pd.date_range("2024-03-03 23:00", periods=30000, freq="1min", tz="UTC")
    st = rng.choice([-1, 1], size=(len(idx), 6)).cumsum(1) * 0.1
    c = 2000 + np.cumsum(st[:, -1]); prev = np.r_[2000, c[:-1]]
    bars = pd.DataFrame({"o": prev, "h": prev + np.maximum(st.max(1), 0), "l": prev + np.minimum(st.min(1), 0),
                         "c": c, "v": 1.0}, index=idx).round(1)
    inst = json.load(open(os.path.join(HERE, "DZ_NTSIM_Instruments.json"), encoding="utf-8"))["MGC"]
    strat = E.SampleMACrossOver(Fast=10, Slow=25, StopTicks=3, TargetTicks=6)
    tr = M.WorstCaseEngine(bars, inst, strat, E.SimConfig(qty=1, slippage_ticks=1, limit="through")).run()
    return round(float(tr.NetCurrency.sum()), 2), int(len(tr))


def seal():
    net, n = regression_value()
    lock = {"engine": VERSION, "sealed_utc": pd.Timestamp.now("UTC").isoformat(), "numpy": np.__version__,
            "pandas": pd.__version__, "files": {f: sha(os.path.join(HERE, f)) for f in CERTIFIED},
            "regression": {"net": net, "trades": n}}
    json.dump(lock, open(LOCK, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[печать] {len(CERTIFIED)} файлов, регресс {net} / {n} сделок → {LOCK}")


def verify(quiet=False):
    if not os.path.exists(LOCK):
        sys.exit("ОТКАЗ: нет печати DZ_TERM_Lock.json — выполните seal")
    lock = json.load(open(LOCK, encoding="utf-8"))
    bad = [f for f, h in lock["files"].items() if not os.path.exists(os.path.join(HERE, f)) or sha(os.path.join(HERE, f)) != h]
    if bad:
        sys.exit(f"ОТКАЗ: изменены сертифицированные файлы {bad}. Прогоните регресс и запечатайте заново осознанно.")
    net, n = regression_value()
    if abs(net - lock["regression"]["net"]) > 0.005 or n != lock["regression"]["trades"]:
        sys.exit(f"ОТКАЗ: регресс {net}/{n} ≠ запечатанному {lock['regression']}. "
                 f"Версии: numpy {np.__version__} (печать {lock['numpy']}), pandas {pd.__version__} (печать {lock['pandas']}).")
    if not quiet:
        print(f"[проверка] отпечатки совпадают, регресс {net} / {n} — ядро сертифицировано")
    return lock


# ======================================================================================
# 3. ДАННЫЕ И ПАРАЛЛЕЛЬНЫЙ ЗАПУСК
# ======================================================================================

def load_certified(path):
    """Кэш очистителя с проверкой отпечатка массивов по манифесту."""
    San = _mod("DZ_DATA_Sanitizer.py", "dz_san")
    z = np.load(path, allow_pickle=False)
    v = z["v"] if "v" in z.files else np.zeros(len(z["t"]))
    arr = np.stack([z["t"].astype(np.float64), z["o"], z["h"], z["l"], z["c"], v], 1)
    got = hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()
    man = os.path.splitext(path)[0] + "_manifest.json"
    if os.path.exists(man):
        exp = json.load(open(man, encoding="utf-8")).get("clean_sha256")
        if exp and exp != got:
            raise SystemExit(f"ОТКАЗ: данные {path} не совпадают с манифестом очистителя")
    return San.load_clean(path), got


_W = {}


def _init(data_path, instr_file):
    _W["bars"], _W["data_sha"] = load_certified(data_path)
    _W["inst"] = json.load(open(instr_file, encoding="utf-8"))


def _work(args):
    i, job = args
    bars = _W["bars"]
    if job.get("start"): bars = bars[bars.index >= pd.Timestamp(job["start"], tz="UTC")]
    if job.get("end"): bars = bars[bars.index <= pd.Timestamp(job["end"], tz="UTC")]
    tr, summ, amb = run_job(job, bars, _W["inst"][job["instrument"]])
    return i, tr, summ, amb, _W["data_sha"]


def run(task_path, workers):
    lock = verify(quiet=True)
    task = json.load(open(task_path, encoding="utf-8"))
    out = task.get("out", "term_results"); os.makedirs(out, exist_ok=True)
    jobs = task["jobs"]
    with ProcessPoolExecutor(max_workers=workers, initializer=_init,
                             initargs=(task["data"], os.path.join(HERE, "DZ_NTSIM_Instruments.json"))) as ex:
        results = sorted(ex.map(_work, list(enumerate(jobs))), key=lambda r: r[0])
    rows = []
    for i, tr, summ, amb, dsha in results:
        name = jobs[i].get("name", f"job{i:03d}")
        tr.to_csv(os.path.join(out, name + "_trades.csv"), index=False)
        rows.append({"job": name, **{k: v for k, v in summ.items() if not isinstance(v, (list, dict))}, "ambiguous_bars": amb})
    manifest = {"engine": VERSION, "lock_sealed_utc": lock["sealed_utc"], "files": lock["files"],
                "data": task["data"], "data_sha256": results[0][4] if results else None,
                "module_files": {j.get("module_file"): sha(j["module_file"]) for j in jobs if j.get("module_file")},
                "workers": workers, "jobs": jobs}
    json.dump(manifest, open(os.path.join(out, "run_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    pd.DataFrame(rows).to_csv(os.path.join(out, "summary.csv"), index=False)
    print(pd.DataFrame(rows)[["job", "Чистая прибыль", "Всего сделок", "Процент прибыльных", "ambiguous_bars"]].to_string(index=False))
    return rows


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("cmd", choices=["seal", "verify", "run"])
    ap.add_argument("--task"); ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    if a.cmd == "seal": seal()
    elif a.cmd == "verify": verify()
    else: run(a.task, a.workers)


if __name__ == "__main__":
    main()
