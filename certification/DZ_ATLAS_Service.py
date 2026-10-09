#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_ATLAS_Service.py — служба оптимизатора «Атласа»: работа без командной строки, v1.0 (2026-09-30)

  Пульт → POST /task → файл в task_queue → служба запускает оптимизатор (или проверку вперёд
  для плана WFA) → пульт читает GET /status и GET /summary?id=…

БЕЗОПАСНОСТЬ — как у сервера пульта: только 127.0.0.1; источник — только file://, null,
  app://atlas; ключ в заголовке X-Atlas-Token (файл atlas_service_token.txt рядом со службой).
ОЧЕРЕДЬ — task_queue/*.json → running/ → done/ либо failed/ (с хвостом ошибки). Состояние —
  results/_service_status.json; переживает перезапуск службы.

  Запуск: двойной щелчок по START_ATLAS_SERVICE.bat или python DZ_ATLAS_Service.py [--port 8090]
==========================================================================================
"""
import argparse, glob, json, os, secrets, shutil, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

VERSION = "DZ_ATLAS_Service-v1.0 (2026-09-30)"
HERE = os.path.dirname(os.path.abspath(__file__))
ORIGINS = ("null", "file://", "app://atlas")
LOCK = threading.Lock()


class Svc:
    def __init__(self, root, workers):
        self.root, self.workers = root, workers
        self.q = os.path.join(root, "task_queue"); self.res = os.path.join(root, "results")
        for d in ("", "running", "done", "failed"): os.makedirs(os.path.join(self.q, d), exist_ok=True)
        os.makedirs(self.res, exist_ok=True)
        tf = os.path.join(root, "atlas_service_token.txt")
        if not os.path.exists(tf): open(tf, "w").write(secrets.token_hex(16))
        self.token = open(tf).read().strip()
        self.sf = os.path.join(self.res, "_service_status.json")
        self.status = json.load(open(self.sf, encoding="utf-8")) if os.path.exists(self.sf) else {}
        for f in glob.glob(os.path.join(self.q, "running", "*.json")):      # прерванные при остановке — снова в очередь
            shutil.move(f, os.path.join(self.q, os.path.basename(f)))

    def save(self):
        with LOCK:
            tmp = self.sf + ".tmp"; json.dump(self.status, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(tmp, self.sf)

    def enqueue(self, body):
        tid = body.get("plan_id") or body.get("task_id") or time.strftime("T%Y%m%d_%H%M%S")
        if not ("jobs" in body or "optimize" in body or "target" in body or "hypothesis" in body or "windows" in body):
            raise ValueError("это не задача оптимизатора и не план проверки вперёд")
        path = os.path.join(self.q, tid + ".json"); tmp = path + ".tmp"
        json.dump(body, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2); os.replace(tmp, path)
        self.status[tid] = {"state": "queued", "kind": "wfa" if "windows" in body else "task", "queued": time.strftime("%Y-%m-%d %H:%M:%S")}
        self.save(); return tid

    def worker(self):
        while True:
            files = sorted(glob.glob(os.path.join(self.q, "*.json")), key=os.path.getmtime)
            if not files: time.sleep(1.0); continue
            f = files[0]; tid = os.path.splitext(os.path.basename(f))[0]
            run = os.path.join(self.q, "running", os.path.basename(f)); shutil.move(f, run)
            wfa = "windows" in json.load(open(run, encoding="utf-8"))
            self.status.setdefault(tid, {}).update(state="running", started=time.strftime("%Y-%m-%d %H:%M:%S"), kind="wfa" if wfa else "task"); self.save()
            cmd = ([sys.executable, os.path.join(HERE, "DZ_OPT_WFA.py"), "--plan", run, "--results", self.res, "--workers", str(self.workers)] if wfa else
                   [sys.executable, os.path.join(HERE, "DZ_OPT_Engine_S021.py"), "run", "--task", run, "--results", self.res, "--workers", str(self.workers)])
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root)
            ok = r.returncode == 0
            shutil.move(run, os.path.join(self.q, "done" if ok else "failed", os.path.basename(run)))
            st = {"state": "done" if ok else "failed", "finished": time.strftime("%Y-%m-%d %H:%M:%S")}
            if ok and not wfa:
                s = json.load(open(os.path.join(self.res, tid, "summary.json"), encoding="utf-8"))
                st.update({k: s.get(k) for k in ("objective", "deflated_sharpe", "pbo", "verdict", "trials_this_task", "data_sha256")}, best=s.get("best_selected"))
            elif ok:
                w = os.path.join(self.res, f"wfa_{tid}_wfa.json") if not tid.startswith("wfa_") else os.path.join(self.res, f"{tid}_wfa.json")
                if os.path.exists(w): st["wfa"] = json.load(open(w, encoding="utf-8"))["summary"]
            else:
                st["error"] = (r.stderr or r.stdout)[-1500:]
            self.status[tid].update(st); self.save()


def handler(svc):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _origin_ok(self):
            o = self.headers.get("Origin")
            return o is None or o == "null" or o.startswith(ORIGINS)
        def _send(self, code, obj):
            b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin") or "null")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        def _guard(self):
            if not self._origin_ok(): self._send(403, {"error": "чужой источник"}); return False
            if self.headers.get("X-Atlas-Token") != svc.token: self._send(401, {"error": "неверный ключ"}); return False
            return True
        def do_OPTIONS(self):
            self.send_response(204 if self._origin_ok() else 403)
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin") or "null")
            self.send_header("Access-Control-Allow-Headers", "X-Atlas-Token, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST"); self.end_headers()
        def do_GET(self):
            if not self._guard(): return
            u = urlparse(self.path)
            if u.path == "/status": self._send(200, {"service": VERSION, "jobs": svc.status})
            elif u.path == "/summary":
                tid = (parse_qs(u.query).get("id") or [""])[0]; p = os.path.join(svc.res, os.path.basename(tid), "summary.json")
                self._send(200, json.load(open(p, encoding="utf-8"))) if os.path.exists(p) else self._send(404, {"error": "нет итога"})
            else: self._send(404, {"error": "нет такого адреса"})
        def do_POST(self):
            if not self._guard(): return
            if urlparse(self.path).path != "/task": self._send(404, {"error": "нет такого адреса"}); return
            n = int(self.headers.get("Content-Length") or 0)
            if n > 1_000_000: self._send(413, {"error": "слишком большая задача"}); return
            try: self._send(200, {"queued": svc.enqueue(json.loads(self.rfile.read(n).decode("utf-8")))})
            except Exception as ex: self._send(400, {"error": str(ex)})
    return H


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--root", default="."); ap.add_argument("--port", type=int, default=8090); ap.add_argument("--workers", type=int, default=0)
    a = ap.parse_args()
    svc = Svc(os.path.abspath(a.root), a.workers)
    threading.Thread(target=svc.worker, daemon=True).start()
    print(f"{VERSION}\n  адрес http://127.0.0.1:{a.port}  ключ: {os.path.join(svc.root, 'atlas_service_token.txt')}")
    ThreadingHTTPServer(("127.0.0.1", a.port), handler(svc)).serve_forever()


if __name__ == "__main__":
    main()
