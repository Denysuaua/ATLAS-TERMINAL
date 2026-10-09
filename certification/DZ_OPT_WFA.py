#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_OPT_WFA.py — скользящая проверка вперёд (walk-forward), v1.0 (2026-09-28)

Сам ничего не считает: для каждого окна вызывает DZ_OPT_Engine_S021.py так же, как оператор.
  1. обучение  — задача плана на периоде train: оптимизатор выбирает лучший набор;
  2. проверка  — тот же набор, одно испытание, на периоде test, которого обучение не видело.
Каждый запуск записывается оптимизатором в реестр испытаний — проверка вперёд не бесплатна.

ПЛАН (формирует конфигуратор пульта):
  {"plan": "DZ-WFA-v1", "plan_id": "...", "task": {...задача без периода...},
   "windows": [{"train": ["2020-01-01", "2023-01-01"], "test": ["2023-01-01", "2024-01-01"]}, ...]}
Конец периода не включается: окна не делят ни одного бара.

ИТОГ — results/<plan_id>_wfa.csv и .json: по окнам — результат обучения и проверки;
  в целом — сумма вне выборки, доля прибыльных окон, эффективность проверки вперёд
  (прибыль вне выборки в день / прибыль в выборке в день). Около 1 — устойчиво; около 0 и
  ниже — параметры подогнаны под историю.

  python DZ_OPT_WFA.py --plan wfa_plan.json [--workers 0]
==========================================================================================
"""
import argparse, copy, json, os, subprocess, sys
import pandas as pd

VERSION = "DZ_OPT_WFA-v1.0 (2026-09-28)"
HERE = os.path.dirname(os.path.abspath(__file__))


def bdays(a, b):
    return max(1, len(pd.bdate_range(a, pd.Timestamp(b) - pd.Timedelta(days=1))))


def run(task, results, workers, graph):
    os.makedirs(os.path.join(results, "_wfa_tasks"), exist_ok=True)
    path = os.path.join(results, "_wfa_tasks", task["task_id"] + ".json")
    json.dump(task, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    cmd = [sys.executable, os.path.join(HERE, "DZ_OPT_Engine_S021.py"), "run", "--task", path, "--results", results,
           "--workers", str(workers), "--graph", graph, "--ref", os.path.join(HERE, "DZ_BT_DualBreakout_S021.py")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ОТКАЗ: оптимизатор не выполнил {task['task_id']}:\n{r.stderr[-1500:]}")
    return json.load(open(os.path.join(results, task["task_id"], "summary.json"), encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--plan", required=True); ap.add_argument("--results", default="results")
    ap.add_argument("--workers", type=int, default=0); ap.add_argument("--graph", default=os.path.join(HERE, "DZ_OPT_Graph_DualBreakout.json"))
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))
    base_task, pid = plan["task"], plan.get("plan_id", "wfa")
    names = set(json.load(open(a.graph, encoding="utf-8"))["params"])
    obj = base_task.get("objective", "SharpeDaily"); sel = base_task.get("select", "plateau")
    rows = []
    for i, w in enumerate(plan["windows"], 1):
        tr = copy.deepcopy(base_task); tr.update(task_id=f"{pid}_w{i:02d}_train", start=w["train"][0], end=w["train"][1])
        s_tr = run(tr, a.results, a.workers, a.graph)
        best = s_tr["best_selected"]; ins = s_tr["metrics_best_plateau" if sel == "plateau" else "metrics_best_raw"]
        fixed = {k: v for k, v in best.items() if k in names}
        te = {"task_id": f"{pid}_w{i:02d}_test", "data": base_task["data"], "profile": base_task.get("profile", "chicago"),
              "mode": "dev", "optimize": {k: [v] for k, v in fixed.items()}, "base": fixed, "max_trials": 1,
              "objective": obj, "select": "raw", "start": w["test"][0], "end": w["test"][1]}
        for k in ("cache", "capital"):
            if k in base_task: te[k] = base_task[k]
        s_te = run(te, a.results, a.workers, a.graph); oos = s_te["metrics_best_raw"]
        rows.append({"окно": i, "обучение": f"{w['train'][0]}…{w['train'][1]}", "проверка": f"{w['test'][0]}…{w['test'][1]}",
                     f"{obj} в выборке": ins.get(obj), "прибыль в выборке": ins.get("NetProfit"),
                     f"{obj} вне выборки": oos.get(obj), "прибыль вне выборки": oos.get("NetProfit"), "сделок вне выборки": oos.get("Trades"),
                     "дефл. Шарп обучения": s_tr.get("deflated_sharpe"), "PBO обучения": s_tr.get("pbo"), "вердикт обучения": s_tr.get("verdict"),
                     "в день в выборке": (ins.get("NetProfit") or 0) / bdays(*w["train"]), "в день вне выборки": (oos.get("NetProfit") or 0) / bdays(*w["test"]),
                     "лучший набор": json.dumps(fixed, ensure_ascii=False)})
        print(f"  окно {i}: в выборке {ins.get('NetProfit')}, вне выборки {oos.get('NetProfit')}", flush=True)
    df = pd.DataFrame(rows)
    ins_d, oos_d = df["в день в выборке"].mean(), df["в день вне выборки"].mean()
    agg = {"plan_id": pid, "windows": len(df), "oos_net_total": round(float(df["прибыль вне выборки"].fillna(0).sum()), 2),
           "oos_positive_windows": int((df["прибыль вне выборки"].fillna(0) > 0).sum()),
           "walk_forward_efficiency": round(float(oos_d / ins_d), 3) if ins_d > 0 else None}
    df.to_csv(os.path.join(a.results, f"{pid}_wfa.csv"), index=False)
    json.dump({"engine": VERSION, "summary": agg, "windows": rows}, open(os.path.join(a.results, f"{pid}_wfa.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[проверка вперёд] {agg}")


if __name__ == "__main__":
    main()
