#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_STATUS_Board.py — светофор терминала «Атлас», v1.0 (2026-09-28)

Статус пишется в файлы, а не в имена папок: переименование порвало бы пути скриптов,
NinjaTrader и Excel. Результат:
  • STATUS.json в папке каждого инструмента и стратегии;
  • status/ATLAS_STATUS.json и status/ATLAS_STATUS.html — сводная панель для браузера.

ИНСТРУМЕНТ
  КРАСНЫЙ  нет паспорта или сертификата данных, либо проверка отпечатков не прошла
  ЖЁЛТЫЙ   паспорт и данные целы; шаблоны не выше жёлтого
  ЗЕЛЁНЫЙ  есть шаблон с рангом GREEN
  ЗОЛОТОЙ  есть шаблон с рангом GOLD
СТРАТЕГИЯ — по явному списку STRATEGY_ELEMENTS.json (восемь элементов)
  КРАСНЫЙ  списка нет либо хотя бы один элемент отсутствует
  ЖЁЛТЫЙ   все восемь на месте
  ЗЕЛЁНЫЙ / ЗОЛОТОЙ — ранг сертификата допуска (элемент DOC7_TRADING_CERTIFICATE)
==========================================================================================
"""
import argparse, glob, html, json, os, sys

VERSION = "DZ_STATUS_Board-v1.0 (2026-09-28)"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from DZ_CERT_Common import read_cert, sha_file  # noqa: E402

ELEMENTS = ["DOC1_TZ", "DOC2_MANUAL", "DOC3_DEV_GUIDE", "DOC4_SETTINGS_DICT", "DOC5_SETTINGS_LINKS",
            "DOC6_MODULES", "DOC7_TRADING_CERTIFICATE", "DOC8_ENGINE_CS"]
COLOR = {"RED": ("#FFC7CE", "🔴 КРАСНЫЙ"), "YELLOW": ("#FFEB9C", "🟡 ЖЁЛТЫЙ"),
         "GREEN": ("#C6EFCE", "🟢 ЗЕЛЁНЫЙ"), "GOLD": ("#FFD966", "🥇 ЗОЛОТОЙ")}


def instrument_status(root, sym, data_verify):
    folder = os.path.join(root, "certified_vault", sym); why = []
    pas = os.path.join(folder, f"{sym}.instrument.cert.json")
    dc = os.path.join(root, "data_certified", sym, f"{sym}_DATA_CERTIFICATE.json")
    if not os.path.exists(pas): why.append("нет паспорта инструмента")
    else:
        p, ok = read_cert(pas)
        if not ok or not p.get("verified_in_nt"): why.append("паспорт изменён или не сверен с NinjaTrader")
    if not os.path.exists(dc): why.append("нет сертификата данных")
    else:
        ok, errs, _ = data_verify(dc, quiet=True)
        if not ok: why += errs
    ranks = []
    for c in glob.glob(os.path.join(folder, "*", "templates", "*.cert.json")):
        t, ok = read_cert(c)
        if ok: ranks.append(t.get("rank"))
    st = "RED" if why else ("GOLD" if "GOLD" in ranks else "GREEN" if "GREEN" in ranks else "YELLOW")
    return {"kind": "инструмент", "name": sym, "status": st, "reasons": why,
            "templates": {r: ranks.count(r) for r in set(ranks)}}


def strategy_status(folder):
    name = os.path.basename(folder); man = os.path.join(folder, "STRATEGY_ELEMENTS.json")
    if not os.path.exists(man):
        return {"kind": "стратегия", "name": name, "status": "RED", "reasons": ["нет STRATEGY_ELEMENTS.json"]}
    m = json.load(open(man, encoding="utf-8")); why, found = [], {}
    for e in ELEMENTS:
        f = m.get(e)
        if not f or not os.path.exists(os.path.join(folder, f)): why.append(f"нет {e}")
        else: found[e] = {"file": f, "sha256": sha_file(os.path.join(folder, f))}
    rank = None
    if "DOC7_TRADING_CERTIFICATE" in found and found["DOC7_TRADING_CERTIFICATE"]["file"].endswith(".json"):
        c, ok = read_cert(os.path.join(folder, found["DOC7_TRADING_CERTIFICATE"]["file"]))
        rank = c.get("rank") if ok else None
    st = "RED" if why else (rank if rank in ("GREEN", "GOLD") else "YELLOW")
    return {"kind": "стратегия", "name": name, "status": st, "reasons": why, "elements": found}


def main():
    ap = argparse.ArgumentParser(description=VERSION); ap.add_argument("--root", default=".")
    a = ap.parse_args()
    import importlib.util
    s = importlib.util.spec_from_file_location("dz_cd", os.path.join(HERE, "DZ_CERT_Data.py"))
    cd = importlib.util.module_from_spec(s); s.loader.exec_module(cd)
    rows = []
    for d in sorted(glob.glob(os.path.join(a.root, "certified_vault", "*"))):
        if os.path.isdir(d):
            r = instrument_status(a.root, os.path.basename(d), cd.verify); rows.append(r)
            json.dump(r, open(os.path.join(d, "STATUS.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    for d in sorted(glob.glob(os.path.join(a.root, "strategies_vault", "*"))):
        if os.path.isdir(d):
            r = strategy_status(d); rows.append(r)
            json.dump(r, open(os.path.join(d, "STATUS.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.makedirs(os.path.join(a.root, "status"), exist_ok=True)
    json.dump(rows, open(os.path.join(a.root, "status", "ATLAS_STATUS.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    tr = "".join(f"<tr style='background:{COLOR[r['status']][0]}'><td>{r['kind']}</td><td><b>{html.escape(r['name'])}</b></td>"
                 f"<td>{COLOR[r['status']][1]}</td><td>{html.escape('; '.join(r['reasons']) or '—')}</td></tr>" for r in rows)
    page = (f"<!doctype html><meta charset='utf-8'><title>Атлас — статус</title><body style='font-family:sans-serif'>"
            f"<h2>Терминал «Атлас» — статус</h2><table cellpadding=6 style='border-collapse:collapse' border=1>"
            f"<tr><th>Вид</th><th>Имя</th><th>Статус</th><th>Причины</th></tr>{tr}</table></body>")
    open(os.path.join(a.root, "status", "ATLAS_STATUS.html"), "w", encoding="utf-8").write(page)
    for r in rows:
        print(f"  {COLOR[r['status']][1]:12} {r['kind']:10} {r['name']:18} {'; '.join(r['reasons'])[:70]}")


if __name__ == "__main__":
    main()
