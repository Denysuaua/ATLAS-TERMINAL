#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_HOUSE_Order_S021.py — порция 0: порядок в терминале «Атлас», v1.0 (2026-10-05)

НИЧЕГО НЕ УДАЛЯЕТ. Каждое действие — перенос; каждый перенос — строка в
archive/MOVE_JOURNAL.jsonl (время, откуда, куда, SHA-256, причина). Корень терминала —
папка над certification (C:\\Atlas_terminal).

  plan            составить план → archive/plans/plan_<время>.json и таблица на экране.
                  Файлы не трогает. Правила плана:
                    П1  файл корня, побайтно равный копии в certification\\  → archive\\<дата>_порядок\\корень
                        (кроме DZ_WATCHDOG_Backup.py: сторож может быть запущен из корня)
                    П2  пресеты DZ_PRESET_*.json из корня                    → certification\\presets_library
                    П3  прочие JSON корня — отчёты исследований               → certification\\results\\research\\<дата файла>
                    П4  «…Справочное_Руководство еще старее.md», равный текущему → archive
                    П5  .py, где кириллица уничтожена кодировкой («????»)     → archive
  apply --plan F  выполнить ровно план F: отпечаток каждого файла сверяется с планом
                  (файл изменился — пропуск); файл назначения не перезаписывается.
  rotate-token    новый ключ службы (64 знака); прежний — в archive\\secrets, в журнал —
                  только его отпечаток. Причина: прежний ключ был в переданном архиве.
  certify-v2      сертификат данных v2 рядом с v1 — data_certified_v2\\<СИМВОЛ>. M1 те же,
                  старшие ТФ — от 17:00 по Чикаго (очиститель v2). v1 не трогается: на нём
                  посчитаны все испытания реестра. После выпуска — сверка: массивы M1 v1 = v2,
                  доля старших баров на сетке 17:00.
  verify-all      все проверки → certification\\status\\HOUSE_REPORT_<время>.md и .json.
                  Функции проверок — из DZ_ATLAS_Service_v2.py: одна проверка, один источник.

  python DZ_HOUSE_Order_S021.py plan
  python DZ_HOUSE_Order_S021.py apply --plan ..\\archive\\plans\\plan_20261005_190000.json
