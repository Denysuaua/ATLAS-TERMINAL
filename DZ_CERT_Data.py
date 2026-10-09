#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DZ_CERT_Data.py — сертификат исторических данных, постулат П11, v1.2 (2026-10-04)

v1.2 — очиститель выбирается параметром --sanitizer (по умолчанию DZ_DATA_Sanitizer_v2.py:
  старшие таймфреймы от начала сессии 17:00 по Чикаго, как у NinjaTrader и эталона). Имя
  файла очистителя пишется в сертификат, и verify проверяет именно его: прежние
  сертификаты без этого поля проверяются по DZ_DATA_Sanitizer.py и остаются действительны.
  --note — свободная пометка в сертификат, например «объём GC — прокси для MGC».

  certify  M1 из кэша очистителя + старшие таймфреймы ТОЙ ЖЕ функцией DZ_DATA_Sanitizer.resample
           (постулат П7) → data_certified/<СИМВОЛ>/, каждый файл с SHA-256 и «только чтение».
           В сертификат пишется отпечаток самого очистителя: изменится функция ресемплинга —
           кэш старших таймфреймов перестаёт быть действительным.
  verify   пересчёт всех отпечатков; любое расхождение — DATA_TAMPERING_DETECTED.

Свинги — описательная статистика зигзага по закрытиям с порогом в тиках; порог записан в
сертификат, потому что от него зависит результат.

  python DZ_CERT_Data.py certify --symbol MGC --clean mgc.npz --tick 0.1 --point-value 10 --tf 5 15 30 45 60 120 240
  python DZ_CERT_Data.py verify --cert data_certified/MGC/MGC_DATA_CERTIFICATE.json
