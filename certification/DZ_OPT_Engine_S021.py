#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_OPT_Engine_S021.py — автономная машина оптимизации и сверки со Strategy Analyzer
Версия: DZ_OPT_Engine_S021-v1.0 (2026-09-26)

ПРИНЦИП ЕДИНСТВЕННОГО ИСТОЧНИКА. Логика стратегии не переписывается: машина импортирует
проверенный эталон DZ_BT_DualBreakout_S021.py (--ref). Две реализации одной логики
расходятся молча; эталон проверен на случайном блуждании и сверен с модулем NinjaTrader.

КОМАНДЫ
  run     --task task.json            одна задача оптимизации
  watch   --queue task_queue          наблюдение за папкой задач
  parity  --nt nt.csv --engine e.csv  сверка сделок со Strategy Analyzer
  cache   --data gc-1m.csv            подготовка двоичного кэша данных

РЕЖИМЫ ОПТИМИЗАЦИИ (поле "mode" задачи)
  system  гипотеза: группа параметров из графа; остальное — из базы
  param   цель и её соседи по графу зависимостей до глубины "depth"
  dev     строго перечисленные параметры; никаких автодополнений

ЗАЩИТА ОТ ПЕРЕПОДГОНКИ — встроена, а не опциональна
  реестр испытаний  каждый прогон дописывает число испытаний в trials_registry.csv;
                    дефлированный Шарп считается по СОВОКУПНОМУ числу испытаний проекта
  DSR               Bailey & López de Prado: вероятность, что лучший Шарп выше
                    ожидаемого максимума при нулевом преимуществе
  PBO               вероятность переподгонки по CSCV
  плато             лучшая точка по сглаженной поверхности, а не одиночный пик
