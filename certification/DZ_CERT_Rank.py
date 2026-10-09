#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_CERT_Rank.py — повышение ранга шаблона: жёлтый → зелёный → золотой, v1.0 (2026-09-28)

Каждое повышение — НОВЫЙ сертификат со ссылкой на отпечаток предыдущего: цепочку нельзя
подделать задним числом. Прежний сертификат не переписывается.

ЗЕЛЁНЫЙ — сертифицированный бэктест:
  • жёлтый сертификат шаблона цел, шаблон не изменён;
  • штамп шлюза DZ_AUDIT_Gatekeeper — «СЕРТИФИЦИРОВАНО»;
  • отложенный период: чистая прибыль > 0 и не меньше 30 сделок;
  • если параметры подбирались оптимизацией (--opt-summary) — дефлированный Шарп ≥ 0,95 и PBO ≤ 0,5.
  В сертификат записываются метрики сделок бэктеста — эталон для золота.

ЗОЛОТОЙ — реальная торговля (П12), выгрузка сделок NinjaTrader:
  1. не меньше 30 календарных дней;  2. не меньше 30 сделок;  3. чистая прибыль > 0;
  4. PF ≥ 80% от PF бэктеста;  5. просадка ≤ просадки худшего сценария × коэффициент;
  6. статистика: бутстреп 95% интервал ожидания сделки — реальная торговля не значимо хуже
     бэктеста (ожидание бэктеста не выше верхней границы интервала).
  ЭКСПЕРИМЕНТ: монитор дрейфа — первая сделка, где капитал ушёл ниже полосы E·n − 2σ·√n.
  ЭКСПЕРИМЕНТ: значимость прибыли — нижняя граница интервала выше нуля или нет.
