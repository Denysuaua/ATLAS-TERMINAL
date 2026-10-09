# -*- coding: utf-8 -*-
"""
DZ_TS_Lab_Orchestrator.py ? ???????? ?????????? ?????? ???????????? ???????????? S021
"""
import os, sys, json, sqlite3, time

PLAN_FILE = "DZ_LAB_Research_Plan.json"
DB_FILE = "DZ_LAB_Results.db"

class LabOrchestrator:
    def __init__(self):
        if not os.path.exists(PLAN_FILE):
            print("??????: ???? ????? ?? ??????!")
            sys.exit(1)
        with open(PLAN_FILE, "r", encoding="utf-8") as f:
            self.plan = json.load(f)
            
    def status(self):
        print("===============================================================")
        print(f" ???????????? ???? ????????????: {self.plan['strategy']}")
        print("===============================================================")
        for cluster in self.plan["clusters"]:
            print(f"\n[???????]: {cluster['name']} ({cluster['cluster_id']})")
            for p in cluster["parameters"]:
                coupled = ", ".join(p["coupled_with"]) if p["coupled_with"] else "???"
                print(f"  * {p['param_name']:<22} | ??????: {p['default']:<5} | ?????: [{coupled}] | ??????: {p['status']}")
                
    def record_run(self, param_name, method, tested_params, sharpe, mdd, pnl, trades, status="PASS"):
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO lab_runs (timestamp, param_name, method, params_tested, sharpe_ratio, max_drawdown, net_profit, trades_count, pbo_score, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (time.strftime("%Y-%m-%d %H:%M:%S"), param_name, method, json.dumps(tested_params), sharpe, mdd, pnl, trades, 0.0, status))
        conn.commit()
        conn.close()
        print(f"[???????????] ???????????? ????????? ?? {param_name} ({method}): Sharpe={sharpe}, NetPnL={pnl}")

if __name__ == "__main__":
    lab = LabOrchestrator()
    lab.status()
