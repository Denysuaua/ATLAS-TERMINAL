#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_ATLAS_Service_v2.py — служба терминала «Атлас», v2.0 (2026-10-05)

Одна служба на всё, что пульт делает без командной строки: очередь оптимизатора и проверки
вперёд, результаты, реестр испытаний, сертификаты и ворота выпуска, пресеты для коммутатора,
позиции счёта из папки outgoing NinjaTrader, аварийные команды OIF, бары для графика из
сертифицированных данных. Совместима с пультом v1: адреса /task, /status, /summary прежние.

ЧТО ИСПРАВЛЕНО ПРОТИВ v1 (ревизия 2026-10-05)
  • Поток очереди не умирает: сбой задачи — «ошибка» этой задачи, очередь работает дальше.
  • id задачи проверяется; повтор id — отказ 409, прежние результаты не перезаписываются.
  • Задача, прерванная остановкой службы, не перезапускается молча — состояние «прервана».
  • Отмена, предельное время, журнал расчёта каждой задачи (results/_logs/<id>.log).
  • Данные — только символ сертифицированных данных; поля "cache" и "data_root" отвергаются:
    в v1 задача с "cache" считалась на несертифицированном файле при проверенном сертификате.
  • Единицы: инструмент подставляется по символу данных, расхождение с профилем — предупреждение.
  • Замок отложенной выборки (по умолчанию с 2022-01-01): задача без конца периода обрезается
    до даты замка с пометкой; явный заход за дату — отказ; вскрытие — только с причиной.
  • Пресет — формулой оптимизатора nt_values (с nt_fixed и nt_expr), проверкой по схеме меню
    и защитным списком коммутатора; целые пишутся без дробной точки; страж догмы [MOD1].
  • Ворота выпуска — из настоящих проверок; ворота 9 больше не зависят от Excel.
  • До первой задачи проверяется, что интерпретатор видит numpy и pandas (сбой v1: «No module
    named numpy» у шести задач).

БЕЗОПАСНОСТЬ. Только 127.0.0.1; Origin — ровно null, file:// или app://atlas; ключ в заголовке
X-Atlas-Token (файл atlas_service_token.txt); тело запроса ≤ 1 МБ. Аварийные команды — со словом
подтверждения, не чаще раза в 3 с; поля OIF — без «;» и перевода строки. В службе НЕТ команд,
которые включают торговлю, меняют режим без ордеров [E01], ключи или разрешения пульта.

ЭКСПЕРИМЕНТЫ — выключены в DZ_ATLAS_Service_v2.config.json
  Э-Т1 «бюджетный замок» (budget_lock): отказ в постановке задачи, если порог «случайного
        лучшего» после неё превысит sigma (4σ) или исчерпан бюджет испытаний стратегии.
  Э-Т2 «сторож рассинхрона» (desync_watch): позиция стратегии из её сервера пульта против
        позиции счёта из outgoing; расхождение дольше grace_sec — тревога, по желанию — пауза входов.

  Запуск: START_ATLAS_SERVICE_v2.bat  или  python DZ_ATLAS_Service_v2.py [--port 8090]
