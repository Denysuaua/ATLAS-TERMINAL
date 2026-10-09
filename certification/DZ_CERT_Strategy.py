#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DZ_CERT_Strategy.py — аудит восьми элементов стратегии, v1.0 (2026-09-28)

  certify  по STRATEGY_ELEMENTS.json: наличие восьми элементов, их отпечатки, «только чтение»;
           исходник C# (DOC8): версия в шапке и баланс скобок вне комментариев;
           ЭКСПЕРИМЕНТ: --passport — сверка исходника с паспортом сборки DZ_SYS_Bridge:
           доказывает, что в хранилище ровно тот код, что скомпилирован в NinjaTrader.
  verify   пересчёт отпечатков по сертификату.
Ранг: всё в порядке → ЖЁЛТЫЙ; иначе ОТКЛОНЁН. Зелёный и золотой — по сертификату допуска (DOC7).

  python DZ_CERT_Strategy.py certify --dir strategies_vault/DZ_S021 [--passport build_passport.json]
"""
import argparse, json, os, re, sys
from DZ_CERT_Common import sha_file, write_cert, read_cert, now_utc, seal_readonly

VERSION = "DZ_CERT_Strategy-v1.0 (2026-09-28)"
ELEMENTS = ["DOC1_TZ", "DOC2_MANUAL", "DOC3_DEV_GUIDE", "DOC4_SETTINGS_DICT", "DOC5_SETTINGS_LINKS",
            "DOC6_MODULES", "DOC7_TRADING_CERTIFICATE", "DOC8_ENGINE_CS"]


def cs_checks(path):
    """Версия в шапке и баланс скобок вне комментариев и строк."""
    src = open(path, encoding="utf-8", errors="replace").read()
    head = "\n".join(src.splitlines()[:40])
    ver = re.search(r"v\d+\.\d+(\.\d+)?", head)
    code = re.sub(r"//[^\n]*|/\*.*?\*/", "", src, flags=re.S)
    code = re.sub(r'@"(?:[^"]|"")*"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])\'', '""', code)
    bal = {p: code.count(p[0]) - code.count(p[1]) for p in ("{}", "()", "[]")}
    return (ver.group(0) if ver else None), {k: v for k, v in bal.items() if v}


def certify(d, passport):
    man = os.path.join(d, "STRATEGY_ELEMENTS.json")
    if not os.path.exists(man):
        sys.exit(f"ОТКАЗ: нет {man}")
    m = json.load(open(man, encoding="utf-8")); errors, warnings, found = [], [], {}
    for e in ELEMENTS:
        f = m.get(e)
        if not f or not os.path.exists(os.path.join(d, f)):
            errors.append(f"нет {e}"); continue
        found[e] = {"file": f, "sha256": sha_file(os.path.join(d, f))}
    eng = found.get("DOC8_ENGINE_CS")
    if eng:
        ver, bad = cs_checks(os.path.join(d, eng["file"])); eng["version"] = ver
        if not ver: errors.append("DOC8: в шапке исходника нет версии вида vN.N")
        if bad: errors.append(f"DOC8: скобки не сбалансированы {bad} — файл обрезан или повреждён")
        if passport:
            ps = json.load(open(passport, encoding="utf-8"))
            hit = [r for r, meta in ps.get("files", {}).items() if os.path.basename(r) == os.path.basename(eng["file"])]
            if not hit: warnings.append("DOC8 не найден в паспорте сборки")
            elif ps["files"][hit[0]]["sha256"] != eng["sha256"]:
                errors.append("DOC8 отличается от исходника, скомпилированного в NinjaTrader (паспорт сборки)")
            else:
                eng["nt_build_id"] = ps.get("build_id")
    for e in found.values():
        seal_readonly(os.path.join(d, e["file"]))
    cert = {"certificate": "DZ-STRATEGY-CERT-v1.0", "issued_utc": now_utc(), "strategy": os.path.basename(os.path.abspath(d)),
            "rank": "REJECTED" if errors else "YELLOW", "elements": found, "errors": errors, "warnings": warnings}
    write_cert(os.path.join(d, "STRATEGY_CERT.json"), cert)
    print(f"[стратегия] {cert['strategy']}: {cert['rank']}, элементов {len(found)} из 8"
          + (f", движок {eng.get('version')}" if eng else "") + (f", сборка NinjaTrader {eng.get('nt_build_id')}" if eng and eng.get("nt_build_id") else ""))
    for x in errors: print("  ОШИБКА:", x)
    for x in warnings: print("  ВНИМАНИЕ:", x)
    return not errors


def verify(d):
    c, ok = read_cert(os.path.join(d, "STRATEGY_CERT.json")); errs = [] if ok else ["сертификат изменён после выпуска"]
    for e, meta in c["elements"].items():
        p = os.path.join(d, meta["file"])
        if not os.path.exists(p): errs.append(f"{e}: файл отсутствует")
        elif sha_file(p) != meta["sha256"]: errs.append(f"{e}: отпечаток не совпадает")
    print(f"[проверка] {c['strategy']}: " + ("элементы соответствуют сертификату" if not errs else "НАРУШЕНИЕ: " + "; ".join(errs)))
    return not errs


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("cmd", choices=["certify", "verify"]); ap.add_argument("--dir", required=True); ap.add_argument("--passport")
    a = ap.parse_args()
    sys.exit(0 if (certify(a.dir, a.passport) if a.cmd == "certify" else verify(a.dir)) else 1)


if __name__ == "__main__":
    main()
