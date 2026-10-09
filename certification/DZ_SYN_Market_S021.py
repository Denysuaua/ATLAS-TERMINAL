#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_SYN_Market_S021.py — синтетический рынок для проверки модулей «Атласа», v1.0 (2026-10-04)

ЗАЧЕМ. Реальная история даёт по одному разу каждую неприятность. Синтетика даёт их сколько
нужно, с известной разметкой: где тренд, где флэт, где гэп, где V-прокол, где новость.
Модуль, переживший жёсткую синтетику, устойчивее на реальных данных; модуль, который на
чистом случайном блуждании «зарабатывает», заглядывает в будущее (AFML гл. 13: проверка
на синтетических данных; MLAM гл. 8: контроль переобучения).

КАК СТРОИТСЯ МИНУТКА. Путь цены считается по 12 подшагам на минуту, каждый подшаг
округляется до тика; OHLC — из подшагов. Поэтому High ≥ max(Open, Close) и Low ≤ min(...)
выполняются всегда, а путь внутри бара известен: по нему можно проверить исполнение.

РЕЖИМЫ: TREND_UP, TREND_DOWN — снос; FLAT — процесс Орнштейна–Уленбека (AFML 13.4, с. 172);
SQUEEZE — сжатие волатильности и выброс; CHOP — частые развороты.
СОБЫТИЯ: GAP — разрыв на открытии сессии; VSPIKE — V-образный прокол и возврат; NEWS —
скачок, всплеск волатильности и объёма в 08:30 по Нью-Йорку (14:30 по Берлину); WICK —
прокол одной минуты тенью; MISSING — пропавшие минутки; ZEROVOL — минутки без объёма.

ЭКСПЕРИМЕНТЫ
  Э28 сценарий markov — режимы сменяются по марковской цепи с матрицей переходов
      (банковская книга, гл. 4, с. pdf 107: p_ii близко к 1 — режимы устойчивы).
  Э29 calibrate-ou — оценка φ, σ и полураспада O-U по сертифицированным данным МНК, как
      в AFML 13.5 (с. 173); результат подставляется во флэт через --ou.

ВЫХОДЫ
  <out>_raw.txt          формат сырья GC: ДД/ММ/ГГГГ<TAB>ЧЧ:ММ:СС<TAB>O<TAB>H<TAB>L<TAB>C<TAB>V,
                         время биржи, метка — открытие бара: читается эталоном и движком ПК
  <out>_nt/<имя>.Last.txt импорт в NinjaTrader (руководство, с. 717–719): yyyyMMdd HHmmss;O;H;L;C;V,
                         UTC, метка — начало бара
  <out>_labels.csv       режим каждой минутки и события
  <out>_manifest.json    паспорт, сценарий, зерно, отпечатки файлов

  python DZ_SYN_Market_S021.py generate --instrument MGC --start 2025-03-03 --days 60 --scenario stress --seed 7 --out syn/mgc_stress
  python DZ_SYN_Market_S021.py calibrate-ou --npz data_certified/MGC2/MGC2_M15.npz --start 2019-01-01 --end 2021-12-31
