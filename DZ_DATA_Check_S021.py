#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_DATA_Check_S021.py — проверки данных перед бэктестами, v1.0 (2026-10-04)

  compare       --old A_M1.npz --new B_M1.npz   сверка двух версий минуток на общем периоде:
                                                  доля одинаковых OHLC, расхождения по годам
  volume        --npz X_M1.npz                  объём по годам: доля нулевых минуток, медиана
  htf-selftest  --npz X_M1.npz                  старшие ТФ очистителя v2 против build_htf
                                                  эталона пробоя на 15 и 240 минутах: OHLC и
                                                  закрытия обязаны совпасть полностью
  dollar-bars   --npz X_M1.npz --usd N --point-value P --out Y.npz
                                                  ЭКСПЕРИМЕНТ Э8: долларовые бары (AFML, гл. 2)

Код возврата 0 — проверка пройдена, 1 — нет. Только чтение входных файлов.
==========================================================================================
"""
import argparse, importlib.util, os, sys
import numpy as np
import pandas as pd

VERSION = "DZ_DATA_Check_S021-v1.0 (2026-10-04)"
HERE = os.path.dirname(os.path.abspath(__file__))


def _mod(fname, name):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def compare(a):
    san = _mod("DZ_DATA_Sanitizer_v2.py", "san")
    old, new = san.load_clean(a.old), san.load_clean(a.new)
    lo, hi = max(old.index[0], new.index[0]), min(old.index[-1], new.index[-1])
    o, n = old.loc[lo:hi], new.loc[lo:hi]
    both = o.index.intersection(n.index)
    eq = (o.loc[both, ["o", "h", "l", "c"]].values == n.loc[both, ["o", "h", "l", "c"]].values).all(axis=1)
    diff = np.abs(o.loc[both, ["o", "h", "l", "c"]].values - n.loc[both, ["o", "h", "l", "c"]].values).max(axis=1)
    print(f"{VERSION} · compare\n  общий период {lo} … {hi}")
    print(f"  минуток: старая {len(o):,}, новая {len(n):,}, в обеих {len(both):,}; "
          f"только в старой {len(o.index.difference(n.index)):,}, только в новой {len(n.index.difference(o.index)):,}")
    print(f"  одинаковых OHLC {eq.mean():.4%}; наибольшее расхождение цены {diff.max() if len(diff) else 0:.4f}")
    yr = pd.Series(eq, index=both.year).groupby(level=0).mean()
    for y, v in yr.items():
        if v < 1.0:
            print(f"    {y}: одинаковых {v:.4%}")
    ok = len(both) > 0 and eq.mean() >= a.min_equal
    print("  ИТОГ: " + ("версии совпадают на общем периоде" if ok else f"совпадение ниже порога {a.min_equal:.2%} — разбор обязателен"))
    return ok


def volume(a):
    san = _mod("DZ_DATA_Sanitizer_v2.py", "san")
    d = san.load_clean(a.npz)
    df = pd.DataFrame({"zero": d.v.values <= 0, "v": d.v.values}, index=d.index.year)
    g = df.groupby(level=0).agg(bars=("zero", "size"), zero_share=("zero", "mean"), median_v=("v", "median"))
    print(f"{VERSION} · volume  {a.npz}")
    print(g.to_string(float_format=lambda x: f"{x:.4f}"))
    share = float((d.v.values <= 0).mean())
    ok = share <= a.max_zero_share
    print(f"  ИТОГ: минуток без объёма {share:.4%} — " + ("в пределах порога" if ok else f"выше порога {a.max_zero_share:.2%}"))
    return ok


def htf_selftest(a):
    san = _mod("DZ_DATA_Sanitizer_v2.py", "san")
    ref = _mod("DZ_BT_DualBreakout_S021.py", "ref")
    m1 = san.load_clean(a.npz)
    if a.days:
        m1 = m1.loc[m1.index[0]: m1.index[0] + pd.Timedelta(days=a.days)]
    ok = True
    for tf in (15, 240):
        b2 = san.resample(m1, tf, 17)
        br = ref.build_htf(m1, tf, 17)
        same_n = len(b2) == len(br)
        same_px = same_n and np.allclose(b2[["o", "h", "l", "c"]].values, br[["o", "h", "l", "c"]].values, rtol=0, atol=0)
        same_close = same_n and (pd.DatetimeIndex(b2.close_utc).asi8 == pd.DatetimeIndex(br.close_utc).asi8).all()
        print(f"  M{tf}: баров v2 {len(b2):,}, эталон {len(br):,}; OHLC {'совпадают' if same_px else 'РАЗЛИЧАЮТСЯ'}, "
              f"закрытия {'совпадают' if same_close else 'РАЗЛИЧАЮТСЯ'}")
        ok = ok and same_px and same_close
    print(f"{VERSION} · htf-selftest: " + ("очиститель v2 строит те же бары, что эталон" if ok else "РАСХОЖДЕНИЕ с эталоном"))
    return ok


def dollar(a):
    san = _mod("DZ_DATA_Sanitizer_v2.py", "san")
    d = san.load_clean(a.npz)
    b = san.dollar_bars(d, a.usd, a.point_value)
    np.savez(a.out, t_open=pd.DatetimeIndex(b.open_utc).asi8, t_last=pd.DatetimeIndex(b.last_minute_open_utc).asi8,
             o=b.o.values, h=b.h.values, l=b.l.values, c=b.c.values, v=b.v.values)
    per_day = len(b) / max(1, d.index.normalize().nunique())
    print(f"{VERSION} · dollar-bars: баров {len(b):,}, в среднем {per_day:.1f} в день → {a.out}")
    return True


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare"); c.add_argument("--old", required=True); c.add_argument("--new", required=True)
    c.add_argument("--min-equal", type=float, default=0.999)
    v = sub.add_parser("volume"); v.add_argument("--npz", required=True); v.add_argument("--max-zero-share", type=float, default=0.01)
    h = sub.add_parser("htf-selftest"); h.add_argument("--npz", required=True); h.add_argument("--days", type=int, default=0)
    d = sub.add_parser("dollar-bars"); d.add_argument("--npz", required=True); d.add_argument("--usd", type=float, required=True)
    d.add_argument("--point-value", type=float, required=True); d.add_argument("--out", required=True)
    a = ap.parse_args()
    ok = {"compare": compare, "volume": volume, "htf-selftest": htf_selftest, "dollar-bars": dollar}[a.cmd](a)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
