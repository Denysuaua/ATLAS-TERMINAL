#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_ACCEPT_S021.py — приёмка торговой системы «Атлас», v1.0 (2026-10-04)

  check   --output output.txt [--version v1.8] [--fingerprint 3aed6564743e] [--allow-block]
          Разбор сохранённого окна Output NinjaTrader после прогона в воспроизведении рынка:
          строка запуска нужной версии, «новые входы разрешены», отпечаток схемы меню, ни
          одного [HUB-БЛОК] и ошибки платформы, в [HUB-ИТОГ] — потерь сигнала 0, у каждого
          модуля потеряно 0 и отказов 0, конфигурация без замечаний. Отчёт — JSON и Markdown.
  compare --a decisions_A.csv --b decisions_B.csv        ЭКСПЕРИМЕНТ Э26
          Детерминированность: два прогона одного дня с одними настройками обязаны принять
          одинаковые решения. Первое расхождение печатается целиком.
  trades  --dry dry_trades.csv [--min-bets 30] [--target-sr 0]   ЭКСПЕРИМЕНТ Э27
          Метрики ставок по журналу виртуальных сделок [T17] — вторая, независимая реализация
          того, что ядро считает в [T21] и [T22]: точность, p* и P[p < p*] (AFML гл. 15,
          апостериорное Beta), PSR[0] (AFML 14.7.2), концентрация h+ и h− (AFML 14), просадка.
          Расхождение с риск-строкой ядра — ошибка в одной из реализаций.