"""
import argparse, importlib.util, json, os, shutil, sys
import numpy as np
import pandas as pd
from DZ_CERT_Common import sha_file, write_cert, read_cert, now_utc, seal_readonly, make_writable

VERSION = "DZ_CERT_Data-v1.2 (2026-10-04)"
HERE = os.path.dirname(os.path.abspath(__file__))


def _san(fname="DZ_DATA_Sanitizer_v2.py"):
    s = importlib.util.spec_from_file_location("dz_san", os.path.join(HERE, fname))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def ns(x):
    x = pd.DatetimeIndex(x)
    return x.as_unit("ns").asi8 if hasattr(x, "as_unit") else x.asi8


def swings(close, thr_price):
    """
    Зигзаг по закрытиям. До первого свинга отслеживаются максимум и минимум от начала:
    первый свинг начинается, когда цена ушла от одного из них на порог. Прежде
    экстремум вёлся в обе стороны сразу, и на M1 разворот не наступал никогда.
    Амплитуда записывается, когда свинг подтверждён обратным ходом на порог.
    """
    if len(close) < 2:
        return []
    hi = lo = close[0]; d = 0; piv = ext = None; amps = []
    for p in close[1:]:
        if d == 0:
            hi, lo = max(hi, p), min(lo, p)
            if hi - p >= thr_price: d, piv, ext = -1, hi, p
            elif p - lo >= thr_price: d, piv, ext = 1, lo, p
            continue
        if d == 1:
            if p > ext: ext = p
            elif ext - p >= thr_price: amps.append(ext - piv); piv, ext, d = ext, p, -1
        else:
            if p < ext: ext = p
            elif p - ext >= thr_price: amps.append(piv - ext); piv, ext, d = ext, p, 1
    return amps


def certify(a):
    san = _san(a.sanitizer)
    m1 = san.load_clean(a.clean)
    out = os.path.join(a.root, a.symbol); os.makedirs(out, exist_ok=True)
    man = os.path.splitext(a.clean)[0] + "_manifest.json"
    src = json.load(open(man, encoding="utf-8")) if os.path.exists(man) else {}
    series = {}

    def put(name, t_open, t_close, df):
        path = os.path.join(out, f"{a.symbol}_{name}.npz")
        make_writable(path)
        np.savez(path, t_open=t_open, t_close=t_close, o=df.o.to_numpy(float), h=df.h.to_numpy(float),
                 l=df.l.to_numpy(float), c=df.c.to_numpy(float), v=df.v.to_numpy(float))
        seal_readonly(path)
        amps = np.array(swings(df.c.to_numpy(float), a.swing_ticks * a.tick))
        series[name] = {"file": os.path.basename(path), "sha256": sha_file(path), "bars": int(len(df)),
                        "first_open_utc": str(pd.Timestamp(t_open[0], tz="UTC")), "last_open_utc": str(pd.Timestamp(t_open[-1], tz="UTC")),
                        "swings": {"threshold_ticks": a.swing_ticks, "count": int(len(amps)),
                                   "total_ticks": round(float(amps.sum() / a.tick), 1) if len(amps) else 0.0,
                                   "total_currency": round(float(amps.sum() / a.tick * a.tick * a.point_value), 2) if len(amps) else 0.0,
                                   "avg_ticks": round(float(amps.mean() / a.tick), 1) if len(amps) else 0.0}}
        print(f"  {name:6} баров {len(df):>9,}  свингов {len(amps):>7,}  sha {series[name]['sha256'][:12]}")

    t = ns(m1.index)
    v1 = m1["v"].to_numpy(float) if "v" in m1 else np.zeros(len(m1))
    bad_vol = int((v1 <= 0).sum())
    if bad_vol and a.strict_volume:
        sys.exit(f"ОТКАЗ: {bad_vol} минутных баров с объёмом ≤ 0 (строгий режим --strict-volume)")
    put("M1", t, t + 60_000_000_000, m1.assign(v=v1))
    conservation = {}
    for tf in a.tf:
        b = san.resample(m1.assign(v=v1), tf, a.anchor)
        # Закон сохранения объёма — НЕЗАВИСИМО от группировки ресемплинга: сумма минуток
        # по интервалу [открытие; закрытие) каждого старшего бара через бинарный поиск.
        cum = np.r_[0.0, np.cumsum(v1)]
        lo_i = np.searchsorted(t, ns(b.open_utc), "left"); hi_i = np.searchsorted(t, ns(b.close_utc), "left")
        diff = np.abs((cum[hi_i] - cum[lo_i]) - b.v.to_numpy(float))
        conservation[f"M{tf}"] = {"max_abs_diff": float(diff.max()) if len(diff) else 0.0, "total_htf": float(b.v.sum()), "total_m1": float(v1.sum())}
        if len(diff) and diff.max() > 1e-6:
            sys.exit(f"ОТКАЗ: M{tf} нарушает закон сохранения объёма: расхождение до {diff.max():g}")
        put(f"M{tf}", ns(b.open_utc), ns(b.close_utc), b)
    cert = {"certificate": "DZ-DATA-CERT-v1.1", "issued_utc": now_utc(), "status": "SEALED_READONLY",
            "issuer": VERSION, "note": a.note or "",
            "symbol": a.symbol, "tick_size": a.tick, "point_value": a.point_value,
            "source": {"clean_cache": os.path.basename(a.clean), "clean_cache_sha256": sha_file(a.clean),
                       "clean_arrays_sha256": src.get("clean_sha256"), "raw_sha256": src.get("raw_sha256"),
                       "time": "UTC, наносекунды, время открытия бара"},
            "resample": {"function": os.path.splitext(a.sanitizer)[0] + ".resample", "anchor_hours_chicago": a.anchor,
                         "sanitizer_file": a.sanitizer, "sanitizer_version": getattr(san, "VERSION", "?"),
                         "sanitizer_sha256": sha_file(os.path.join(HERE, a.sanitizer))},
            "series": series,
            "volume": {"m1_bars_volume_le_zero": bad_vol, "strict": bool(a.strict_volume), "conservation": conservation,
                       "rule": "Σ объёма старшего бара = Σ объёма минуток его интервала; проверено независимо от ресемплинга"}}
    path = os.path.join(out, f"{a.symbol}_DATA_CERTIFICATE.json")
    write_cert(path, cert)
    print(f"[сертификат] {path}")


def verify(cert_path, quiet=False):
    cert, self_ok = read_cert(cert_path)
    d = os.path.dirname(cert_path); errs = []
    if not self_ok: errs.append("сертификат изменён после выпуска")
    for name, s in cert["series"].items():
        p = os.path.join(d, s["file"])
        if not os.path.exists(p): errs.append(f"{name}: файл отсутствует")
        elif sha_file(p) != s["sha256"]: errs.append(f"{name}: отпечаток не совпадает")
    san = os.path.join(HERE, cert["resample"].get("sanitizer_file", "DZ_DATA_Sanitizer.py"))
    if not os.path.exists(san):
        errs.append("нет файла очистителя " + os.path.basename(san))
    elif sha_file(san) != cert["resample"]["sanitizer_sha256"]:
        errs.append("функция ресемплинга изменена — старшие таймфреймы нужно сертифицировать заново")
    if not quiet:
        print(("DATA_TAMPERING_DETECTED: " + "; ".join(errs)) if errs else f"[проверка] {cert['symbol']}: данные соответствуют сертификату")
    return not errs, errs, cert


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("certify")
    c.add_argument("--symbol", required=True); c.add_argument("--clean", required=True)
    c.add_argument("--tick", type=float, required=True); c.add_argument("--point-value", type=float, required=True)
    c.add_argument("--tf", type=int, nargs="*", default=[5, 15, 30, 45, 60, 120, 240])
    c.add_argument("--anchor", type=int, default=17); c.add_argument("--swing-ticks", type=float, default=20.0)
    c.add_argument("--root", default="data_certified")
    c.add_argument("--strict-volume", action="store_true", help="отказ, если есть минутки с объёмом ≤ 0; по умолчанию — подсчёт")
    c.add_argument("--sanitizer", default="DZ_DATA_Sanitizer_v2.py", help="файл очистителя рядом со скриптом")
    c.add_argument("--note", default="", help="пометка в сертификат")
    v = sub.add_parser("verify"); v.add_argument("--cert", required=True)
    a = ap.parse_args()
    if a.cmd == "certify": certify(a)
    else: sys.exit(0 if verify(a.cert)[0] else 2)


if __name__ == "__main__":
    main()