==========================================================================================
"""
import argparse, hashlib, json, math, os, sys
from datetime import date, datetime, time as dtime, timedelta
import numpy as np
import pandas as pd

VERSION = "DZ_SYN_Market_S021-v1.0 (2026-10-04)"
HERE = os.path.dirname(os.path.abspath(__file__))
S = 12                                   # подшагов на минуту
REG = ["TREND_UP", "TREND_DOWN", "FLAT", "SQUEEZE", "CHOP"]


def passport(symbol, path=None):
    p = json.load(open(path or os.path.join(HERE, "DZ_INSTRUMENTS_S021.json"), encoding="utf-8"))
    if symbol not in p["instruments"]:
        sys.exit(f"нет инструмента {symbol}; есть: {', '.join(p['instruments'])}")
    ins = dict(p["instruments"][symbol]); ins["symbol"] = symbol
    ins["sess"] = p["sessions"][ins["session"]]
    return ins


def session_minutes(day, sess):
    """Время открытия минуток торгового дня, UTC. Глобекс: с 17:00 Чикаго накануне до 16:00."""
    tz = sess["tz"]
    o = datetime.combine(day, dtime.fromisoformat(sess["open"]))
    c = datetime.combine(day, dtime.fromisoformat(sess["close"]))
    if sess["overnight"]:
        o -= timedelta(days=1)
    a = pd.Timestamp(o).tz_localize(tz).tz_convert("UTC")
    b = pd.Timestamp(c).tz_localize(tz).tz_convert("UTC")
    return pd.date_range(a, b, freq="1min", inclusive="left")


def news_minute(idx):
    """Минутка 08:30 по Нью-Йорку внутри сессии или −1."""
    ny = idx.tz_convert("America/New_York")
    k = np.where((ny.hour == 8) & (ny.minute == 30))[0]
    return int(k[0]) if len(k) else -1


def regimes_for_day(n, scenario, rng, markov_state):
    """Режим каждой минутки. stress — блоки по 120 мин; markov — блоки по 30 мин по цепи (Э28)."""
    if scenario in ("randomwalk", "gaps", "vspikes", "news", "calm"):
        return np.full(n, -1), markov_state
    if scenario in ("trend", "flat"):
        r = (rng.integers(0, 2) if scenario == "trend" else 2)
        return np.full(n, r), markov_state
    if scenario == "markov":
        P = np.full((5, 5), 0.1 / 4); np.fill_diagonal(P, 0.9)       # p_ii = 0,9: 10 блоков в среднем
        out, s = np.empty(n, int), markov_state if markov_state is not None else int(rng.integers(0, 5))
        for b0 in range(0, n, 30):
            out[b0:b0 + 30] = s
            s = int(rng.choice(5, p=P[s]))
        return out, s
    out = np.empty(n, int)
    for b0 in range(0, n, 120):
        out[b0:b0 + 120] = rng.choice(5, p=[0.22, 0.22, 0.26, 0.15, 0.15])
    return out, markov_state


def build_day(ins, idx, x0, scenario, rng, ou, markov_state, sigma_day):
    """Путь дня по подшагам: базовый процесс + события. Возвращает OHLCV, метки, события, конец пути."""
    n = len(idx)
    sig_min = sigma_day / math.sqrt(1380 if ins["sess"]["overnight"] else 390)
    reg, markov_state = regimes_for_day(n, scenario, rng, markov_state)
    prof = ins["sess"].get("synthetic_hour_profile")
    if prof:
        # профиль по часам биржи — из реальных данных (паспорт); среднее по дню — 1
        hrs = idx.tz_convert(ins["sess"]["tz"]).hour
        season = np.array([prof.get(str(hh), 1.0) for hh in hrs], float)
        season /= season.mean()
    else:
        m = np.arange(n) / max(1, n - 1)
        season = 0.75 + 1.0 * (2 * m - 1) ** 2                 # U-образная волатильность основной сессии акций
    drift = np.zeros(n); volm = season.copy(); kappa = np.zeros(n)
    hl = ou.get("half_life_min", 30.0)
    for code in range(5):
        k = reg == code
        if not k.any():
            continue
        if code == 0: drift[k] = 0.08
        if code == 1: drift[k] = -0.08
        if code == 2: kappa[k] = math.log(2) / hl; volm[k] *= ou.get("vol_mult", 0.7)
        if code == 3:
            pos = np.cumsum(k) / max(1, k.sum())
            volm[k] *= np.where(pos[k] < 0.8, 1.0 - 0.85 * pos[k], 2.5)
        if code == 4:
            seg = (np.arange(n) // 10) % 2
            drift[k] = np.where(seg[k] == 0, 0.15, -0.15)

    events, ev_min = [], np.zeros(n, dtype=object); ev_min[:] = ""
    volx = np.ones(n)
    add = np.zeros(n * S)
    stress = scenario in ("stress", "markov")
    # GAP на открытии
    if scenario in ("gaps",) or (stress and rng.random() < 0.5):
        J = float(rng.choice([-1, 1]) * rng.uniform(0.5, 3.0) * sigma_day * 0.3)
        add[:] += J; events.append(("GAP", 0, J)); ev_min[0] = "GAP"
    # V-прокол
    if scenario == "vspikes" or (stress and rng.random() < 0.6):
        for _ in range(1 if scenario != "vspikes" else 3):
            t0 = int(rng.integers(30, max(31, n - 60)))
            A = float(rng.choice([-1, 1]) * rng.uniform(4, 10) * sig_min * math.sqrt(30))
            m1, m2 = int(rng.integers(1, 6)), int(rng.integers(5, 31))
            a0, a1, a2 = t0 * S, (t0 + m1) * S, min(n * S, (t0 + m1 + m2) * S)
            add[a0:a1] += np.linspace(0, A, a1 - a0)
            add[a1:a2] += np.linspace(A, 0, a2 - a1)
            volx[t0:t0 + m1 + m2] *= 6
            events.append(("VSPIKE", t0, A)); ev_min[t0] = "VSPIKE"
    # Новость 08:30 Нью-Йорка
    kn = news_minute(idx)
    if kn >= 0 and (scenario == "news" or (stress and rng.random() < 0.7)):
        J = float(rng.choice([-1, 1]) * rng.uniform(5, 15) * sig_min)
        D = int(rng.integers(5, 21))
        add[kn * S:] += J
        volm[kn:kn + D] *= rng.uniform(5, 12)
        volx[kn:kn + D] *= rng.uniform(5, 20)
        events.append(("NEWS", kn, J)); ev_min[kn] = "NEWS"
    # Прокол тенью
    if stress and rng.random() < 0.5:
        t0 = int(rng.integers(10, n - 10))
        W = float(rng.choice([-1, 1]) * rng.uniform(6, 15) * sig_min)
        add[t0 * S + S // 2] += W
        events.append(("WICK", t0, W)); ev_min[t0] = (ev_min[t0] + " WICK").strip()

    # Базовый процесс по подшагам: снос, волатильность, притяжение O-U к уровню дня
    eps = rng.standard_normal(n * S)
    sig = np.repeat(sig_min * volm, S) / math.sqrt(S)
    dr = np.repeat(drift * sig_min, S) / S
    kp = np.repeat(kappa, S) / S
    x = np.empty(n * S); cur, level = 0.0, 0.0
    for i in range(n * S):
        cur += dr[i] + sig[i] * eps[i] - kp[i] * (cur - level)
        x[i] = cur
    tick = ins["tick"]
    path = x0 + x + add
    path = np.maximum(path, tick)
    path = np.round(path / tick) * tick
    pm = path.reshape(n, S)
    o, h, l, c = pm[:, 0], pm.max(1), pm.min(1), pm[:, -1]
    v = ins["synthetic_volume_per_min"] * season * volx * np.exp(rng.normal(0, 0.4, n)) * (volm / season) ** 0.8
    v = np.maximum(1, np.round(v)).astype(np.int64)
    keep = np.ones(n, bool)
    if stress:
        v[rng.random(n) < 0.002] = 0                                  # ZEROVOL
        keep &= rng.random(n) >= 0.002                                # MISSING
    lab = np.array([REG[r] if r >= 0 else "RW" for r in reg], dtype=object)
    df = pd.DataFrame({"o": o, "h": h, "l": l, "c": c, "v": v, "regime": lab, "event": ev_min}, index=idx)
    df.loc[df.v == 0, "event"] = (df.loc[df.v == 0, "event"] + " ZEROVOL").str.strip()
    dropped = int((~keep).sum())
    return df[keep], float(path[-1]), events, markov_state, dropped


def fmt_price(x, tick):
    from decimal import Decimal
    dec = max(0, -Decimal(str(tick)).normalize().as_tuple().exponent)
    return f"{x:.{dec}f}"


def generate(a):
    ins = passport(a.instrument, a.passport)
    rng = np.random.default_rng(a.seed)
    ou = json.load(open(a.ou, encoding="utf-8")) if a.ou else {}
    start = date.fromisoformat(a.start)
    days, d = [], start
    while len(days) < a.days:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    price = float(a.price or ins["synthetic_price"])
    sigma_day = price * ins["synthetic_daily_vol_pct"] / 100.0
    frames, events_all, dropped, mstate = [], [], 0, None
    for day in days:
        idx = session_minutes(day, ins["sess"])
        if not ins["sess"]["overnight"] and frames:
            price += rng.normal(0, 0.5) * sigma_day                          # ночной разрыв акций
        df, end, ev, mstate, dr = build_day(ins, idx, price, a.scenario, rng, ou, mstate, sigma_day)
        frames.append(df); dropped += dr
        events_all += [{"day": str(day), "event": e, "time_utc": str(idx[k]), "size": round(s, 6)} for e, k, s in ev]
        price = float(df.c.iloc[-1]) if len(df) else price
    m1 = pd.concat(frames)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    tick = ins["tick"]
    fp = lambda s: s.map(lambda x: fmt_price(x, tick))
    loc = m1.index.tz_convert(ins["sess"]["tz"])
    raw = pd.DataFrame({"d": loc.strftime("%d/%m/%Y"), "t": loc.strftime("%H:%M:%S"),
                        "o": fp(m1.o), "h": fp(m1.h), "l": fp(m1.l), "c": fp(m1.c), "v": m1.v.values})
    raw_path = a.out + "_raw.txt"
    raw.to_csv(raw_path, sep="\t", header=False, index=False)
    nt_dir = a.out + "_nt"; os.makedirs(nt_dir, exist_ok=True)
    nt_name = (a.nt_name or f"DZSYN{a.instrument}")
    nt_path = os.path.join(nt_dir, f"{nt_name}.Last.txt")
    nt = pd.DataFrame({"t": m1.index.strftime("%Y%m%d %H%M%S"), "o": fp(m1.o), "h": fp(m1.h), "l": fp(m1.l),
                       "c": fp(m1.c), "v": m1.v.values})
    nt.to_csv(nt_path, sep=";", header=False, index=False)
    lab_path = a.out + "_labels.csv"
    m1[["regime", "event"]].assign(time_utc=m1.index.strftime("%Y-%m-%d %H:%M:%S")).to_csv(
        lab_path, sep=";", index=False, columns=["time_utc", "regime", "event"])
    sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    man = {"generator": VERSION, "instrument": ins["symbol"], "tick": tick, "point_value_usd": ins["point_value_usd"],
           "scenario": a.scenario, "seed": a.seed, "start": a.start, "days": a.days, "minutes": int(len(m1)),
           "dropped_minutes": dropped, "zero_volume_minutes": int((m1.v == 0).sum()),
           "regime_share": {k: round(float(v), 4) for k, v in m1.regime.value_counts(normalize=True).items()},
           "events": events_all, "ou": ou,
           "files": {os.path.basename(p): sha(p) for p in (raw_path, nt_path, lab_path)},
           "nt_import": {"file": os.path.relpath(nt_path), "format": "NinjaTrader (timestamps represent start of bar time)",
                         "time_zone": "UTC", "manual": "NinjaTrader 8, Historical Data → Import, с. 717–719"}}
    json.dump(man, open(a.out + "_manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{VERSION}: {ins['symbol']} {a.scenario}, минуток {len(m1):,}, событий {len(events_all)}, "
          f"пропущено {dropped}, без объёма {man['zero_volume_minutes']} → {a.out}_*")
    return m1


def calibrate_ou(a):
    """Э29: P_t − E = φ(P_{t−1} − E) + σε (AFML 13.4–13.5). Оценка по каждому дню отдельно: E — среднее дня."""
    z = np.load(a.npz)
    t = pd.to_datetime(z["t_open"] if "t_open" in z.files else z["t"], utc=True)
    c = pd.Series(z["c"], index=t)
    if a.start: c = c[c.index >= pd.Timestamp(a.start, tz="UTC")]
    if a.end: c = c[c.index < pd.Timestamp(a.end, tz="UTC")]
    xs, ys = [], []
    for _, s in c.groupby(c.index.tz_convert("America/Chicago").date):
        if len(s) < 20:
            continue
        d = s.values - s.values.mean()
        xs.append(d[:-1]); ys.append(d[1:])
    x, y = np.concatenate(xs), np.concatenate(ys)
    phi = float((x * y).sum() / (x * x).sum())
    sig = float(np.std(y - phi * x))
    step = float(np.median(np.diff(t.asi8)) / 6e10)
    hl = -math.log(2) / math.log(phi) * step if 0 < phi < 1 else float("inf")
    out = {"source": os.path.basename(a.npz), "phi": round(phi, 6), "sigma": round(sig, 6),
           "bar_minutes": step, "half_life_min": round(hl, 2), "vol_mult": 0.7, "method": "AFML 13.5, МНК по дням"}
    print(json.dumps(out, ensure_ascii=False))
    if a.save:
        json.dump(out, open(a.save, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return out


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--instrument", required=True); g.add_argument("--start", required=True)
    g.add_argument("--days", type=int, default=60); g.add_argument("--seed", type=int, default=7)
    g.add_argument("--scenario", default="stress",
                   choices=["stress", "markov", "trend", "flat", "gaps", "vspikes", "news", "calm", "randomwalk"])
    g.add_argument("--price", type=float); g.add_argument("--ou"); g.add_argument("--nt-name")
    g.add_argument("--passport"); g.add_argument("--out", required=True)
    c = sub.add_parser("calibrate-ou")
    c.add_argument("--npz", required=True); c.add_argument("--start"); c.add_argument("--end"); c.add_argument("--save")
    a = ap.parse_args()
    generate(a) if a.cmd == "generate" else calibrate_ou(a)


if __name__ == "__main__":
    main()
