#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_DOC_Dev_S021.py — генератор руководства разработчика DZ_SW_S021_02, v1.0 (2026-10-04)

Контракты и такт исполнения берутся из исходников при каждом запуске: перечисления ролей,
здоровья, требований и вердиктов; поля SwSignal и SwAction; открытые члены SwModule и
SwHostView; шаги OnBarUpdate. Повествовательные разделы — постоянный текст ниже. Документ
не правится руками: правится код или этот генератор.

  python DZ_DOC_Dev_S021.py --src <папка с DZ_SW_*.cs> --out <папка документов>
==========================================================================================
"""
import argparse, glob, os, re

VERSION = "DZ_DOC_Dev_S021-v1.0 (2026-10-04)"


def block(src, header):
    """Тело блока { … } после заголовка, с учётом вложенности."""
    i = src.find(header)
    if i < 0:
        return ""
    j = src.find("{", i)
    depth, k = 0, j
    while k < len(src):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[j + 1:k]
        k += 1
    return ""


def enum_rows(src, name):
    rows = []
    for line in block(src, "public enum " + name).splitlines():
        m = re.match(r"\s*(\w+)\s*,?\s*(?://\s*(.*))?$", line)
        if m and m.group(1):
            rows.append((m.group(1), (m.group(2) or "").strip()))
    return rows


def field_rows(src, name):
    body = block(src, "public struct " + name)
    body = body.split("public static")[0]
    rows, summary = [], []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("///"):
            t = re.sub(r"</?summary>", "", s[3:]).strip()
            if t:
                summary.append(t)
            continue
        m = re.match(r"public ([\w.<>\[\]]+) (\w+);\s*(?://\s*(.*))?$", s)
        if m:
            rows.append((m.group(2), m.group(1), (m.group(3) or " ".join(summary)).strip()))
            summary = []
    return rows


def member_rows(src, name, kinds=("public", "protected")):
    body = block(src, "class " + name)
    rows, depth = [], 0
    for line in body.splitlines():
        s = line.strip()
        if depth == 0 and any(s.startswith(k + " ") for k in kinds) and "class " not in s:
            sig = re.split(r"\s*(\{|=>|;\s*//|;$)", s)[0].strip()
            com = re.search(r"//\s*(.*)$", s)
            rows.append((sig, com.group(1).strip() if com and "{" not in s[:s.find("//")] else ""))
        depth += line.count("{") - line.count("}")
    return rows


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--src", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    hub = open(os.path.join(a.src, "DZ_SW_Hub_S021.cs"), encoding="utf-8").read()
    ver = re.search(r'HubVersion = "([^"]+)"', hub).group(1)
    steps = re.findall(r"// ---------- (\d+)\. ([^-\n]+?) ----------", hub)
    mods = []
    for f in sorted(glob.glob(os.path.join(a.src, "DZ_SW_Mod_*_S021.cs"))):
        t = open(f, encoding="utf-8").read()
        cls = re.search(r"public class (\w+)\s*:\s*SwModule", t)
        v = re.search(r"v(\d+\.\d+(?:\.\d+)?) \((\d{4}-\d{2}-\d{2})\)", t)
        mods.append((os.path.basename(f), cls.group(1) if cls else "—", f"v{v.group(1)} ({v.group(2)})" if v else "—"))

    o = []
    w = o.append
    w("# DZ_SW_S021_02 — Руководство разработчика\n")
    w(f"**Сгенерировано:** {VERSION} из `{ver}`. Руками не править: контракты и такт — из кода.\n")
    w("## 1. Устройство\n")
    w("Одна стратегия — коммутатор `DZ_SW_Hub_S021` — и подключаемые модули `DZ_SW_Mod_*_S021`. "
      "Модули считают и голосуют, заявки отправляет только исполнитель внутри коммутатора. "
      "Модуль видит ядро через `SwHostView` — представление без ордерного API: вызвать "
      "`EnterLong` из модуля невозможно физически. Обмен — через ящики: модуль кладёт `SwSignal` "
      "или `SwAction`, коммутатор забирает и сверяет «отправлено — принято»: расхождение — потеря.\n")
    w("## 2. Такт серии исполнения\n")
    w("Порядок шагов `OnBarUpdate` — из кода:\n")
    w("| Шаг | Что происходит |\n|---|---|")
    for n, t in steps:
        w(f"| {n} | {re.sub(r'^v[\d.]+:\s*', '', t.strip())} |")
    w("\nМодули считаются на каждой серии пула; разбор, решение и заявки — только на закрытии бара "
      "серии исполнения `[S90]` (руководство NT, с. 2350: заявки — в первый контекст инструмента).\n")
    w("## 3. Контракты\n")
    for e in ("SwRole", "SwHealth", "SwActionKind", "SwVerdict"):
        w(f"**{e}:** " + "; ".join(f"`{n}`" + (f" — {c}" if c else "") for n, c in enum_rows(hub, e)) + ".\n")
    for s in ("SwSignal", "SwAction"):
        w(f"**{s}**\n\n| Поле | Тип | Смысл |\n|---|---|---|")
        for n, t, c in field_rows(hub, s):
            w(f"| `{n}` | `{t}` | {c} |")
        w("")
    for c, title in (("SwModule", "Базовый класс модуля `SwModule`"), ("SwHostView", "Представление ядра `SwHostView`")):
        w(f"**{title}**\n\n| Член | Примечание |\n|---|---|")
        for sig, com in member_rows(hub, c):
            w(f"| `{sig}` | {com} |")
        w("")
    w("## 4. Модули\n\n| Файл | Класс | Версия |\n|---|---|---|")
    for f, c, v in mods:
        w(f"| `{f}` | `{c}` | {v} |")
    w("\nСлоты, роли и умолчания — в `DZ_SW_S021_12`; настройки — в `DZ_SW_S021_03`.\n")
    w("## 5. Как добавить модуль\n")
    for i, t in enumerate([
        "Файл `DZ_SW_Mod_<Имя>_S021.cs`: класс конфигурации и класс-наследник `SwModule`; версия и дата в шапке.",
        "`Compute(int barsInProgress)`: только расчёт и `Emit`. Без выделения памяти в такте, без заглядывания вперёд, без ордерного API.",
        "Слот `[MODn]` в коммутаторе: флаг включения, передача настроек в сборке слотов, создание модуля.",
        "Настройки меню: индекс `[Xnn]`, русское название и описание, `Range` где есть пределы, умолчание в `SetDefaults`.",
        "Одна-две экспериментальные функции, выключенные по умолчанию, со ссылкой на учебник базы проекта.",
        "`python DZ_DEV_MemberCheck.py \"DZ_SW_*.cs\"` — ноль ошибок; затем компиляция F5.",
        "`DZ_DOC_Menu_S021.py` и `DZ_DOC_Dev_S021.py` — документы из кода; отпечаток схемы `[T15]` совпадает со справочником.",
        "Режим без ордеров с журналом `[T17]`; при наличии эталона на ПК — сверка `parity`.",
    ], 1):
        w(f"{i}. {t}")
    w("\n## 6. Правила\n")
    for t in [
        "Одна величина — один источник; вторая реализация — только с перекрёстной сверкой.",
        "Решение по OHLC не опирается на порядок цен внутри бара; спорный порядок — худший.",
        "Исключение модуля изолируется: `MarkFault`, модуль снимается, торговля идёт без него.",
        "Код NinjaScript сверяется с руководством NinjaTrader 8 со ссылкой на страницу.",
        "Статистика и проверки — по AFML, MLAM и банковской книге; уровни объёма — по Volume Profile.",
        "Документы 02, 03, 11, 12 генерируются; 00 и 05 ведутся вручную.",
    ]:
        w(f"- {t}")
    w("\n## 7. Инструменты\n\n| Инструмент | Назначение |\n|---|---|")
    for n, d in [
        ("`DZ_DEV_MemberCheck.py`", "члены и аргументы вызовов до компиляции"),
        ("`DZ_DOC_Menu_S021.py`", "справочник меню, карта связей, перечень модулей"),
        ("`DZ_DOC_Dev_S021.py`", "это руководство"),
        ("`DZ_OPT_Engine_S021.py parity`", "сделка в сделку: NinjaTrader против эталона"),
        ("`DZ_SA_Audit_S021.py`", "DSR и PBO оптимизации Strategy Analyzer"),
        ("`DZ_ACCEPT_S021.py`", "приёмка по Output, детерминированность, метрики ставок"),
    ]:
        w(f"| {n} | {d} |")
    path = os.path.join(a.out, "DZ_SW_S021_02_Руководство_Разработчика.md")
    open(path, "w", encoding="utf-8").write("\n".join(o) + "\n")
    print(f"{VERSION}: {path} — шагов такта {len(steps)}, модулей {len(mods)}")


if __name__ == "__main__":
    main()