==========================================================================================
"""
import argparse, glob, hashlib, importlib.util, itertools, json, math, os, random, re, shutil, sys, time
from concurrent.futures import ProcessPoolExecutor
from statistics import NormalDist
import numpy as np
import pandas as pd

VERSION = "DZ_OPT_Engine_S021-v1.3 (2026-09-30)"
ND = NormalDist()
EULER = 0.5772156649015329


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# ======================================================================================
# 1. ЭТАЛОН И ДАННЫЕ
# ======================================================================================

def load_reference(path):
    spec = importlib.util.spec_from_file_location("dz_reference", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_cache(ref, data_path, cache_path):
    """Разбор CSV — один раз. Рабочие процессы читают двоичный кэш, а не 6 млн строк CSV."""
    m1, val = ref.load_m1(data_path, ref.Params(), lambda *_: None)
    np.savez(cache_path, t=(m1.index.as_unit("ns") if hasattr(m1.index, "as_unit") else m1.index).asi8, o=m1.o.values, h=m1.h.values, l=m1.l.values,
             c=m1.c.values, validation=np.array(json.dumps(val, ensure_ascii=False, default=str)))
    return val


def load_cache(cache_path):
    z = np.load(cache_path, allow_pickle=False)
    # t — кэш оптимизатора и очистителя; t_open — сертифицированные массивы DZ_CERT_Data
    idx = pd.to_datetime(z["t"] if "t" in z.files else z["t_open"], utc=True)
    return pd.DataFrame({"o": z["o"], "h": z["h"], "l": z["l"], "c": z["c"]}, index=idx)


# ======================================================================================
# 2. ГРАФ ПАРАМЕТРОВ И ПРОСТРАНСТВО ПОИСКА
# ======================================================================================

def resolve_space(graph, task):
    """
    Возвращает словарь «параметр → список значений». Три режима различаются только
    тем, КАКИЕ параметры попадают в перебор; значения берутся из графа либо из задачи.
    """
    P = graph["params"]
    mode = task.get("mode", "dev")
    if mode == "dev":
        keys = list(task["optimize"].keys())
        space = {k: list(v) for k, v in task["optimize"].items()}
    elif mode == "param":
        depth = int(task.get("depth", 1))
        adj = {}
        for e in graph["edges"]:
            adj.setdefault(e["a"], set()).add(e["b"]); adj.setdefault(e["b"], set()).add(e["a"])
        keys, frontier = set(task["target"]), set(task["target"])
        for _ in range(depth):
            frontier = {n for f in frontier for n in adj.get(f, ())} - keys
            keys |= frontier
        space = {k: list(P[k]["range"]) for k in sorted(keys)}
    elif mode == "system":
        keys = graph["groups"][task["hypothesis"]]
        space = {k: list(P[k]["range"]) for k in keys}
    else:
        raise SystemExit(f"неизвестный режим {mode}")
    unknown = [k for k in space if k not in P]
    if unknown:
        raise SystemExit(f"параметры отсутствуют в графе: {unknown}")
    return space


def enumerate_trials(space, max_trials, seed):
    """Полная сетка, если помещается; иначе случайная выборка без повторов."""
    keys = list(space)
    total = int(np.prod([len(space[k]) for k in keys])) if keys else 1
    if total <= max_trials:
        return [dict(zip(keys, v)) for v in itertools.product(*[space[k] for k in keys])], total
    rng, seen, out = random.Random(seed), set(), []
    while len(out) < max_trials:
        combo = tuple(rng.choice(space[k]) for k in keys)
        if combo not in seen:
            seen.add(combo); out.append(dict(zip(keys, combo)))
    return out, total


# ======================================================================================
# 3. ПАРАЛЛЕЛЬНЫЕ ИСПЫТАНИЯ
# ======================================================================================

_W = {}


def _period(m1, start=None, end=None):
    """Период задачи: начало включается, конец НЕТ — смежные окна проверки вперёд не делят баров."""
    if start: m1 = m1[m1.index >= pd.Timestamp(start, tz="UTC")]
    if end: m1 = m1[m1.index < pd.Timestamp(end, tz="UTC")]
    if len(m1) == 0: raise ValueError(f"в периоде {start}…{end} нет баров")
    return m1


def _feasible(t, constraints):
    """Ограничение «a < b», операнды — имена параметров или числа. Неизвестное имя — ошибка задачи."""
    for c in constraints:
        m = re.fullmatch(r"\s*([\w\.]+)\s*(<=|>=|<|>)\s*([\w\.]+)\s*", c)
        if not m: raise ValueError(f"ограничение не разобрано: {c}")
        def val(x):
            if re.fullmatch(r"-?\d+(\.\d+)?", x): return float(x)
            if x not in t: raise ValueError(f"в ограничении «{c}» неизвестный параметр {x}")
            return float(t[x])
        a, op, b = val(m.group(1)), m.group(2), val(m.group(3))
        if not {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]: return False
    return True


def _init_worker(ref_path, cache_path, start=None, end=None):
    _W["ref"] = load_reference(ref_path)
    _W["m1"] = _period(load_cache(cache_path), start, end)


def _run_trial(args):
    """Испытание изолировано: новый объект параметров, общего изменяемого состояния нет."""
    tid, params = args
    ref = _W["ref"]
    p = ref.Params(**params)
    p.control_runs = 0
    _, tr = ref.simulate(_W["m1"], p, lambda *_: None, "OPT")
    if len(tr) == 0:
        return tid, {"NetUSD": [], "ExitTimeUTC": [], "MAE_Ticks": [], "MFE_Ticks": []}
    return tid, {k: tr[k].tolist() for k in ("NetUSD", "ExitTimeUTC", "MAE_Ticks", "MFE_Ticks")}


# ======================================================================================
# 4. ПОКАЗАТЕЛИ В СТРУКТУРЕ ОТЧЁТА STRATEGY ANALYZER
# ======================================================================================

def daily_pnl(tr, index):
    """Дневной результат по дате выхода, дни без сделок — нули. Иначе Шарп завышается."""
    if not tr["NetUSD"]:
        return pd.Series(0.0, index=index)
    s = pd.Series(tr["NetUSD"], index=pd.to_datetime(tr["ExitTimeUTC"], utc=True).normalize())
    return s.groupby(level=0).sum().reindex(index, fill_value=0.0)


SUMMARY_KEYS = ["Trades", "NetProfit", "GrossProfit", "GrossLoss", "ProfitFactor", "MaxDrawdown",
                "SharpeDaily", "SharpeAnnual", "SortinoAnnual", "UlcerIndex", "WinRatePct", "AvgWin",
                "AvgLoss", "WinLossRatio", "MaxConsecWins", "MaxConsecLosses", "AvgMAE_Ticks", "AvgMFE_Ticks"]


def summary(tr, days, capital):
    net = np.array(tr["NetUSD"], dtype=float)
    if len(net) == 0:
        # Полный набор полей и для пустого испытания: иначе столбец целевой функции
        # пропадёт из таблицы, и отбор лучшего упадёт.
        return {k: (0 if k in ("Trades", "MaxConsecWins", "MaxConsecLosses") else None) for k in SUMMARY_KEYS}
    wins, losses = net[net > 0], net[net < 0]
    eq = np.cumsum(net)
    dd = float((np.maximum.accumulate(np.r_[0.0, eq]) - np.r_[0.0, eq]).max())
    cw = cl = mw = ml = 0
    for v in net:
        if v > 0: cw, cl = cw + 1, 0
        elif v < 0: cl, cw = cl + 1, 0
        mw, ml = max(mw, cw), max(ml, cl)
    d = days.values
    sd = d.std(ddof=1) if len(d) > 1 else 0.0
    dn = d[d < 0]
    ddn = math.sqrt((dn ** 2).sum() / len(d)) if len(d) else 0.0
    curve = capital + np.cumsum(d)
    pct = (np.maximum.accumulate(curve) - curve) / np.maximum.accumulate(curve)
    gp, gl = float(wins.sum()), float(-losses.sum())
    return {
        "Trades": int(len(net)), "NetProfit": round(float(net.sum()), 2),
        "GrossProfit": round(gp, 2), "GrossLoss": round(-gl, 2),
        "ProfitFactor": round(gp / gl, 3) if gl > 0 else None,
        "MaxDrawdown": round(-dd, 2),
        "SharpeDaily": round(float(d.mean() / sd), 5) if sd > 0 else None,
        "SharpeAnnual": round(float(d.mean() / sd * math.sqrt(252)), 3) if sd > 0 else None,
        "SortinoAnnual": round(float(d.mean() / ddn * math.sqrt(252)), 3) if ddn > 0 else None,
        "UlcerIndex": round(float(math.sqrt((pct ** 2).mean()) * 100), 4),
        "WinRatePct": round(100 * len(wins) / len(net), 2),
        "AvgWin": round(float(wins.mean()), 2) if len(wins) else None,
        "AvgLoss": round(float(losses.mean()), 2) if len(losses) else None,
        "WinLossRatio": round(float(wins.mean() / -losses.mean()), 3) if len(wins) and len(losses) else None,
        "MaxConsecWins": mw, "MaxConsecLosses": ml,
        "AvgMAE_Ticks": round(float(np.mean(tr["MAE_Ticks"])), 2),
        "AvgMFE_Ticks": round(float(np.mean(tr["MFE_Ticks"])), 2),
    }


# ======================================================================================
# 5. ЗАЩИТА ОТ ПЕРЕПОДГОНКИ
# ======================================================================================

def deflated_sharpe(sr, sr_var, n_trials, T, skew, kurt):
    """
    Дефлированный Шарп: Φ((SR − SR₀)·√(T−1) / √(1 − γ₃·SR + (γ₄−1)/4·SR²)),
    SR₀ = √Var[SR]·((1−γ)·Φ⁻¹(1−1/N) + γ·Φ⁻¹(1−1/(N·e))) — ожидаемый максимум Шарпа
    среди N испытаний без преимущества. Шарп дневной, неаннуализированный.
    """
    if n_trials < 2 or T < 3:
        return None, None
    sr0 = math.sqrt(max(sr_var, 0.0)) * ((1 - EULER) * ND.inv_cdf(1 - 1 / n_trials)
                                         + EULER * ND.inv_cdf(1 - 1 / (n_trials * math.e)))
    den = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr * sr))
    return round(ND.cdf((sr - sr0) * math.sqrt(T - 1) / den), 4), round(sr0, 5)


def pbo_cscv(M, S=10):
    """
    Вероятность переподгонки (CSCV). M — дни × испытания. Для каждого разбиения блоков
    пополам: лучший на одной половине, его относительный ранг на другой; PBO — доля
    случаев, когда лучший в выборке оказывается ниже медианы вне выборки.
    """
    T, N = M.shape
    if N < 2 or T < S * 2:
        return None
    blocks = np.array_split(np.arange(T), S)
    below = total = 0
    for comb in itertools.combinations(range(S), S // 2):
        a = np.concatenate([blocks[i] for i in comb])
        b = np.concatenate([blocks[i] for i in range(S) if i not in comb])
        sa = M[a].mean(0) / (M[a].std(0) + 1e-12)
        sb = M[b].mean(0) / (M[b].std(0) + 1e-12)
        best = int(np.argmax(sa))
        w = (np.sum(sb <= sb[best])) / (N + 1)
        below += int(math.log(w / (1 - w)) <= 0)
        total += 1
    return round(below / total, 4)


def plateau_best(trials, keys, obj):
    """Лучшая точка по среднему целевой функции в окрестности ±1 шаг сетки по каждой оси."""
    if not keys:
        return int(np.nanargmax(obj)), list(obj)
    grids = {k: sorted({t[k] for t in trials}) for k in keys}
    P = np.array([[grids[k].index(t[k]) for k in keys] for t in trials])
    o = np.array(obj, dtype=float)
    sm = [float(np.nanmean(o[np.all(np.abs(P - P[i]) <= 1, axis=1)])) for i in range(len(trials))]
    return int(np.nanargmax(sm)), sm


def registry_add(path, task_id, strategy, n):
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write("TaskId,Strategy,Trials,UTC\n")
        f.write(f"{task_id},{strategy},{n},{pd.Timestamp.utcnow().isoformat()}\n")
    return int(pd.read_csv(path).query("Strategy == @strategy").Trials.sum())


# ======================================================================================
# 6. ВЫГРУЗКА В ШАБЛОН NINJATRADER
# ======================================================================================

def nt_values(graph, params):
    """Значения свойств NinjaTrader: прямые соответствия и производные выражения."""
    out = {}
    for k, v in params.items():
        spec = graph["params"][k]
        if spec.get("nt"):
            out[spec["nt"]] = v
        for prop, expr in spec.get("nt_expr", {}).items():
            out[prop] = round(eval(expr, {"__builtins__": {}}, dict(params)), 6)
    return out


def patch_template(src, dst, values):
    """
    Правит СУЩЕСТВУЮЩИЙ шаблон, сохранённый самим NinjaTrader: меняет значения элементов,
    чьё имя совпадает с именем свойства. Структуру не выдумывает; ненайденные свойства
    сообщаются. Пишет в новый файл, исходный не трогает.
    """
    import xml.etree.ElementTree as ET
    tree = ET.parse(src)
    found = {}
    for el in tree.iter():
        tag = el.tag.split("}")[-1]
        if tag in values and (el.text is not None) and len(el) == 0:
            el.text = str(values[tag]).lower() if isinstance(values[tag], bool) else str(values[tag])
            found[tag] = el.text
    tree.write(dst, encoding="utf-8", xml_declaration=True)
    return found, sorted(set(values) - set(found))


# ======================================================================================
# 7. ЗАДАЧА
# ======================================================================================

def data_sha256(npz_path):
    """Отпечаток массивов — по той же формуле, что очиститель и эмулятор: связь с сертификатом данных."""
    z = np.load(npz_path, allow_pickle=False)
    t = z["t"] if "t" in z.files else z["t_open"]
    v = z["v"] if "v" in z.files else np.zeros(len(t))
    arr = np.stack([t.astype(np.float64), z["o"], z["h"], z["l"], z["c"], v], 1)
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def resolve_certified(task):
    """
    "data": "MGC" — символ инструмента: данные из data_certified/MGC/MGC_M1.npz, и перед
    расчётом проверяется сертификат (постулат П11). Путь к CSV работает как прежде.
    """
    d = str(task["data"])
    if not re.fullmatch(r"[A-Za-z0-9_]{1,16}", d):
        return None, None
    root = task.get("data_root", "data_certified")
    npz = os.path.join(root, d, f"{d}_M1.npz"); cert = os.path.join(root, d, f"{d}_DATA_CERTIFICATE.json")
    if not os.path.exists(npz):
        raise FileNotFoundError(f"нет сертифицированных данных {npz}: сначала DZ_CERT_Data.py certify --symbol {d}")
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location("dz_cert_data", os.path.join(here, "DZ_CERT_Data.py"))
    cd = importlib.util.module_from_spec(spec); spec.loader.exec_module(cd)
    ok, errs, _ = cd.verify(cert, quiet=True)
    if not ok:
        raise ValueError(f"сертификат данных {d} не прошёл проверку: {'; '.join(errs)}")
    return npz, cert


def run_task(task, ref_path, graph, out_root, registry, workers):
    tid = task.get("task_id") or time.strftime("T%Y%m%d_%H%M%S")
    out = os.path.join(out_root, tid)
    os.makedirs(out, exist_ok=True)
    ref = load_reference(ref_path)

    cert_npz, cert_file = resolve_certified(task)
    cache = task.get("cache") or cert_npz or os.path.splitext(task["data"])[0] + ".npz"
    if not os.path.exists(cache):
        log(f"[{tid}] кэш данных: {cache}")
        build_cache(ref, task["data"], cache)
    m1 = _period(load_cache(cache), task.get("start"), task.get("end"))

    base = {k: v["default"] for k, v in graph["params"].items()}
    prof = (graph.get("instrument_profiles") or {}).get(task.get("instrument", ""), {})
    base.update(prof.get("reference", {}))          # tick, usd_per_tick, комиссия — из профиля инструмента
    base.update(task.get("base", {}))
    base["profile"] = task.get("profile", "chicago")
    space = resolve_space(graph, task)
    combos, total = enumerate_trials(space, int(task.get("max_trials", 200)), int(task.get("seed", 1)))
    trials = [dict(base, **c) for c in combos]
    cons = task.get("constraints") or []
    if cons:
        feas = [t for t in trials if _feasible(t, cons)]
        log(f"[{tid}] ограничения {cons}: отброшено невозможных комбинаций {len(trials) - len(feas)}")
        if not feas: raise ValueError("после ограничений не осталось ни одной комбинации")
        trials = feas
    log(f"[{tid}] режим {task.get('mode')}, параметры {list(space)}, испытаний {len(trials)} из {total}")

    nw = workers or max(1, (os.cpu_count() or 2) - 1)
    results = {}
    with ProcessPoolExecutor(max_workers=nw, initializer=_init_worker, initargs=(ref_path, cache, task.get("start"), task.get("end"))) as ex:
        for tid_i, tr in ex.map(_run_trial, list(enumerate(trials)), chunksize=1):
            results[tid_i] = tr

    days = pd.date_range(m1.index[0].normalize(), m1.index[-1].normalize(), freq="B", tz="UTC")
    capital = float(task.get("capital", 20000))
    rows, M = [], np.zeros((len(days), len(trials)))
    for i, t in enumerate(trials):
        dp = daily_pnl(results[i], days)
        M[:, i] = dp.values
        rows.append({**{k: t[k] for k in space}, **summary(results[i], dp, capital)})
    df = pd.DataFrame(rows)

    objective = task.get("objective", "SharpeDaily")
    obj = df[objective].astype(float).fillna(-1e18).values
    raw_best = int(np.argmax(obj))
    plat_best, smooth = plateau_best(trials, list(space), obj)
    df["Plateau_" + objective] = smooth

    n_cum = registry_add(registry, tid, graph["strategy"], len(trials))
    srs = df["SharpeDaily"].astype(float).dropna()
    best_days = M[:, raw_best]
    s = pd.Series(best_days)
    dsr, sr0 = deflated_sharpe(float(df.loc[raw_best, "SharpeDaily"] or 0), float(srs.var(ddof=1)) if len(srs) > 1 else 0.0,
                               n_cum, len(days), float(s.skew() or 0), float(s.kurt() or 0) + 3)
    pbo = pbo_cscv(M, int(task.get("cscv_blocks", 10)))

    best = trials[plat_best if task.get("select", "plateau") == "plateau" else raw_best]
    res = {
        "engine": VERSION, "task_id": tid, "mode": task.get("mode"), "space": space,
        "trials_this_task": len(trials), "trials_cumulative": n_cum, "grid_total": total,
        "objective": objective, "best_raw": trials[raw_best], "best_plateau": trials[plat_best],
        "best_selected": best, "metrics_best_raw": rows[raw_best], "metrics_best_plateau": rows[plat_best],
        "deflated_sharpe": dsr, "expected_max_sharpe_null": sr0, "pbo": pbo,
        "verdict": verdict(dsr, pbo), "nt_values": nt_values(graph, {k: best[k] for k in graph["params"]}),
    }

    # Сделки выбранного набора — для сверки со Strategy Analyzer.
    p = ref.Params(**best); p.control_runs = 0
    _, tr_best = ref.simulate(m1, p, lambda *_: None, "BEST")
    tr_best.to_csv(os.path.join(out, "best_trades.csv"), index=False)
    df.to_csv(os.path.join(out, "trials.csv"), index=False)
    # Связь итога с данными — для DZ_AUDIT_Gatekeeper: отпечаток тех же массивов, что в сертификате
    _dsha = data_sha256(cache)
    res.update({"data_sha256": _dsha, "data_file": cache, "data_certificate": cert_file, "period": [task.get("start"), task.get("end")]})
    with open(os.path.join(out, "run_manifest.json"), "w", encoding="utf-8") as _mf:
        json.dump({"engine": VERSION, "task_id": tid, "data_sha256": _dsha, "data_file": cache, "data_certificate": cert_file,
                   "period": [task.get("start"), task.get("end")], "instrument": task.get("instrument")}, _mf, ensure_ascii=False, indent=2)
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2, default=str)
    write_excel(os.path.join(out, "report.xlsx"), res, df)

    if task.get("nt_template"):
        found, missing = patch_template(task["nt_template"], os.path.join(out, "template_patched.xml"), res["nt_values"])
        res["template"] = {"patched": found, "not_found": missing}
        log(f"[{tid}] шаблон: изменено {len(found)}, не найдено {missing}")

    log(f"[{tid}] лучший {objective}: {rows[raw_best].get(objective)}, на плато: {rows[plat_best].get(objective)}; "
        f"DSR {dsr}, PBO {pbo} — {res['verdict']}")
    return res


def verdict(dsr, pbo):
    if dsr is None or pbo is None:
        return "недостаточно данных для оценки переподгонки"
    if pbo > 0.5:
        return "ПЕРЕПОДГОНКА ВЕРОЯТНА: лучший в выборке чаще хуже медианы вне выборки"
    if dsr < 0.95:
        return "преимущество не доказано с учётом числа испытаний"
    return "результат выдерживает поправку на число испытаний"


def write_excel(path, res, df):
    try:
        with pd.ExcelWriter(path) as xw:
            flat = {k: json.dumps(v, ensure_ascii=False, default=str) if isinstance(v, (dict, list)) else v
                    for k, v in res.items()}
            pd.DataFrame(list(flat.items()), columns=["Показатель", "Значение"]).to_excel(xw, sheet_name="Итог", index=False)
            df.to_excel(xw, sheet_name="Испытания", index=False)
    except Exception as e:
        log(f"Excel не записан ({e}); данные — в trials.csv и summary.json")


# ======================================================================================
# 8. СВЕРКА СО STRATEGY ANALYZER
# ======================================================================================

NT_COLS = {
    "entry_time": ["entry time", "время входа", "einstiegszeit"],
    "direction": ["market pos.", "market pos", "позиция", "marktposition"],
    "entry_price": ["entry price", "цена входа", "einstiegspreis"],
    "exit_price": ["exit price", "цена выхода", "ausstiegspreis"],
    "profit": ["profit", "прибыль", "gewinn"],
}


def _find(cols, names):
    low = {c.strip().lower(): c for c in cols}
    for n in names:
        if n in low:
            return low[n]
    return None


def parity(nt_path, eng_path, nt_tz, tol_min, tol_usd, out_path):
    """
    Сделка к сделке: сопоставление по времени входа (в пределах tol_min минут) и
    направлению; расхождения цен и результата. Критерий паритета: все сделки
    сопоставлены и |ΔProfit| ≤ tol_usd.
    """
    nt = pd.read_csv(nt_path, sep=None, engine="python")
    col = {k: _find(nt.columns, v) for k, v in NT_COLS.items()}
    miss = [k for k, v in col.items() if v is None]
    if miss:
        raise SystemExit(f"в выгрузке NinjaTrader не найдены столбцы {miss}; столбцы: {list(nt.columns)}")
    num = lambda s: pd.to_numeric(s.astype(str).str.replace(r"[^\d,.\-]", "", regex=True).str.replace(",", "."), errors="coerce")
    a = pd.DataFrame({
        "t": pd.to_datetime(nt[col["entry_time"]], dayfirst=True, errors="coerce").dt.tz_localize(nt_tz).dt.tz_convert("UTC"),
        "dir": nt[col["direction"]].astype(str).str.lower().map(lambda s: 1 if s.startswith(("long", "лон", "buy")) else -1),
        "ep": num(nt[col["entry_price"]]), "xp": num(nt[col["exit_price"]]), "pnl": num(nt[col["profit"]]),
    }).dropna(subset=["t"]).sort_values("t").reset_index(drop=True)
    e = pd.read_csv(eng_path)
    b = pd.DataFrame({"t": pd.to_datetime(e.EntryTimeUTC, utc=True), "dir": e.Direction,
                      "ep": e.EntryPriceWithSlip, "xp": e.ExitPriceWithSlip, "pnl": e.NetUSD}).sort_values("t").reset_index(drop=True)
    used, rows = set(), []
    for i, r in a.iterrows():
        cand = b[(~b.index.isin(used)) & (b.dir == r.dir) & ((b.t - r.t).abs() <= pd.Timedelta(minutes=tol_min))]
        if len(cand) == 0:
            rows.append({"nt_time": r.t, "status": "ТОЛЬКО_NT", "d_pnl": None}); continue
        j = (cand.t - r.t).abs().idxmin(); used.add(j); m = b.loc[j]
        rows.append({"nt_time": r.t, "eng_time": m.t, "dir": r.dir, "d_entry": round(m.ep - r.ep, 6),
                     "d_exit": round(m.xp - r.xp, 6), "d_pnl": round(m.pnl - r.pnl, 2),
                     "status": "СОВПАДАЕТ" if abs(m.pnl - r.pnl) <= tol_usd else "РАСХОЖДЕНИЕ"})
    for j in b.index.difference(list(used)):
        rows.append({"eng_time": b.loc[j].t, "status": "ТОЛЬКО_ДВИЖОК", "d_pnl": None})
    rep = pd.DataFrame(rows)
    rep.to_csv(out_path, index=False)
    cnt = rep.status.value_counts().to_dict()
    ok = cnt.get("СОВПАДАЕТ", 0) == len(a) == len(b)
    log(f"[паритет] NT {len(a)}, движок {len(b)}: {cnt}; "
        f"{'ПАРИТЕТ ДОСТИГНУТ' if ok else 'паритета нет — см. ' + out_path}")
    return ok, cnt


# ======================================================================================
# 9. ЗАПУСК
# ======================================================================================

def main():
    ap = argparse.ArgumentParser(description=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "watch"):
        s = sub.add_parser(name)
        s.add_argument("--ref", default="DZ_BT_DualBreakout_S021.py")
        s.add_argument("--graph", default="DZ_OPT_Graph_DualBreakout.json")
        s.add_argument("--results", default="results")
        s.add_argument("--registry", default="trials_registry.csv")
        s.add_argument("--workers", type=int, default=0)
        if name == "run":
            s.add_argument("--task", required=True)
        else:
            s.add_argument("--queue", default="task_queue")
            s.add_argument("--done", default="task_done")
            s.add_argument("--poll", type=float, default=2.0)
    s = sub.add_parser("parity")
    s.add_argument("--nt", required=True); s.add_argument("--engine", required=True)
    s.add_argument("--nt-tz", default="Europe/Berlin"); s.add_argument("--tol-min", type=float, default=1.0)
    s.add_argument("--tol-usd", type=float, default=0.005); s.add_argument("--out", default="parity_report.csv")
    s = sub.add_parser("cache")
    s.add_argument("--data", required=True); s.add_argument("--ref", default="DZ_BT_DualBreakout_S021.py")
    a = ap.parse_args()

    if a.cmd == "parity":
        ok, _ = parity(a.nt, a.engine, a.nt_tz, a.tol_min, a.tol_usd, a.out)
        sys.exit(0 if ok else 1)
    if a.cmd == "cache":
        val = build_cache(load_reference(a.ref), a.data, os.path.splitext(a.data)[0] + ".npz")
        log(f"кэш готов; формат {val['date_format']}, разметка {val['bar_label']}")
        return

    graph = json.load(open(a.graph, encoding="utf-8"))
    if a.cmd == "run":
        run_task(json.load(open(a.task, encoding="utf-8")), a.ref, graph, a.results, a.registry, a.workers)
        return

    os.makedirs(a.queue, exist_ok=True); os.makedirs(a.done, exist_ok=True)
    log(f"наблюдение за {a.queue}")
    while True:
        for path in sorted(glob.glob(os.path.join(a.queue, "*.json"))):
            # Файл берётся в работу, только когда его размер перестал меняться:
            # защита от чтения недописанной задачи.
            size = os.path.getsize(path); time.sleep(0.5)
            if os.path.getsize(path) != size:
                continue
            try:
                task = json.load(open(path, encoding="utf-8"))
                run_task(task, a.ref, graph, a.results, a.registry, a.workers)
            except Exception as ex:
                log(f"ОШИБКА задачи {path}: {ex}")
            shutil.move(path, os.path.join(a.done, os.path.basename(path)))
        time.sleep(a.poll)


if __name__ == "__main__":
    main()
