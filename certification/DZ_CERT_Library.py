#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DZ_CERT_Library.py — сертификатор библиотеки документов, v1.0 (2026-09-28)

  certify  ЗОЛОТО — автор OPUS_MAX (первоисточник); ЗЕЛЕНЬ — перекрёстная проверка: рецензент
           обязан отличаться от автора; иначе ОТКЛОНЁН. Документ получает «только чтение».
           Автор и рецензент ЗАПИСЫВАЮТСЯ, но не доказываются: кто писал текст, по файлу не узнать.
  verify   все сертификаты папки: документ на месте, отпечаток совпадает, сертификат цел.
           ЭКСПЕРИМЕНТ: висячие ссылки — упомянутые в тексте файлы DZ_*, которых нет в хранилище.

  python DZ_CERT_Library.py certify --doc library_certified/X.md --author LEADER --reviewer OPUS_MAX
  python DZ_CERT_Library.py verify --dir library_certified --root .
"""
import argparse, glob, os, re, sys
from DZ_CERT_Common import sha_file, write_cert, read_cert, now_utc, seal_readonly

VERSION = "DZ_CERT_Library-v1.0 (2026-09-28)"
PRIMARY = "OPUS_MAX"


def certify(doc, author, reviewer):
    author, reviewer = author.upper(), (reviewer or "").upper()
    if author == PRIMARY: rank, why = "GOLD", "первоисточник"
    elif reviewer and reviewer != author: rank, why = "GREEN", f"перекрёстная проверка: {reviewer}"
    else: rank, why = "REJECTED", "нет перекрёстной проверки: рецензент не указан или совпадает с автором"
    cert = {"certificate": "DZ-LIBRARY-CERT-v1.0", "issued_utc": now_utc(), "document": os.path.basename(doc),
            "sha256": sha_file(doc), "author_declared": author, "reviewer_declared": reviewer or None,
            "rank": rank, "basis": why, "note": "автор и рецензент заявлены, а не доказаны"}
    write_cert(doc + ".doc.cert.json", cert)
    if rank != "REJECTED": seal_readonly(doc)
    print(f"[библиотека] {cert['document']}: {rank} — {why}")
    return rank != "REJECTED"


def verify(folder, root):
    names = {f for _, _, fs in os.walk(root) for f in fs}; bad = 0
    for c in sorted(glob.glob(os.path.join(folder, "*.doc.cert.json"))):
        cert, ok = read_cert(c); doc = c[: -len(".doc.cert.json")]
        state = ("ИЗМЕНЁН" if not ok else "НЕТ ДОКУМЕНТА" if not os.path.exists(doc)
                 else "ИЗМЕНЁН" if sha_file(doc) != cert["sha256"] else cert["rank"])
        refs = sorted(set(re.findall(r"\bDZ_[\w\-]+\.(?:py|cs|json|md|xlsx)\b", open(doc, encoding="utf-8", errors="replace").read()))) if os.path.exists(doc) else []
        dangling = [r for r in refs if r not in names]
        bad += state in ("ИЗМЕНЁН", "НЕТ ДОКУМЕНТА")
        print(f"  {state:14} {cert['document']}" + (f"\n    висячие ссылки: {', '.join(dangling)}" if dangling else ""))
    return bad == 0


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("cmd", choices=["certify", "verify"]); ap.add_argument("--doc"); ap.add_argument("--author")
    ap.add_argument("--reviewer"); ap.add_argument("--dir", default="library_certified"); ap.add_argument("--root", default=".")
    a = ap.parse_args()
    sys.exit(0 if (certify(a.doc, a.author, a.reviewer) if a.cmd == "certify" else verify(a.dir, a.root)) else 1)


if __name__ == "__main__":
    main()