==========================================================================================
"""
import argparse, base64, dataclasses, glob, hashlib, hmac, importlib.util, json, math, os, re, secrets
import shutil, socket, struct, subprocess, sys, threading, time, traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from statistics import NormalDist
from urllib.parse import urlparse, parse_qs

VERSION = "DZ_ATLAS_Service-v2.0 (2026-10-05)"
HERE = os.path.dirname(os.path.abspath(__file__))
ALLOWED_ORIGINS = ("null", "file://", "app://atlas")
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]{0,79}")
SYM_RE = re.compile(r"[A-Za-z0-9_]{1,16}")
OIF_RE = re.compile(r"[A-Za-z0-9 ._\-]{1,64}")
CONS_RE = re.compile(r"\s*([\w.]+)\s*(<=|>=|<|>)\s*([\w.]+)\s*")
PRESET_DENIED = ("DryRunMode", "WsEnabled", "WsAllowCommands", "ExportSchema", "PresetFile")   # как PresetDenied коммутатора
OBJECTIVES = ("SharpeDaily", "SharpeAnnual", "SortinoAnnual", "NetProfit", "ProfitFactor")
QUEUE_DIRS = ("running", "done", "failed", "cancelled", "interrupted")
SETS = ("best_selected", "best_plateau", "best_raw")
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
PLACEHOLDER_BYTES = 600
MAX_BODY = 1_000_000

DEFAULT_CONFIG = {
    "port": 8090,
    "workers": 0,
    "python": "",                                   # пусто — тот же интерпретатор, что у службы
    "nt_root": "~/Documents/NinjaTrader 8",
    "engine": "DZ_OPT_Engine_S021.py",
    "wfa": "DZ_OPT_WFA.py",
    "reference": "DZ_BT_DualBreakout_S021.py",
    "graph": "DZ_OPT_Graph_DualBreakout.json",
    "registry": "trials_registry.csv",
    "data_roots": ["data_certified", "data_certified_v2"],
    "strategy_dir": "strategies_vault/DZ_S021",
    "holdout_from": "2022-01-01",
    "holdout_policy": "clip",                       # clip — обрезать задачу без конца периода; refuse — отказ
    "task_timeout_min": 1440,
    "allow_uncertified_data": False,
    "min_trades_for_evidence": 150,
    "dogma_guard": True,
    "emergency": {"enabled": True, "wait_sec": 10, "flat_wait_sec": 15},
    "budget_lock": {"enabled": False, "sigma": 4.0, "budgets": {}},
    "desync_watch": {"enabled": False, "ws_port": 8088, "account": "", "instrument_prefix": "MGC",
                     "grace_sec": 20, "action": "alarm"},
}


# ======================================================================================
# 1. ОБЩИЕ ФУНКЦИИ — ими же пользуется DZ_HOUSE_Order_S021.py: одна проверка, один источник
# ======================================================================================

def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def iso_utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json_atomic(path, obj, indent=1):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def merge(base, over):
    out = json.loads(json.dumps(base))
    for k, v in (over or {}).items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def child_env(extra=None, drop=()):
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"                         # журналы задач по-русски не ломают cp1252
    env["PYTHONIOENCODING"] = "utf-8"
    for k in drop:
        env.pop(k, None)
    env.update(extra or {})
    return env


def run_script(root, python, args, timeout=900):
    """Скрипт проекта отдельным процессом: код возврата и хвост вывода."""
    try:
        r = subprocess.run([python] + args, cwd=root, capture_output=True, timeout=timeout, env=child_env())
        out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
        return r.returncode, out.strip()[-3000:]
    except subprocess.TimeoutExpired:
        return 124, f"превышено время {timeout} с"
    except OSError as ex:
        return 127, f"не запущен: {ex}"


def emax_sigma(n, engine=None):
    """
    Ожидаемый максимум n испытаний без преимущества в единицах σ(Шарпа). Формула — оптимизатора:
    SR₀ функции deflated_sharpe при Var[SR] = 1 (Bailey & López de Prado). Без оптимизатора —
    та же формула напрямую; источник указывается в ответе.
    """
    n = int(n)
    if n < 2:
        return 0.0
    if engine is not None:
        return float(engine.deflated_sharpe(0.0, 1.0, n, 10, 0.0, 3.0)[1])
    nd, g = NormalDist(), 0.5772156649015329
    return (1 - g) * nd.inv_cdf(1 - 1 / n) + g * nd.inv_cdf(1 - 1 / (n * math.e))


def trials_to_sigma(target, engine=None):
    """Наименьшее число испытаний, при котором порог «случайного лучшего» достигает target σ."""
    lo, hi = 2, 4
    while emax_sigma(hi, engine) < target:
        lo, hi = hi, hi * 2
        if hi > 10 ** 13:
            return None
    while lo < hi:
        mid = (lo + hi) // 2
        if emax_sigma(mid, engine) >= target:
            hi = mid
        else:
            lo = mid + 1
    return lo


def htf_anchor_check(npz_path, minutes, anchor_hour=17):
    """Доля старших баров, открытых по сетке от anchor_hour по Чикаго (как строит NinjaTrader)."""
    import numpy as np
    import pandas as pd
    z = np.load(npz_path, allow_pickle=False)
    t = z["t_open"] if "t_open" in z.files else z["t"]
    ct = pd.to_datetime(t, utc=True).tz_convert("America/Chicago")
    off = (np.asarray(ct.hour) * 60 + np.asarray(ct.minute) - anchor_hour * 60) % minutes
    return {"file": os.path.basename(npz_path), "bars": int(len(t)), "on_grid": round(float((off == 0).mean()), 4),
            "anchor": f"{anchor_hour:02d}:00 America/Chicago"}


def vault_vs_passport(root, strategy_dir):
    """Полнота хранилища стратегии против паспорта сборки: тот ли код лежит на ПК, что скомпилирован."""
    pp = read_json(os.path.join(root, "build_passport.json"))
    vault = os.path.join(root, strategy_dir)
    out = {"passport": bool(pp), "build_id": (pp or {}).get("build_id"), "taken_utc": (pp or {}).get("taken_utc"),
           "missing": [], "different": [], "same": []}
    for rel, meta in ((pp or {}).get("files") or {}).items():
        name = rel.replace("\\", "/").split("/")[-1]
        if not name.startswith("DZ_SW_"):
            continue
        p = os.path.join(vault, name)
        if not os.path.exists(p):
            out["missing"].append(name)
        elif sha256_file(p) != meta.get("sha256"):
            out["different"].append(name)
        else:
            out["same"].append(name)
    return out


def strategy_elements(root, strategy_dir):
    """Восемь элементов стратегии: размер файла; меньше PLACEHOLDER_BYTES — заглушка, а не документ."""
    vault = os.path.join(root, strategy_dir)
    el = read_json(os.path.join(vault, "STRATEGY_ELEMENTS.json"), {}) or {}
    rows = []
    for k, fname in el.items():
        p = os.path.join(vault, fname)
        size = os.path.getsize(p) if os.path.exists(p) else None
        rows.append({"element": k, "file": fname, "bytes": size,
                     "placeholder": size is not None and size < PLACEHOLDER_BYTES and not fname.endswith(".cs")})
    return rows


def passport_vs_nt(root, nt_root):
    """Сверка паспорта сборки с исходниками в терминале сейчас (только чтение, как DZ_SYS_Bridge check)."""
    pp = read_json(os.path.join(root, "build_passport.json"))
    if not pp:
        return {"ok": False, "text": "нет build_passport.json — снимите паспорт: DZ_SYS_Bridge.py snapshot"}
    if not os.path.isdir(nt_root):
        return {"ok": None, "text": f"папка NinjaTrader не найдена: {nt_root}"}
    now = {}
    for sub, pref in (("Strategies", "DZ_SW_"), ("Indicators", "DZ_IND_")):
        d = os.path.join(nt_root, "bin", "Custom", sub)
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.endswith(".cs") and f.startswith(pref):
                    now[f"bin\\Custom\\{sub}\\{f}"] = sha256_file(os.path.join(d, f))
    was = {k: v["sha256"] for k, v in pp["files"].items()}
    changed = sorted(k for k in was.keys() & now.keys() if was[k] != now[k])
    added, removed = sorted(now.keys() - was.keys()), sorted(was.keys() - now.keys())
    dll = os.path.join(nt_root, "bin", "Custom", "NinjaTrader.Custom.dll")
    stale = []
    if os.path.exists(dll):
        dm = os.path.getmtime(dll)
        stale = [k for k in now if os.path.getmtime(os.path.join(nt_root, k.replace("\\", os.sep))) > dm]
    ok = not (changed or added or removed or stale or pp.get("warnings"))
    return {"ok": ok, "build_id": pp.get("build_id"), "changed": changed, "added": added, "removed": removed,
            "newer_than_dll": stale, "passport_warnings": pp.get("warnings") or [],
            "text": "терминал совпадает с паспортом" if ok else "терминал и паспорт расходятся"}


def stamps(root):
    """Штампы шлюза сертификации и проверка, что заштампован настоящий отчёт, а не демонстрация."""
    out = []
    for p in sorted(set(glob.glob(os.path.join(root, "*.stamped.json")) + glob.glob(os.path.join(root, "results", "*", "*.stamped.json")))):
        s = read_json(p, {}) or {}
        body = s.get("СЕРТИФИКАТ_БЭКТЕСТА") or {}
        rep = os.path.join(os.path.dirname(p), (body.get("отчёт") or {}).get("файл", ""))
        trades = None
        try:
            with open(rep, encoding="utf-8-sig") as f:
                for line in f:
                    k, _, v = line.strip().partition(",")
                    if k == "Trades":
                        trades = int(float(v))
        except (OSError, ValueError):
            pass
        out.append({"file": os.path.relpath(p, root), "status": body.get("СТАТУС", ""), "utc": body.get("время_utc"),
                    "report": os.path.relpath(rep, root), "report_trades": trades})
    return out


def accept_reports(root):
    out = []
    for p in sorted(set(glob.glob(os.path.join(root, "accept_report*.json")) + glob.glob(os.path.join(root, "results", "**", "accept_report*.json"), recursive=True))):
        r = read_json(p, {}) or {}
        if str(r.get("tool", "")).startswith("DZ_ACCEPT"):
            out.append({"file": os.path.relpath(p, root), "passed": bool(r.get("passed")), "hub_version": r.get("hub_version"),
                        "mtime_utc": iso_utc(os.path.getmtime(p))})
    return sorted(out, key=lambda r: r["mtime_utc"])


def compute_gates(root, cfg, verify_results, decisions):
    """
    Десять ворот выпуска (DZ_ATLAS_Выпуск_Сборки.md) из настоящих проверок. pass — пройдены;
    fail — нет, с причиной; manual — подтверждает человек; unknown — проверить отсюда нельзя.
    """
    sd = cfg["strategy_dir"]
    G = []

    def gate(n, name, status, evidence):
        G.append({"n": n, "name": name, "status": status, "evidence": evidence})

    d1 = decisions.get(1)
    gate(1, "Чистая компиляция", "manual" if d1 else "unknown",
         f"отмечено оператором {d1['utc']}: {d1['text']}" if d1 else "проверяется только в NinjaTrader (F5); отметка — POST /decision {gate:1}")

    pv = verify_results.get("passport") or {}
    vp = vault_vs_passport(root, sd)
    why = []
    if pv.get("ok") is False:
        why.append(pv.get("text", ""))
    if vp["missing"]:
        why.append(f"в хранилище нет {len(vp['missing'])} файлов из паспорта: {', '.join(vp['missing'])}")
    if vp["different"]:
        why.append(f"отличаются от паспорта: {', '.join(vp['different'])}")
    if not vp["passport"]:
        why.append("нет паспорта сборки")
    gate(2, "Паспорт сборки", "fail" if why else ("pass" if pv.get("ok") else "unknown"),
         "; ".join(why) if why else (pv.get("text") or "терминал недоступен отсюда: POST /verify?what=passport на машине с NinjaTrader"))

    sv = verify_results.get("strategy") or {}
    ph = [r["element"] for r in strategy_elements(root, sd) if r["placeholder"]]
    why = []
    if sv and not sv.get("ok"):
        why.append("проверка сертификата: " + sv.get("text", "")[-300:])
    if ph:
        why.append("элементы-заглушки: " + ", ".join(ph))
    gate(3, "Сертификат стратегии", "fail" if why else ("pass" if sv.get("ok") else "unknown"),
         "; ".join(why) if why else ("сертификат цел" if sv else "не проверялся: POST /verify?what=strategy"))

    why, ok_data = [], False
    inst = glob.glob(os.path.join(root, "certified_vault", "*", "*.instrument.cert.json"))
    if not inst:
        why.append("нет паспорта инструмента")
    dv = [v for k, v in verify_results.items() if k.startswith("data:")]
    if not dv:
        why.append("сертификат данных не проверялся: POST /verify?what=data&symbol=MGC")
    elif not all(v.get("ok") for v in dv):
        why.append("сертификат данных не прошёл проверку")
    else:
        ok_data = True
    gate(4, "Паспорт инструмента и данные", "fail" if not inst else ("unknown" if not dv else ("pass" if ok_data else "fail")),
         "; ".join(why) if why else f"паспортов: {len(inst)}; данные: " + ", ".join(k for k in verify_results if k.startswith("data:")))

    tc = glob.glob(os.path.join(root, "certified_vault", "*", "templates", "*.cert.json")) + glob.glob(os.path.join(root, "*.cert.json"))
    ranks, notes = [], []
    for p in tc:
        c = read_json(p, {}) or {}
        if c.get("certificate", "").startswith("DZ-TEMPLATE-CERT"):
            tf = c.get("template_file", "")
            ranks.append(c.get("rank"))
            if not tf.lower().endswith(".xml"):
                notes.append(f"{tf}: не шаблон NinjaTrader (.xml), а список из {c.get('properties_in_template')} свойств")
    notes = list(dict.fromkeys(notes))
    gate(5, "Шаблон", "pass" if ranks and not notes else "fail",
         ("; ".join(notes) if notes else f"ранги: {ranks}") if ranks else "нет сертификата шаблона")

    ev = verify_results.get("emulator") or {}
    st = stamps(root)
    lock = os.path.exists(os.path.join(root, "DZ_TERM_Lock.json"))
    real = [s for s in st if "СЕРТИФИЦИРОВАНО" in s["status"] and (s["report_trades"] or 0) >= cfg["min_trades_for_evidence"]]
    why = []
    if not lock:
        why.append("нет печати эмулятора DZ_TERM_Lock.json — эмулятор не запустится")
    elif ev and not ev.get("ok"):
        why.append("печать эмулятора не проходит проверку")
    if not real:
        demo = [s for s in st if "СЕРТИФИЦИРОВАНО" in s["status"]]
        why.append("штамп стоит на демонстрационном отчёте из " + ", ".join(str(s["report_trades"]) for s in demo) + " сделок"
                   if demo else "нет заштампованного отчёта")
    gate(6, "Бэктест", "fail" if why else "pass", "; ".join(why) if why else f"штампов на отчётах ≥ {cfg['min_trades_for_evidence']} сделок: {len(real)}")

    green = [p for p in tc if (read_json(p, {}) or {}).get("rank") in ("GREEN", "GOLD")]
    gate(7, "Зелёный ранг", "pass" if green else "fail", f"сертификатов: {len(green)}" if green else "зелёного сертификата шаблона нет")

    acc = accept_reports(root)
    gate(8, "Воспроизведение рынка", "pass" if acc and acc[-1]["passed"] else "fail",
         (f"{acc[-1]['file']}: {'пройдена' if acc[-1]['passed'] else 'не пройдена'}, {acc[-1]['hub_version']}") if acc
         else "нет отчёта приёмки: DZ_ACCEPT_S021.py check --output <Output NinjaTrader>")

    prev = [g for g in G if g["n"] <= 8]
    bad = [str(g["n"]) for g in prev if g["status"] not in ("pass", "manual")]
    gate(9, "Пульт (вместо Excel)", "fail" if bad else "pass",
         "🔴 реальный счёт не допущен: ворота " + ", ".join(bad) + " не пройдены" if bad else "🟢 ворота 1–8 пройдены: решение — за руководителем")

    d10 = decisions.get(10)
    gate(10, "Решение руководителя", "manual" if d10 else "unknown",
         f"{d10['utc']}: {d10['text']}" if d10 else "решения нет. Служба только записывает решение; торговлю она не включает")
    return G


# ======================================================================================
# 2. МИНИМАЛЬНЫЙ КЛИЕНТ WEBSOCKET — для Э-Т2 (сервер пульта стратегии, RFC 6455)
# ======================================================================================

class MiniWs:
    def __init__(self, port, origin="app://atlas", timeout=10.0):
        self.port, self.origin, self.timeout, self.sock = port, origin, timeout, None

    def connect(self):
        s = socket.create_connection(("127.0.0.1", self.port), timeout=self.timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        s.sendall((f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nOrigin: {self.origin}\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            ch = s.recv(1)
            if not ch or len(head) > 8192:
                raise ConnectionError("рукопожатие оборвано")
            head += ch
        text = head.decode("latin-1")
        acc = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        if " 101 " not in text.split("\r\n")[0] or acc not in text:
            raise ConnectionError("сервер не принял соединение: " + text.split("\r\n")[0])
        self.sock = s

    def _exact(self, n):
        b = b""
        while len(b) < n:
            c = self.sock.recv(n - len(b))
            if not c:
                raise ConnectionError("соединение закрыто")
            b += c
        return b

    def send_text(self, text):
        p = text.encode("utf-8")
        mask = os.urandom(4)
        if len(p) < 126:
            h = bytes([0x81, 0x80 | len(p)])
        elif len(p) < 65536:
            h = bytes([0x81, 0x80 | 126]) + struct.pack(">H", len(p))
        else:
            h = bytes([0x81, 0x80 | 127]) + struct.pack(">Q", len(p))
        self.sock.sendall(h + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(p)))

    def recv_text(self):
        while True:
            h = self._exact(2)
            op, n = h[0] & 0x0F, h[1] & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._exact(8))[0]
            mask = self._exact(4) if h[1] & 0x80 else None
            p = self._exact(n) if n else b""
            if mask:
                p = bytes(b ^ mask[i % 4] for i, b in enumerate(p))
            if op == 0x8:
                raise ConnectionError("сервер закрыл соединение")
            if op == 0x1:
                return p.decode("utf-8", "replace")

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass


# ======================================================================================
# 3. СЛУЖБА
# ======================================================================================

class Refuse(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


def need(x, msg, code=404):
    if not x:
        raise Refuse(msg, code)
    return x


def kill_tree(proc):
    """Остановить задачу вместе с рабочими процессами оптимизатора."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=60)
        else:
            import signal
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