==========================================================================================
"""
import argparse, glob, hashlib, json, os, re, secrets, shutil, sys, time

VERSION = "DZ_HOUSE_Order_S021-v1.0 (2026-10-05)"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import DZ_ATLAS_Service_v2 as S   # noqa: E402  — общие проверки службы

KEEP_IN_ROOT = {"DZ_WATCHDOG_Backup.py"}
OLD_MANUAL = "DZ_SW_S021_01_Справочное_Руководство еще старее.md"
CUR_MANUAL = "DZ_SW_S021_01_Справочное_Руководство.md"


def journal(T, **rec):
    os.makedirs(os.path.join(T, "archive"), exist_ok=True)
    rec = {"utc": S.utc_now(), "tool": VERSION, **rec}
    with open(os.path.join(T, "archive", "MOVE_JOURNAL.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def destroyed_encoding(path):
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return False
    return len(re.findall(r"\?{3,}", text)) >= 10 and not re.search(r"[А-Яа-яЁё]", text)


def make_plan(T):
    C = os.path.join(T, "certification")
    day = time.strftime("%Y-%m-%d")
    items, kept = [], []

    def add(src, dst, rule, why):
        items.append({"rule": rule, "src": os.path.relpath(src, T), "dst": os.path.relpath(dst, T),
                      "sha256": S.sha256_file(src), "bytes": os.path.getsize(src), "why": why})

    for f in sorted(os.listdir(T)):
        p = os.path.join(T, f)
        if not os.path.isfile(p):
            continue
        twin = os.path.join(C, f)
        if f in KEEP_IN_ROOT:
            kept.append({"file": f, "why": "сторож может быть запущен из корня планировщиком — не трогаю"})
        elif os.path.isfile(twin) and S.sha256_file(twin) == S.sha256_file(p):
            add(p, os.path.join(T, "archive", f"{day}_порядок", "корень", f), "П1", "побайтный дубль certification\\" + f)
        elif re.fullmatch(r"DZ_PRESET_.*\.json", f):
            add(p, os.path.join(C, "presets_library", f), "П2", "пресет коммутатора — в библиотеку пресетов")
        elif f.lower().endswith(".json"):
            d = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(p)))
            add(p, os.path.join(C, "results", "research", d, f), "П3", "отчёт исследования — в папку результатов")
        elif os.path.isfile(twin):
            kept.append({"file": f, "why": "есть копия в certification, но содержимое ДРУГОЕ — разберите вручную"})
        else:
            kept.append({"file": f, "why": "не классифицирован — оставлен"})
    vault = os.path.join(C, "strategies_vault", "DZ_S021")
    old, cur = os.path.join(vault, OLD_MANUAL), os.path.join(vault, CUR_MANUAL)
    if os.path.isfile(old) and os.path.isfile(cur) and S.sha256_file(old) == S.sha256_file(cur):
        add(old, os.path.join(T, "archive", f"{day}_порядок", "strategies_vault", OLD_MANUAL), "П4", "побайтный дубль текущего руководства")
    for p in sorted(glob.glob(os.path.join(C, "*.py"))):
        if destroyed_encoding(p):
            add(p, os.path.join(T, "archive", f"{day}_порядок", "испорченная_кодировка", os.path.basename(p)), "П5",
                "кириллица заменена на «?» безвозвратно; работу ведёт DZ_LAB_Automated_Orchestrator_v2.py")
    return {"plan": "DZ-HOUSE-PLAN-v1", "tool": VERSION, "created_utc": S.utc_now(), "root": T, "items": items, "kept": kept}


def cmd_plan(T):
    plan = make_plan(T)
    d = os.path.join(T, "archive", "plans")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"plan_{time.strftime('%Y%m%d_%H%M%S')}.json")
    S.write_json_atomic(path, plan, indent=2)
    for it in plan["items"]:
        print(f"  {it['rule']}  {it['src']}\n        → {it['dst']}   ({it['why']})")
    for k in plan["kept"]:
        print(f"  оставлен  {k['file']}: {k['why']}")
    print(f"\nПереносов: {len(plan['items'])}. План: {path}\nВыполнить: python {os.path.basename(__file__)} apply --plan \"{path}\"")


def cmd_apply(T, plan_path):
    plan = S.read_json(plan_path)
    if not plan or plan.get("plan") != "DZ-HOUSE-PLAN-v1":
        sys.exit("ОТКАЗ: это не план DZ_HOUSE")
    if os.path.abspath(plan["root"]) != os.path.abspath(T):
        sys.exit(f"ОТКАЗ: план составлен для {plan['root']}, а корень сейчас {T}")
    done = skipped = 0
    for it in plan["items"]:
        src, dst = os.path.join(T, it["src"]), os.path.join(T, it["dst"])
        if not os.path.isfile(src):
            print(f"  пропуск: {it['src']} — файла уже нет")
            skipped += 1
            continue
        if S.sha256_file(src) != it["sha256"]:
            print(f"  пропуск: {it['src']} — файл изменился после плана")
            skipped += 1
            continue
        if it["rule"] == "П1":
            twin = os.path.join(T, "certification", os.path.basename(src))
            if not os.path.isfile(twin) or S.sha256_file(twin) != it["sha256"]:
                print(f"  пропуск: {it['src']} — копия в certification изменилась, дубля больше нет")
                skipped += 1
                continue
        base, ext = os.path.splitext(dst)
        n = 2
        while os.path.exists(dst):
            dst = f"{base}_v{n:03d}{ext}"
            n += 1
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            shutil.move(src, dst)
        except OSError as ex:
            print(f"  пропуск: {it['src']} — {ex} (файл открыт?)")
            skipped += 1
            continue
        if S.sha256_file(dst) != it["sha256"]:
            sys.exit(f"АВАРИЯ: после переноса отпечаток {dst} другой — остановка, разберите вручную")
        journal(T, action="move", rule=it["rule"], src=it["src"], dst=os.path.relpath(dst, T), sha256=it["sha256"], why=it["why"])
        print(f"  ✓ {it['src']} → {os.path.relpath(dst, T)}")
        done += 1
    print(f"\nПеренесено {done}, пропущено {skipped}. Журнал: {os.path.join(T, 'archive', 'MOVE_JOURNAL.jsonl')}")


def cmd_rotate(T):
    C = os.path.join(T, "certification")
    tf = os.path.join(C, "atlas_service_token.txt")
    old = None
    if os.path.exists(tf):
        old = hashlib.sha256(open(tf, "rb").read().strip()).hexdigest()[:12]
        d = os.path.join(T, "archive", "secrets")
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, f"{time.strftime('%Y%m%d_%H%M%S')}_atlas_service_token.txt")
        shutil.move(tf, dst)
    tok = secrets.token_hex(32)
    with open(tf + ".tmp", "w", encoding="utf-8") as f:
        f.write(tok)
    os.replace(tf + ".tmp", tf)
    new = hashlib.sha256(tok.encode()).hexdigest()[:12]
    journal(T, action="rotate_token", file=os.path.relpath(tf, T), old_sha12=old, new_sha12=new)
    print(f"Новый ключ службы записан в {tf} (отпечаток {new}). Прежний ({old}) — в archive\\secrets.\n"
          f"Перезапустите службу; в пульт v1 вставьте ключ из файла заново.")


def arrays_sha(npz):
    import numpy as np
    z = np.load(npz, allow_pickle=False)
    t = z["t"] if "t" in z.files else z["t_open"]
    v = z["v"] if "v" in z.files else np.zeros(len(t))
    arr = np.stack([t.astype(np.float64), z["o"], z["h"], z["l"], z["c"], v], 1)
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def cmd_certify_v2(T, symbol, python):
    C = os.path.join(T, "certification")
    src = os.path.join(C, "data_certified", symbol, f"{symbol}_M1.npz")
    out_cert = os.path.join(C, "data_certified_v2", symbol, f"{symbol}_DATA_CERTIFICATE.json")
    if not os.path.exists(src):
        sys.exit(f"ОТКАЗ: нет {src}")
    if os.path.exists(out_cert):
        sys.exit(f"ОТКАЗ: {out_cert} уже есть — повторная сертификация перезаписала бы файлы")
    inst = S.read_json(os.path.join(C, "certified_vault", symbol, f"{symbol}.instrument.cert.json"), {}) or {}
    mm = inst.get("market_mathematics") or {}
    if not mm.get("tick_size") or not mm.get("point_value"):
        sys.exit("ОТКАЗ: нет паспорта инструмента с tick_size и point_value — единицы не выдумываются")
    rc, out = S.run_script(C, python, ["DZ_CERT_Data.py", "certify", "--symbol", symbol, "--clean", os.path.relpath(src, C),
                                       "--tick", str(mm["tick_size"]), "--point-value", str(mm["point_value"]),
                                       "--root", "data_certified_v2",
                                       "--note", f"v2: старшие ТФ от 17:00 Чикаго (очиститель v2); M1 те же, что в data_certified/{symbol} (v1)"],
                           timeout=7200)
    print(out)
    if rc != 0:
        sys.exit(f"ОТКАЗ: сертификация не выполнена (код {rc})")
    rc2, out2 = S.run_script(C, python, ["DZ_CERT_Data.py", "verify", "--cert", os.path.relpath(out_cert, C)])
    v2dir = os.path.dirname(out_cert)
    same_m1 = arrays_sha(src) == arrays_sha(os.path.join(v2dir, f"{symbol}_M1.npz"))
    anchor = {}
    for tf in (45, 120, 240):
        a, b = os.path.join(C, "data_certified", symbol, f"{symbol}_M{tf}.npz"), os.path.join(v2dir, f"{symbol}_M{tf}.npz")
        anchor[f"M{tf}"] = {"v1": S.htf_anchor_check(a, tf)["on_grid"] if os.path.exists(a) else None,
                            "v2": S.htf_anchor_check(b, tf)["on_grid"] if os.path.exists(b) else None}
    rep = {"tool": VERSION, "utc": S.utc_now(), "symbol": symbol, "verify_v2_ok": rc2 == 0, "verify_text": out2[-500:],
           "m1_arrays_identical_v1_v2": same_m1, "htf_on_grid_17h_chicago": anchor}
    S.write_json_atomic(os.path.join(v2dir, "V2_CHECK.json"), rep, indent=2)
    journal(T, action="certify_v2", symbol=symbol, cert=os.path.relpath(out_cert, T), verify_ok=rc2 == 0, m1_identical=same_m1)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    if not (rc2 == 0 and same_m1 and all((x["v2"] or 0) > 0.999 for x in anchor.values())):
        sys.exit("ВНИМАНИЕ: сверка v2 не пройдена — смотрите V2_CHECK.json")


def cmd_verify_all(T, python):
    C = os.path.join(T, "certification")
    cfg = S.load_config(os.path.join(C, "DZ_ATLAS_Service_v2.config.json"))
    nt = os.path.expanduser(cfg["nt_root"])
    res = {}
    for rn in cfg["data_roots"]:
        for cert in sorted(glob.glob(os.path.join(C, rn, "*", "*_DATA_CERTIFICATE.json"))):
            sym = os.path.basename(os.path.dirname(cert))
            rc, out = S.run_script(C, python, ["DZ_CERT_Data.py", "verify", "--cert", os.path.relpath(cert, C)])
            res[f"data:{rn}:{sym}"] = {"ok": rc == 0, "text": out[-500:], "utc": S.utc_now()}
            m240 = os.path.join(os.path.dirname(cert), f"{sym}_M240.npz")
            if os.path.exists(m240):
                res[f"data:{rn}:{sym}"]["M240_on_grid_17h"] = S.htf_anchor_check(m240, 240)["on_grid"]
    rc, out = S.run_script(C, python, ["DZ_CERT_Strategy.py", "verify", "--dir", cfg["strategy_dir"]])
    res["strategy"] = {"ok": rc == 0, "text": out[-500:], "utc": S.utc_now()}
    lock = os.path.join(C, "DZ_TERM_Lock.json")
    if os.path.exists(lock):
        rc, out = S.run_script(C, python, ["DZ_TERM_Emulator.py", "verify"])
        res["emulator"] = {"ok": rc == 0, "text": out[-500:], "utc": S.utc_now()}
    else:
        res["emulator"] = {"ok": False, "text": "нет печати DZ_TERM_Lock.json", "utc": S.utc_now()}
    res["passport"] = dict(S.passport_vs_nt(C, nt), utc=S.utc_now())
    S.write_json_atomic(os.path.join(C, "results", "_service_verify.json"), res)   # служба v2 подхватит при запуске
    gates = S.compute_gates(C, cfg, res, {})
    vp = S.vault_vs_passport(C, cfg["strategy_dir"])
    el = S.strategy_elements(C, cfg["strategy_dir"])
    st = S.stamps(C)
    os.makedirs(os.path.join(C, "status"), exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    rep = {"tool": VERSION, "utc": S.utc_now(), "verify": res, "gates": gates, "vault_vs_passport": vp, "elements": el, "stamps": st}
    S.write_json_atomic(os.path.join(C, "status", f"HOUSE_REPORT_{stamp}.json"), rep, indent=2)
    mark = {"pass": "✅ пройдены", "fail": "❌ нет", "manual": "✋ отметка", "unknown": "❔ не проверить отсюда"}
    lines = [f"# Сводная проверка терминала — {S.utc_now()}", "", f"{VERSION}", "", "## Проверки", "",
             "| Проверка | Итог | Подробно |", "|---|---|---|"]
    for k, v in res.items():
        lines.append(f"| {k} | {'✅' if v.get('ok') else ('❔' if v.get('ok') is None else '❌')} | {str(v.get('text', ''))[-160:].replace('|', '/').replace(chr(10), ' ')} |")
    lines += ["", "## Ворота выпуска", "", "| № | Ворота | Итог | Основание |", "|---|---|---|---|"]
    for g in gates:
        lines.append(f"| {g['n']} | {g['name']} | {mark[g['status']]} | {g['evidence'].replace('|', '/')} |")
    lines += ["", "## Хранилище стратегии против паспорта сборки", "",
              f"Совпадают: {len(vp['same'])}; нет в хранилище: {len(vp['missing'])} — {', '.join(vp['missing']) or '—'}; "
              f"отличаются: {', '.join(vp['different']) or '—'}.", "",
              "Заглушки среди элементов: " + (", ".join(f"{e['element']} ({e['bytes']} байт)" for e in el if e["placeholder"]) or "нет") + "."]
    with open(os.path.join(C, "status", f"HOUSE_REPORT_{stamp}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("cmd", choices=["plan", "apply", "rotate-token", "certify-v2", "verify-all"])
    ap.add_argument("--root", default=os.path.dirname(HERE), help="корень терминала (папка над certification)")
    ap.add_argument("--plan")
    ap.add_argument("--symbol", default="MGC")
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args()
    T = os.path.abspath(a.root)
    if not os.path.isdir(os.path.join(T, "certification")):
        sys.exit(f"ОТКАЗ: в {T} нет папки certification — укажите --root")
    if a.cmd == "plan":
        cmd_plan(T)
    elif a.cmd == "apply":
        if not a.plan:
            sys.exit("нужен --plan: сначала plan, просмотр, потом apply ровно этого плана")
        cmd_apply(T, a.plan)
    elif a.cmd == "rotate-token":
        cmd_rotate(T)
    elif a.cmd == "certify-v2":
        cmd_certify_v2(T, a.symbol, a.python)
    else:
        cmd_verify_all(T, a.python)


if __name__ == "__main__":
    main()