Код возврата: 0 — пройдено, 1 — нет, 2 — ошибка ввода.
==========================================================================================
"""
import argparse, json, math, re, sys
import numpy as np
import pandas as pd

VERSION = "DZ_ACCEPT_S021-v1.0 (2026-10-04)"


def _read(path):
    for enc in ("utf-8-sig", "utf-16", "cp1251"):
        try:
            return open(path, encoding=enc).read()
        except (UnicodeError, UnicodeDecodeError):
            continue
    sys.exit(2)


# ======================================================================================
# check
# ======================================================================================

def check(a):
    text = _read(a.output)
    lines = text.splitlines()
    res, ok = [], True

    def gate(name, passed, detail):
        nonlocal ok
        res.append({"проверка": name, "итог": "пройдено" if passed else "НЕ ПРОЙДЕНО", "подробно": detail})
        ok = ok and passed

    start = [l for l in lines if re.search(r"\[HUB\] DZ_SW_Hub_S021-v[\d.]+", l)]
    ver = re.search(r"DZ_SW_Hub_S021-(v[\d.]+)", start[-1]).group(1) if start else None
    gate("строка запуска", bool(start), start[-1].strip() if start else "нет строки «[HUB] DZ_SW_Hub_S021-…»")
    if a.version:
        gate("версия коммутатора", ver == a.version, f"в Output {ver}, ожидается {a.version}")
    if start:
        gate("новые входы разрешены", "новые входы разрешены" in start[-1], start[-1].strip())

    fp = [re.search(r"отпечаток ([0-9a-f]{12})", l).group(1) for l in lines if "схема меню: отпечаток" in l]
    if a.fingerprint:
        gate("отпечаток схемы меню", bool(fp) and fp[-1] == a.fingerprint,
             f"в Output {fp[-1] if fp else 'нет строки — включите [T15]'}, в справочнике {a.fingerprint}")

    blocks = [l.strip() for l in lines if "[HUB-БЛОК]" in l]
    gate("блокировки [HUB-БЛОК]", a.allow_block or not blocks, f"{len(blocks)}" + (": " + blocks[0][:160] if blocks else ""))
    warns = [l.strip() for l in lines if "[HUB-ВНИМАНИЕ]" in l]
    res.append({"проверка": "предупреждения [HUB-ВНИМАНИЕ]", "итог": "к сведению", "подробно": f"{len(warns)}"
                + (": " + warns[0][:160] if warns else "")})

    errs = [l.strip() for l in lines if re.search(r"Error on calling|Ошибка при вызове|Unhandled exception|Exception:", l)]
    gate("ошибки платформы", not errs, f"{len(errs)}" + (": " + errs[0][:160] if errs else ""))

    idx = [i for i, l in enumerate(lines) if "[HUB-ИТОГ]" in l]
    if not idx:
        gate("итоговая сводка", False, "нет [HUB-ИТОГ] — стратегию нужно выключить до сохранения Output")
    else:
        block = lines[idx[-1]: idx[-1] + 80]
        loss = [int(m.group(1)) for l in block for m in [re.search(r"потерь сигнала (\d+)", l)] if m]
        gate("потери сигнала", bool(loss) and loss[0] == 0, f"потерь сигнала {loss[0] if loss else '?'}")
        bad = []
        for l in block:
            m = re.search(r"^\s+(\S+)\s+роль .*потеряно (\d+)\s+отказов (\d+)", l)
            if m and (int(m.group(2)) or int(m.group(3))):
                bad.append(f"{m.group(1)}: потеряно {m.group(2)}, отказов {m.group(3)}")
        gate("модули: потери и отказы", not bad, "; ".join(bad) if bad else "у всех модулей 0 и 0")
        conf = [l for l in block if "конфигурация:" in l]
        gate("конфигурация", bool(conf) and "замечаний нет" in conf[0], conf[0].strip() if conf else "нет строки")

    rep = {"tool": VERSION, "output": a.output, "hub_version": ver, "passed": ok, "checks": res}
    json.dump(rep, open(a.report + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    with open(a.report + ".md", "w", encoding="utf-8") as f:
        f.write(f"# Приёмка «Атласа» — {'ПРОЙДЕНА' if ok else 'НЕ ПРОЙДЕНА'}\n\n{VERSION} · Output: `{a.output}` · коммутатор {ver}\n\n")
        f.write("| Проверка | Итог | Подробно |\n|---|---|---|\n")
        for r in res:
            f.write(f"| {r['проверка']} | {r['итог']} | {r['подробно'].replace('|', '/')} |\n")
    for r in res:
        print(f"  {r['итог']:<13} {r['проверка']}: {r['подробно'][:140]}")
    print(f"{VERSION}: приёмка {'ПРОЙДЕНА' if ok else 'НЕ ПРОЙДЕНА'} → {a.report}.md")
    return ok


# ======================================================================================
# compare — Э26
# ======================================================================================

def compare(a):
    x = pd.read_csv(a.a, sep=";", dtype=str).fillna("")
    y = pd.read_csv(a.b, sep=";", dtype=str).fillna("")
    cols = [c for c in x.columns if c in y.columns and c not in ("hub_version",)]
    n = min(len(x), len(y))
    for i in range(n):
        if list(x.loc[i, cols]) != list(y.loc[i, cols]):
            print(f"{VERSION} · compare: РАСХОЖДЕНИЕ в строке {i + 1}")
            for c in cols:
                if x.loc[i, c] != y.loc[i, c]:
                    print(f"  {c}: A = {x.loc[i, c][:120]} | B = {y.loc[i, c][:120]}")
            return False
    if len(x) != len(y):
        print(f"{VERSION} · compare: первые {n} решений совпадают, но строк {len(x)} и {len(y)}")
        return False
    print(f"{VERSION} · compare: прогоны детерминированы — {n} решений совпадают полностью")
    return True


# ======================================================================================
# trades — Э27
# ======================================================================================

def implied_precision(sl, pt, freq, tsr):
    """AFML snippet 15.3 binHR."""
    d = pt - sl
    A = (freq + tsr * tsr) * d * d
    B = (2 * freq * sl - tsr * tsr * d) * d
    C = freq * sl * sl
    disc = B * B - 4 * A * C
    if -1e-9 * (B * B + 1) < disc < 0:
        disc = 0.0
    return (-B + math.sqrt(disc)) / (2 * A) if A > 0 and disc >= 0 else float("nan")


def trades(a):
    from scipy.stats import beta, norm
    d = pd.read_csv(a.dry, sep=None, engine="python")
    num = lambda s: pd.to_numeric(s.astype(str).str.replace(",", "."), errors="coerce")
    d["Profit"] = num(d["Profit"])
    d["t_in"] = pd.to_datetime(d["Entry time"], dayfirst=True, errors="coerce")
    d["t_out"] = pd.to_datetime(d["Exit time"], dayfirst=True, errors="coerce")
    # ставка — вход с его частичными выходами (AFML с. 196): группировка по времени и стороне входа
    bets = d.groupby(["t_in", "Market pos."], sort=True).agg(pnl=("Profit", "sum"), t_out=("t_out", "max")).reset_index()
    r = bets.pnl.to_numpy(float)
    n = len(r)
    if n < 3:
        print("ставок меньше трёх"); return False
    w, l = r[r > 0], r[r <= 0]
    p_hat = len(w) / n
    years = max(1 / 12, (bets.t_out.max() - bets.t_in.min()).days / 365.25)
    p_star = implied_precision(l.mean(), w.mean(), n / years, a.target_sr) if len(w) and len(l) else float("nan")
    p_fail = float(beta.cdf(p_star, 1 + len(w), 1 + len(l))) if not math.isnan(p_star) else (1.0 if not len(w) else 0.0)
    mu, sd = r.mean(), r.std()
    g3 = ((r - mu) ** 3).mean() / sd ** 3
    g4 = ((r - mu) ** 4).mean() / sd ** 4
    sr = mu / sd
    den = 1 - g3 * sr + (g4 - 1) / 4 * sr * sr
    psr = float(norm.cdf(sr * math.sqrt(n - 1) / math.sqrt(den))) if den > 0 else float("nan")
    conc = lambda x: (len(x) * (x ** 2).sum() / x.sum() ** 2 - 1) / (len(x) - 1) if len(x) > 1 else float("nan")
    eq = np.cumsum(r)
    hwm = np.maximum.accumulate(np.maximum(eq, 0))
    dd = float((hwm - eq).max())
    since = int(n - 1 - np.argmax(eq == eq.max())) if eq.max() > 0 else n
    print(f"{VERSION} · trades  {a.dry}")
    print(f"  ставок {n}, точность {p_hat:.3f}, p* {p_star:.3f}, P[p < p*] {p_fail:.3f}, PSR[0] {psr:.3f}")
    print(f"  концентрация выигрышей {conc(w):.3f}, проигрышей {conc(l):.3f}, итог {r.sum():.2f}, "
          f"просадка {dd:.0f}, ставок без нового максимума {since}")
    verdict = n >= a.min_bets and psr >= 0.95 and p_fail <= 0.05
    print("  ИТОГ: " + ("ставки проходят пороги AFML: PSR ≥ 0,95 и P[p < p*] ≤ 0,05" if verdict
                        else f"пороги AFML не пройдены (нужно ставок ≥ {a.min_bets}, PSR ≥ 0,95, P[p < p*] ≤ 0,05)"))
    return verdict


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("--output", required=True); c.add_argument("--version")
    c.add_argument("--fingerprint"); c.add_argument("--allow-block", action="store_true"); c.add_argument("--report", default="accept_report")
    m = sub.add_parser("compare"); m.add_argument("--a", required=True); m.add_argument("--b", required=True)
    t = sub.add_parser("trades"); t.add_argument("--dry", required=True); t.add_argument("--min-bets", type=int, default=30)
    t.add_argument("--target-sr", type=float, default=0.0)
    a = ap.parse_args()
    ok = {"check": check, "compare": compare, "trades": trades}[a.cmd](a)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
