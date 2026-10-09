#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_DISPATCHER_DropZone.py — горячая папка терминала «Атлас», v1.0 (2026-09-28)

  init   создать хранилище:  DROP_ZONE_INBOX, DROP_ZONE_QUARANTINE, library_certified,
         data_certified, certified_vault, strategies_vault, status
  run    каждые 1,5 с разбирать DROP_ZONE_INBOX по правилам имён

ПРАВИЛА (первое совпавшее)
  LIB_* | *CANON* | *OPUS*                     → library_certified/
  <СИМВОЛ>.instrument.cert.json                → certified_vault/<СИМВОЛ>/
  <СТРАТЕГИЯ>__<СИМВОЛ>__*.xml | *.cert.json    → certified_vault/<СИМВОЛ>/<СТРАТЕГИЯ>/templates/
  DZ_*_S<NNN>*.dll | *.zip                     → strategies_vault/DZ_S<NNN>/releases/
  DZ_*_S<NNN>*.cs | .md | .json                → strategies_vault/DZ_S<NNN>/
  всё остальное                                → DROP_ZONE_QUARANTINE/ с причиной в журнале

ГАРАНТИИ
  • Файл берётся, только когда его размер не менялся два прохода подряд: недописанный не трогается.
  • Существующий файл НЕ перезаписывается: пришедший получает номер версии _vNNN.
  • Копия сверяется по SHA-256, получает «только чтение», и лишь затем исчезает из INBOX.
  • В папки NinjaTrader диспетчер НЕ пишет никогда: bin\\Custom — только руками руководителя.
==========================================================================================
"""
import argparse, datetime as dt, json, os, re, shutil, stat, sys, time

VERSION = "DZ_DISPATCHER_DropZone-v1.0 (2026-09-28)"
DIRS = ["DROP_ZONE_INBOX", "DROP_ZONE_QUARANTINE", "library_certified", "data_certified",
        "certified_vault", "strategies_vault", "status"]
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from DZ_CERT_Common import sha_file, seal_readonly  # noqa: E402


def symbols():
    p = os.path.join(HERE, "DZ_NTSIM_Instruments.json")
    return {k for k in json.load(open(p, encoding="utf-8")) if not k.startswith("_")} if os.path.exists(p) else set()


def route(name, syms):
    """Возвращает (относительная папка назначения, правило) либо (None, причина)."""
    up = name.upper()
    if up.startswith("LIB_") or "CANON" in up or "OPUS" in up:
        return "library_certified", "библиотека"
    m = re.match(r"^([A-Z0-9]+)\.instrument\.cert\.json$", name)
    if m and m.group(1) in syms:
        return os.path.join("certified_vault", m.group(1)), "паспорт инструмента"
    m = re.match(r"^(.+?)__([A-Z0-9]+)__.+\.(xml|cert\.json)$", name)
    if m and m.group(2) in syms:
        return os.path.join("certified_vault", m.group(2), m.group(1), "templates"), "шаблон"
    m = re.match(r"^DZ_.*?_(S\d{3}).*\.(dll|zip)$", name, re.I)
    if m:
        return os.path.join("strategies_vault", "DZ_" + m.group(1).upper(), "releases"), "релиз для импорта"
    m = re.match(r"^DZ_.*?_(S\d{3}).*\.(cs|md|json)$", name, re.I)
    if m:
        return os.path.join("strategies_vault", "DZ_" + m.group(1).upper()), "элемент стратегии"
    return None, "имя не соответствует ни одному правилу"


def free_name(folder, name):
    if not os.path.exists(os.path.join(folder, name)):
        return name
    stem, ext = os.path.splitext(name)
    if name.endswith(".cert.json"):
        stem, ext = name[:-10], ".cert.json"
    n = 2
    while os.path.exists(os.path.join(folder, f"{stem}_v{n:03d}{ext}")):
        n += 1
    return f"{stem}_v{n:03d}{ext}"


def log(root, text):
    with open(os.path.join(root, "DROP_ZONE_DISPATCH.log"), "a", encoding="utf-8") as f:
        f.write(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {text}\n")


def dispatch(root, sizes, syms):
    inbox = os.path.join(root, "DROP_ZONE_INBOX")
    for name in sorted(os.listdir(inbox)):
        src = os.path.join(inbox, name)
        if not os.path.isfile(src) or name.startswith("~"):
            continue
        size = os.path.getsize(src)
        if sizes.get(name) != size:                 # размер ещё меняется либо файл новый
            sizes[name] = size; continue
        rel, rule = route(name, syms)
        dest_dir = os.path.join(root, rel if rel else "DROP_ZONE_QUARANTINE")
        os.makedirs(dest_dir, exist_ok=True)
        dn = free_name(dest_dir, name); dst = os.path.join(dest_dir, dn)
        h = sha_file(src)
        shutil.copy2(src, dst)
        if sha_file(dst) != h:
            os.remove(dst); log(root, f"ОШИБКА КОПИИ: {name} — отпечаток копии не совпал, файл оставлен в INBOX"); continue
        seal_readonly(dst); os.chmod(src, stat.S_IWRITE | stat.S_IREAD); os.remove(src); sizes.pop(name, None)
        if rel:
            log(root, f"ПРИНЯТО: {name} → {os.path.relpath(dst, root)} | {rule} | sha256 {h}")
        else:
            log(root, f"КАРАНТИН: {name} → {os.path.relpath(dst, root)} | {rule} | sha256 {h}")


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("cmd", choices=["init", "run"]); ap.add_argument("--root", default=".")
    ap.add_argument("--interval", type=float, default=1.5); ap.add_argument("--cycles", type=int, default=0)
    a = ap.parse_args()
    for d in DIRS:
        os.makedirs(os.path.join(a.root, d), exist_ok=True)
    if a.cmd == "init":
        print(f"[хранилище] создано в {os.path.abspath(a.root)}: {', '.join(DIRS)}"); return
    syms, sizes, n = symbols(), {}, 0
    print(f"{VERSION}: наблюдение за {os.path.join(os.path.abspath(a.root), 'DROP_ZONE_INBOX')}")
    while True:
        try:
            dispatch(a.root, sizes, syms)
        except Exception as ex:
            log(a.root, f"ОШИБКА ПРОХОДА: {ex}")
        n += 1
        if a.cycles and n >= a.cycles:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
