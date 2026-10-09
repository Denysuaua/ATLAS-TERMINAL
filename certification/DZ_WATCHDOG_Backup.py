#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_WATCHDOG_Backup.py — сторож-архиватор терминала «Атлас», v1.0 (2026-09-28)

  Следит за папками NinjaTrader и хранилищами Атласа. Каждое изменение файла — новая
  версия в суточном архиве: <имя>_vNNN_ЧЧ-ММ-СС<расширение>. Ничего не перезаписывается.

  базовая копия   в начале каждых суток — все файлы как v001: день восстанавливается сам
  изменение       размер или время изменились → хеш SHA-256 → новая версия, если хеш новый
  удаление        запись в deletions_audit.log; версии в архиве остаются
  журнал          vault_manifest.jsonl — одна строка JSON на событие, только дописывается
  запасной путь   если основной диск недоступен — архив в папке пользователя

ЗАПУСК
  python DZ_WATCHDOG_Backup.py                      постоянная работа
  python DZ_WATCHDOG_Backup.py --once               один проход — для проверки
  python DZ_WATCHDOG_Backup.py --config my.json     свои папки
==========================================================================================
"""
import argparse, datetime as dt, fnmatch, hashlib, json, os, shutil, sys, time

VERSION = "DZ_WATCHDOG_Backup-v1.0 (2026-09-28)"
HOME = os.path.expanduser("~")
NT = os.path.join(HOME, "Documents", "NinjaTrader 8")
DEFAULT = {
    "vault": r"D:\NinjaTrader_Vault",
    "fallback": os.path.join(HOME, "NinjaTrader_Vault_Fallback"),
    "interval_sec": 1.5,
    "watch": {
        "Strategies": os.path.join(NT, "bin", "Custom", "Strategies"),
        "Indicators": os.path.join(NT, "bin", "Custom", "Indicators"),
        "AddOns": os.path.join(NT, "bin", "Custom", "AddOns"),
        "Templates": os.path.join(NT, "templates", "Strategy"),
    },
    "ignore": ["~*", "*.tmp", "*.suo", "*.user", "*.pdb", "*.lock", ".git", "__pycache__", "*.pyc"],
}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Watchdog:
    def __init__(self, cfg):
        self.cfg = cfg
        self.state = {}        # (категория, отн. путь) → (размер, mtime, sha)
        self.day = None

    # ---------- архив ----------
    def vault_root(self):
        v = self.cfg["vault"]
        try:
            os.makedirs(v, exist_ok=True)
            probe = os.path.join(v, ".probe"); open(probe, "w").close(); os.remove(probe)
            return v
        except OSError:
            os.makedirs(self.cfg["fallback"], exist_ok=True)
            return self.cfg["fallback"]

    def day_dir(self):
        return os.path.join(self.vault_root(), dt.date.today().isoformat())

    def log(self, rec):
        rec = {"time_local": dt.datetime.now().isoformat(timespec="seconds"), **rec}
        d = self.day_dir(); os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "vault_manifest.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def ignored(self, name):
        return any(fnmatch.fnmatch(name, p) for p in self.cfg["ignore"])

    def next_version(self, target_dir, stem, ext):
        n = 0
        if os.path.isdir(target_dir):
            pre = stem + "_v"
            for f in os.listdir(target_dir):
                if f.startswith(pre) and f.endswith(ext):
                    try: n = max(n, int(f[len(pre):len(pre) + 3]))
                    except ValueError: pass
        return n + 1

    def backup(self, cat, rel, src, digest, reason):
        stem, ext = os.path.splitext(os.path.basename(rel))
        tdir = os.path.join(self.day_dir(), cat, os.path.dirname(rel))
        os.makedirs(tdir, exist_ok=True)
        v = self.next_version(tdir, stem, ext)
        dst = os.path.join(tdir, f"{stem}_v{v:03d}_{dt.datetime.now():%H-%M-%S}{ext}")
        shutil.copy2(src, dst)
        self.log({"action": reason, "category": cat, "file": rel, "version": f"v{v:03d}",
                  "backup": os.path.relpath(dst, self.vault_root()), "sha256": digest,
                  "size_bytes": os.path.getsize(src)})

    # ---------- проход ----------
    def scan(self):
        seen = set()
        new_day = dt.date.today() != self.day
        if new_day:
            self.day = dt.date.today()
        for cat, root in self.cfg["watch"].items():
            if not os.path.isdir(root):
                continue
            for dirpath, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if not self.ignored(d)]
                for f in files:
                    if self.ignored(f):
                        continue
                    p = os.path.join(dirpath, f); rel = os.path.relpath(p, root); key = (cat, rel)
                    seen.add(key)
                    try:
                        st = os.stat(p)
                    except OSError:
                        continue
                    old = self.state.get(key)
                    if old and old[0] == st.st_size and old[1] == st.st_mtime and not new_day:
                        continue                        # ничего не изменилось — хеш не нужен
                    try:
                        d = sha(p)
                    except OSError:
                        continue                        # файл занят записью — следующий проход
                    if new_day:
                        self.backup(cat, rel, p, d, "DAILY_BASELINE")
                    elif old is None:
                        self.backup(cat, rel, p, d, "FILE_ADDED")
                    elif old[2] != d:
                        self.backup(cat, rel, p, d, "FILE_CHANGED")
                    self.state[key] = (st.st_size, st.st_mtime, d)
        for key in [k for k in self.state if k not in seen]:
            cat, rel = key
            line = (f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] УДАЛЕНИЕ | {cat} | {rel} | "
                    f"последний sha256 {self.state[key][2]}\n")
            for d in (self.vault_root(), self.day_dir()):
                os.makedirs(d, exist_ok=True)
                with open(os.path.join(d, "deletions_audit.log"), "a", encoding="utf-8") as fh:
                    fh.write(line)
            self.log({"action": "FILE_DELETED", "category": cat, "file": rel, "sha256": self.state[key][2]})
            del self.state[key]


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--config"); ap.add_argument("--once", action="store_true")
    ap.add_argument("--cycles", type=int, default=0, help="число проходов, 0 — бесконечно")
    a = ap.parse_args()
    cfg = dict(DEFAULT)
    if a.config:
        user = json.load(open(a.config, encoding="utf-8"))
        cfg.update({k: v for k, v in user.items() if k != "watch"})
        cfg["watch"] = {**DEFAULT["watch"], **user.get("watch", {})}
    w = Watchdog(cfg)
    print(f"{VERSION}\nархив: {w.vault_root()}")
    for cat, root in cfg["watch"].items():
        print(f"  {'есть' if os.path.isdir(root) else 'НЕТ '} {cat:12} {root}")
    n = 0
    while True:
        try:
            w.scan()
        except Exception as ex:                          # сторож не падает из-за одного файла
            print("ошибка прохода:", ex, file=sys.stderr)
        n += 1
        if a.once or (a.cycles and n >= a.cycles):
            break
        time.sleep(cfg["interval_sec"])


if __name__ == "__main__":
    main()
