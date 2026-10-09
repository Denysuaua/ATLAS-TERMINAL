#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_SYS_Bridge.py — страж идентичности «терминал ↔ ПК», v1.0 (2026-09-27)

ГАРАНТИЯ: на ПК оптимизируется ТОТ ЖЕ исходный код, из которого NinjaTrader собрал
торгующую сборку. Подтверждается отпечатками SHA-256, а не договорённостью.

  discover   найти папки терминала: исходники, сборку, шаблоны
  snapshot   паспорт сборки: отпечатки DZ_SW_*.cs и NinjaTrader.Custom.dll; проверка, что
             сборка НОВЕЕ всех исходников (иначе терминал торгует старым кодом)
  sync       неизменяемая копия исходников на ПК: nt_build/<отпечаток паспорта>/
  check      сравнить снимок на ПК с тем, что лежит в терминале сейчас
  export     положить шаблон настроек в папку шаблонов стратегии NinjaTrader

Скомпилированную сборку вне NinjaTrader не запустить: классы стратегий зависят от среды
выполнения терминала. Поэтому идентичность обеспечивается на уровне ИСХОДНИКОВ: ПК
компилирует ровно снимок, отпечаток которого совпадает с паспортом сборки терминала.
==========================================================================================
"""
import argparse, hashlib, json, os, shutil, stat, sys, time

DEFAULT_ROOT = os.path.join(os.path.expanduser("~"), "Documents", "NinjaTrader 8")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def paths(root):
    return {"root": root, "strategies": os.path.join(root, "bin", "Custom", "Strategies"),
            "indicators": os.path.join(root, "bin", "Custom", "Indicators"),
            "dll": os.path.join(root, "bin", "Custom", "NinjaTrader.Custom.dll"),
            "templates": os.path.join(root, "templates", "Strategy")}


def sources(P, pattern_prefixes=("DZ_SW_", "DZ_IND_")):
    out = {}
    for d in (P["strategies"], P["indicators"]):
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(".cs") and f.startswith(pattern_prefixes):
                out[os.path.relpath(os.path.join(d, f), P["root"])] = os.path.join(d, f)
    return out


def snapshot(root, out):
    P = paths(root); src = sources(P)
    if not src:
        sys.exit(f"ОТКАЗ: исходники DZ_SW_/DZ_IND_ не найдены в {P['strategies']}")
    files = {rel: {"sha256": sha(p), "mtime": os.path.getmtime(p)} for rel, p in src.items()}
    dll = {"exists": os.path.exists(P["dll"])}
    warnings = []
    if dll["exists"]:
        dll.update(sha256=sha(P["dll"]), mtime=os.path.getmtime(P["dll"]))
        newer = [r for r, v in files.items() if v["mtime"] > dll["mtime"]]
        if newer:
            warnings.append(f"исходники изменены ПОСЛЕ последней компиляции: {newer} — терминал торгует старым кодом; "
                            f"скомпилируйте в NinjaTrader и снимите паспорт заново")
    else:
        warnings.append("сборка NinjaTrader.Custom.dll не найдена")
    ident = hashlib.sha256("".join(f"{r}:{v['sha256']}\n" for r, v in sorted(files.items())).encode()).hexdigest()[:16]
    passport = {"build_id": ident, "taken_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "terminal_root": root, "files": files, "dll": dll, "warnings": warnings}
    json.dump(passport, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[паспорт] сборка {ident}: {len(files)} исходников" + ("".join(f"\n  ВНИМАНИЕ: {w}" for w in warnings) or ""))
    return passport


def sync(passport_path, dest_root):
    ps = json.load(open(passport_path, encoding="utf-8"))
    if ps["warnings"]:
        sys.exit("ОТКАЗ: у паспорта есть предупреждения — сначала скомпилируйте в терминале и снимите паспорт заново")
    dest = os.path.join(dest_root, ps["build_id"])
    for rel, meta in ps["files"].items():
        src = os.path.join(ps["terminal_root"], rel)
        if sha(src) != meta["sha256"]:
            sys.exit(f"ОТКАЗ: {rel} изменился после снятия паспорта")
        dst = os.path.join(dest, rel); os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        os.chmod(dst, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)       # снимок — только чтение
    shutil.copy2(passport_path, os.path.join(dest, "build_passport.json"))
    print(f"[снимок] {len(ps['files'])} файлов → {dest} (только чтение)")
    return dest


def check(snapshot_dir, root):
    ps = json.load(open(os.path.join(snapshot_dir, "build_passport.json"), encoding="utf-8"))
    now = {rel: sha(p) for rel, p in sources(paths(root)).items()}
    was = {rel: m["sha256"] for rel, m in ps["files"].items()}
    changed = sorted(r for r in was.keys() & now.keys() if was[r] != now[r])
    added, removed = sorted(now.keys() - was.keys()), sorted(was.keys() - now.keys())
    same_snapshot = all(sha(os.path.join(snapshot_dir, r)) == h for r, h in was.items())
    ok = not (changed or added or removed) and same_snapshot
    print(f"[сверка] сборка {ps['build_id']}: " + ("ИДЕНТИЧНА терминалу" if ok else
          f"РАСХОЖДЕНИЕ — изменены {changed}, добавлены {added}, удалены {removed}, снимок цел: {same_snapshot}"))
    return ok


def export(template, root, strategy):
    dst_dir = os.path.join(paths(root)["templates"], strategy); os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(template))
    shutil.copy2(template, dst)
    print(f"[шаблон] → {dst}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["discover", "snapshot", "sync", "check", "export"])
    ap.add_argument("--root", default=DEFAULT_ROOT); ap.add_argument("--passport", default="build_passport.json")
    ap.add_argument("--dest", default="nt_build"); ap.add_argument("--snapshot")
    ap.add_argument("--template"); ap.add_argument("--strategy", default="DZ_SW_Hub_S021")
    a = ap.parse_args()
    if a.cmd == "discover":
        for k, v in paths(a.root).items(): print(f"  {k:11} {'есть ' if os.path.exists(v) else 'НЕТ  '} {v}")
        print(f"  исходников DZ: {len(sources(paths(a.root)))}")
    elif a.cmd == "snapshot": snapshot(a.root, a.passport)
    elif a.cmd == "sync": sync(a.passport, a.dest)
    elif a.cmd == "check": sys.exit(0 if check(a.snapshot, a.root) else 1)
    else: export(a.template, a.root, a.strategy)


if __name__ == "__main__":
    main()
