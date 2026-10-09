#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_XL_Cockpit.py — Excel-пульт терминала «Атлас», v1.0 (2026-09-28)

  build  книга DZ_ATLAS_COCKPIT.xlsx из состояния хранилища:
         «Пульт» — выбор стратегии, инструмента, режима; восемь элементов стратегии;
                   три ресурса инструмента; арбитраж рисков против паспорта; баннер допуска;
         «Задача», «Параметры» — значения для task.json (без формул);
         «Данные», «Паспорта», «Списки» — служебные, формулы пульта читают их по ключам.
  task   книга → task.json: проверка ключей, типов и ворот (инструмент не красный).

БАННЕР
  🔴 ЗАБЛОКИРОВАНО — дефицит элементов или нарушение рисков, при любом режиме;
  🟡 ВОСПРОИЗВЕДЕНИЕ — всё в сборе, режим воспроизведения рынка;
  🟢 РЕАЛЬНЫЙ СЧЁТ — всё в сборе и инструмент зелёный; 🥇 — золотой;
  🔴 реальный счёт не допущен — всё в сборе, но инструмент ниже зелёного.
==========================================================================================
"""
import argparse, glob, json, os, sys
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.worksheet.datavalidation import DataValidation

VERSION = "DZ_XL_Cockpit-v1.0 (2026-09-28)"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from DZ_CERT_Common import read_cert  # noqa: E402

ELEM = [("DOC1_TZ", "ТЗ на разработку"), ("DOC2_MANUAL", "Руководство по эксплуатации"),
        ("DOC3_DEV_GUIDE", "Руководство разработчика"), ("DOC4_SETTINGS_DICT", "Словарь меню настроек"),
        ("DOC5_SETTINGS_LINKS", "Карта связей настроек"), ("DOC6_MODULES", "Перечень модулей"),
        ("DOC7_TRADING_CERTIFICATE", "Сертификат допуска"), ("DOC8_ENGINE_CS", "Исходник C# движка")]
RED, YEL, GRN, GLD = (PatternFill("solid", fgColor=c) for c in ("FFC7CE", "FFEB9C", "C6EFCE", "FFD966"))
TASK_KEYS = {"data", "out", "instrument", "module_file", "module_class", "start", "end"}
EXEC_KEYS = {"stop_ticks", "target_ticks", "slippage", "limit", "qty", "session_exit"}


def collect(root):
    """Состояние хранилища → строки «ключ | значение» и паспорта."""
    import importlib.util
    s = importlib.util.spec_from_file_location("dz_cd", os.path.join(HERE, "DZ_CERT_Data.py"))
    cd = importlib.util.module_from_spec(s); s.loader.exec_module(cd)
    rows, passports, strategies, instruments = [], [], [], []
    for d in sorted(glob.glob(os.path.join(root, "strategies_vault", "*"))):
        if not os.path.isdir(d): continue
        n = os.path.basename(d); strategies.append(n)
        man = os.path.join(d, "STRATEGY_ELEMENTS.json")
        m = json.load(open(man, encoding="utf-8")) if os.path.exists(man) else {}
        for e, _ in ELEM:
            rows.append((f"strategy|{n}|{e}", "ДА" if m.get(e) and os.path.exists(os.path.join(d, m[e])) else "НЕТ"))
    for d in sorted(glob.glob(os.path.join(root, "certified_vault", "*"))):
        if not os.path.isdir(d): continue
        sym = os.path.basename(d); instruments.append(sym)
        pp = os.path.join(d, f"{sym}.instrument.cert.json"); p, pok = (read_cert(pp) if os.path.exists(pp) else ({}, False))
        dc = os.path.join(root, "data_certified", sym, f"{sym}_DATA_CERTIFICATE.json")
        rows.append((f"instrument|{sym}|PASSPORT", "ДА" if pok and p.get("verified_in_nt") else "НЕТ"))
        rows.append((f"instrument|{sym}|DATA_CERT", "ДА" if os.path.exists(dc) else "НЕТ"))
        rows.append((f"instrument|{sym}|DATA_INTEGRITY", "ДА" if os.path.exists(dc) and cd.verify(dc, quiet=True)[0] else "НЕТ"))
        st = os.path.join(d, "STATUS.json")
        rows.append((f"instrument|{sym}|STATUS", json.load(open(st, encoding="utf-8"))["status"] if os.path.exists(st) else "RED"))
        if p:
            tv = p["market_mathematics"]["tick_value"]; c = p["costs_per_contract"]; r = p["risk_limits"]
            passports.append((sym, tv, r["stop_usd_per_contract"][1] / tv, r["daily_loss_usd"], c["round_turn"],
                              c["slippage_ticks_per_fill"], c["min_breakeven_offset_ticks_costs_and_slippage"]))
    return rows, passports, strategies or ["—"], instruments or ["—"]


def build(root, out):
    rows, passports, strategies, instruments = collect(root)
    wb = Workbook(); ws = wb.active; ws.title = "Пульт"
    lists, data, pas = wb.create_sheet("Списки"), wb.create_sheet("Данные"), wb.create_sheet("Паспорта")
    task, par = wb.create_sheet("Задача"), wb.create_sheet("Параметры")

    lists.append(["Стратегии", "Инструменты", "Режимы"])
    modes = ["ВОСПРОИЗВЕДЕНИЕ", "РЕАЛЬНЫЙ СЧЁТ"]
    for i in range(max(len(strategies), len(instruments), 2)):
        lists.append([strategies[i] if i < len(strategies) else None, instruments[i] if i < len(instruments) else None,
                      modes[i] if i < 2 else None])
    data.append(["Ключ", "Значение"]); [data.append(list(r)) for r in rows]
    pas.append(["Инструмент", "Тик, валюта", "Макс. стоп, тиков", "Дневной лимит", "Круг, валюта", "Проскальз., тиков", "Мин. безубыток, тиков"])
    [pas.append(list(p)) for p in passports]

    B = Font(bold=True); ws.column_dimensions["A"].width = 38
    for c in "BCD": ws.column_dimensions[c].width = 24
    ws["A1"] = "ТЕРМИНАЛ «АТЛАС» — ПУЛЬТ ДОПУСКА"; ws["A1"].font = Font(bold=True, size=14)
    for r, (label, val) in enumerate([("Стратегия", strategies[0]), ("Инструмент", instruments[0]), ("Режим", modes[0])], 3):
        ws.cell(r, 1, label).font = B; ws.cell(r, 2, val).fill = PatternFill("solid", fgColor="DDEBF7")
    for rng, col, n in (("B3", "A", len(strategies)), ("B4", "B", len(instruments)), ("B5", "C", 2)):
        dv = DataValidation(type="list", formula1=f"=Списки!${col}$2:${col}${n + 1}", allow_blank=False); ws.add_data_validation(dv); dv.add(ws[rng])

    ws["A9"] = "1. СТРАТЕГИЯ — ВОСЕМЬ ЭЛЕМЕНТОВ"; ws["A9"].font = B
    for i, (e, label) in enumerate(ELEM):
        r = 10 + i; ws.cell(r, 1, label)
        ws.cell(r, 2, f'=IFERROR(INDEX(Данные!$B:$B,MATCH("strategy|"&$B$3&"|{e}",Данные!$A:$A,0)),"НЕТ")')
    ws["A19"] = "2. ИНСТРУМЕНТ — ТРИ РЕСУРСА"; ws["A19"].font = B
    for i, (k, label) in enumerate([("PASSPORT", "Паспорт, сверен с NinjaTrader"), ("DATA_CERT", "Сертификат данных"),
                                    ("DATA_INTEGRITY", "Отпечатки данных целы")]):
        ws.cell(20 + i, 1, label); ws.cell(20 + i, 2, f'=IFERROR(INDEX(Данные!$B:$B,MATCH("instrument|"&$B$4&"|{k}",Данные!$A:$A,0)),"НЕТ")')
    ws["H4"] = '=IFERROR(INDEX(Данные!$B:$B,MATCH("instrument|"&$B$4&"|STATUS",Данные!$A:$A,0)),"RED")'

    ws["A24"] = "3. АРБИТРАЖ РИСКОВ"; ws["A24"].font = B
    for c, t in zip("ABCD", ("Параметр", "Стратегия (ввод)", "Паспорт", "Согласование")): ws.cell(24, "ABCD".index(c) + 1, t).font = B
    look = lambda col: f'IFERROR(INDEX(Паспорта!${col}:${col},MATCH($B$4,Паспорта!$A:$A,0)),0)'
    arb = [("Стоп, тиков", 200, look("C"), "<=", "ПРЕВЫШЕНИЕ РИСКА"), ("Дневной лимит потерь", 1500, look("D"), "<=", "ПРЕВЫШЕНИЕ РИСКА"),
           ("Издержки круга на контракт", 0.44, look("E"), ">=", "ЗАНИЖЕНЫ ИЗДЕРЖКИ"),
           ("Проскальзывание, тиков на исполнение", 1, look("F"), ">=", "ЗАНИЖЕНО ПРОСКАЛЬЗЫВАНИЕ"),
           ("Отступ безубытка, тиков", 2, look("G"), ">=", "НЕ ПОКРЫВАЕТ ИЗДЕРЖКИ")]
    for i, (label, dflt, f, op, bad) in enumerate(arb):
        r = 25 + i; ws.cell(r, 1, label); ws.cell(r, 2, dflt).fill = PatternFill("solid", fgColor="DDEBF7")
        ws.cell(r, 3, "=" + f); ws.cell(r, 4, f'=IF(B{r}{op}C{r},"СОГЛАСОВАНО","{bad}")')

    ws.merge_cells("A7:D7"); a7 = ws["A7"]; a7.font = Font(bold=True, size=13); a7.alignment = Alignment(wrap_text=True)
    ws.row_dimensions[7].height = 34
    a7.value = ('=IF(OR(COUNTIF(B10:B17,"НЕТ")>0,COUNTIF(B20:B22,"НЕТ")>0,COUNTIF(D25:D29,"СОГЛАСОВАНО")<5),'
                '"🔴 ЗАБЛОКИРОВАНО: дефицит элементов или нарушение рисков",'
                'IF($B$5="ВОСПРОИЗВЕДЕНИЕ","🟡 ДОПУЩЕНО К ВОСПРОИЗВЕДЕНИЮ РЫНКА",'
                'IF($H$4="GOLD","🥇 ЗОЛОТОЙ: ДОПУЩЕНО К РЕАЛЬНОМУ СЧЁТУ",'
                'IF($H$4="GREEN","🟢 ДОПУЩЕНО К РЕАЛЬНОМУ СЧЁТУ","🔴 РЕАЛЬНЫЙ СЧЁТ НЕ ДОПУЩЕН: инструмент ниже зелёного"))))')
    for rng in ("B10:B17", "B20:B22"):
        ws.conditional_formatting.add(rng, FormulaRule(formula=[f'{rng.split(":")[0]}="НЕТ"'], fill=RED, font=Font(bold=True, color="9C0006")))
        ws.conditional_formatting.add(rng, FormulaRule(formula=[f'{rng.split(":")[0]}="ДА"'], fill=GRN))
    ws.conditional_formatting.add("D25:D29", FormulaRule(formula=['D25<>"СОГЛАСОВАНО"'], fill=RED, font=Font(bold=True, color="9C0006")))
    ws.conditional_formatting.add("D25:D29", FormulaRule(formula=['D25="СОГЛАСОВАНО"'], fill=GRN))
    for key, fill in (("🔴", RED), ("🟡", YEL), ("🟢", GRN), ("🥇", GLD)):
        ws.conditional_formatting.add("A7", FormulaRule(formula=[f'LEFT($A$7,1)=LEFT("{key}",1)'], fill=fill))

    task.append(["Ключ", "Значение"])
    for k, v in (("data", "mgc.npz"), ("out", "term_results"), ("instrument", instruments[0]), ("module_file", None), ("module_class", None)):
        task.append([k, v])
    par.append(["name", "N", "stop_ticks", "target_ticks", "slippage", "limit"]); par.append(["mom20", 20, 20, 40, 1, "through"])
    wb.save(out)
    print(f"[пульт] {out}: стратегий {len(strategies)}, инструментов {len(instruments)}, паспортов {len(passports)}")


def make_task(xlsx, out, root):
    wb = load_workbook(xlsx, data_only=True)
    t = {r[0]: r[1] for r in wb["Задача"].iter_rows(min_row=2, values_only=True) if r[0]}
    bad = sorted(set(t) - TASK_KEYS)
    if bad: sys.exit(f"ОТКАЗ: неизвестные ключи листа «Задача»: {bad}")
    task = {k: v for k, v in t.items() if v not in (None, "")}
    head = [c.value for c in wb["Параметры"][1]]; jobs = []
    for row in wb["Параметры"].iter_rows(min_row=2, values_only=True):
        if not row or not row[0]: continue
        rec = dict(zip(head, row)); job = {"name": rec.pop("name"), "instrument": task["instrument"], "execution": {}, "module_params": {}}
        for k, v in rec.items():
            if v in (None, ""): continue
            (job["execution"] if k in EXEC_KEYS else job["module_params"])[k] = v
        for k in ("module_file", "module_class", "start", "end"):
            if k in task: job[k] = task[k]
        jobs.append(job)
    st = os.path.join(root, "certified_vault", task["instrument"], "STATUS.json")
    status = json.load(open(st, encoding="utf-8"))["status"] if os.path.exists(st) else "RED"
    if status == "RED":
        sys.exit(f"ОТКАЗ: инструмент {task['instrument']} красный — задача не выпускается. Смотрите status/ATLAS_STATUS.html")
    body = {"data": task["data"], "out": task.get("out", "term_results"), "jobs": jobs}
    tmp = out + ".tmp"; json.dump(body, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2, sort_keys=True); os.replace(tmp, out)
    print(f"[задача] {out}: заданий {len(jobs)}, инструмент {task['instrument']} ({status})")


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("cmd", choices=["build", "task"]); ap.add_argument("--root", default=".")
    ap.add_argument("--xlsx", default="DZ_ATLAS_COCKPIT.xlsx"); ap.add_argument("--out", default="task.json")
    a = ap.parse_args()
    build(a.root, a.xlsx) if a.cmd == "build" else make_task(a.xlsx, a.out, a.root)


if __name__ == "__main__":
    main()
