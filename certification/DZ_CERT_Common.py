# -*- coding: utf-8 -*-
"""DZ_CERT_Common.py — общие функции сертификации Атласа, v1.0 (2026-09-28)."""
import hashlib, json, os, stat, datetime as dt


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha_obj(obj):
    """Отпечаток содержимого JSON без поля content_sha256 — сертификат проверяет сам себя."""
    body = {k: v for k, v in obj.items() if k != "content_sha256"}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def now_utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_writable(path):
    if os.path.exists(path):
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


def seal_readonly(path):
    os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)


def write_cert(path, obj):
    obj["content_sha256"] = sha_obj(obj)
    make_writable(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    seal_readonly(path)
    return obj


def read_cert(path):
    obj = json.load(open(path, encoding="utf-8"))
    return obj, obj.get("content_sha256") == sha_obj(obj)