==========================================================================================
"""
import argparse, json, os, sys
import numpy as np
import pandas as pd
from DZ_CERT_Common import sha_file, write_cert, read_cert, now_utc

VERSION = "DZ_CERT_Rank-v1.0 (2026-09-28)"
LIVE_COLS = {"entry": ["entry time", "время входа", "einstiegszeit"], "exit": ["exit time", "время выхода", "ausstiegszeit"],
             "profit": ["profit", "прибыль", "gewinn", "netcurrency"]}


def fresh(path):
    """Сертификаты не перезаписываются: повторное присвоение получает номер версии."""
    if not os.path.exists(path):
        return path
    base = path[: -len(".cert.json")]; n = 2
    while os.path.exists(f"{base}_v{n:03d}.cert.json"):
        n += 1
    return f"{base}_v{n:03d}.cert.json"


def metrics(pnl):
    pnl = np.asarray(pnl, float); eq = np.cumsum(pnl)
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    return {"trades": int(len(pnl)), "net": round(float(pnl.sum()), 2), "mean": round(float(pnl.mean()), 4),
            "std": round(float(pnl.std(ddof=1)), 4) if len(pnl) > 1 else 0.0, "pf": round(float(gp / gl), 4) if gl > 0 else None,
            "max_dd": round(float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max()), 2)}


def promote_green(a):
    tc, ok = read_cert(a.template_cert); fails = []
    if not ok or tc.get("rank") != "YELLOW": fails.append("жёлтый сертификат шаблона изменён или ранг не жёлтый")
    tfile = os.path.join(os.path.dirname(a.template_cert), tc.get("template_file", ""))
    if not os.path.exists(tfile) or sha_file(tfile) != tc.get("template_sha256"): fails.append("шаблон изменён после жёлтой сертификации")
    st = json.load(open(a.stamp, encoding="utf-8")).get("СЕРТИФИКАТ_БЭКТЕСТА", {}).get("СТАТУС", "")
    if not st.startswith("СЕРТИФИЦИРОВАНО"): fails.append("штамп шлюза отсутствует или «не сертифицировано»")
    h = pd.read_csv(a.holdout_summary)
    row = h[h["job"] == a.holdout_job].iloc[0] if a.holdout_job else h.iloc[0]
    if not (row["Чистая прибыль"] > 0 and row["Всего сделок"] >= 30):
        fails.append(f"отложенный период: прибыль {row['Чистая прибыль']}, сделок {row['Всего сделок']} — нужно > 0 и ≥ 30")
    opt = None
    if a.opt_summary:
        opt = json.load(open(a.opt_summary, encoding="utf-8"))
        if not ((opt.get("deflated_sharpe") or 0) >= 0.95 and (opt.get("pbo") if opt.get("pbo") is not None else 1) <= 0.5):
            fails.append(f"оптимизация: дефлированный Шарп {opt.get('deflated_sharpe')}, PBO {opt.get('pbo')} — нужно ≥ 0,95 и ≤ 0,5")
    bt = pd.read_csv(a.backtest_trades)
    if fails:
        print("ЗЕЛЁНЫЙ НЕ ПРИСВОЕН:"); [print("  —", f) for f in fails]; return False
    cert = {"certificate": "DZ-TEMPLATE-CERT-v1.0", "issued_utc": now_utc(), "rank": "GREEN",
            "rank_meaning": "зелёный: допуск к реальному счёту", "template_file": tc["template_file"],
            "template_sha256": tc["template_sha256"], "instrument": tc.get("instrument"),
            "previous_cert_sha256": tc["content_sha256"], "gatekeeper_stamp_sha256": sha_file(a.stamp),
            "holdout": {"job": row["job"], "net": float(row["Чистая прибыль"]), "trades": int(row["Всего сделок"])},
            "optimization": {"deflated_sharpe": opt.get("deflated_sharpe"), "pbo": opt.get("pbo")} if opt else None,
            "backtest_reference": metrics(bt["NetCurrency"])}
    out = a.template_cert.replace(".cert.json", ".GREEN.cert.json")
    out = fresh(out); write_cert(out, cert)
    print(f"🟢 ЗЕЛЁНЫЙ присвоен → {out}\n  эталон бэктеста: {cert['backtest_reference']}"); return True


def find(cols, names):
    low = {c.strip().lower(): c for c in cols}
    return next((low[n] for n in names if n in low), None)


def promote_gold(a):
    gc, ok = read_cert(a.green_cert)
    if not ok or gc.get("rank") != "GREEN": sys.exit("ОТКАЗ: зелёный сертификат изменён или ранг не зелёный")
    df = pd.read_csv(a.live, sep=None, engine="python")
    c = {k: find(df.columns, v) for k, v in LIVE_COLS.items()}
    if None in c.values(): sys.exit(f"ОТКАЗ: в выгрузке не найдены столбцы {[k for k, v in c.items() if v is None]}: {list(df.columns)}")
    num = lambda s: pd.to_numeric(s.astype(str).str.replace(r"[^\d,.\-]", "", regex=True).str.replace(",", "."), errors="coerce")
    pnl = num(df[c["profit"]]).dropna().to_numpy()
    t0 = pd.to_datetime(df[c["entry"]], dayfirst=True, errors="coerce").min(); t1 = pd.to_datetime(df[c["exit"]], dayfirst=True, errors="coerce").max()
    live, ref = metrics(pnl), gc["backtest_reference"]; days = (t1 - t0).days
    rng = np.random.default_rng(20260928)
    boot = rng.choice(pnl, size=(10000, len(pnl)), replace=True).mean(1); lo, hi = np.percentile(boot, [2.5, 97.5])
    band = np.arange(1, len(pnl) + 1) * ref["mean"] - 2 * ref["std"] * np.sqrt(np.arange(1, len(pnl) + 1))
    below = np.flatnonzero(np.cumsum(pnl) < band)
    checks = [("срок ≥ 30 дней", days >= 30, f"{days} дн."), ("сделок ≥ 30", live["trades"] >= 30, str(live["trades"])),
              ("чистая прибыль > 0", live["net"] > 0, str(live["net"])),
              ("PF ≥ 80% бэктеста", ref["pf"] is not None and live["pf"] is not None and live["pf"] >= 0.8 * ref["pf"], f"{live['pf']} против {ref['pf']}"),
              ("просадка ≤ худшего сценария", live["max_dd"] <= ref["max_dd"] * a.dd_factor, f"{live['max_dd']} против {ref['max_dd']}×{a.dd_factor}"),
              ("не значимо хуже бэктеста", ref["mean"] <= hi, f"ожидание бэктеста {ref['mean']:.2f}, интервал реальной [{lo:.2f}; {hi:.2f}]")]
    for n, p, d in checks: print(f"  {'✓' if p else '✗'} {n}: {d}")
    print(f"  ЭКСПЕРИМЕНТ — значимость прибыли: {'доказана' if lo > 0 else 'не доказана — интервал включает ноль'}")
    print(f"  ЭКСПЕРИМЕНТ — дрейф: " + (f"капитал ниже полосы с сделки №{below[0] + 1}" if len(below) else "капитал в полосе бэктеста"))
    if not all(p for _, p, _ in checks):
        print("ЗОЛОТО НЕ ПРИСВОЕНО"); return False
    cert = {**{k: gc[k] for k in ("certificate", "template_file", "template_sha256", "instrument")}, "issued_utc": now_utc(),
            "rank": "GOLD", "rank_meaning": "золотой: подтверждено реальной торговлей", "previous_cert_sha256": gc["content_sha256"],
            "live_export_sha256": sha_file(a.live), "live": {**live, "days": days, "mean_ci95": [round(lo, 4), round(hi, 4)]},
            "backtest_reference": ref, "profit_significant": bool(lo > 0), "drift_first_breach_trade": int(below[0] + 1) if len(below) else None}
    out = a.green_cert.replace(".GREEN.cert.json", ".GOLD.cert.json")
    out = fresh(out); write_cert(out, cert)
    print(f"🥇 ЗОЛОТО присвоено → {out}"); return True


def main():
    ap = argparse.ArgumentParser(description=VERSION); sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("green")
    for k in ("template-cert", "stamp", "holdout-summary", "backtest-trades"): g.add_argument(f"--{k}", required=True)
    g.add_argument("--holdout-job"); g.add_argument("--opt-summary")
    o = sub.add_parser("gold"); o.add_argument("--green-cert", required=True); o.add_argument("--live", required=True)
    o.add_argument("--dd-factor", type=float, default=1.0)
    a = ap.parse_args()
    sys.exit(0 if (promote_green(a) if a.cmd == "green" else promote_gold(a)) else 1)


if __name__ == "__main__":
    main()
