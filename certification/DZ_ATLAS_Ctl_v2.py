#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_ATLAS_Ctl_v2.py — управление службой v2 из окна команд, v1.0 (2026-10-05)

Временный пульт до приложения v2 (порция 2): те же вызовы, что сделает приложение. Ключ
читается из atlas_service_token.txt рядом — вводить его не нужно.

  smoke                         приёмка службы: связь, состояние, результаты, реестр,
                                сертификаты, ворота, счёт, бары — одна таблица
  status | results | registry | gates | certificates | account | alarms
  verify data|strategy|emulator|passport [--symbol MGC] [--root data_certified]
  log <id>                      журнал расчёта задачи
  submit <task.json>            поставить задачу или план проверки вперёд
  cancel <id> | requeue <id>
  preset <id> [--set best_selected] [--reason "…"]   пресет в dz_export\\presets для [U05]
  decision 1|10 "текст"         отметка ворот 1 (компиляция) или 10 (решение руководителя)
  flatten-all                   FLATTENEVERYTHING — спросит слово FLATTEN
  close <счёт> "<инструмент биржа>"   CLOSEPOSITION — спросит слово CLOSE
==========================================================================================
"""
import argparse, json, os, sys, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "DZ_ATLAS_Ctl_v2-v1.0 (2026-10-05)"


def call(port, method, path, body=None):
    tok = open(os.path.join(HERE, "atlas_service_token.txt"), encoding="utf-8").read().strip()
    data = json.dumps(body).encode("utf-8") if body is not None else (b"{}" if method == "POST" else None)
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method,
                                 headers={"X-Atlas-Token": tok, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=3600) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")
    except urllib.error.URLError as e:
        sys.exit(f"служба не отвечает на порту {port}: {e.reason} — запущена ли START_ATLAS_SERVICE_v2.bat?")


def show(code, obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    if code >= 400:
        sys.exit(1)


def smoke(port):
    rows = []

    def row(name, ok, info):
        rows.append((name, ok, info))
    c, h = call(port, "GET", "/health")
    row("связь и поток очереди", c == 200 and h.get("worker_alive"), h.get("service", ""))
    c, s = call(port, "GET", "/status")
    row("интерпретатор задач видит numpy и pandas", s.get("deps", {}).get("ok"), s.get("deps", {}).get("versions") or s.get("deps", {}).get("error"))
    row("замок отложенной выборки", bool(s.get("holdout", {}).get("from")), str(s.get("holdout")))
    c, r = call(port, "GET", "/results")
    row("результаты читаются", c == 200, f"прогонов {len(r.get('results', []))}, проверок вперёд {len(r.get('wfa', []))}")
    c, g = call(port, "GET", "/registry")
    row("реестр испытаний", c == 200, "; ".join(f"{k}: {v['trials']} исп., порог {v['emax_sigma']}σ, до {v['stop_sigma']}σ — {v['trials_left_to_stop']}"
                                              for k, v in g.get("by_strategy", {}).items()))
    c, v = call(port, "POST", "/verify?what=data&symbol=MGC&root=data_certified")
    row("сертификат данных MGC", v.get("ok"), v.get("text", v.get("error", ""))[-100:])
    c, p = call(port, "POST", "/verify?what=passport")
    row("паспорт сборки против NinjaTrader", p.get("ok"), p.get("text", p.get("error", "")))
    c, a = call(port, "GET", "/account")
    row("папка outgoing NinjaTrader", a.get("available"), f"позиций {len(a.get('positions', []))}, связей {len(a.get('connections', []))}")
    c, b = call(port, "GET", "/bars?symbol=MGC&tf=240&limit=30")
    row("бары 4H из сертифицированных данных", c == 200 and b.get("count", 0) > 0, b.get("source", b.get("error", "")))
    c, gt = call(port, "GET", "/gates")
    row("ворота выпуска считаются", c == 200, " ".join(f"{x['n']}:{x['status']}" for x in gt.get("gates", [])))
    w = max(len(x[0]) for x in rows)
    for n, ok, info in rows:
        print(f"{'✅' if ok else '❌'} {n.ljust(w)}  {info}")
    print(f"\nИтог приёмки службы: {sum(1 for x in rows if x[1])} из {len(rows)}. "
          f"Не пройдено по причине самой системы (паспорт, заглушки, печать эмулятора) — это находки ревизии, не сбой службы.")


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--symbol", default="MGC")
    ap.add_argument("--root", default="data_certified")
    ap.add_argument("--set", default="best_selected")
    ap.add_argument("--reason", default="")
    a = ap.parse_args()
    P = a.port
    simple = {"status": "/status", "results": "/results", "registry": "/registry", "gates": "/gates",
              "certificates": "/certificates", "account": "/account", "alarms": "/alarms"}
    if a.cmd == "smoke":
        smoke(P)
    elif a.cmd in simple:
        show(*call(P, "GET", simple[a.cmd]))
    elif a.cmd == "verify":
        show(*call(P, "POST", f"/verify?what={a.args[0]}&symbol={a.symbol}&root={a.root}"))
    elif a.cmd == "log":
        c, r = call(P, "GET", f"/log?id={a.args[0]}")
        print(r.get("text", r))
    elif a.cmd == "submit":
        show(*call(P, "POST", "/task", json.load(open(a.args[0], encoding="utf-8-sig"))))
    elif a.cmd in ("cancel", "requeue"):
        show(*call(P, "POST", f"/{a.cmd}?id={a.args[0]}"))
    elif a.cmd == "preset":
        body = {"id": a.args[0], "set": a.set}
        if a.reason:
            body["dogma_override_reason"] = a.reason
        show(*call(P, "POST", "/preset", body))
    elif a.cmd == "decision":
        show(*call(P, "POST", "/decision", {"gate": int(a.args[0]), "text": " ".join(a.args[1:])}))
    elif a.cmd == "flatten-all":
        word = input("Закрыть ВСЕ позиции во ВСЕХ счетах NinjaTrader? Наберите FLATTEN: ").strip()
        show(*call(P, "POST", "/emergency/flatten_all", {"confirm": word}))
    elif a.cmd == "close":
        word = input(f"Закрыть позицию {a.args[1]} на счёте {a.args[0]} мимо стратегии? Наберите CLOSE: ").strip()
        show(*call(P, "POST", "/emergency/close_position", {"account": a.args[0], "instrument": a.args[1], "confirm": word}))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
