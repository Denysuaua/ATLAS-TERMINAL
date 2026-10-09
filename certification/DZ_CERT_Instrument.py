#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DZ_CERT_Instrument.py — паспорт инструмента, v1.0 (2026-09-28)

TickSize и PointValue берутся из манифеста выгрузки NinjaTrader (DZ_IND_BarExporter_S021) —
это значения, которыми торгует сам терминал. Реестр DZ_NTSIM_Instruments.json обязан с ними
совпасть; при расхождении паспорт НЕ выдаётся, и реестр исправляется до сертификации.

  python DZ_CERT_Instrument.py --symbol MGC --nt-manifest MGC_12-26_Minute1_utc_open.manifest.json --out certified_vault/MGC
"""
import argparse, json, math, os, sys
from DZ_CERT_Common import write_cert, now_utc, sha_file

VERSION = "DZ_CERT_Instrument-v1.0 (2026-09-28)"


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--symbol", required=True); ap.add_argument("--nt-manifest", required=True)
    ap.add_argument("--registry", default="DZ_NTSIM_Instruments.json"); ap.add_argument("--out", required=True)
    ap.add_argument("--commission-per-side", type=float, help="за контракт; по умолчанию из реестра")
    ap.add_argument("--fees-per-side", type=float, default=0.0, help="биржевые сборы за контракт за сторону")
    ap.add_argument("--slippage-ticks", type=float, default=1.0)
    ap.add_argument("--min-stop-usd", type=float, default=5.0); ap.add_argument("--max-stop-usd", type=float, default=1000.0)
    ap.add_argument("--max-qty", type=int, default=10); ap.add_argument("--daily-loss-usd", type=float, default=1500.0)
    a = ap.parse_args()

    reg = json.load(open(a.registry, encoding="utf-8"))[a.symbol]
    nt = json.load(open(a.nt_manifest, encoding="utf-8"))
    tick, pv = float(nt["tick_size"]), float(nt["point_value"])
    mismatch = [f"{k}: реестр {reg[r]} ≠ NinjaTrader {v}" for k, r, v in (("tick", "tick", tick), ("point_value", "point_value", pv))
                if abs(float(reg[r]) - v) > 1e-12]
    if mismatch:
        print(f"ОТКАЗ: реестр {a.symbol} расходится с NinjaTrader: {mismatch}. Исправьте DZ_NTSIM_Instruments.json.")
        sys.exit(1)

    comm = reg.get("commission_per_side", 0.0) if a.commission_per_side is None else a.commission_per_side
    tv = tick * pv
    rt = 2 * (comm + a.fees_per_side)
    be_costs = math.ceil(rt / tv - 1e-9) if tv > 0 else None
    passport = {
        "certificate": "DZ-INSTRUMENT-CERT-v1.0", "issued_utc": now_utc(), "status": "CERTIFIED",
        "symbol": a.symbol, "nt_instrument": nt.get("instrument"), "currency": reg.get("currency"),
        "verified_in_nt": True, "nt_manifest_sha256": sha_file(a.nt_manifest),
        "market_mathematics": {"tick_size": tick, "point_value": pv, "tick_value": round(tv, 6)},
        "costs_per_contract": {"commission_per_side": comm, "fees_per_side": a.fees_per_side,
                               "round_turn": round(rt, 4), "slippage_ticks_per_fill": a.slippage_ticks,
                               "min_breakeven_offset_ticks_costs": be_costs,
                               "min_breakeven_offset_ticks_costs_and_slippage": (be_costs or 0) + math.ceil(a.slippage_ticks)},
        "risk_limits": {"stop_usd_per_contract": [a.min_stop_usd, a.max_stop_usd], "max_qty": a.max_qty,
                        "daily_loss_usd": a.daily_loss_usd},
        "session": {"tz": reg.get("tz"), "open": reg.get("session_open"), "close": reg.get("session_close")},
    }
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, f"{a.symbol}.instrument.cert.json")
    write_cert(path, passport)
    print(f"[паспорт] {a.symbol}: тик {tick}, пункт {pv}, тик = {tv} {reg.get('currency')}, круг {rt:.2f}, "
          f"безубыток ≥ {passport['costs_per_contract']['min_breakeven_offset_ticks_costs_and_slippage']} т → {path}")


if __name__ == "__main__":
    main()
