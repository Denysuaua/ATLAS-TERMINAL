#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_DATA_Sanitizer.py — очистка минутных данных и канонический ресемплинг, v1.0 (2026-09-26)

  clean     сырой CSV → проверенный кэш M1 в UTC (.npz, либо .parquet при наличии pyarrow)
  diff      сравнение двух манифестов: какие дни изменились между выгрузками
  resample  старший таймфрейм из кэша M1 в CSV — для сверки с графиком NinjaTrader

ПРИНЦИПЫ
  Единственный источник разбора. Формат даты и разметка бара определяются функциями
  эталона DZ_BT_DualBreakout_S021.py: второй разборщик разошёлся бы с первым.
  Выбросы не удаляются, а помечаются: удаление по порогу срезает именно те прострелы,
  что выбили бы стоп, и незаметно улучшает результат.
  Время хранится целыми НАНОСЕКУНДАМИ UTC, единица записана в метаданных (урок Д-23).
  Схема кэша совпадает с кэшем DZ_OPT_Engine_S021: один формат, а не два.
==========================================================================================
"""
import argparse, hashlib, importlib.util, json, os, sys
import numpy as np
import pandas as pd

VERSION = "DZ_DATA_Sanitizer-v1.0 (2026-09-26)"
TZ_EX = "America/Chicago"
NS_MIN = 60_000_000_000


def load_ref(path):
    spec = importlib.util.spec_from_file_location("dz_reference", path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def to_ns(idx):
    idx = pd.DatetimeIndex(idx)
    return idx.as_unit("ns").asi8 if hasattr(idx, "as_unit") else idx.asi8


# ======================================================================================
# ОЧИСТКА
# ======================================================================================

def clean(raw, out, ref_path, spike_k, min_coverage, src_tz=TZ_EX):
    ref = load_ref(ref_path)
    rep = {"script": VERSION, "raw_file": os.path.basename(raw), "raw_sha256": sha256_file(raw)}

    stamp, df = ref.read_raw(raw)
    fmt, fmt_rep = ref.detect_date_format(stamp, "auto")
    ts = pd.to_datetime(stamp, format=fmt, errors="coerce")
    num = lambda c: pd.to_numeric(df[c], errors="coerce") if c in df.columns else pd.Series(np.nan, index=df.index)
    d = pd.DataFrame({"ts": ts, "o": num("Open"), "h": num("High"), "l": num("Low"),
                      "c": num("Close"), "v": num("Volume")})
    rep["rows_read"] = int(len(d))
    rep["volume_present"] = bool(d.v.notna().any())
    d["v"] = d.v.fillna(0.0)

    bad = d[["ts", "o", "h", "l", "c"]].isna().any(axis=1)
    rep["dropped_unparsed"] = int(bad.sum()); d = d[~bad]

    # 1. Геометрия бара — каждый инвариант считается отдельно.
    inv = {"high_lt_low": d.h < d.l, "high_lt_open": d.h < d.o, "high_lt_close": d.h < d.c,
           "low_gt_open": d.l > d.o, "low_gt_close": d.l > d.c, "price_le_zero": d.l <= 0, "volume_lt_zero": d.v < 0}
    rep["ohlc_violations"] = {k: int(v.sum()) for k, v in inv.items()}
    anyinv = np.logical_or.reduce([v.values for v in inv.values()])
    rep["dropped_bad_ohlc"] = int(anyinv.sum()); d = d[~anyinv]

    # 2. Пояс источника — по умолчанию Чикаго; выгрузка DZ_IND_BarExporter пишет UTC.
    loc = pd.DatetimeIndex(d.ts).tz_localize(src_tz, ambiguous="NaT", nonexistent="NaT")
    rep["dropped_dst_nat"] = int(loc.isna().sum())
    d = d[~loc.isna()]; loc = loc[~loc.isna()]

    label, lab_ev = ref.detect_bar_label(loc.tz_convert(TZ_EX).tz_localize(None), "auto")
    utc = loc.tz_convert("UTC")
    if label == "close":
        utc = utc - pd.Timedelta(minutes=1)
    d = d.set_index(pd.DatetimeIndex(utc, name="t")).drop(columns="ts")
    if hasattr(d.index, "as_unit"):
        d.index = d.index.as_unit("ns")
    d = d.sort_index()

    # 3. Дубликаты: одинаковые и конфликтующие — разные величины.
    dup = d.index.duplicated(keep=False)
    grp = d[dup].groupby(level=0).nunique()
    rep["duplicates_identical"] = int((grp[["o", "h", "l", "c"]].max(axis=1) <= 1).sum()) if len(grp) else 0
    rep["duplicates_conflicting"] = int((grp[["o", "h", "l", "c"]].max(axis=1) > 1).sum()) if len(grp) else 0
    d = d[~d.index.duplicated(keep="first")]

    # 4. Выходные — однозначно вне Globex: суббота и воскресенье до 17:00 по Чикаго.
    ct = d.index.tz_convert(TZ_EX)
    wk = (ct.dayofweek == 5) | ((ct.dayofweek == 6) & (ct.hour < 17))
    rep["dropped_weekend"] = int(wk.sum()); d = d[~wk]; ct = ct[~wk]

    # Ежедневный перерыв НЕ удаляется правилом: его границы менялись по годам, и
    # удаление по сегодняшнему расписанию выбросило бы настоящие бары прошлых лет.
    hm = ct.hour * 100 + ct.minute
    rep["bars_in_halt_1600_1700_ct_by_year"] = {int(k): int(v) for k, v in
        pd.Series(((hm >= 1600) & (hm < 1700)), index=ct.year).groupby(level=0).sum().items() if v}

    # 5. Выбросы: истинный диапазон больше k медиан за 60 баров при объёме не выше медианы.
    pc = d.c.shift(1)
    tr = pd.concat([d.h - d.l, (d.h - pc).abs(), (d.l - pc).abs()], axis=1).max(axis=1)
    med = tr.rolling(60, min_periods=20).median()
    vmed = d.v.rolling(60, min_periods=20).median()
    spike = (tr > spike_k * med) & (med > 0) & ((d.v <= vmed) | (~rep["volume_present"]))
    sp = d[spike].assign(TR=tr[spike], TRMedian60=med[spike])
    rep["spikes_flagged_not_removed"] = int(spike.sum())

    # ЭКСПЕРИМЕНТ 2. Покрытие сессии: доля минут Globex, присутствующих в торговом дне.
    tday = (ct - pd.Timedelta(hours=17)).normalize() + pd.Timedelta(days=1)
    cov = pd.Series(1, index=tday).groupby(level=0).sum()
    cov = pd.DataFrame({"TradingDay": cov.index.date, "Minutes": cov.values, "Coverage": (cov.values / 1380.0).round(4)})
    low = cov[cov.Coverage < min_coverage]
    rep["days_total"] = int(len(cov)); rep["days_low_coverage"] = int(len(low))

    rep.update({"date_format": fmt, "date_format_report": fmt_rep, "bar_label": label, "bar_label_evidence": lab_ev,
                "rows_clean": int(len(d)), "first_bar_utc": str(d.index[0]), "last_bar_utc": str(d.index[-1]),
                "time_unit": "ns", "time_zone": "UTC", "time_label": "bar_open"})

    # ЭКСПЕРИМЕНТ 1. Отпечаток по дням: какие дни изменятся при следующей выгрузке.
    t = to_ns(d.index)
    arr = np.stack([t.astype(np.float64), d.o.values, d.h.values, d.l.values, d.c.values, d.v.values], 1)
    rep["clean_sha256"] = hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()
    dd = pd.Series(range(len(d)), index=d.index.tz_convert(TZ_EX).date)
    day_hash = {}
    for day, pos in dd.groupby(level=0):
        day_hash[str(day)] = hashlib.sha256(np.ascontiguousarray(arr[pos.values]).tobytes()).hexdigest()[:16]

    base = os.path.splitext(out)[0]
    if out.endswith(".parquet"):
        try:
            import pyarrow as pa, pyarrow.parquet as pq
            tbl = pa.table({"t": pa.array(t, pa.timestamp("ns", tz="UTC")), "o": d.o.values, "h": d.h.values,
                            "l": d.l.values, "c": d.c.values, "v": d.v.values})
            tbl = tbl.replace_schema_metadata({"dz_meta": json.dumps(rep, ensure_ascii=False, default=str)})
            pq.write_table(tbl, out)
        except ImportError:
            out = base + ".npz"
            print("pyarrow не установлен — запись в .npz", file=sys.stderr)
    if out.endswith(".npz"):
        np.savez(out, t=t, o=d.o.values, h=d.h.values, l=d.l.values, c=d.c.values, v=d.v.values,
                 validation=np.array(json.dumps(rep, ensure_ascii=False, default=str)))

    with open(base + "_manifest.json", "w", encoding="utf-8") as f:
        json.dump({**rep, "day_hash": day_hash}, f, ensure_ascii=False, indent=2, default=str)
    cov.to_csv(base + "_coverage.csv", index=False)
    sp.reset_index().to_csv(base + "_spikes.csv", index=False)
    print(f"[очистка] {rep['rows_read']:,} → {rep['rows_clean']:,} баров | формат {fmt}, разметка {label} | "
          f"OHLC {rep['dropped_bad_ohlc']}, выходные {rep['dropped_weekend']}, дубли {rep['duplicates_identical']}+"
          f"{rep['duplicates_conflicting']} конфл. | выбросов помечено {rep['spikes_flagged_not_removed']} | "
          f"дней с покрытием ниже {min_coverage:.0%}: {rep['days_low_coverage']} из {rep['days_total']}")
    return out, rep


def load_clean(path):
    """Кэш в DataFrame с индексом UTC в наносекундах; столбцы o, h, l, c, v."""
    if path.endswith(".parquet"):
        import pyarrow.parquet as pq
        tb = pq.read_table(path).to_pandas()
        idx = pd.DatetimeIndex(tb.pop("t"))
        return tb.set_index(idx.tz_convert("UTC") if idx.tz else idx.tz_localize("UTC"))
    z = np.load(path, allow_pickle=False)
    idx = pd.to_datetime(z["t"], utc=True)
    v = z["v"] if "v" in z.files else np.zeros(len(idx))
    return pd.DataFrame({"o": z["o"], "h": z["h"], "l": z["l"], "c": z["c"], "v": v}, index=idx)


# ======================================================================================
# КАНОНИЧЕСКИЙ РЕСЕМПЛИНГ — то же правило границ, что у эталона
# ======================================================================================

def resample(m1, minutes, anchor_hours=17):
    """
    Бар старшего таймфрейма по биржевому времени Чикаго с якорем начала сессии 17:00.
    Возвращает бары с open_utc и close_utc. close_utc — ПЛАНОВОЕ закрытие: значение бара
    пригодно для решения только с этого момента, и не раньше.
    """
    ct = m1.index.tz_convert(TZ_EX).tz_localize(None)
    sh = pd.Timedelta(hours=anchor_hours)
    start = (ct - sh).floor(f"{minutes}min") + sh
    g = m1.groupby(start)
    b = pd.DataFrame({"o": g.o.first(), "h": g.h.max(), "l": g.l.min(), "c": g.c.last(), "v": g.v.sum()})
    op = pd.DatetimeIndex(b.index).tz_localize(TZ_EX, ambiguous="NaT", nonexistent="NaT")
    b["open_utc"] = op.tz_convert("UTC")
    b["close_utc"] = (pd.DatetimeIndex(b.index) + pd.Timedelta(minutes=minutes)).tz_localize(
        TZ_EX, ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
    return b.dropna(subset=["open_utc", "close_utc"]).reset_index(drop=True)


def diff_manifests(a, b):
    A = json.load(open(a, encoding="utf-8"))["day_hash"]; B = json.load(open(b, encoding="utf-8"))["day_hash"]
    changed = sorted(k for k in A.keys() & B.keys() if A[k] != B[k])
    print(f"[сравнение] дней: {len(A)} и {len(B)} | только в первом {len(A.keys() - B.keys())}, "
          f"только во втором {len(B.keys() - A.keys())}, изменились {len(changed)}")
    for k in changed[:50]:
        print("  изменён", k)
    return changed


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("clean")
    s.add_argument("--raw-csv", required=True); s.add_argument("--out", default="gc-1m.npz")
    s.add_argument("--ref", default="DZ_BT_DualBreakout_S021.py")
    s.add_argument("--spike-k", type=float, default=15.0); s.add_argument("--min-coverage", type=float, default=0.9)
    s.add_argument("--src-tz", default=TZ_EX, help="пояс меток сырого файла; для выгрузки DZ_IND_BarExporter — UTC")
    s = sub.add_parser("diff"); s.add_argument("a"); s.add_argument("b")
    s = sub.add_parser("resample")
    s.add_argument("--data", required=True); s.add_argument("--tf", type=int, required=True)
    s.add_argument("--anchor", type=int, default=17); s.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "clean":
        clean(a.raw_csv, a.out, a.ref, a.spike_k, a.min_coverage, a.src_tz)
    elif a.cmd == "diff":
        diff_manifests(a.a, a.b)
    else:
        resample(load_clean(a.data), a.tf, a.anchor).to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