class Service:
    def __init__(self, root, cfg):
        self.root, self.cfg = root, cfg
        self.lock = threading.RLock()
        self.vlock = threading.Lock()
        self.stop_evt = threading.Event()
        self.q = os.path.join(root, "task_queue")
        self.res = os.path.join(root, "results")
        self.logs = os.path.join(self.res, "_logs")
        for d in ("",) + QUEUE_DIRS:
            os.makedirs(os.path.join(self.q, d), exist_ok=True)
        os.makedirs(self.logs, exist_ok=True)
        self.journal_path = os.path.join(self.res, "_service_journal.jsonl")
        self.status_path = os.path.join(self.res, "_service_status_v2.json")
        self.nt_root = os.path.expanduser(cfg["nt_root"])
        self.python = cfg.get("python") or sys.executable
        self.token = self._load_token()
        self.status = read_json(self.status_path, {}) or {}
        self.current = None
        self.alarms = []
        self.verify_results = read_json(os.path.join(self.res, "_service_verify.json"), {}) or {}
        self.desync = {"enabled": bool(cfg["desync_watch"].get("enabled")), "state": "выключен"}
        self._mods, self._m1 = {}, {}
        self.last_emergency = 0.0
        self.worker_beat = 0.0
        self.deps = self._check_deps()
        self._import_v1_status()
        self._recover()

    # ---------- основа ----------
    def _load_token(self):
        tf = os.path.join(self.root, "atlas_service_token.txt")
        if not os.path.exists(tf):
            with open(tf, "w", encoding="utf-8") as f:
                f.write(secrets.token_hex(32))
        with open(tf, encoding="utf-8") as f:
            tok = f.read().strip()
        if len(tok) < 32:
            raise SystemExit(f"ОТКАЗ: ключ в {tf} короче 32 знаков — сгенерируйте новый: DZ_HOUSE_Order_S021.py rotate-token")
        return tok

    def journal(self, event, **kw):
        rec = {"utc": utc_now(), "event": event, **kw}
        with self.lock:
            with open(self.journal_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                f.flush()
                os.fsync(f.fileno())
        return rec

    def _set(self, tid, **kw):
        with self.lock:
            self.status.setdefault(tid, {}).update(kw)
            write_json_atomic(self.status_path, self.status)

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.status, default=str))

    def mod(self, key):
        """Модули проекта загружаются лениво и один раз: оптимизатор, эталон, очиститель v2, граф."""
        with self.lock:
            if key not in self._mods:
                if key == "graph":
                    self._mods[key] = read_json(os.path.join(self.root, self.cfg["graph"]))
                    if not self._mods[key]:
                        raise Refuse(f"граф {self.cfg['graph']} не читается", 500)
                else:
                    f = {"engine": self.cfg["engine"], "reference": self.cfg["reference"], "san2": "DZ_DATA_Sanitizer_v2.py"}[key]
                    self._mods[key] = load_module(os.path.join(self.root, f), "dz_svc_" + key)
            return self._mods[key]

    def engine_or_none(self):
        try:
            return self.mod("engine")
        except Exception:
            return None

    def _check_deps(self):
        rc, out = run_script(self.root, self.python, ["-c", "import numpy, pandas; print(numpy.__version__, pandas.__version__)"], 120)
        ok = rc == 0
        return {"ok": ok, "python": self.python, "versions": out if ok else None,
                "error": None if ok else f"интерпретатор задач не видит numpy/pandas: {out[-300:]} — установите: "
                                           f"\"{self.python}\" -m pip install numpy pandas openpyxl, либо укажите \"python\" в конфигурации"}

    def _import_v1_status(self):
        v1 = read_json(os.path.join(self.res, "_service_status.json"), {}) or {}
        n = 0
        for tid, rec in v1.items():
            if tid in self.status:
                continue
            rec = dict(rec, source="служба v1")
            if rec.get("state") in ("queued", "running"):
                for d, st in (("done", "done"), ("failed", "failed")):
                    if os.path.exists(os.path.join(self.q, d, tid + ".json")):
                        rec.update(state=st, note=f"состояние сверено по папке {d}: в файле v1 стояло «{rec.get('state')}»")
                        break
            self.status[tid] = rec
            n += 1
        if n:
            write_json_atomic(self.status_path, self.status)
            self.journal("import_v1", records=n)

    def _recover(self):
        for f in glob.glob(os.path.join(self.q, "running", "*.json")):
            tid = os.path.splitext(os.path.basename(f))[0]
            os.replace(f, os.path.join(self.q, "interrupted", os.path.basename(f)))
            self._set(tid, state="interrupted", finished=local_now(),
                      note="служба остановилась во время расчёта; результат не принят. Повтор — POST /requeue (новый id)")
            self.journal("interrupted", id=tid)
        for f in sorted(glob.glob(os.path.join(self.q, "*.json")), key=os.path.getmtime):
            tid = os.path.splitext(os.path.basename(f))[0]
            if (self.status.get(tid) or {}).get("state") == "queued" and self.status[tid].get("version") == VERSION:
                continue
            try:                                     # задача из очереди v1: проверяется заново
                body = read_json(f)
                if body is None:
                    raise Refuse("файл не JSON")
                notes = []
                kind = "wfa" if "windows" in body else "task"
                self._validate(body, kind, notes)
                write_json_atomic(f, body, indent=2)
                self._set(tid, state="queued", kind=kind, queued=local_now(), queued_utc=utc_now(), notes=notes, version=VERSION)
            except Refuse as ex:
                os.replace(f, os.path.join(self.q, "failed", os.path.basename(f)))
                self._set(tid, state="failed", finished=local_now(), error=f"не прошла проверку службы v2: {ex}")

    # ---------- проверка задачи ----------
    def _id_taken(self, tid):
        if tid in self.status:
            return True
        if any(os.path.exists(os.path.join(self.q, d, tid + ".json")) for d in ("",) + QUEUE_DIRS):
            return True
        if os.path.exists(os.path.join(self.res, tid)) or os.path.exists(os.path.join(self.res, tid + "_wfa.json")):
            return True
        return bool(glob.glob(os.path.join(self.res, glob.escape(tid) + "_w[0-9][0-9]_*")))

    def _date(self, s, what):
        try:
            return datetime.strptime(str(s)[:10], "%Y-%m-%d")
        except ValueError:
            raise Refuse(f"{what}: дата ГГГГ-ММ-ДД, получено «{s}»")

    def _validate(self, body, kind, notes):
        if kind == "wfa":
            t = body.get("task")
            if not isinstance(t, dict):
                raise Refuse("план проверки вперёд: нет объекта «task»")
            w = body.get("windows")
            if not isinstance(w, list) or not w or len(w) > 60:
                raise Refuse("план проверки вперёд: «windows» — от 1 до 60 окон")
            for i, win in enumerate(w, 1):
                try:
                    a, b = (self._date(x, f"окно {i}") for x in win["train"])
                    c, d = (self._date(x, f"окно {i}") for x in win["test"])
                except (KeyError, TypeError, ValueError):
                    raise Refuse(f"окно {i}: нужны train [начало, конец] и test [начало, конец]")
                if not (a < b <= c < d):
                    raise Refuse(f"окно {i}: обучение раньше проверки, начало раньше конца")
        else:
            t = body
        g = self.mod("graph")
        P = g["params"]
        d = t.get("data")
        if not (isinstance(d, str) and SYM_RE.fullmatch(d)) and not self.cfg["allow_uncertified_data"]:
            raise Refuse("«data» — только символ сертифицированных данных (например, MGC): прогон на "
                         "несертифицированных данных ничего не доказывает (проверка №1)")
        for k in ("cache", "data_root"):
            if k in t and not self.cfg["allow_uncertified_data"]:
                raise Refuse(f"поле «{k}» запрещено: оптимизатор считал бы не сертифицированный файл, а {t[k]}")
        if isinstance(d, str) and SYM_RE.fullmatch(d):
            if not os.path.exists(os.path.join(self.root, "data_certified", d, f"{d}_M1.npz")):
                raise Refuse(f"нет сертифицированных данных {d}: DZ_CERT_Data.py certify --symbol {d}")
            prof = (g.get("instrument_profiles") or {})
            if not t.get("instrument") and d in prof:
                t["instrument"] = d
                notes.append(f"инструмент подставлен по символу данных: профиль {d} {prof[d].get('reference')}")
            ref = (prof.get(t.get("instrument") or "") or {}).get("reference") or {}
            for k, v in (t.get("base") or {}).items():
                if k in ref and float(v) != float(ref[k]):
                    notes.append(f"ВНИМАНИЕ, единицы: base.{k} = {v}, в профиле {t.get('instrument')} — {ref[k]} (проверка №4)")
        mode = t.get("mode", "dev")
        if mode == "dev":
            opt = t.get("optimize")
            if not isinstance(opt, dict) or not opt:
                raise Refuse("режим dev: нужен непустой «optimize»")
            for k, v in opt.items():
                if k not in P:
                    raise Refuse(f"«{k}» нет в графе {self.cfg['graph']}: оптимизатор его не исполнит")
                if not isinstance(v, list) or not v or len(v) > 500 or not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
                    raise Refuse(f"«{k}»: список чисел, от 1 до 500 значений")
        elif mode == "param":
            tg = t.get("target")
            tg = [tg] if isinstance(tg, str) else tg
            if not isinstance(tg, list) or not tg or any(x not in P for x in tg):
                raise Refuse("режим param: «target» — параметры графа")
            if not isinstance(t.get("depth", 1), int) or not 0 <= t.get("depth", 1) <= 3:
                raise Refuse("режим param: «depth» от 0 до 3")
        elif mode == "system":
            if t.get("hypothesis") not in (g.get("groups") or {}):
                raise Refuse(f"режим system: гипотеза из графа: {list((g.get('groups') or {}).keys())}")
        else:
            raise Refuse("режим: dev, param или system")
        if t.get("objective", "SharpeDaily") not in OBJECTIVES:
            raise Refuse(f"цель — одна из {OBJECTIVES}: иначе оптимизатор упадёт после всех испытаний")
        mt = t.get("max_trials", 200)
        if not isinstance(mt, int) or isinstance(mt, bool) or not 1 <= mt <= 100000:
            raise Refuse("«max_trials» — целое от 1 до 100000")
        if t.get("profile", "chicago") not in ("chicago", "berlin"):
            raise Refuse("«profile» — chicago или berlin: профили не смешиваются")
        fields = {f.name for f in dataclasses.fields(self.mod("reference").Params)}
        unknown = [k for k in (t.get("base") or {}) if k not in fields]
        if unknown:
            raise Refuse(f"в «base» неизвестные эталону параметры: {unknown}")
        for c in t.get("constraints") or []:
            m = CONS_RE.fullmatch(str(c))
            if not m or any(not re.fullmatch(r"-?\d+(\.\d+)?", x) and x not in fields for x in (m.group(1), m.group(3))):
                raise Refuse(f"ограничение не разобрано или с неизвестным параметром: {c}")
        if kind == "task" and t.get("start") and t.get("end"):
            if self._date(t["start"], "start") >= self._date(t["end"], "end"):
                raise Refuse("начало периода не раньше конца")
        if t.get("nt_template") and not os.path.exists(os.path.join(self.root, t["nt_template"])):
            raise Refuse(f"шаблон {t['nt_template']} не найден")
        if "timeout_min" in body and not (isinstance(body["timeout_min"], (int, float)) and 1 <= body["timeout_min"] <= 10080):
            raise Refuse("«timeout_min» от 1 до 10080")
        self._holdout(body, kind, notes)
        self._budget(body, kind, notes)

    def _holdout(self, body, kind, notes):
        hf = self.cfg.get("holdout_from")
        if not hf:
            return
        hfd = self._date(hf, "holdout_from")
        if kind == "task":
            if body.get("unlock_holdout"):
                if len(str(body.get("unlock_reason") or "").strip()) < 10:
                    raise Refuse("вскрытие отложенной выборки — только с причиной «unlock_reason» (не короче 10 знаков)")
                notes.append(f"ВНИМАНИЕ: отложенная выборка с {hf} вскрывается — оптимизатор запишет это в holdout_log.csv")
                return
            end = body.get("end")
            if end is None:
                if self.cfg.get("holdout_policy") == "clip":
                    if body.get("start") and self._date(body["start"], "start") >= hfd:
                        raise Refuse(f"начало периода внутри отложенной выборки с {hf}")
                    body["end"], body["holdout_clipped"] = hf, True
                    notes.append(f"период обрезан замком отложенной выборки: конец {hf} (не включается)")
                else:
                    raise Refuse(f"задача без конца периода заходит в отложенную выборку с {hf}: укажите «end» не позже даты")
            elif self._date(end, "end") > hfd:
                raise Refuse(f"конец периода {end} заходит в отложенную выборку с {hf}: «end» не позже даты или "
                             f"«unlock_holdout»: true с причиной «unlock_reason»")
        else:
            last = max(self._date(w["test"][1], "окно") for w in body["windows"])
            if last > hfd:
                if not body.get("unlock_holdout") or len(str(body.get("unlock_reason") or "").strip()) < 10:
                    raise Refuse(f"окна плана заходят в отложенную выборку с {hf}: сдвиньте окна или "
                                 f"«unlock_holdout»: true с причиной «unlock_reason»")
                notes.append(f"ВНИМАНИЕ: план вскрывает отложенную выборку с {hf} — запись в holdout_log.csv")

    def trials_upper(self, body, kind):
        t = body["task"] if kind == "wfa" else body
        mt = int(t.get("max_trials", 200))
        if t.get("mode", "dev") == "dev":
            n = 1
            for v in t["optimize"].values():
                n *= len(set(v))
            mt = min(mt, n)
        return mt * len(body["windows"]) + len(body["windows"]) if kind == "wfa" else mt

    def registry_frame(self):
        import pandas as pd
        p = os.path.join(self.root, self.cfg["registry"])
        return pd.read_csv(p) if os.path.exists(p) else pd.DataFrame(columns=["TaskId", "Strategy", "Trials", "UTC"])

    def _budget(self, body, kind, notes):
        bl = self.cfg.get("budget_lock") or {}
        if not bl.get("enabled"):
            return
        strat = self.mod("graph")["strategy"]
        r = self.registry_frame()
        n_now = int(r[r.Strategy == strat].Trials.sum()) if len(r) else 0
        add = self.trials_upper(body, kind)
        e_after = emax_sigma(n_now + add, self.engine_or_none())
        sigma = float(bl.get("sigma", 4.0))
        budget = (bl.get("budgets") or {}).get(strat)
        problems = []
        if e_after > sigma:
            problems.append(f"порог «случайного лучшего» после задачи {e_after:.2f}σ > {sigma}σ (испытаний станет {n_now + add})")
        if budget and n_now + add > budget:
            problems.append(f"бюджет испытаний {strat} {budget}, станет {n_now + add}")
        if problems:
            reason = str(body.get("budget_override") or "").strip()
            if len(reason) < 20:
                raise Refuse("Э-Т1 бюджетный замок: " + "; ".join(problems) + ". Доказать уже нечего (критерии №1 и №7 "
                             "раздела «стоп»). Снять — «budget_override» с причиной не короче 20 знаков", 409)
            notes.append("Э-Т1: замок снят оператором: " + reason)
        notes.append(f"Э-Т1: испытаний {strat} станет {n_now + add}, порог {e_after:.2f}σ")

    # ---------- очередь ----------
    def enqueue(self, body):
        if not isinstance(body, dict):
            raise Refuse("задача — объект JSON")
        if not self.deps["ok"]:
            raise Refuse(self.deps["error"], 503)
        kind = "wfa" if "windows" in body else "task"
        if kind == "task" and not any(k in body for k in ("optimize", "target", "hypothesis")):
            raise Refuse("это не задача оптимизатора и не план проверки вперёд")
        key = "plan_id" if kind == "wfa" else "task_id"
        tid = str(body.get(key) or (("wfa_" if kind == "wfa" else "T") + time.strftime("%Y%m%d_%H%M%S")))
        if not ID_RE.fullmatch(tid):
            raise Refuse("id задачи: латиница, цифры, «_» и «-», до 80 знаков")
        body[key] = tid
        notes = []
        with self.lock:
            if self._id_taken(tid):
                raise Refuse(f"id {tid} уже использован: прежние результаты не перезаписываются — дайте новый id", 409)
            self._validate(body, kind, notes)
            write_json_atomic(os.path.join(self.q, tid + ".json"), body, indent=2)
            self._set(tid, state="queued", kind=kind, queued=local_now(), queued_utc=utc_now(), notes=notes, version=VERSION,
                      trials_upper=self.trials_upper(body, kind))
        self.journal("enqueue", id=tid, kind=kind, notes=notes)
        return tid, notes

    def cancel(self, tid):
        with self.lock:
            st = self.status.get(tid)
            if not st:
                raise Refuse("нет такой задачи", 404)
            if st.get("state") == "queued":
                src = os.path.join(self.q, tid + ".json")
                if os.path.exists(src):
                    os.replace(src, os.path.join(self.q, "cancelled", tid + ".json"))
                self._set(tid, state="cancelled", finished=local_now(), note="отменена до запуска")
            elif st.get("state") == "running" and self.current and self.current["id"] == tid:
                self.current["cancel"] = True
            else:
                raise Refuse(f"задача в состоянии «{st.get('state')}» не отменяется", 409)
        self.journal("cancel", id=tid)
        return st.get("state")

    def requeue(self, tid):
        st = self.status.get(tid) or {}
        if st.get("state") not in ("failed", "cancelled", "interrupted"):
            raise Refuse("повторяется только задача с ошибкой, отменённая или прерванная", 409)
        src = next((os.path.join(self.q, d, tid + ".json") for d in ("failed", "cancelled", "interrupted")
                    if os.path.exists(os.path.join(self.q, d, tid + ".json"))), None)
        if not src:
            raise Refuse("файл задачи не найден", 404)
        body = read_json(src)
        n = 2
        base = re.sub(r"_r\d+$", "", tid)
        while self._id_taken(f"{base}_r{n}"):
            n += 1
        body["plan_id" if "windows" in body else "task_id"] = f"{base}_r{n}"
        new, notes = self.enqueue(body)
        self.journal("requeue", id=tid, new=new)
        return new, notes

    def _next(self):
        with self.lock:
            q = sorted((v.get("queued_utc") or "", k) for k, v in self.status.items() if v.get("state") == "queued")
        for _, k in q:
            if os.path.exists(os.path.join(self.q, k + ".json")):
                return k
            self._set(k, state="failed", finished=local_now(), error="файл задачи пропал из очереди")
        return None

    def worker(self):
        while not self.stop_evt.is_set():
            try:
                self.worker_beat = time.time()
                tid = self._next() if self.deps["ok"] else None
                if tid is None:
                    self.stop_evt.wait(1.0)
                    continue
                self._run(tid)
            except Exception:
                self.journal("worker_error", error=traceback.format_exc()[-2000:])
                self.stop_evt.wait(2.0)

    def _command(self, kind, run, body):
        R = lambda k: os.path.join(self.root, self.cfg[k])
        hf = self.cfg.get("holdout_from")
        w = str(self.cfg.get("workers", 0))
        if kind == "task":
            cmd = [self.python, R("engine"), "run", "--task", run, "--results", self.res, "--workers", w,
                   "--registry", R("registry"), "--graph", R("graph"), "--ref", R("reference")]
            if hf:
                cmd += ["--holdout-from", hf]
            return cmd, child_env(drop=("DZ_HOLDOUT_FROM",))
        cmd = [self.python, R("wfa"), "--plan", run, "--results", self.res, "--workers", w, "--graph", R("graph")]
        if hf and body.get("unlock_holdout"):
            with open(os.path.join(self.root, "holdout_log.csv"), "a", encoding="utf-8") as f:
                f.write(f"{body['plan_id']},{hf},{utc_now()}\n")
            return cmd, child_env(drop=("DZ_HOLDOUT_FROM",))
        return cmd, child_env({"DZ_HOLDOUT_FROM": hf} if hf else None)

    def _tail(self, path, n=1500):
        try:
            with open(path, "rb") as f:
                f.seek(max(0, os.path.getsize(path) - n))
                return f.read().decode("utf-8", "replace")
        except OSError:
            return ""

    def _run(self, tid):
        src, run = os.path.join(self.q, tid + ".json"), os.path.join(self.q, "running", tid + ".json")
        os.replace(src, run)
        logp = os.path.join(self.logs, tid + ".log")
        try:
            body = read_json(run)
            if not isinstance(body, dict):
                raise ValueError("файл задачи не JSON")
            kind = "wfa" if "windows" in body else "task"
            cmd, env = self._command(kind, run, body)
        except Exception as ex:
            os.replace(run, os.path.join(self.q, "failed", tid + ".json"))
            self._set(tid, state="failed", finished=local_now(), error=f"задача не читается: {ex}")
            self.journal("failed", id=tid, error=str(ex))
            return
        self._set(tid, state="running", started=local_now(), started_utc=utc_now(), log=os.path.relpath(logp, self.root))
        self.journal("start", id=tid, cmd=cmd[1:])
        timeout = float(body.get("timeout_min") or self.cfg["task_timeout_min"]) * 60
        reason = None
        with open(logp, "ab") as lf:
            lf.write(f"# {VERSION} · {utc_now()} · {' '.join(cmd)}\n".encode("utf-8"))
            lf.flush()
            kw = {"cwd": self.root, "stdout": lf, "stderr": subprocess.STDOUT, "env": env}
            if os.name == "nt":
                kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kw["start_new_session"] = True
            t0 = time.time()
            try:
                proc = subprocess.Popen(cmd, **kw)
            except OSError as ex:
                proc = None
                lf.write(f"# запуск не удался: {ex}\n".encode("utf-8"))
        if proc is None:
            os.replace(run, os.path.join(self.q, "failed", tid + ".json"))
            self._set(tid, state="failed", finished=local_now(), error=f"оптимизатор не запустился: {self.python}")
            self.journal("failed", id=tid, error="popen")
            return
        with self.lock:
            self.current = {"id": tid, "proc": proc, "cancel": False, "t0": t0}
        while proc.poll() is None:
            self.worker_beat = time.time()
            if self.current["cancel"]:
                reason = "cancelled"
            elif time.time() - t0 > timeout:
                reason = "timeout"
            elif self.stop_evt.is_set():
                reason = "service_stop"
            if reason:
                kill_tree(proc)
                break
            time.sleep(0.5)
        try:
            rc = proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            rc = -9
        with self.lock:
            self.current = None
        fin = {"finished": local_now(), "finished_utc": utc_now(), "seconds": round(time.time() - t0, 1)}
        if reason == "cancelled":
            os.replace(run, os.path.join(self.q, "cancelled", tid + ".json"))
            self._set(tid, state="cancelled", note="отменена во время расчёта: итог не записан, испытания в реестр не внесены"
                      + ("; окна проверки вперёд, завершённые до отмены, — внесены" if kind == "wfa" else ""), **fin)
        elif reason == "service_stop":
            os.replace(run, os.path.join(self.q, "interrupted", tid + ".json"))
            self._set(tid, state="interrupted", note="служба остановлена во время расчёта", **fin)
        elif reason == "timeout":
            os.replace(run, os.path.join(self.q, "failed", tid + ".json"))
            self._set(tid, state="failed", error=f"превышено предельное время {timeout / 60:.0f} мин", **fin)
        elif rc == 0:
            st = self._result_fields(tid, kind)
            ok = st.pop("_ok")
            os.replace(run, os.path.join(self.q, "done" if ok else "failed", tid + ".json"))
            self._set(tid, state="done" if ok else "failed", **st, **fin)
        else:
            os.replace(run, os.path.join(self.q, "failed", tid + ".json"))
            self._set(tid, state="failed", error=self._tail(logp), returncode=rc, **fin)
        self.journal("finish", id=tid, state=self.status[tid]["state"], reason=reason)

    def _result_fields(self, tid, kind):
        if kind == "wfa":
            w = read_json(os.path.join(self.res, f"{tid}_wfa.json"))
            return {"_ok": True, "wfa": w["summary"]} if w else {"_ok": False, "error": "проверка вперёд завершилась без итога"}
        s = read_json(os.path.join(self.res, tid, "summary.json"))
        if not s:
            return {"_ok": False, "error": "оптимизатор завершился, но summary.json нет"}
        sel = "metrics_best_plateau" if s.get("best_selected") == s.get("best_plateau") else "metrics_best_raw"
        m = s.get(sel) or {}
        out = {"_ok": True, "best": s.get("best_selected"), "net": m.get("NetProfit"), "trades": m.get("Trades"),
               "pf": m.get("ProfitFactor")}
        out.update({k: s.get(k) for k in ("objective", "deflated_sharpe", "pbo", "verdict", "trials_this_task",
                                          "trials_cumulative", "data_sha256", "expected_max_sharpe_null", "period")})
        if (out["trades"] or 0) < self.cfg["min_trades_for_evidence"]:
            out["warning"] = f"сделок {out['trades']} < {self.cfg['min_trades_for_evidence']}: выборки не хватит для вывода (критерий №9)"
        return out

    # ---------- результаты ----------
    def _rid(self, q):
        tid = (q.get("id") or [""])[0]
        if not ID_RE.fullmatch(tid):
            raise Refuse("неверный id")
        return tid

    def results(self):
        rows, wfa = [], []
        for d in sorted(os.listdir(self.res)):
            p = os.path.join(self.res, d)
            if d.startswith("_") or not os.path.isdir(p):
                if d.endswith("_wfa.json"):
                    w = read_json(p, {}) or {}
                    wfa.append({"id": d[:-len("_wfa.json")], **(w.get("summary") or {})})
                continue
            s = read_json(os.path.join(p, "summary.json"))
            if not s:
                rows.append({"id": d, "summary": False})
                continue
            m = s.get("metrics_best_plateau" if s.get("best_selected") == s.get("best_plateau") else "metrics_best_raw") or {}
            rows.append({"id": d, "summary": True, "mode": s.get("mode"), "engine": s.get("engine"), "objective": s.get("objective"),
                         "trials": s.get("trials_this_task"), "trials_cumulative": s.get("trials_cumulative"),
                         "dsr": s.get("deflated_sharpe"), "pbo": s.get("pbo"), "threshold": s.get("expected_max_sharpe_null"),
                         "verdict": s.get("verdict"), "net": m.get("NetProfit"), "trades": m.get("Trades"),
                         "pf": m.get("ProfitFactor"), "max_dd": m.get("MaxDrawdown"), "period": s.get("period"),
                         "wfa_window": bool(re.search(r"_w\d\d_(train|test)$", d)),
                         "data_sha256": (s.get("data_sha256") or "")[:12],
                         "mtime_utc": iso_utc(os.path.getmtime(os.path.join(p, "summary.json")))})
        return {"results": rows, "wfa": wfa}

    def trades(self, tid, limit=3000):
        import pandas as pd
        p = os.path.join(self.res, tid, "best_trades.csv")
        if not os.path.exists(p):
            raise Refuse("нет best_trades.csv", 404)
        df = pd.read_csv(p)
        if df.empty:
            return {"id": tid, "count": 0}
        t_exit = pd.to_datetime(df["ExitTimeUTC"], utc=True, errors="coerce")
        t_ent = pd.to_datetime(df["EntryTimeUTC"], utc=True, errors="coerce")
        df = df.assign(x_exit=t_exit, x_entry=t_ent).sort_values("x_exit")
        cum = df["NetUSD"].astype(float).cumsum()
        dd = cum - cum.cummax()
        idx = list(range(0, len(df), max(1, len(df) // 2000))) + [len(df) - 1]
        eq = [[int(df["x_exit"].iloc[i].timestamp()), round(float(cum.iloc[i]), 2), round(float(dd.iloc[i]), 2)] for i in sorted(set(idx))
              if pd.notna(df["x_exit"].iloc[i])]
        years = []
        for y, g in df.groupby(df["x_exit"].dt.year):
            w, l = g.NetUSD[g.NetUSD > 0].sum(), -g.NetUSD[g.NetUSD < 0].sum()
            years.append({"year": int(y), "trades": int(len(g)), "net": round(float(g.NetUSD.sum()), 2),
                          "win_pct": round(float((g.NetUSD > 0).mean() * 100), 1), "pf": round(float(w / l), 3) if l > 0 else None})
        cap = {}
        if {"MFE_Ticks", "GrossTicks"} <= set(df.columns):
            mfe, gross = df.MFE_Ticks.astype(float), df.GrossTicks.astype(float)
            pos = mfe > 0
            win = pos & (gross > 0)
            cap = {"capture_total": round(float(gross[pos].sum() / mfe[pos].sum()), 4) if mfe[pos].sum() > 0 else None,
                   "capture_winners_median": round(float((gross[win] / mfe[win]).median()), 4) if win.any() else None,
                   "definition": "доля забранного потенциала: GrossTicks / MFE_Ticks (по сделкам с MFE > 0)"}
        ent = df.head(limit)
        cols = [c for c in ("Direction", "EntryPriceWithSlip", "ExitPriceWithSlip", "ExitReason", "NetUSD", "Profile", "Session") if c in df.columns]
        tr = [{"entry": int(r.x_entry.timestamp()) if pd.notna(r.x_entry) else None, "exit": int(r.x_exit.timestamp()) if pd.notna(r.x_exit) else None,
               **{c: (None if pd.isna(getattr(r, c)) else getattr(r, c)) for c in cols}} for r in ent.itertuples()]
        return {"id": tid, "count": int(len(df)), "net": round(float(cum.iloc[-1]), 2), "max_drawdown": round(float(dd.min()), 2),
                "equity": eq, "years": years, "mfe_capture": cap,
                "exit_reasons": {str(k): int(v) for k, v in df["ExitReason"].value_counts().items()} if "ExitReason" in df else {},
                "ambiguous_trades": int((df["AmbiguousBars"] > 0).sum()) if "AmbiguousBars" in df else None,
                "trades": tr, "trades_truncated": len(df) > limit}

    def trials(self, tid, limit=20000):
        import pandas as pd
        p = os.path.join(self.res, tid, "trials.csv")
        if not os.path.exists(p):
            raise Refuse("нет trials.csv", 404)
        df = pd.read_csv(p).head(limit)
        return {"id": tid, "columns": list(df.columns), "rows": json.loads(df.to_json(orient="values"))}

    def registry(self):
        r = self.registry_frame()
        eng = self.engine_or_none()
        sigma = float((self.cfg.get("budget_lock") or {}).get("sigma", 4.0))
        to = trials_to_sigma(sigma, eng)
        pool_p = os.path.splitext(os.path.join(self.root, self.cfg["registry"]))[0] + "_sr_pool.csv"
        pool = None
        if os.path.exists(pool_p):
            import pandas as pd
            pool = pd.read_csv(pool_p)
        by = {}
        for s, g in r.groupby("Strategy"):
            n = int(g.Trials.sum())
            e = emax_sigma(n, eng)
            rec = {"trials": n, "tasks": int(len(g)), "emax_sigma": round(e, 3), "stop_sigma": sigma,
                   "trials_left_to_stop": max(0, to - n) if to else None}
            if pool is not None:
                d = pool[pool.Strategy == s].SharpeDaily.astype(float).dropna()
                if len(d) > 1:
                    rec["sr_pool"] = {"size": int(len(d)), "sd": float(d.std(ddof=1))}
                    rec["threshold_sharpe_daily"] = round(float(d.std(ddof=1)) * e, 5)
            by[str(s)] = rec
        return {"total": int(r.Trials.sum()) if len(r) else 0, "by_strategy": by, "formula": "оптимизатор" if eng else "та же формула напрямую",
                "trials_to_stop_sigma": to, "last": json.loads(r.tail(30).to_json(orient="records"))}

    # ---------- сертификаты, проверки, ворота ----------
    def verify(self, what, q):
        with self.vlock:
            if what == "data":
                sym = (q.get("symbol") or ["MGC"])[0]
                rn = (q.get("root") or ["data_certified"])[0]
                if not SYM_RE.fullmatch(sym) or rn not in self.cfg["data_roots"]:
                    raise Refuse("неверный символ или корень данных")
                cert = os.path.join(rn, sym, f"{sym}_DATA_CERTIFICATE.json")
                if not os.path.exists(os.path.join(self.root, cert)):
                    raise Refuse(f"нет сертификата {cert}", 404)
                rc, out = run_script(self.root, self.python, ["DZ_CERT_Data.py", "verify", "--cert", cert])
                key = f"data:{rn}:{sym}"
            elif what == "strategy":
                rc, out = run_script(self.root, self.python, ["DZ_CERT_Strategy.py", "verify", "--dir", self.cfg["strategy_dir"]])
                key = "strategy"
            elif what == "emulator":
                if not os.path.exists(os.path.join(self.root, "DZ_TERM_Lock.json")):
                    rc, out = 1, "нет печати DZ_TERM_Lock.json — эмулятор не запустится"
                else:
                    rc, out = run_script(self.root, self.python, ["DZ_TERM_Emulator.py", "verify"])
                key = "emulator"
            elif what == "passport":
                r = passport_vs_nt(self.root, self.nt_root)
                rc, out, key = (0 if r["ok"] else 1), json.dumps(r, ensure_ascii=False), "passport"
                self.verify_results[key] = dict(r, utc=utc_now())
                write_json_atomic(os.path.join(self.res, "_service_verify.json"), self.verify_results)
                self.journal("verify", what=what, ok=r["ok"])
                return self.verify_results[key]
            else:
                raise Refuse("проверка: data, strategy, emulator или passport")
            res = {"ok": rc == 0, "returncode": rc, "text": out, "utc": utc_now()}
            self.verify_results[key] = res
            write_json_atomic(os.path.join(self.res, "_service_verify.json"), self.verify_results)
        self.journal("verify", what=key, ok=res["ok"])
        return res

    def certificates(self):
        data = []
        for rn in self.cfg["data_roots"]:
            for cert in sorted(glob.glob(os.path.join(self.root, rn, "*", "*_DATA_CERTIFICATE.json"))):
                c = read_json(cert, {}) or {}
                sym = c.get("symbol")
                rs = c.get("resample") or {}
                m1 = (c.get("series") or {}).get("M1") or {}
                data.append({"root": rn, "symbol": sym, "certificate": c.get("certificate"), "issued_utc": c.get("issued_utc"),
                             "sanitizer": rs.get("sanitizer_file") or rs.get("function"), "note": c.get("note"),
                             "m1_bars": m1.get("bars"), "first_open_utc": m1.get("first_open_utc"), "last_open_utc": m1.get("last_open_utc"),
                             "timeframes": list((c.get("series") or {}).keys()), "verify": self.verify_results.get(f"data:{rn}:{sym}")})
        inst = [read_json(p, {}) for p in glob.glob(os.path.join(self.root, "certified_vault", "*", "*.instrument.cert.json"))]
        tpl = []
        for p in glob.glob(os.path.join(self.root, "certified_vault", "*", "templates", "*.cert.json")) + glob.glob(os.path.join(self.root, "*.cert.json")):
            c = read_json(p, {}) or {}
            if str(c.get("certificate", "")).startswith("DZ-TEMPLATE-CERT"):
                tpl.append({"file": os.path.relpath(p, self.root), "rank": c.get("rank"), "template": c.get("template_file"),
                            "issued_utc": c.get("issued_utc"), "warnings": c.get("warnings")})
        sc = read_json(os.path.join(self.root, self.cfg["strategy_dir"], "STRATEGY_CERT.json"), {}) or {}
        return {"data": data, "instruments": inst, "templates": tpl,
                "strategy": {"rank": sc.get("rank"), "issued_utc": sc.get("issued_utc"), "verify": self.verify_results.get("strategy"),
                             "elements": strategy_elements(self.root, self.cfg["strategy_dir"]),
                             "vault_vs_passport": vault_vs_passport(self.root, self.cfg["strategy_dir"])},
                "emulator_seal": os.path.exists(os.path.join(self.root, "DZ_TERM_Lock.json")),
                "stamps": stamps(self.root), "accept": accept_reports(self.root),
                "passport": self.verify_results.get("passport")}

    def decisions(self):
        out = {}
        if os.path.exists(self.journal_path):
            with open(self.journal_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if r.get("event") == "decision":
                        out[r.get("gate")] = r
        return out

    def gates(self):
        return {"gates": compute_gates(self.root, self.cfg, self.verify_results, self.decisions()), "utc": utc_now(),
                "note": "служба считает ворота и записывает решения; включить торговлю она не может"}

    def decision(self, body):
        gate, text = body.get("gate"), str(body.get("text") or "").strip()
        if gate not in (1, 10) or len(text) < 10:
            raise Refuse("отметка: gate 1 (компиляция) или 10 (решение руководителя) и текст не короче 10 знаков")
        return self.journal("decision", gate=gate, text=text)

    # ---------- схема меню и пресет ----------
    def schema(self):
        for p in (os.path.join(self.nt_root, "dz_export", "hub_menu_schema.json"), os.path.join(self.root, "hub_menu_schema.json")):
            s = read_json(p)
            if s and s.get("properties"):
                return s, p
        raise Refuse("нет схемы меню: включите [U04] в стратегии и запустите её один раз", 404)

    @staticmethod
    def convert(p, v):
        t = p.get("type")
        if t == "bool":
            return (v, None) if isinstance(v, bool) else (None, "ожидалось true или false")
        if isinstance(v, bool) and t in ("int", "double"):
            return None, "ожидалось число"
        if t == "int":
            if not isinstance(v, (int, float)) or not float(v).is_integer():
                return None, f"ожидалось целое, получено {v}"
            v = int(v)
        elif t == "double":
            if not isinstance(v, (int, float)) or not math.isfinite(float(v)):
                return None, "ожидалось число"
            v = float(v)
        elif t == "enum":
            return (str(v), None) if str(v) in (p.get("enum") or []) else (None, f"нет значения {v} в перечислении")
        elif t == "string":
            return (v, None) if isinstance(v, str) else (None, "ожидалась строка")
        else:
            return None, f"тип {t} пресетом не задаётся"
        lo, hi = p.get("min"), p.get("max")
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            return None, f"значение {v} вне предела {lo}…{hi}"
        return v, None

    def preset(self, body):
        tid, set_name = str(body.get("id") or ""), body.get("set", "best_selected")
        if not ID_RE.fullmatch(tid) or set_name not in SETS:
            raise Refuse(f"нужны id итога и набор из {SETS}")
        s = read_json(os.path.join(self.res, tid, "summary.json"))
        if not s or not s.get(set_name):
            raise Refuse(f"в итоге {tid} нет набора {set_name}", 404)
        g = self.mod("graph")
        vals = self.mod("engine").nt_values(g, {k: s[set_name][k] for k in g["params"] if k in s[set_name]})
        schema, schema_path = self.schema()
        props = {p["name"]: p for p in schema["properties"]}
        out, errors, warnings = {}, [], []
        for k, v in vals.items():
            if k in PRESET_DENIED:
                errors.append(f"{k}: защитное свойство — пресетом не меняется")
                continue
            if k not in props:
                errors.append(f"{k}: нет в схеме меню — граф и сборка расходятся")
                continue
            cv, err = self.convert(props[k], v)
            if err:
                errors.append(f"{k}: {err}")
            else:
                out[k] = cv
        if self.cfg.get("dogma_guard"):
            viol = (["[MOD1] структура выключается"] if out.get("Slot1Enabled") is False else []) + \
                   (["[MOD8] пробой включается вторым источником сигнала"] if out.get("Slot8Enabled") is True else [])
            if viol:
                reason = str(body.get("dogma_override_reason") or "").strip()
                if len(reason) < 20:
                    errors.append("догма: входы даёт только [MOD1] — " + "; ".join(viol) + ". Для испытания в воспроизведении "
                                  "рынка — «dogma_override_reason» не короче 20 знаков")
                else:
                    warnings.append("догма нарушена по решению оператора: " + reason)
        if errors:
            raise Refuse("ОТКАЗ, пресет не сформирован: " + "; ".join(errors))
        if s.get("deflated_sharpe") is None or s["deflated_sharpe"] < 0.95:
            warnings.append(f"оптимизатор: {s.get('verdict')} — пресет только для воспроизведения рынка")
        preset = {"preset": "DZ-PRESET-v1", "strategy": "DZ_SW_Hub_S021", "created": utc_now(),
                  "source": {"service": VERSION, "task_id": tid, "set": set_name, "objective": s.get("objective"),
                             "engine": s.get("engine"), "verdict": s.get("verdict"), "deflated_sharpe": s.get("deflated_sharpe"),
                             "pbo": s.get("pbo"), "schema_exported": schema.get("exported_local"), "schema_file": schema_path,
                             "dogma_override": body.get("dogma_override_reason") or None},
                  "params": out}
        text = json.dumps(preset, ensure_ascii=False, indent=2)
        if text.count('"params"') != 1 or '"DZ_SW_Hub_S021"' not in text:
            raise Refuse("пресет не прошёл самопроверку формата коммутатора", 500)
        name = f"DZ_S021_preset_{tid}_{set_name}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        dirs = [os.path.join(self.res, tid, "presets")]
        nt_dir = os.path.join(self.nt_root, "dz_export", "presets")
        if os.path.isdir(os.path.join(self.nt_root, "dz_export")):
            dirs.insert(0, nt_dir)
        else:
            warnings.append(f"папки {os.path.join(self.nt_root, 'dz_export')} нет: пресет сохранён только в результатах")
        files = []
        for d in dirs:
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, name)
            if os.path.exists(p):
                raise Refuse("файл пресета уже есть — повторите через секунду", 409)
            with open(p + ".tmp", "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(p + ".tmp", p)
            files.append(p)
        self.journal("preset", id=tid, set=set_name, files=files, params=len(out), warnings=warnings)
        return {"files": files, "file_for_U05": name, "params": out, "warnings": warnings}

    # ---------- счёт и аварийные команды (папки incoming / outgoing NinjaTrader) ----------
    def account(self):
        od = os.path.join(self.nt_root, "outgoing")
        if not os.path.isdir(od):
            return {"available": False, "folder": od, "positions": [], "connections": []}
        pos, conn = [], []
        for f in sorted(os.listdir(od)):
            p = os.path.join(od, f)
            if not f.lower().endswith(".txt"):
                continue
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    txt = fh.read().strip()
            except OSError:
                continue
            upd = iso_utc(os.path.getmtime(p))
            if f.endswith("_Position.txt") and "_" in f[:-len("_Position.txt")]:
                inst, acct = f[:-len("_Position.txt")].rsplit("_", 1)
                parts = [x.strip() for x in txt.split(";")]

                def num(x, cast):
                    try:
                        return cast(float(x.replace(",", ".")))
                    except (ValueError, AttributeError):
                        return None
                pos.append({"instrument": inst, "account": acct, "side": parts[0].upper() if parts else "",
                            "qty": num(parts[1], int) if len(parts) > 1 else None,
                            "avg": num(parts[2], float) if len(parts) > 2 else None, "updated_utc": upd})
            elif txt.upper() in ("CONNECTED", "DISCONNECTED"):
                conn.append({"connection": f[:-4], "state": txt.upper(), "updated_utc": upd})
        return {"available": True, "folder": od, "positions": pos, "connections": conn,
                "source": "руководство NT8 §10.4.1.4.2: <инструмент биржа>_<счёт>_Position.txt, LONG/SHORT/FLAT"}

    def emergency(self, kind, body):
        em = self.cfg.get("emergency") or {}
        if not em.get("enabled"):
            raise Refuse("аварийные команды выключены в конфигурации", 403)
        if time.time() - self.last_emergency < 3:
            raise Refuse("не чаще раза в 3 секунды", 429)
        if kind == "flatten_all":
            if body.get("confirm") != "FLATTEN":
                raise Refuse("подтверждение: «confirm»: \"FLATTEN\"")
            line, acct, inst = ";".join(["FLATTENEVERYTHING"] + [""] * 12), None, None
        else:
            acct, inst = str(body.get("account") or ""), str(body.get("instrument") or "")
            if body.get("confirm") != "CLOSE":
                raise Refuse("подтверждение: «confirm»: \"CLOSE\"")
            if not OIF_RE.fullmatch(acct) or not OIF_RE.fullmatch(inst):
                raise Refuse("счёт и инструмент — без «;» и перевода строки; инструмент с биржей, как в файле позиции")
            line = ";".join(["CLOSEPOSITION", acct, inst] + [""] * 10)
        assert line.count(";") == 12
        inc = os.path.join(self.nt_root, "incoming")
        if not os.path.isdir(inc):
            raise Refuse(f"папки {inc} нет — NinjaTrader не найден по пути nt_root", 404)
        self.last_emergency = time.time()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        tmp, final = os.path.join(inc, f"~dz_{stamp}.tmp"), os.path.join(inc, f"oif_dz_{stamp}.txt")
        with open(tmp, "w", encoding="ascii") as f:
            f.write(line + "\n")
        os.replace(tmp, final)                       # руководство: файл переместить или писать напрямую, не копировать
        self.journal("emergency", kind=kind, file=final, account=acct, instrument=inst)
        with open(os.path.join(self.root, "kill_switch.log"), "a", encoding="utf-8") as f:
            f.write(f"[{local_now()}] СЛУЖБА v2 ЗАПИСАЛА {final}: {line}\n")
        t0, picked = time.time(), None
        while time.time() - t0 < float(em.get("wait_sec", 10)):
            if not os.path.exists(final):
                picked = round(time.time() - t0, 2)
                break
            time.sleep(0.2)
        flat, after = None, []
        t1 = time.time()
        while time.time() - t1 < float(em.get("flat_wait_sec", 15)):
            after = [p for p in self.account()["positions"] if (inst is None or (p["instrument"] == inst and p["account"] == acct))]
            if after and all(p["side"] == "FLAT" for p in after):
                flat = True
                break
            time.sleep(0.5)
        if flat is None and after:
            flat = False
        res = {"written": final, "line": line, "picked_up_sec": picked, "flat_confirmed": flat, "positions_after": after,
               "note": ("Файл забран терминалом" if picked is not None else "Файл НЕ забран: включён ли интерфейс автоматической торговли? "
                        "Закройте позиции вручную") + ". После Flatten Everything изредка остаётся встречная позиция "
                        "(руководство NT8, In Flight Executions) — проверьте счёт."}
        if kind == "close_position":
            res["note"] += " Позиция закрыта мимо стратегии: стратегию после этого выключите — её позиция и позиция счёта разошлись."
        self.journal("emergency_result", kind=kind, picked_up_sec=picked, flat_confirmed=flat)
        return res

    # ---------- бары из сертифицированных данных ----------
    def bars(self, q):
        import numpy as np
        import pandas as pd
        sym = (q.get("symbol") or ["MGC"])[0]
        try:
            tf = int((q.get("tf") or ["5"])[0])
            limit = max(1, min(int((q.get("limit") or ["5000"])[0]), 20000))
        except ValueError:
            raise Refuse("tf и limit — целые числа")
        if not SYM_RE.fullmatch(sym) or not 1 <= tf <= 1440:
            raise Refuse("символ и ТФ от 1 до 1440 минут")
        with self.lock:
            if sym not in self._m1:
                cert = os.path.join(self.root, "data_certified", sym, f"{sym}_DATA_CERTIFICATE.json")
                if not os.path.exists(cert):
                    raise Refuse(f"нет сертифицированных данных {sym}", 404)
                cd = load_module(os.path.join(self.root, "DZ_CERT_Data.py"), "dz_svc_certdata")
                ok, errs, _ = cd.verify(cert, quiet=True)
                if not ok:
                    raise Refuse(f"сертификат {sym} не прошёл проверку: {'; '.join(errs)}", 409)
                z = np.load(os.path.join(os.path.dirname(cert), f"{sym}_M1.npz"), allow_pickle=False)
                self._m1[sym] = {k: z[k] for k in ("t_open", "o", "h", "l", "c", "v") if k in z.files}
            m = self._m1[sym]
        t = m["t_open"]
        try:
            to = pd.Timestamp(q["to"][0], tz="UTC") if q.get("to") else pd.Timestamp(int(t[-1]), unit="ns", tz="UTC") + pd.Timedelta(minutes=1)
            fr = pd.Timestamp(q["from"][0], tz="UTC") if q.get("from") else to - pd.Timedelta(minutes=tf * limit * 3)
        except ValueError:
            raise Refuse("from и to — даты ГГГГ-ММ-ДД")
        i0 = int(np.searchsorted(t, (fr - pd.Timedelta(minutes=tf)).value, "left"))
        i1 = int(np.searchsorted(t, to.value, "left"))
        if i1 - i0 > 3_000_000:
            raise Refuse("слишком длинный период для одного запроса")
        df = pd.DataFrame({k: m[k][i0:i1] for k in ("o", "h", "l", "c", "v") if k in m}, index=pd.to_datetime(t[i0:i1], utc=True))
        if tf > 1 and len(df):
            b = self.mod("san2").resample(df, tf)
            b = b[(b.index >= fr) & (b.index < to)]
        else:
            b = df[(df.index >= fr) & (df.index < to)]
        b = b.tail(limit)
        return {"symbol": sym, "tf": tf, "count": int(len(b)), "t": [int(x.timestamp()) for x in b.index],
                **{k: [round(float(x), 6) for x in b[k].values] for k in ("o", "h", "l", "c", "v") if k in b},
                "source": "сертифицированные M1, старшие ТФ — очиститель v2 от 17:00 по Чикаго", "time": "UTC, открытие бара"}

    # ---------- Э-Т2: сторож рассинхрона ----------
    def desync_loop(self):
        c = self.cfg["desync_watch"]
        tokf = os.path.join(self.nt_root, "dz_export", "atlas_ws_token.txt")
        while not self.stop_evt.is_set():
            ws = None
            try:
                with open(tokf, encoding="utf-8") as f:
                    tok = f.read().strip()
                ws = MiniWs(int(c.get("ws_port", 8088)))
                ws.connect()
                ws.send_text(json.dumps({"cmd": "auth", "token": tok}))
                commands, since, paused, ep = False, None, False, 0
                self.desync.update(state="подключён")
                while not self.stop_evt.is_set():
                    m = json.loads(ws.recv_text())
                    if m.get("t") == "auth":
                        commands = bool(m.get("commands"))
                    if m.get("t") != "bar":
                        continue
                    side, qty = int(m.get("pos") or 0), abs(int(m.get("qty") or 0))
                    acc = [p for p in self.account()["positions"] if p["instrument"].startswith(c.get("instrument_prefix", ""))
                           and (not c.get("account") or p["account"] == c["account"])]
                    a_side = sum({"LONG": 1, "SHORT": -1}.get(p["side"], 0) for p in acc)
                    a_qty = sum(p["qty"] or 0 for p in acc if p["side"] in ("LONG", "SHORT"))
                    match = (side == a_side) and (side == 0 or qty == a_qty)
                    self.desync.update(strategy={"side": side, "qty": qty}, account={"side": a_side, "qty": a_qty, "files": len(acc)},
                                       match=match, utc=utc_now())
                    if match:
                        since, paused = None, False
                        continue
                    since = since or time.time()
                    if time.time() - since >= float(c.get("grace_sec", 20)) and ep != int(since):
                        ep = int(since)
                        al = {"utc": utc_now(), "kind": "desync", "strategy": {"side": side, "qty": qty},
                              "account": {"side": a_side, "qty": a_qty}, "seconds": round(time.time() - since, 1)}
                        if c.get("action") == "pause" and commands and not paused:
                            ws.send_text(json.dumps({"cmd": "pause", "token": tok}))
                            al["action"], paused = "пауза входов отправлена", True
                        with self.lock:
                            self.alarms = (self.alarms + [al])[-200:]
                        self.journal("alarm", **al)
            except Exception as ex:
                self.desync.update(state=f"нет связи: {str(ex)[:160]}")
            finally:
                if ws:
                    ws.close()
            self.stop_evt.wait(5.0)


# ======================================================================================
# 4. HTTP
# ======================================================================================

def handler(svc):
    class H(BaseHTTPRequestHandler):
        server_version = "Atlas/2"

        def log_message(self, *a):
            pass

        def _origin(self):
            o = self.headers.get("Origin")
            return o is None or o in ALLOWED_ORIGINS, o

        def _send(self, code, obj):
            b = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
            ok, o = self._origin()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            if ok:
                self.send_header("Access-Control-Allow-Origin", o or "null")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def _guard(self):
            ok, _ = self._origin()
            if not ok:
                self._send(403, {"error": "чужой источник"})
                return False
            if not hmac.compare_digest((self.headers.get("X-Atlas-Token") or "").encode("utf-8"), svc.token.encode("utf-8")):
                self._send(401, {"error": "неверный ключ"})
                return False
            return True

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                raise Refuse("слишком большое тело запроса", 413)
            raw = self.rfile.read(n) if n else b"{}"
            try:
                return json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                raise Refuse("тело запроса — не JSON")

        def do_OPTIONS(self):
            ok, o = self._origin()
            self.send_response(204 if ok else 403)
            if ok:
                self.send_header("Access-Control-Allow-Origin", o or "null")
                self.send_header("Access-Control-Allow-Headers", "X-Atlas-Token, Content-Type")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                if self.headers.get("Access-Control-Request-Private-Network") == "true":
                    self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _route(self, method):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            p = u.path.rstrip("/") or "/"
            if method == "GET" and p == "/health":
                return self._send(200, {"service": VERSION, "ok": True, "worker_alive": time.time() - svc.worker_beat < 15,
                                        "deps_ok": svc.deps["ok"], "utc": utc_now()})
            if not self._guard():
                return
            try:
                if method == "GET":
                    R = {"/status": lambda: {"service": VERSION, "jobs": svc.snapshot(), "deps": svc.deps,
                                             "worker_alive": time.time() - svc.worker_beat < 15,
                                             "running": svc.current["id"] if svc.current else None,
                                             "holdout": {"from": svc.cfg.get("holdout_from"), "policy": svc.cfg.get("holdout_policy")},
                                             "experiments": {"budget_lock": bool(svc.cfg["budget_lock"].get("enabled")),
                                                             "desync_watch": svc.desync}, "alarms": svc.alarms[-20:]},
                         "/summary": lambda: need(read_json(os.path.join(svc.res, svc._rid(q), "summary.json")), "нет итога"),
                         "/log": lambda: self._log(q),
                         "/results": svc.results,
                         "/trades": lambda: svc.trades(svc._rid(q), min(int((q.get("limit") or ["3000"])[0]), 20000)),
                         "/trials": lambda: svc.trials(svc._rid(q)),
                         "/wfa": lambda: need(read_json(os.path.join(svc.res, svc._rid(q) + "_wfa.json")), "нет итога проверки вперёд"),
                         "/registry": svc.registry,
                         "/certificates": svc.certificates,
                         "/gates": svc.gates,
                         "/account": svc.account,
                         "/schema": lambda: svc.schema()[0],
                         "/graph": lambda: svc.mod("graph"),
                         "/bars": lambda: svc.bars(q),
                         "/alarms": lambda: {"alarms": svc.alarms, "desync": svc.desync},
                         "/journal": lambda: self._journal(q),
                         "/config": lambda: svc.cfg}
                    if p not in R:
                        return self._send(404, {"error": "нет такого адреса"})
                    return self._send(200, R[p]())
                body = self._body()
                if p == "/task":
                    tid, notes = svc.enqueue(body)
                    return self._send(200, {"queued": tid, "notes": notes})
                if p == "/cancel":
                    return self._send(200, {"cancelled": svc._rid(q), "was": svc.cancel(svc._rid(q))})
                if p == "/requeue":
                    new, notes = svc.requeue(svc._rid(q))
                    return self._send(200, {"queued": new, "notes": notes})
                if p == "/verify":
                    return self._send(200, svc.verify((q.get("what") or [""])[0], q))
                if p == "/preset":
                    return self._send(200, svc.preset(body))
                if p == "/decision":
                    return self._send(200, svc.decision(body))
                if p == "/emergency/flatten_all":
                    return self._send(200, svc.emergency("flatten_all", body))
                if p == "/emergency/close_position":
                    return self._send(200, svc.emergency("close_position", body))
                return self._send(404, {"error": "нет такого адреса"})
            except Refuse as ex:
                return self._send(ex.code, {"error": str(ex)})
            except Exception as ex:
                svc.journal("http_error", path=p, error=traceback.format_exc()[-1500:])
                return self._send(500, {"error": f"{type(ex).__name__}: {ex}"})

        def _log(self, q):
            tid = svc._rid(q)
            p = os.path.join(svc.logs, tid + ".log")
            if not os.path.exists(p):
                raise Refuse("журнала нет", 404)
            size = os.path.getsize(p)
            off = max(0, min(int((q.get("offset") or ["0"])[0]), size))
            with open(p, "rb") as f:
                f.seek(off)
                chunk = f.read(256 * 1024)
            return {"id": tid, "offset": off, "next": off + len(chunk), "size": size,
                    "text": chunk.decode("utf-8", "replace"), "state": (svc.status.get(tid) or {}).get("state")}

        def _journal(self, q):
            n = min(int((q.get("limit") or ["200"])[0]), 2000)
            if not os.path.exists(svc.journal_path):
                return {"records": []}
            with open(svc.journal_path, encoding="utf-8") as f:
                lines = f.readlines()[-n:]
            return {"records": [json.loads(x) for x in lines if x.strip()]}

        def do_GET(self):
            self._route("GET")

        def do_POST(self):
            self._route("POST")
    return H


def single_instance(path):
    """Вторая служба на той же очереди не стартует: файл-замок держится открытым до выхода процесса."""
    f = open(path, "a+")
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f


def load_config(path):
    if not os.path.exists(path):
        write_json_atomic(path, DEFAULT_CONFIG, indent=2)
    return merge(DEFAULT_CONFIG, read_json(path, {}) or {})


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--root", default=HERE)
    ap.add_argument("--config", default=None)
    ap.add_argument("--port", type=int, default=None)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    cfg = load_config(a.config or os.path.join(root, "DZ_ATLAS_Service_v2.config.json"))
    port = a.port or int(cfg["port"])
    os.makedirs(os.path.join(root, "task_queue"), exist_ok=True)
    lock = single_instance(os.path.join(root, "task_queue", ".service_v2.lock"))
    if lock is None:
        raise SystemExit("ОТКАЗ: служба v2 уже работает с этой очередью")
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), None)
    except OSError as ex:
        raise SystemExit(f"ОТКАЗ: порт {port} занят ({ex}). Окно службы v1 закрыто? Две службы на одной очереди не работают")
    svc = Service(root, cfg)
    httpd.RequestHandlerClass = handler(svc)
    threading.Thread(target=svc.worker, daemon=True, name="DZ_SVC_Worker").start()
    if cfg["desync_watch"].get("enabled"):
        threading.Thread(target=svc.desync_loop, daemon=True, name="DZ_SVC_Desync").start()
    svc.journal("service_start", version=VERSION, port=port, python=svc.python, deps=svc.deps["ok"])
    print(f"{VERSION}\n  адрес     http://127.0.0.1:{port}\n  ключ      {os.path.join(root, 'atlas_service_token.txt')}"
          f"\n  задачи    {svc.python}: " + ("numpy и pandas есть " + (svc.deps["versions"] or "") if svc.deps["ok"] else svc.deps["error"]) +
          f"\n  замок     отложенная выборка с {cfg.get('holdout_from') or '— выключен'} ({cfg.get('holdout_policy')})"
          f"\n  Э-Т1      бюджетный замок: {'ВКЛЮЧЁН' if cfg['budget_lock'].get('enabled') else 'выключен'}"
          f"\n  Э-Т2      сторож рассинхрона: {'ВКЛЮЧЁН' if cfg['desync_watch'].get('enabled') else 'выключен'}"
          f"\n  NinjaTrader {svc.nt_root}: {'найден' if os.path.isdir(svc.nt_root) else 'НЕ НАЙДЕН — счёт, пресеты в dz_export и аварийные команды недоступны'}"
          f"\nОкно не закрывайте, пока идут расчёты. Остановка — Ctrl+C: текущая задача будет прервана и помечена.", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        svc.stop_evt.set()
        cur = svc.current
        if cur:
            kill_tree(cur["proc"])
            time.sleep(2)
        svc.journal("service_stop")
        httpd.server_close()


if __name__ == "__main__":
    main()
