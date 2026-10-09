#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_LAB_Automated_Orchestrator.py — исследовательская оболочка S021, v1.0 (2026-10-01)

  build-matrix        матрица DZ_LAB_Matrix_S021.json на ВСЕ настройки hub_menu_schema.json:
                      класс (защитный, структурный, числовой), исполнитель, связи, три прохода
  status              карта прогресса: состояния, классы, отклонённые с причиной
  run-next            следующий шаг первого готового параметра (родители — VALIDATED)
  run-cluster <id>    следующий шаг каждого параметра группы графа
  export-best-preset  VALIDATED-параметры → пресет DZ-PRESET-v1 для [U05] коммутатора

АВТОМАТ: UNTOUCHED → ISOLATED_DONE → COUPLED_DONE → VALIDATED | REJECTED. Шаг выполняется
  целиком в одном вызове, поэтому промежуточные «_IN_PROGRESS» видны только во время расчёта.
  Ребёнок по рёбрам графа не исследуется, пока родитель не VALIDATED.
ИСПОЛНИТЕЛЬ — DZ_OPT_Engine_S021.py на сертифицированных данных ("data": символ) и
  DZ_OPT_WFA.py. Своего расчёта у оболочки нет. Параметр без исполнителя — NO_EXECUTOR.
АУДИТ — SQLite DZ_LAB_Master_Audit.db: каждый прогон с вектором параметров, метриками и
  отпечатком (вектор + отпечаток данных + версия движка).
ЭКСПЕРИМЕНТЫ:
  • одиночный пик — сырой лучший дальше шага сетки от плато → REJECTED на изолированном проходе;
  • устойчивость — лучшее в связке ушло от изолированного больше допуска → REJECTED;
  • бюджет испытаний — запуск, поднимающий порог «случайного лучшего» выше бюджета, без --force не идёт.
