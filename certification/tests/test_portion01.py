#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Испытания порции 01 (служба v2) на КОПИИ терминала. Не запускать на рабочей папке: тесты
ставят задачи на синтетических данных SYN1, пишут в поддельную папку NinjaTrader и
останавливают службу.

  python tests/test_portion01.py --root <копия>/certification --nt <поддельная папка NinjaTrader>
"""
import argparse, base64, hashlib, json, os, signal, socket, subprocess, sys, threading, time, urllib.request, urllib.error

RES = []


def check(name, cond, info=""):
    RES.append((name, bool(cond), info))
    print(f"  {'ПРОЙДЕН ' if cond else 'ПРОВАЛ  '} {name}" + (f" — {info}" if info else ""), flush=True)


class Api:
    def __init__(self, port, token):
        self.base, self.token = f"http://127.0.0.1:{port}", token

    def call(self, method, path, body=None, token=True, origin=None):
        h = {"Content-Type": "application/json"}
        if token:
            h["X-Atlas-Token"] = self.token if token is True else token
        if origin:
            h["Origin"] = origin
        data = json.dumps(body).encode() if body is not None else (b"{}" if method == "POST" else None)
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                return r.status, json.loads(r.read().decode()), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode() or "{}"), dict(e.headers)


def start(root, port):
    p = subprocess.Popen([sys.executable, os.path.join(root, "DZ_ATLAS_Service_v2.py"), "--root", root, "--port", str(port)],
                         stdout=open(os.path.join(root, "..", f"svc_{port}.out"), "ab"), stderr=subprocess.STDOUT,
                         start_new_session=True)
    for _ in range(240):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                if json.loads(r.read())["ok"]:
                    return p
        except Exception:
            time.sleep(0.5)
    raise SystemExit("служба не поднялась")


def wait_state(api, tid, states, limit=600):
    t0 = time.time()
    while time.time() - t0 < limit:
        st = api.call("GET", "/status")[1]["jobs"].get(tid, {})
        if st.get("state") in states:
            return st
        time.sleep(1)
    return api.call("GET", "/status")[1]["jobs"].get(tid, {})


def registry_total(root):
    import pandas as pd
    return int(pd.read_csv(os.path.join(root, "trials_registry.csv")).Trials.sum())


def fake_nt(nt, stop):
    """Поддельный NinjaTrader: забирает OIF из incoming и пишет FLAT в файлы позиций outgoing."""
    inc, out = os.path.join(nt, "incoming"), os.path.join(nt, "outgoing")
    while not stop.is_set():
        for f in os.listdir(inc):
            if f.startswith("oif") and f.endswith(".txt"):
                p = os.path.join(inc, f)
                line = open(p).read().strip()
                os.remove(p)
                with open(os.path.join(nt, "oif_seen.log"), "a") as lg:
                    lg.write(line + "\n")
                for g in os.listdir(out):
                    if g.endswith("_Position.txt"):
                        open(os.path.join(out, g), "w").write("FLAT;0;0")
        time.sleep(0.1)


def mock_ws(port, token, received, stop, pos=1, qty=3):
    """Сервер пульта стратегии в миниатюре: рукопожатие, вход по ключу, снимки бара с позицией."""
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(2)
    srv.settimeout(1)
    while not stop.is_set():
        try:
            c, _ = srv.accept()
        except socket.timeout:
            continue
        try:
            req = b""
            while b"\r\n\r\n" not in req:
                req += c.recv(1)
            key = [l.split(":", 1)[1].strip() for l in req.decode().split("\r\n") if l.lower().startswith("sec-websocket-key")][0]
            acc = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            c.sendall(f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {acc}\r\n\r\n".encode())

            def send(obj):
                p = json.dumps(obj).encode()
                c.sendall(bytes([0x81, len(p)]) + p if len(p) < 126 else bytes([0x81, 126]) + len(p).to_bytes(2, "big") + p)

            def recv():
                h = c.recv(2)
                n = h[1] & 0x7F
                if n == 126:
                    n = int.from_bytes(c.recv(2), "big")
                m = c.recv(4)
                d = b""
                while len(d) < n:
                    d += c.recv(n - len(d))
                return json.loads(bytes(b ^ m[i % 4] for i, b in enumerate(d)))
            auth = recv()
            send({"t": "auth", "ok": auth.get("token") == token, "commands": True})
            c.settimeout(0.3)
            while not stop.is_set():
                send({"t": "bar", "ts": int(time.time()), "pos": pos, "qty": qty})
                try:
                    received.append(recv())
                except (socket.timeout, IndexError):
                    pass
                time.sleep(0.5)
        except Exception:
            pass
        finally:
            c.close()
    srv.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--nt", required=True)
    ap.add_argument("--port", type=int, default=18090)
    a = ap.parse_args()
    root, nt, port = os.path.abspath(a.root), os.path.abspath(a.nt), a.port
    cfgp = os.path.join(root, "DZ_ATLAS_Service_v2.config.json")
    json.dump({"nt_root": nt, "port": port}, open(cfgp, "w"))
    svc = start(root, port)
    api = Api(port, open(os.path.join(root, "atlas_service_token.txt")).read().strip())
    stop = threading.Event()
    threading.Thread(target=fake_nt, args=(nt, stop), daemon=True).start()
    try:
        print("— доступ")
        check("health без ключа", api.call("GET", "/health", token=False)[0] == 200)
        check("status без ключа — 401", api.call("GET", "/status", token=False)[0] == 401)
        check("неверный ключ — 401", api.call("GET", "/status", token="x" * 64)[0] == 401)
        check("чужой Origin — 403", api.call("GET", "/status", origin="https://evil.example")[0] == 403)
        check("app://atlas.evil — 403 (точное совпадение)", api.call("GET", "/status", origin="app://atlas.evil")[0] == 403)
        c, b, h = api.call("GET", "/status", origin="null")
        check("Origin null с ключом — 200 и CORS", c == 200 and h.get("Access-Control-Allow-Origin") == "null")
        print("— наследие v1")
        jobs = b["jobs"]
        check("история v1 импортирована", "system_20261001155754" in jobs and jobs["system_20261001155754"].get("source") == "служба v1")
        check("зависшее «queued» v1 сверено по папке done", jobs.get("param_20261001122040", {}).get("state") == "done",
              jobs.get("param_20261001122040", {}).get("note", ""))
        print("— результаты")
        r = api.call("GET", "/results")[1]
        row = next((x for x in r["results"] if x["id"] == "system_20261001155754"), {})
        check("список результатов", row.get("trades") == 3007 and row.get("net") is not None, f"net {row.get('net')}, DSR {row.get('dsr')}")
        c, t, _ = api.call("GET", "/trades?id=system_20261001155754")
        check("сделки: кривая, годы, MFE capture", c == 200 and t["count"] == 3007 and t["mfe_capture"].get("capture_total") is not None,
              f"capture_total {t.get('mfe_capture', {}).get('capture_total')}, max DD {t.get('max_drawdown')}, лет {len(t.get('years', []))}")
        check("испытания", api.call("GET", "/trials?id=system_20261001155754")[1].get("columns", [None])[0] == "stop_ticks")
        check("итог проверки вперёд", api.call("GET", "/wfa?id=wfa_dev_20261001130938")[1]["summary"]["windows"] == 7)
        reg = api.call("GET", "/registry")[1]
        db = reg["by_strategy"].get("DualBreakout", {})
        check("реестр: 13 148 испытаний, порог ≈ 3,9σ", db.get("trials", 0) >= 13148 and 3.8 < db.get("emax_sigma", 0) < 4.0,
              f"порог {db.get('emax_sigma')}σ, до 4σ осталось {db.get('trials_left_to_stop')} испытаний, формула: {reg['formula']}")
        print("— сертификаты и ворота")
        cert = api.call("GET", "/certificates")[1]
        check("сертификаты данных v1, v2 и SYN1", {(d["root"], d["symbol"]) for d in cert["data"]} >= {("data_certified", "MGC"), ("data_certified_v2", "MGC"), ("data_certified", "SYN1")})
        check("заглушки элементов найдены", sum(e["placeholder"] for e in cert["strategy"]["elements"]) == 6)
        check("хранилище против паспорта: 10 нет", len(cert["strategy"]["vault_vs_passport"]["missing"]) == 10)
        v = api.call("POST", "/verify?what=data&symbol=MGC&root=data_certified")[1]
        check("проверка данных MGC через службу", v.get("ok") is True, v.get("text", "")[-80:])
        v = api.call("POST", "/verify?what=strategy")[1]
        check("проверка сертификата стратегии — нарушение видно", v.get("ok") is False and "DOC2" in v.get("text", ""))
        g = {x["n"]: x for x in api.call("GET", "/gates")[1]["gates"]}
        check("ворота 4 пройдены, 6 и 9 — нет", g[4]["status"] == "pass" and g[6]["status"] == "fail" and g[9]["status"] == "fail", g[6]["evidence"][:90])
        print("— бары")
        c, bars, _ = api.call("GET", "/bars?symbol=MGC&tf=240&from=2026-06-01&to=2026-07-22")
        import pandas as pd
        hours = sorted(set(pd.to_datetime(bars.get("t", []), unit="s", utc=True).tz_convert("America/Chicago").hour))
        check("4H от 17:00 по Чикаго", c == 200 and bars["count"] > 50 and set(hours) <= {17, 21, 1, 5, 9, 13}, f"часы открытия {hours}")
        c, b5, _ = api.call("GET", "/bars?symbol=MGC&tf=5&limit=500")
        check("M5 последние 500", c == 200 and b5["count"] == 500)
        print("— счёт (outgoing)")
        out = os.path.join(nt, "outgoing")
        open(os.path.join(out, "MGC 12-26 Nymex_Sim101_Position.txt"), "w").write("LONG;3;3337.4")
        open(os.path.join(out, "Rithmic.txt"), "w").write("CONNECTED")
        acc = api.call("GET", "/account")[1]
        check("позиция и связь прочитаны", acc["positions"][0] == {**acc["positions"][0], "instrument": "MGC 12-26 Nymex", "account": "Sim101", "side": "LONG", "qty": 3}
              and acc["connections"][0]["state"] == "CONNECTED")
        print("— пресет")
        c, b, _ = api.call("POST", "/preset", {"id": "system_20261001155754", "set": "best_selected"})
        check("пресет [MOD8] без [MOD1] — отказ по догме", c == 400 and "догма" in b.get("error", ""), b.get("error", "")[:120])
        c, b, _ = api.call("POST", "/preset", {"id": "system_20261001155754", "set": "best_plateau",
                                                "dogma_override_reason": "испытание пробоя в воспроизведении рынка, без реального счёта"})
        ok = c == 200
        if ok:
            txt = open(b["files"][0], encoding="utf-8").read()
            pj = json.loads(txt)
            ok = txt.count('"params"') == 1 and "DryRunMode" not in pj["params"] and isinstance(pj["params"]["StopLossTicks"], int) \
                and pj["params"].get("BreakevenMode") == "AtRMultiple"
        check("пресет с причиной: формат коммутатора, целые без точки, nt_fixed на месте", ok, (b.get("error") or str(b.get("warnings")))[:160])
        print("— постановка задач: отказы")
        base = {"data": "SYN1", "mode": "dev", "optimize": {"stop_ticks": [150, 250]}, "max_trials": 2, "objective": "SharpeDaily"}
        cases = [("поле cache", dict(base, task_id="bad_cache", cache="C:/x.npz"), 400),
                 ("параметр не из графа", dict(base, task_id="bad_param", optimize={"no_such": [1]}), 400),
                 ("цель не из списка", dict(base, task_id="bad_obj", objective="Foo"), 400),
                 ("данные — путь к CSV", dict(base, task_id="bad_data", data="C:/gc-1m.csv"), 400),
                 ("конец в отложенной выборке", dict(base, task_id="bad_end", end="2023-01-01"), 400),
                 ("вскрытие без причины", dict(base, task_id="bad_unlock", unlock_holdout=True), 400),
                 ("повтор id", dict(base, task_id="system_20261001155754"), 409),
                 ("id с путём", dict(base, task_id="../evil"), 400),
                 ("неизвестный ключ base", dict(base, task_id="bad_base", base={"zzz": 1}), 400),
                 ("план в отложенной выборке", {"plan_id": "bad_wfa", "task": base, "windows": [{"train": ["2019-01-01", "2021-01-01"], "test": ["2021-01-01", "2023-01-01"]}]}, 400)]
        for name, body, code in cases:
            c, b, _ = api.call("POST", "/task", body)
            check(f"отказ: {name}", c == code, f"{c}: {b.get('error', '')[:100]}")
        print("— очередь: сквозной прогон, отмена, журнал")
        reg0 = registry_total(root)
        c, b, _ = api.call("POST", "/task", dict(base, task_id="e2e_syn1"))
        check("задача на SYN1 принята, период обрезан замком", c == 200 and any("обрезан" in n for n in b["notes"]), str(b.get("notes"))[:140])
        c2, b2, _ = api.call("POST", "/task", dict(base, task_id="e2e_queued", optimize={"stop_ticks": [150, 200, 250]}, max_trials=3))
        time.sleep(1)
        c3, b3, _ = api.call("POST", "/cancel?id=e2e_queued")
        check("отмена задачи в очереди", c3 == 200 and wait_state(api, "e2e_queued", ("cancelled",), 30).get("state") == "cancelled")
        st = wait_state(api, "e2e_syn1", ("done", "failed"), 900)
        check("сквозной прогон выполнен", st.get("state") == "done", (st.get("error") or st.get("verdict") or "")[-200:])
        check("итог и журнал расчёта на месте", os.path.exists(os.path.join(root, "results", "e2e_syn1", "summary.json"))
              and "испытаний" in api.call("GET", "/log?id=e2e_syn1")[1].get("text", ""))
        check("реестр +2 испытания", registry_total(root) == reg0 + 2, f"{reg0} → {registry_total(root)}")
        check("предупреждение о малой выборке", "критерий №9" in (st.get("warning") or ""), st.get("warning", ""))
        c, b, _ = api.call("POST", "/task", dict(base, task_id="e2e_cancel", optimize={"stop_ticks": list(range(100, 300, 10)), "be_offset_ticks": [1, 2, 3]}, max_trials=60))
        wait_state(api, "e2e_cancel", ("running",), 60)
        time.sleep(4)
        reg1 = registry_total(root)
        api.call("POST", "/cancel?id=e2e_cancel")
        st = wait_state(api, "e2e_cancel", ("cancelled", "done", "failed"), 120)
        check("отмена во время расчёта", st.get("state") == "cancelled" and registry_total(root) == reg1, st.get("note", ""))
        print("— аварийные команды")
        open(os.path.join(out, "MGC 12-26 Nymex_Sim101_Position.txt"), "w").write("LONG;3;3337.4")
        c, b, _ = api.call("POST", "/emergency/close_position", {"account": "Sim101", "instrument": "MGC 12-26 Nymex;PLACE", "confirm": "CLOSE"})
        check("поле OIF с «;» — отказ", c == 400)
        c, b, _ = api.call("POST", "/emergency/close_position", {"account": "Sim101", "instrument": "MGC 12-26 Nymex", "confirm": "CLOSE"})
        seen = open(os.path.join(nt, "oif_seen.log")).read().splitlines()
        check("CLOSEPOSITION: 13 полей, забран, FLAT подтверждён", c == 200 and seen[-1] == "CLOSEPOSITION;Sim101;MGC 12-26 Nymex;;;;;;;;;;"
              and b["picked_up_sec"] is not None and b["flat_confirmed"] is True, f"{seen[-1]!r}")
        c, b, _ = api.call("POST", "/emergency/flatten_all", {"confirm": "FLATTEN"})
        check("не чаще раза в 3 с — 429", c == 429)
        time.sleep(3.2)
        c, b, _ = api.call("POST", "/emergency/flatten_all", {"confirm": "FLATTEN"})
        seen = open(os.path.join(nt, "oif_seen.log")).read().splitlines()
        check("FLATTENEVERYTHING как в руководстве", c == 200 and seen[-1] == "FLATTENEVERYTHING;;;;;;;;;;;;")
        print("— отметки ворот и журнал")
        api.call("POST", "/decision", {"gate": 10, "text": "испытательная отметка: реальный счёт не включать"})
        g = {x["n"]: x for x in api.call("GET", "/gates")[1]["gates"]}
        check("ворота 10 — отметка записана, 9 по-прежнему красные", g[10]["status"] == "manual" and g[9]["status"] == "fail")
        check("журнал службы", len(api.call("GET", "/journal?limit=50")[1]["records"]) > 10)
        print("— прерывание службы во время расчёта")
        c, b, _ = api.call("POST", "/task", dict(base, task_id="e2e_interrupt", optimize={"stop_ticks": list(range(100, 300, 10)), "be_offset_ticks": [1, 2, 3]}, max_trials=60))
        wait_state(api, "e2e_interrupt", ("running",), 60)
        os.killpg(svc.pid, signal.SIGKILL)                   # окно службы закрыто силой
        time.sleep(1)
        subprocess.run(["pkill", "-f", "e2e_interrupt.json"])  # осиротевший оптимизатор (на Windows закрытие окна делает это само)
        open(os.path.join(root, "task_queue", "garbage_1.json"), "w").write("{не json")
        svc = start(root, port)
        st = api.call("GET", "/status")[1]["jobs"]
        check("после перезапуска — «прервана», не перезапущена молча", st.get("e2e_interrupt", {}).get("state") == "interrupted")
        check("мусор в очереди — в failed с причиной", st.get("garbage_1", {}).get("state") == "failed", st.get("garbage_1", {}).get("error", "")[:80])
        c, b, _ = api.call("POST", "/requeue?id=e2e_interrupt")
        check("повтор прерванной — новый id", c == 200 and b["queued"] == "e2e_interrupt_r2")
        api.call("POST", "/cancel?id=e2e_interrupt_r2")
        wait_state(api, "e2e_interrupt_r2", ("cancelled", "done", "failed"), 120)
        print("— Э-Т1 бюджетный замок")
        os.killpg(svc.pid, signal.SIGINT)
        svc.wait(timeout=60)
        json.dump({"nt_root": nt, "port": port, "budget_lock": {"enabled": True, "sigma": 4.0},
                   "desync_watch": {"enabled": True, "ws_port": port + 1, "account": "Sim101", "instrument_prefix": "MGC",
                                    "grace_sec": 2, "action": "pause"}}, open(cfgp, "w"))
        tok_ws = "w" * 32
        open(os.path.join(nt, "dz_export", "atlas_ws_token.txt"), "w").write(tok_ws)
        open(os.path.join(out, "MGC 12-26 Nymex_Sim101_Position.txt"), "w").write("FLAT;0;0")
        received = []
        threading.Thread(target=mock_ws, args=(port + 1, tok_ws, received, stop), daemon=True).start()
        svc = start(root, port)
        big = dict(base, task_id="budget_big", optimize={"stop_ticks": list(range(100, 300)), "be_offset_ticks": list(range(1, 101))}, max_trials=20000)
        c, b, _ = api.call("POST", "/task", big)
        check("Э-Т1: задача за 4σ — отказ", c == 409 and "Э-Т1" in b.get("error", ""), b.get("error", "")[:140])
        c, b, _ = api.call("POST", "/task", dict(big, task_id="budget_override", budget_override="проверка замка службы: задача будет отменена сразу"))
        api.call("POST", "/cancel?id=budget_override")
        check("Э-Т1: снятие с причиной принято и записано", c == 200 and any("снят" in n for n in b["notes"]))
        wait_state(api, "budget_override", ("cancelled", "done", "failed"), 120)
        print("— Э-Т2 сторож рассинхрона")
        t0 = time.time()
        while time.time() - t0 < 30 and not api.call("GET", "/alarms")[1]["alarms"]:
            time.sleep(1)
        al = api.call("GET", "/alarms")[1]
        check("Э-Т2: стратегия LONG 3, счёт FLAT — тревога", bool(al["alarms"]) and al["alarms"][-1]["kind"] == "desync", str(al["alarms"][-1:])[:160])
        check("Э-Т2: пауза входов отправлена в сервер пульта", any(m.get("cmd") == "pause" and m.get("token") == tok_ws for m in received))
    finally:
        stop.set()
        try:
            os.killpg(svc.pid, signal.SIGINT)
            svc.wait(timeout=60)
        except Exception:
            pass
    bad = [r for r in RES if not r[1]]
    print(f"\nИТОГ: пройдено {len(RES) - len(bad)} из {len(RES)}" + ("" if not bad else "; провалы: " + "; ".join(r[0] for r in bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
