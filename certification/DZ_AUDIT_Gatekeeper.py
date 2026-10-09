#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DZ_AUDIT_Gatekeeper.py — шлюз сертификации отчётов, v1.0 (2026-09-28)

Штамп «СЕРТИФИЦИРОВАНО» ставится, только если выполнены все проверки:
  1. печать эмулятора — отпечатки сертифицированных файлов и регресс до цента (постулаты П1–П10);
  2. сертификат данных — отпечатки всех таймфреймов и функции ресемплинга (П11);
  3. паспорт инструмента — цел и сверен с NinjaTrader;
  4. сертификат шаблона — если указан: цел и не отклонён;
  5. связь отчёта с данными — отпечаток данных прогона равен сертифицированному.
Исходный отчёт не меняется: рядом пишется <отчёт>.stamped.json.

  python DZ_AUDIT_Gatekeeper.py --report term_results/summary.csv --run-manifest term_results/run_manifest.json \
      --data-cert data_certified/MGC/MGC_DATA_CERTIFICATE.json --instrument-cert certified_vault/MGC/MGC.instrument.cert.json
"""
import argparse, contextlib, importlib.util, io, json, os, sys
from DZ_CERT_Common import read_cert, sha_file, now_utc

VERSION = "DZ_AUDIT_Gatekeeper-v1.0 (2026-09-28)"
HERE = os.path.dirname(os.path.abspath(__file__))


def _mod(path, name):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--report", required=True); ap.add_argument("--run-manifest")
    ap.add_argument("--data-cert", required=True); ap.add_argument("--instrument-cert", required=True)
    ap.add_argument("--template-cert"); ap.add_argument("--emulator-dir", default=HERE)
    a = ap.parse_args()
    ok, log = True, []

    def check(label, passed, detail):
        nonlocal ok
        ok &= bool(passed)
        log.append(f"[{label}] {'ПОДТВЕРЖДЕНО' if passed else 'ОТКАЗ'}: {detail}")

    try:                                                                    # 1
        emu = _mod(os.path.join(a.emulator_dir, "DZ_TERM_Emulator.py"), "dz_emu")
        with contextlib.redirect_stdout(io.StringIO()):
            lock = emu.verify(quiet=True)
        check("П1–П10", True, f"печать эмулятора от {lock['sealed_utc']}, регресс {lock['regression']['net']}")
    except SystemExit as e:
        check("П1–П10", False, str(e).removeprefix("ОТКАЗ: "))

    dmod = _mod(os.path.join(HERE, "DZ_CERT_Data.py"), "dz_cd")             # 2
    d_ok, d_err, dcert = dmod.verify(a.data_cert, quiet=True)
    check("П11", d_ok, "данные соответствуют сертификату" if d_ok else "; ".join(d_err))

    pas, p_ok = read_cert(a.instrument_cert)                               # 3
    check("ИНСТРУМЕНТ", p_ok and pas.get("status") == "CERTIFIED" and pas.get("verified_in_nt"),
          f"{pas.get('symbol')}: паспорт {'цел, сверен с NinjaTrader' if p_ok else 'изменён после выпуска'}")

    if a.template_cert:                                                     # 4
        tc, t_ok = read_cert(a.template_cert)
        tfile = os.path.join(os.path.dirname(a.template_cert), tc.get("template_file", ""))
        same = os.path.exists(tfile) and sha_file(tfile) == tc.get("template_sha256")
        check("ШАБЛОН", t_ok and tc.get("rank") != "REJECTED" and same,
              f"ранг {tc.get('rank')}, шаблон {'совпадает' if same else 'изменён или отсутствует'}")

    if a.run_manifest:                                                      # 5
        rm = json.load(open(a.run_manifest, encoding="utf-8"))
        want = dcert["source"].get("clean_arrays_sha256")
        check("СВЯЗЬ", rm.get("data_sha256") == want and want is not None,
              "прогон выполнен на сертифицированных данных" if rm.get("data_sha256") == want else "отпечаток данных прогона не совпадает с сертификатом")
    else:
        check("СВЯЗЬ", False, "паспорт прогона не указан — связь отчёта с данными не доказана")

    stamp = {"СТАТУС": "СЕРТИФИЦИРОВАНО: отчёт соответствует постулатам П1–П11" if ok
             else "НЕ СЕРТИФИЦИРОВАНО: отчёт не прошёл проверку — использовать для решений нельзя",
             "время_utc": now_utc(), "шлюз": VERSION, "протокол": log,
             "отчёт": {"файл": os.path.basename(a.report), "sha256": sha_file(a.report)}}
    body = json.load(open(a.report, encoding="utf-8")) if a.report.endswith(".json") else None
    out = a.report + ".stamped.json"
    json.dump({"СЕРТИФИКАТ_БЭКТЕСТА": stamp, **({"ОТЧЁТ": body} if body is not None else {})},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(stamp["СТАТУС"]); [print("  " + l) for l in log]; print(f"  штамп → {out}")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
