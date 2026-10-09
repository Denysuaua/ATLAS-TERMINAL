#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DZ_CERT_Template.py — сертификатор шаблонов настроек S021, v1.0 (2026-09-28)

Пределы и индексы настроек берутся из ИСХОДНИКА коммутатора, а не из списка в скрипте:
меню и проверки всегда совпадают с кодом. Правила ссылаются на индексы ([MOD8], [S90]),
поэтому переименование свойства их не ломает. Нет свойства в шаблоне — правило «н/п».

Ранг: ошибок нет → ЖЁЛТЫЙ (допуск к бэктесту и воспроизведению рынка); есть — ОТКЛОНЁН.
Зелёный и золотой присваиваются позже — по бэктесту и по реальной торговле.

  python DZ_CERT_Template.py --template S021_MGC.xml --hub DZ_SW_Hub_S021.cs --instrument-cert certified_vault/MGC/MGC.instrument.cert.json
"""
import argparse, json, os, re, sys
import xml.etree.ElementTree as ET
from DZ_CERT_Common import sha_file, write_cert, read_cert, now_utc

VERSION = "DZ_CERT_Template-v1.0 (2026-09-28)"


def parse_hub(path):
    """Свойство → индекс, тип, пределы — из атрибутов исходника коммутатора."""
    src = open(path, encoding="utf-8").read()
    props, prev = {}, 0
    for m in re.finditer(r"public\s+([\w\.<>]+)\s+(\w+)\s*\{\s*get;\s*set;\s*\}", src):
        block = src[prev:m.start()]; prev = m.end()
        d = re.search(r'Display\(Name = "\[(\w+)\]', block)
        if not d:
            continue
        r = re.search(r"\[Range\(\s*([-\d\.]+)\s*,\s*([-\d\.]+)\s*\)\]", block)
        props[m.group(2)] = {"index": d.group(1), "type": m.group(1),
                             "range": (float(r.group(1)), float(r.group(2))) if r else None}
    return props


def load_values(path):
    if path.endswith(".json"):
        return {k: str(v) for k, v in json.load(open(path, encoding="utf-8")).items()}
    vals = {}
    for el in ET.parse(path).iter():
        if len(el) == 0 and el.text is not None:
            vals[el.tag.split("}")[-1]] = el.text.strip()
    return vals


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--template", required=True); ap.add_argument("--hub", required=True)
    ap.add_argument("--instrument-cert"); ap.add_argument("--out")
    a = ap.parse_args()

    props = parse_hub(a.hub); raw = load_values(a.template)
    by_idx = {p["index"]: n for n, p in props.items()}

    def val(name):
        if name not in raw: return None
        t = props[name]["type"]
        if t == "bool": return raw[name].lower() == "true"
        if t in ("int", "double", "float"):
            try: return float(raw[name])
            except ValueError: return raw[name]
        return raw[name]

    def v(idx):
        n = by_idx.get(idx)
        return val(n) if n else None

    errors, warnings, checked = [], [], 0
    for name, p in props.items():                                       # 1. пределы
        x = val(name)
        if x is None or p["range"] is None or not isinstance(x, float):
            continue
        checked += 1
        lo, hi = p["range"]
        if not (lo <= x <= hi):
            errors.append(f"[{p['index']}] {name} = {x:g} вне предела {lo:g}…{hi:g}")

    if v("MOD8") and v("MOD3"):                                           # 2. конфликты модулей
        errors.append("[MOD8] и [MOD3] включены вместе: окна пробоя и фильтр времени конфликтуют")
    if v("MOD7") and not v("MOD2"):
        errors.append("[MOD7] требует [MOD2]")
    if v("L16") and not v("MOD9"):
        errors.append("[L16] согласие с ядром включено без [MOD9]")
    if v("MOD8") and v("M84") is not None and v("S90") is not None and v("M84") != v("S90"):
        errors.append(f"[M84] = {v('M84'):g} ≠ [S90] = {v('S90'):g}: стоп-вход встанет на минуту позже")
    if v("MOD8"):                                                          # 3. окна пробоя
        for use, base in (("M82", 10), ("M83", 20)):
            w = [v(f"W{base + i}") for i in range(1, 6)]
            if v(use) and None not in w and not (w[0] < w[1] < w[2] <= w[3] < w[4] <= 235959):
                errors.append(f"[W{base + 1}]–[W{base + 5}] нарушен порядок «база < окно < выход»: {w}")

    pas = None
    if a.instrument_cert:                                                 # 4. риск и издержки
        pas, ok = read_cert(a.instrument_cert)
        if not ok:
            errors.append("паспорт инструмента изменён после выпуска")
        tv = pas["market_mathematics"]["tick_value"]
        lo, hi = pas["risk_limits"]["stop_usd_per_contract"]
        stop, mode = v("E03"), v("F11")
        if isinstance(stop, float) and (mode is None or str(mode) == "FixedTicks"):
            usd = stop * tv
            if not (lo <= usd <= hi):
                errors.append(f"[E03] стоп {stop:g} т = {usd:g} за контракт вне паспорта {lo:g}…{hi:g}")
        off, be = v("F32"), v("F31")
        need = pas["costs_per_contract"]["min_breakeven_offset_ticks_costs_and_slippage"]
        if isinstance(off, float) and str(be) != "Off" and off < need:
            warnings.append(f"[F32] отступ безубытка {off:g} т меньше издержек круга и проскальзывания ({need} т)")
    if v("E01") is True:
        warnings.append("[E01] режим без ордеров включён — для реального счёта его нужно выключить")

    cert = {"certificate": "DZ-TEMPLATE-CERT-v1.0", "issued_utc": now_utc(),
            "rank": "REJECTED" if errors else "YELLOW",
            "rank_meaning": "отклонён" if errors else "жёлтый: допуск к бэктесту и воспроизведению рынка",
            "template_file": os.path.basename(a.template), "template_sha256": sha_file(a.template),
            "hub_source_sha256": sha_file(a.hub), "instrument": pas.get("symbol") if pas else None,
            "instrument_cert_sha256": pas.get("content_sha256") if pas else None,
            "properties_in_template": len(raw), "ranges_checked": checked, "errors": errors, "warnings": warnings}
    out = a.out or (os.path.splitext(a.template)[0] + ".cert.json")
    write_cert(out, cert)
    print(f"[шаблон] {cert['rank']}: ошибок {len(errors)}, предупреждений {len(warnings)}, пределов проверено {checked} → {out}")
    for e in errors: print("  ОШИБКА:", e)
    for w in warnings: print("  ВНИМАНИЕ:", w)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