==========================================================================================
"""
import argparse, datetime as dt, hashlib, json, math, os, sqlite3, subprocess, sys
from statistics import NormalDist

VERSION = "DZ_LAB_Automated_Orchestrator-v2.0 (2026-10-01)"
HERE = os.path.dirname(os.path.abspath(__file__))
SAFETY = {"DryRunMode", "WsEnabled", "WsAllowCommands", "WsPort", "ExportSchema", "PresetFile", "VisualsEnabled", "VisualDebugEnabled"}
SAFETY_PREFIX = ("[S", "[U", "[V", "[Q")   # режим без ордеров [E01] защищён по имени; [E03] стоп — исследовательский
ACCEPT = {"min_trades": 150, "min_profit_factor": 1.35, "max_drawdown_limit_currency": 3500, "stability_tolerance_pct": 25.0}
WFA = {"in_sample_days": 180, "out_of_sample_days": 45, "step_days": 30, "min_wfe": 0.60, "max_pbo": 0.25}


def emax(n):
    if n < 2: return 0.0
    g, N = 0.5772156649, NormalDist()
    return (1 - g) * N.inv_cdf(1 - 1 / n) + g * N.inv_cdf(1 - 1 / (n * math.e))


# ---------------------------------------------------------------------------- матрица
def build_matrix(schema_path, graph_path, out):
    S = json.load(open(schema_path, encoding="utf-8-sig")); G = json.load(open(graph_path, encoding="utf-8"))
    nt2ref = {v["nt"]: k for k, v in G["params"].items() if v.get("nt")}
    edges = G.get("edges", []); slot_of_group = {}
    for p in S["properties"]:
        if p["index"].startswith("MOD"): slot_of_group[p["description"][:0] + p["label"]] = p["name"]
    rows = []
    for p in S["properties"]:
        ref = nt2ref.get(p["name"]); label = p["label"]
        cls = ("SAFETY" if p["name"] in SAFETY or label.startswith(SAFETY_PREFIX) or p["type"] == "string" or p["index"].startswith("MOD")
               else "STRUCTURAL" if p["type"] in ("bool", "enum") else "NUMERIC")
        links = [{"param": (e["b"] if e["a"] == ref else e["a"]), "why": e["why"]} for e in edges if ref and ref in (e["a"], e["b"])]
        parents = [e["a"] for e in edges if ref and e["b"] == ref]
        g = G["params"].get(ref, {}) if ref else {}
        rng = g.get("range") or []
        rows.append({
            "property_id": f"{p['index']}_{p['name']}", "name": p["name"], "menu_group": p["group"], "data_type": p["type"],
            "default_value": p.get("default"), "current_value": p.get("value"), "min": p.get("min"), "max": p.get("max"),
            "market_physics": p.get("description") or "—", "physics_source": "описание [Display] в коде коммутатора",
            "class": cls, "executor": ("DZ_OPT_Engine_S021 + DZ_BT_DualBreakout_S021" if ref and cls == "NUMERIC" else None), "reference_name": ref,
            "coupling_graph": {"hard_dependencies": parents, "functional_links": links},
            "three_pass_optimization": {
                "method_1_isolated": {"enabled": bool(ref and cls == "NUMERIC"), "grid": rng},
                "method_2_coupled": {"enabled": bool(ref and links), "coupled_cluster": [l["param"] for l in links]},
                "method_3_ensemble_wfa": {"enabled": bool(ref and cls == "NUMERIC"), "wfa_windows": WFA}},
            "acceptance_criteria": ACCEPT})
    m = {"matrix": "DZ-LAB-MATRIX-v1", "built": dt.datetime.now().isoformat(timespec="seconds"), "schema_exported": S.get("exported_local"),
         "count": len(rows), "classes": {c: sum(1 for r in rows if r["class"] == c) for c in ("SAFETY", "STRUCTURAL", "NUMERIC")},
         "executable": sum(1 for r in rows if r["executor"]), "groups": G.get("groups", {}), "properties": rows}
    json.dump(m, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return m


# ---------------------------------------------------------------------------- v2: полная матрица по этапам
STAGES = {1: "Структура рынка и волатильность", 2: "Ядра сигналов входа", 3: "Статистические фильтры",
          4: "Риск и объём", 5: "Сопровождение и выходы"}
EXCLUDED_GROUPS = ("0 ·", "1 ·", "3 ·", "6 ·", "7 ·", "12 ·", "13 ·", "14 ·")   # серии, слоты, исполнение, устаревшее, диагностика, ПК, визуализация, пульт
PAIRS = (("Min", "Max"), ("Low", "High"), ("Fast", "Slow"), ("Lower", "Higher"), ("Short", "Long"))


def stage_of(p):
    g, n = p["group"], p["name"]
    if p["index"] == "E03": return 4
    if g.startswith(EXCLUDED_GROUPS): return None
    if g.startswith("8 ·"):
        if n.endswith(("TrailTicks",)): return 5
        if any(k in n for k in ("Range", "BaseBars", "Flat", "Atr", "Trend")): return 1
        return 2
    if g.startswith(("15 ·", "16 ·", "17 ·")): return 2
    if g.startswith(("9 ·", "10 ·", "11 ·", "2 ·")): return 3
    if g.startswith("5 ·"): return 5 if any(k in n for k in ("Breakeven", "Trail", "Step", "Escort", "Exit")) else 4
    if g.startswith("4 ·"):
        if n.startswith(("Guard", "Risk", "Daily")): return 4
        if n.startswith(("AStop", "Escort", "Adaptive")): return 5
        if n.startswith(("Trfp", "Line")): return 2
        return 1
    return None


def grid_rule(p):
    """Сетка из единиц параметра. Пределы схемы — жёсткие; сетка — вокруг текущего значения."""
    t, n, v, lo, hi = p["type"], p["name"], p.get("value"), p.get("min"), p.get("max")
    if t in ("bool", "enum"): return (p.get("enum") or [False, True]), "гипотеза: перебор значений, не сетка"
    if "Slot" in n: return [], "выбор серии — структурное решение, вне перебора"
    if not isinstance(v, (int, float)): return [], "нет числового значения"
    clip = lambda x: min(hi if hi is not None else x, max(lo if lo is not None else x, x))
    if "Ticks" in n:
        g = sorted({int(round(clip(v * k))) for k in (0.5, 0.75, 1, 1.25, 1.5, 2)} - {0} or {int(v)}); return g, "тики: целые кратные шагу цены, ×0,5…×2"
    if t == "int" or any(k in n for k in ("Period", "Bars", "Window", "Lookback", "Length", "Minutes", "Bandwidth", "Neighbors", "Horizon")):
        g = sorted({max(1, int(round(clip(v * k)))) for k in (0.5, 0.75, 1, 1.5, 2)}); return g, "окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность"
    if lo is not None and hi is not None and lo >= 0 and hi <= 1:
        g = sorted({round(clip(v + d), 2) for d in (-0.15, -0.1, -0.05, 0, 0.05, 0.1, 0.15)}); return g, "доля 0–1: шаг 0,05 вокруг текущего"
    g = sorted({round(clip(v * k), 4) for k in (0.5, 0.75, 1, 1.25, 1.5)}); return g, "множитель: ±50% вокруг текущего"


def build_full(schema_path, graph_path, out_matrix, out_graph):
    S = json.load(open(schema_path, encoding="utf-8-sig")); G = json.load(open(graph_path, encoding="utf-8"))
    nt2ref = {v["nt"]: k for k, v in G["params"].items() if v.get("nt")}; ref2nt = {v: k for k, v in nt2ref.items()}
    P = S["properties"]; by = {p["name"]: p for p in P}; rows = []; edges = []
    for e in G.get("edges", []):
        if e["a"] in ref2nt and e["b"] in ref2nt: edges.append({"a": ref2nt[e["a"]], "b": ref2nt[e["b"]], "rule": "связь графа", "why": e["why"], "hard": True})
    for p in P:                                                       # пары имён внутри группы → жёсткие ограничения
        for a_, b_ in PAIRS:
            if a_ in p["name"]:
                q = p["name"].replace(a_, b_)
                if q in by and by[q]["group"] == p["group"]:
                    edges.append({"a": p["name"], "b": q, "rule": f"{p['name']} < {q}", "why": f"пара {a_}/{b_}: нижняя граница меньше верхней", "hard": True})
        if p["type"] == "bool" and "Exp" in p["name"]:                # флаг эксперимента → его числовые параметры
            stem = p["name"].split("Exp")[0]
            for q in P:
                if q["name"] != p["name"] and q["name"].startswith(stem + "Exp") and q["type"] in ("int", "double"):
                    edges.append({"a": p["name"], "b": q["name"], "rule": f"{q['name']} действует только при {p['name']} = true", "why": "числовой параметр эксперимента без флага не влияет на результат", "hard": True})
    seen = set(); edges = [e for e in edges if not ((e["a"], e["b"]) in seen or seen.add((e["a"], e["b"])))]   # «Lower» начинается с «Low»: без этого пары дублируются
    for p in P:
        st = stage_of(p); ref = nt2ref.get(p["name"]); grid, rule = grid_rule(p)
        if ref: grid, rule = G["params"][ref]["range"], "сетка графа эталона, обоснованная исследованием"
        cls = "SAFETY" if st is None else ("STRUCTURAL" if p["type"] in ("bool", "enum") or "Slot" in p["name"] else "NUMERIC")
        ex = "OPT_ENGINE" if ref and cls == "NUMERIC" else ("HOST_RUNNER" if st in (1, 2, 3) and cls == "NUMERIC" else ("NT_ANALYZER" if cls == "NUMERIC" else None))
        parents = [e["a"] for e in edges if e["b"] == p["name"]]; links = [e for e in edges if p["name"] in (e["a"], e["b"])]
        rows.append({"property_id": f"{p['index']}_{p['name']}", "name": p["name"], "menu_group": p["group"], "stage": st, "stage_name": STAGES.get(st),
                     "data_type": p["type"], "default_value": p.get("default"), "current_value": p.get("value"), "min": p.get("min"), "max": p.get("max"),
                     "market_physics": p.get("description") or "—", "class": cls, "executor_kind": ex, "executor": "DZ_OPT_Engine_S021 + DZ_BT" if ex == "OPT_ENGINE" else None,
                     "reference_name": ref, "grid": grid, "grid_rule": rule,
                     "coupling_graph": {"hard_dependencies": parents, "functional_links": [{"param": e["b"] if e["a"] == p["name"] else e["a"], "rule": e["rule"], "why": e["why"]} for e in links]},
                     "three_pass_optimization": {
                        "method_1_isolated": {"enabled": cls == "NUMERIC", "grid": grid, "expect": "плато отклика; одиночный пик дальше шага сетки — отказ"},
                        "method_2_coupled": {"enabled": cls == "NUMERIC" and bool(links), "coupled_cluster": [l["b"] if l["a"] == p["name"] else l["a"] for l in links],
                                             "max_drift_pct": ACCEPT["stability_tolerance_pct"], "expect": "оптимум в связке не дальше 25% от изолированного"},
                        "method_3_ensemble_wfa": {"enabled": cls == "NUMERIC", "wfa_windows": WFA, "expect": "эффективность ≥ 0,60 и PBO ≤ 0,25"}},
                     "acceptance_criteria": ACCEPT})
    M = {"matrix": "DZ-LAB-FULL-MATRIX-v2", "built": dt.datetime.now().isoformat(timespec="seconds"), "schema_exported": S.get("exported_local"),
         "count": len(rows), "stages": STAGES, "classes": {c: sum(1 for r in rows if r["class"] == c) for c in ("SAFETY", "STRUCTURAL", "NUMERIC")},
         "executors": {k: sum(1 for r in rows if r["executor_kind"] == k) for k in ("OPT_ENGINE", "HOST_RUNNER", "NT_ANALYZER")},
         "executable": sum(1 for r in rows if r["executor_kind"] == "OPT_ENGINE"), "groups": G.get("groups", {}), "properties": rows}
    json.dump(M, open(out_matrix, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"graph": "DZ-OPT-GRAPH-FULL-v1", "built": M["built"], "nodes": [{k: r[k] for k in ("name", "property_id", "stage", "class", "executor_kind", "grid", "grid_rule")} for r in rows],
               "edges": edges}, open(out_graph, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return M


# ---------------------------------------------------------------------------- база
def db(path):
    c = sqlite3.connect(path)
    c.executescript("""CREATE TABLE IF NOT EXISTS params(pid TEXT PRIMARY KEY, name TEXT, ref TEXT, cls TEXT, executable INT,
        state TEXT, iso_best REAL, coupled_best REAL, wfe REAL, pbo REAL, note TEXT, updated TEXT, stage INT);
      CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, ts TEXT, pid TEXT, method TEXT, task_id TEXT, param_vector TEXT,
        net REAL, sharpe REAL, sortino REAL, maxdd REAL, winrate REAL, trades INT, wfe REAL, pbo REAL, dsr REAL, hash TEXT);""")
    if "stage" not in [r[1] for r in c.execute("PRAGMA table_info(params)")]: c.execute("ALTER TABLE params ADD COLUMN stage INT")
    return c


def sync_params(c, M):
    for r in M["properties"]:
        kind = r.get("executor_kind", "OPT_ENGINE" if r["executor"] else None)
        st = ("UNTOUCHED" if kind == "OPT_ENGINE" else "FIXED" if r["class"] == "SAFETY" else
              "AWAITING_RUNNER" if kind == "HOST_RUNNER" else "AWAITING_NT" if kind == "NT_ANALYZER" else "HYPOTHESIS")
        c.execute("INSERT OR IGNORE INTO params(pid,name,ref,cls,executable,state,updated) VALUES(?,?,?,?,?,?,?)",
                  (r["property_id"], r["name"], r["reference_name"], r["class"], int(bool(r["executor"])), st, dt.datetime.now().isoformat(timespec="seconds")))
        # Ещё не исследованные строки принимают новый класс при пересборке матрицы
        c.execute("UPDATE params SET cls=?, executable=?, ref=?, state=?, stage=? WHERE pid=? AND state IN ('FIXED','NO_EXECUTOR','UNTOUCHED','AWAITING_RUNNER','AWAITING_NT','HYPOTHESIS')",
                  (r["class"], int(bool(r["executor"])), r["reference_name"], st, r.get("stage"), r["property_id"]))
        c.execute("UPDATE params SET stage=? WHERE pid=?", (r.get("stage"), r["property_id"]))
    c.commit()


def setp(c, pid, **kw):
    kw["updated"] = dt.datetime.now().isoformat(timespec="seconds")
    c.execute("UPDATE params SET " + ",".join(f"{k}=?" for k in kw) + " WHERE pid=?", (*kw.values(), pid)); c.commit()


# ---------------------------------------------------------------------------- исполнение
def engine(task, a):
    os.makedirs(os.path.join(a.results, "_lab_tasks"), exist_ok=True)
    p = os.path.join(a.results, "_lab_tasks", task.get("task_id", task.get("plan_id")) + ".json")
    json.dump(task, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    wfa = "windows" in task
    cmd = ([sys.executable, os.path.join(HERE, "DZ_OPT_WFA.py"), "--plan", p, "--results", a.results, "--workers", str(a.workers)] if wfa else
           [sys.executable, os.path.join(HERE, "DZ_OPT_Engine_S021.py"), "run", "--task", p, "--results", a.results, "--workers", str(a.workers)])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError((r.stderr or r.stdout)[-800:])
    f = os.path.join(a.results, f"{task['plan_id']}_wfa.json") if wfa else os.path.join(a.results, task["task_id"], "summary.json")
    return json.load(open(f, encoding="utf-8"))


def log_run(c, pid, method, tid, vec, met, s):
    h = hashlib.sha256(json.dumps([vec, s.get("data_sha256"), s.get("engine")], sort_keys=True).encode()).hexdigest()
    c.execute("INSERT INTO runs(ts,pid,method,task_id,param_vector,net,sharpe,sortino,maxdd,winrate,trades,wfe,pbo,dsr,hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (dt.datetime.now().isoformat(timespec="seconds"), pid, method, tid, json.dumps(vec, ensure_ascii=False), met.get("NetProfit"), met.get("SharpeDaily"),
               met.get("SortinoAnnual"), met.get("MaxDrawdown"), met.get("WinRatePct"), met.get("Trades"), s.get("wfe"), s.get("pbo"), s.get("deflated_sharpe"), h)); c.commit()


def budget_ok(a, planned):
    reg = os.path.join(a.results, "..", "trials_registry.csv") if not os.path.exists("trials_registry.csv") else "trials_registry.csv"
    done = sum(1 for _ in open(reg, encoding="utf-8")) - 1 if os.path.exists(reg) else 0
    after = emax(max(2, done + planned))
    if after > a.budget_sigma and not a.force:
        print(f"ОТКАЗ бюджета: после {planned} испытаний (всего {done + planned}) порог «случайного лучшего» ≈ {after:.2f}σ > бюджета {a.budget_sigma}σ. "
              f"Сузьте сетку или запустите с --force осознанно.")
        return False
    return True


def base_task(a, tid):
    return {"task_id": tid, "data": a.data, "instrument": a.instrument, "profile": a.profile, "mode": "dev",
            "objective": "SharpeDaily", "select": "plateau", "max_trials": 500, "start": a.start, "end": a.end}


def step(c, M, row, a):
    r = next(x for x in M["properties"] if x["property_id"] == row["pid"]); ref = r["reference_name"]
    grid = r["three_pass_optimization"]["method_1_isolated"]["grid"]; acc = r["acceptance_criteria"]
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    if row["state"] == "UNTOUCHED":
        if not budget_ok(a, len(grid)): return
        setp(c, row["pid"], state="ISOLATED_IN_PROGRESS")
        t = base_task(a, f"lab_{ref}_iso_{stamp}"); t["optimize"] = {ref: grid}
        s = engine(t, a); raw, plat = s["best_raw"][ref], s["best_plateau"][ref]
        log_run(c, row["pid"], "isolated", t["task_id"], {ref: plat}, s["metrics_best_plateau"], s)
        stepw = min((abs(x - y) for x, y in zip(grid, grid[1:])), default=0) or 1
        if abs(raw - plat) > stepw + 1e-9:
            setp(c, row["pid"], state="REJECTED", iso_best=plat, note=f"одиночный пик: сырой {raw}, плато {plat}"); return
        setp(c, row["pid"], state="ISOLATED_DONE", iso_best=plat, note=s.get("verdict"))
    elif row["state"] == "ISOLATED_DONE":
        cl = [ref] + [x for x in r["three_pass_optimization"]["method_2_coupled"]["coupled_cluster"] if x in M["groups_all"]]
        space = {k: M["grids"][k] for k in cl if M["grids"].get(k)}
        n = math.prod(len(v) for v in space.values())
        if not budget_ok(a, min(n, 500)): return
        setp(c, row["pid"], state="COUPLED_IN_PROGRESS")
        t = base_task(a, f"lab_{ref}_cpl_{stamp}"); t["optimize"] = space
        t["constraints"] = [x for x in ("be_offset_ticks < stop_ticks", "be_trigger_ticks < stop_ticks", "min_range_ticks < max_range_ticks", "atr_fast < atr_slow")
                            if all(k in space or k in M["grids"] for k in x.split(" < "))]
        s = engine(t, a); met = s["metrics_best_plateau"]; best = s["best_plateau"][ref]
        log_run(c, row["pid"], "coupled", t["task_id"], {k: s["best_plateau"].get(k) for k in space}, met, s)
        drift = abs(best - row["iso_best"]) / max(abs(row["iso_best"]), 1e-9) * 100
        fails = [f"сделок {met.get('Trades')} < {acc['min_trades']}" for _ in [0] if (met.get("Trades") or 0) < acc["min_trades"]]
        fails += [f"PF {met.get('ProfitFactor')} < {acc['min_profit_factor']}" for _ in [0] if (met.get("ProfitFactor") or 0) < acc["min_profit_factor"]]
        fails += [f"просадка {met.get('MaxDrawdown')} хуже −{acc['max_drawdown_limit_currency']}" for _ in [0] if (met.get("MaxDrawdown") or 0) < -acc["max_drawdown_limit_currency"]]
        fails += [f"неустойчив: лучшее ушло на {drift:.0f}% от изолированного" for _ in [0] if drift > acc["stability_tolerance_pct"]]
        setp(c, row["pid"], state="REJECTED" if fails else "COUPLED_DONE", coupled_best=best, pbo=s.get("pbo"), note="; ".join(fails) or s.get("verdict"))
    elif row["state"] == "COUPLED_DONE":
        w = r["three_pass_optimization"]["method_3_ensemble_wfa"]["wfa_windows"]
        s0, e0 = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end); wins = []; d = s0
        while d + dt.timedelta(days=w["in_sample_days"] + w["out_of_sample_days"]) <= e0:
            tr1 = d + dt.timedelta(days=w["in_sample_days"]); te1 = tr1 + dt.timedelta(days=w["out_of_sample_days"])
            wins.append({"train": [str(d), str(tr1)], "test": [str(tr1), str(te1)]}); d += dt.timedelta(days=w["step_days"])
        if not wins: setp(c, row["pid"], state="REJECTED", note="период короче одного окна проверки вперёд"); return
        if not budget_ok(a, len(wins) * (len(grid) + 1)): return
        setp(c, row["pid"], state="WFA_IN_PROGRESS")
        t = base_task(a, "x"); t.pop("task_id"); t.pop("start"); t.pop("end"); t["optimize"] = {ref: grid}
        plan = {"plan": "DZ-WFA-v1", "plan_id": f"lab_{ref}_wfa_{stamp}", "task": t, "windows": wins}
        res = engine(plan, a); sm = res["summary"]; pbos = [x.get("PBO обучения") for x in res["windows"] if x.get("PBO обучения") is not None]
        pbo = sum(pbos) / len(pbos) if pbos else None; wfe = sm.get("walk_forward_efficiency")
        log_run(c, row["pid"], "wfa", plan["plan_id"], {ref: row["coupled_best"]}, {"NetProfit": sm.get("oos_net_total")}, {"wfe": wfe, "pbo": pbo})
        ok = wfe is not None and wfe >= w["min_wfe"] and pbo is not None and pbo <= w["max_pbo"]
        setp(c, row["pid"], state="VALIDATED" if ok else "REJECTED", wfe=wfe, pbo=pbo,
             note=f"проверка вперёд: эффективность {wfe}, PBO {None if pbo is None else round(pbo, 3)}, окон {len(wins)}")


def stage_open(c, n):
    """Этап открыт, когда все ИСПОЛНИМЫЕ параметры предыдущих этапов VALIDATED или REJECTED.
    Параметры без исполнителя этап не держат: до исполнителя они заморожены на текущих значениях."""
    left = c.execute("SELECT pid, state FROM params WHERE executable=1 AND stage < ? AND state NOT IN ('VALIDATED','REJECTED')", (n,)).fetchall()
    return not left, left


def ready_rows(c, M, only=None):
    st = {r["ref"]: r["state"] for r in c.execute("SELECT ref,state FROM params WHERE ref IS NOT NULL").fetchall()} if False else \
         {row[0]: row[1] for row in c.execute("SELECT ref,state FROM params WHERE ref IS NOT NULL")}
    out = []
    for row in c.execute("SELECT pid,name,ref,state,iso_best FROM params WHERE executable=1 AND state IN ('UNTOUCHED','ISOLATED_DONE','COUPLED_DONE') ORDER BY pid"):
        pid, name, ref, state, iso = row
        r = next(x for x in M["properties"] if x["property_id"] == pid)
        if only and ref not in M["groups"].get(only, []): continue
        if any(st.get(p) not in (None, "VALIDATED") for p in r["coupling_graph"]["hard_dependencies"] if p in st): continue
        out.append({"pid": pid, "ref": ref, "state": state, "iso_best": iso})
    return out


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("cmd", choices=["build-matrix", "status", "tree", "plan", "run-next", "run-stage", "run-cluster", "report", "export-best-preset"])
    ap.add_argument("cluster", nargs="?", help="группа графа для run-cluster, номер этапа для run-stage, этап или параметр для plan")
    ap.add_argument("--schema", default="hub_menu_schema.json"); ap.add_argument("--graph", default=os.path.join(HERE, "DZ_OPT_Graph_DualBreakout.json"))
    ap.add_argument("--matrix", default="DZ_LAB_Full_Matrix_S021.json"); ap.add_argument("--db", default="DZ_LAB_Master_Audit.db")
    ap.add_argument("--full-graph", default="DZ_OPT_Graph_Full_S021.json")
    ap.add_argument("--results", default="results"); ap.add_argument("--data", default="MGC"); ap.add_argument("--instrument", default="MGC")
    ap.add_argument("--profile", default="chicago"); ap.add_argument("--start", default="2015-01-01"); ap.add_argument("--end", default="2026-01-01")
    ap.add_argument("--workers", type=int, default=0); ap.add_argument("--budget-sigma", type=float, default=4.0); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.cmd == "build-matrix":
        m = build_full(a.schema, a.graph, a.matrix, a.full_graph); sync_params(db(a.db), m)
        print(f"[матрица] {a.matrix}: настроек {m['count']}, классы {m['classes']}, исполнители {m['executors']}\n[граф] {a.full_graph}"); return
    M = json.load(open(a.matrix, encoding="utf-8")); G = json.load(open(a.graph, encoding="utf-8"))
    M["grids"] = {k: v.get("range") for k, v in G["params"].items()}; M["groups_all"] = set(G["params"])
    c = db(a.db); sync_params(c, M); c.row_factory = None
    if a.cmd == "status":
        rows = c.execute("SELECT state, cls, COUNT(*) FROM params GROUP BY state, cls ORDER BY state").fetchall()
        for n_, title in STAGES.items():
            cnt = dict(c.execute("SELECT state, COUNT(*) FROM params WHERE stage=? GROUP BY state", (n_,)).fetchall())
            print(f"  этап {n_} {title:34} " + ", ".join(f"{k} {v}" for k, v in sorted(cnt.items())))
        print(f"{VERSION}\n  всего настроек {sum(r[2] for r in rows)}")
        for s, cl, n in rows: print(f"  {s:22} {cl:11} {n}")
        for pid, note in c.execute("SELECT pid, note FROM params WHERE state='REJECTED'"): print(f"  ✗ {pid}: {note}")
        print(f"  прогонов в аудите: {c.execute('SELECT COUNT(*) FROM runs').fetchone()[0]}"); return
    if a.cmd == "tree":
        R = {r["name"]: r for r in M["properties"]}; st = dict(c.execute("SELECT name, state FROM params").fetchall())
        for n_, title in STAGES.items():
            ok, left = stage_open(c, n_); print(f"\nЭТАП {n_}. {title} — {'открыт' if ok else 'закрыт: ждёт ' + str(len(left)) + ' параметров предыдущих этапов'}")
            for g in sorted({r["menu_group"] for r in M["properties"] if r["stage"] == n_}):
                print(f"  {g}")
                for r in [r for r in M["properties"] if r["stage"] == n_ and r["menu_group"] == g]:
                    deps = r["coupling_graph"]["hard_dependencies"]
                    print(f"    {st.get(r['name'], '—'):16} {r['property_id']:34} {r['class'][:4]:4} {r['executor_kind'] or '—':11}" + (f" ← {', '.join(deps)}" if deps else ""))
        return
    if a.cmd == "plan":
        sel = [r for r in M["properties"] if (a.cluster and (str(r["stage"]) == a.cluster or r["property_id"].startswith(a.cluster) or r["name"] == a.cluster))] if a.cluster else [r for r in M["properties"] if r["stage"]]
        for r in sel:
            t = r["three_pass_optimization"]
            print(f"\n{r['property_id']} · этап {r['stage']} {r['stage_name'] or ''} · {r['class']} · исполнитель {r['executor_kind'] or '—'}")
            print(f"  физика: {r['market_physics'][:160]}")
            print(f"  сетка: {r['grid']}  ({r['grid_rule']}) · пределы {r['min']}…{r['max']} · сейчас {r['current_value']}")
            for l in r["coupling_graph"]["functional_links"]: print(f"  связь: {l['param']} — {l['rule']} ({l['why'][:90]})")
            print(f"  метод 1: {t['method_1_isolated']['expect']} · метод 2: {t['method_2_coupled']['expect']} · метод 3: {t['method_3_ensemble_wfa']['expect']}")
        return
    if a.cmd == "report":
        print("Расхождение изолированного и связанного оптимумов:")
        for pid, iso, cpl, state in c.execute("SELECT pid, iso_best, coupled_best, state FROM params WHERE iso_best IS NOT NULL"):
            d = None if cpl is None or not iso else abs(cpl - iso) / abs(iso) * 100
            print(f"  {pid:34} изолированный {iso:<8} связанный {cpl if cpl is not None else '—':<8} дрейф {'—' if d is None else f'{d:.0f}%'}  {state}")
        return
    if a.cmd == "run-stage":
        n_ = int(a.cluster or 1); ok, left = stage_open(c, n_)
        if not ok: print(f"Этап {n_} закрыт: не завершены {[p for p, _ in left]}"); return
        rows = [r for r in ready_rows(c, M) if next(x for x in M["properties"] if x["property_id"] == r["pid"])["stage"] == n_]
        waiting = c.execute("SELECT COUNT(*) FROM params WHERE stage=? AND state IN ('AWAITING_RUNNER','AWAITING_NT')", (n_,)).fetchone()[0]
        print(f"Этап {n_}: готово к шагу {len(rows)}, ждут исполнителя {waiting}")
        for row in rows:
            print(f"→ {row['pid']}: {row['state']}")
            try: step(c, M, row, a)
            except Exception as ex: setp(c, row["pid"], state=row["state"], note=f"сбой исполнителя: {str(ex)[-300:]}"); print("  сбой:", str(ex)[-300:])
            print("  теперь:", c.execute("SELECT state, note FROM params WHERE pid=?", (row["pid"],)).fetchone())
        return
    if a.cmd == "export-best-preset":
        val = c.execute("SELECT name, coupled_best FROM params WHERE state='VALIDATED'").fetchall()
        if not val: print("VALIDATED-параметров нет — пресет не формируется: в нём оказались бы непроверенные значения."); return
        p = {"preset": "DZ-PRESET-v1", "strategy": "DZ_SW_Hub_S021", "created": dt.datetime.now().isoformat(timespec="seconds"),
             "source": {"orchestrator": VERSION, "db": a.db}, "params": {n: (int(v) if float(v).is_integer() else v) for n, v in val}}
        f = f"DZ_S021_LAB_preset_{dt.datetime.now():%Y%m%d_%H%M}.json"; json.dump(p, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"[пресет] {f}: настроек {len(val)}"); return
    rows = ready_rows(c, M, a.cluster if a.cmd == "run-cluster" else None)
    if not rows: print("Готовых к следующему шагу параметров нет: все проверены, отклонены или ждут родителей."); return
    for row in (rows if a.cmd == "run-cluster" else rows[:1]):
        print(f"→ {row['pid']}: {row['state']}")
        try: step(c, M, row, a)
        except Exception as ex: setp(c, row["pid"], state=row["state"], note=f"сбой исполнителя: {str(ex)[-300:]}"); print("  сбой:", str(ex)[-300:])
        print("  теперь:", c.execute("SELECT state, note FROM params WHERE pid=?", (row["pid"],)).fetchone())


if __name__ == "__main__":
    main()
