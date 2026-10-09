#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_DOC_Menu_S021.py — документы стратегии S021 из исходников, v1.0 (2026-10-04)

Документы с таблицами генерируются из кода, а не пишутся руками: рукописная копия
расходится с кодом молча. Скрипт читает DZ_SW_Hub_S021.cs и модули в той же папке и пишет:

  DZ_SW_S021_03_Справочник_Меню_Настроек.md  — все настройки: индекс, название, тип,
      пределы, умолчание, описание; отпечаток схемы — тот же, что печатает [T15]
  DZ_SW_S021_12_Перечень_Модулей.md          — модули: слот, класс, файл, версия, назначение
  DZ_SW_S021_11_Карта_Связей_Настроек.md     — какая настройка в какое поле модуля идёт,
      ссылки на слоты пула и проверяемые конфликты

ОТПЕЧАТОК СХЕМЫ — SHA-256 строк «имя|тип .NET|название» всех свойств [NinjaScriptProperty],
упорядоченных по имени, первые 12 знаков. Совпадение с [T15] в Output доказывает, что
справочник описывает именно скомпилированное меню.

Запуск: python DZ_DOC_Menu_S021.py --src <папка с .cs> --out <папка документов>
==========================================================================================
"""
import argparse, glob, hashlib, os, re

VERSION = "DZ_DOC_Menu_S021-v1.0 (2026-10-04)"
NET = {"int": "Int32", "double": "Double", "bool": "Boolean", "string": "String", "long": "Int64", "float": "Single"}


def unesc(s):
    return s.replace('\\"', '"').replace("\\\\", "\\")


def _attr_args(text, start):
    """Содержимое атрибута от «(» до парной «)» с учётом строк C#."""
    i, depth, out = start, 0, []
    while i < len(text):
        c = text[i]
        if c == '"':
            j = i + 1
            while j < len(text) and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1]); i = j + 1; continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return "".join(out)[1:], i
        out.append(c); i += 1
    return "", i


def _named(args, key):
    m = re.search(key + r'\s*=\s*"((?:[^"\\]|\\.)*)"', args)
    if m:
        return unesc(m.group(1))
    m = re.search(key + r"\s*=\s*(\d+)", args)
    return m.group(1) if m else None


def parse_props(src):
    """Свойства меню: атрибуты между предыдущим объявлением и «public T Name { get; set; }»."""
    props, prev = [], 0
    for m in re.finditer(r"public\s+([\w\.<>]+)\s+(\w+)\s*\{\s*get;\s*set;\s*\}", src):
        attrs = src[prev:m.start()]
        prev = m.end()
        k = attrs.rfind("[Display(")
        if k < 0:
            continue
        args, _ = _attr_args(attrs, k + len("[Display"))
        name = _named(args, "Name")
        if name is None:
            continue
        r = re.search(r"\[Range\(([^,\)]+),\s*([^\)]+)\)\]", attrs)
        typ = m.group(1).split(".")[-1]
        props.append({
            "name": m.group(2), "type": typ, "net": NET.get(typ, typ),
            "label": name, "order": int(_named(args, "Order") or 0), "group": _named(args, "GroupName") or "",
            "desc": _named(args, "Description") or "", "nsp": "[NinjaScriptProperty]" in attrs,
            "range": (r.group(1).strip(), r.group(2).strip()) if r else None,
        })
    return props


def parse_defaults(src, names):
    i = src.find("if (State == State.SetDefaults)")
    j = src.find("else if (State == State.Configure)", i)
    block = src[i:j]
    out = {}
    for m in re.finditer(r"\b(\w+)\s*=\s*([^;\n]+);", block):
        if m.group(1) in names:
            out[m.group(1)] = m.group(2).strip()
    return out


def parse_enums(files):
    enums = {}
    for f in files:
        for m in re.finditer(r"public\s+enum\s+(\w+)\s*\{([^}]*)\}", open(f, encoding="utf-8").read()):
            vals = [re.sub(r"//.*", "", v).strip() for v in m.group(2).split("\n")]
            items = []
            for v in vals:
                items += [x.strip() for x in v.split(",") if x.strip()]
            enums[m.group(1)] = items
    return enums


def fingerprint(props):
    menu = sorted([p for p in props if p["nsp"]], key=lambda p: p["name"])
    s = "".join(p["name"] + "|" + p["net"] + "|" + p["label"] + "\n" for p in menu)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12], len(menu)


def md_cell(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--src", default=".")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()

    hub_path = os.path.join(a.src, "DZ_SW_Hub_S021.cs")
    hub = open(hub_path, encoding="utf-8").read()
    files = sorted(glob.glob(os.path.join(a.src, "DZ_SW_*.cs")))
    props = parse_props(hub)
    names = {p["name"] for p in props}
    defaults = parse_defaults(hub, names)
    enums = parse_enums(files)
    fp, nmenu = fingerprint(props)
    hub_ver = re.search(r'HubVersion = "([^"]+)"', hub).group(1)
    os.makedirs(a.out, exist_ok=True)

    # ---------------------------------------------------------------- 03 справочник меню
    groups = {}
    for p in props:
        groups.setdefault(p["group"], []).append(p)
    lines = ["# DZ_SW_S021 — справочник меню настроек", "",
             f"**Сборка:** `{hub_ver}` · **Настроек в окне:** {len(props)} · **В схеме [NinjaScriptProperty]:** {nmenu}",
             f"**Отпечаток схемы:** `{fp}` — при [T15] коммутатор печатает его при запуске; несовпадение значит, что справочник описывает другую сборку.",
             f"**Сгенерировано:** `{VERSION}` из исходника. Руками не править — перегенерировать.", ""]
    for g in sorted(groups):
        lines += ["", f"## {g}", "", "| Индекс и название | Свойство | Тип | Пределы | Умолчание | Описание |", "|---|---|---|---|---|---|"]
        for p in sorted(groups[g], key=lambda x: x["order"]):
            typ = p["type"]
            if typ in enums:
                typ += " (" + ", ".join(enums[typ]) + ")"
            rng = f"{p['range'][0]} … {p['range'][1]}" if p["range"] else ""
            dv = defaults.get(p['name'], '')
            if dv == "string.Empty" or dv == '""':
                dv = "пусто"
            elif re.fullmatch(re.escape(p["type"]) + r"\.\w+", dv):
                dv = dv.split(".", 1)[1]
            lines.append(f"| {md_cell(p['label'])} | `{p['name']}` | {md_cell(typ)} | {rng} | {md_cell(dv)} | {md_cell(p['desc'])} |")
    open(os.path.join(a.out, "DZ_SW_S021_03_Справочник_Меню_Настроек.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

    # ---------------------------------------------------------------- 12 перечень модулей
    i = hub.find("private void BuildSlots()")
    j = re.search(r"private (?:void|int) ValidateSlotReferences\(\)", hub).start()
    build = hub[i:j]
    rows = []
    for m in re.finditer(r"if \(Slot(\d+)Enabled\)\s*\{", build):
        k, depth = m.end() - 1, 0
        for e in range(k, len(build)):
            if build[e] == "{": depth += 1
            elif build[e] == "}":
                depth -= 1
                if depth == 0: break
        seg = build[k:e]
        nm = re.search(r'new (Sw\w+Module)\((?:\w+\s*\?\s*)?"([^"]+)"(?:\s*:\s*"([^"]+)")?', seg)
        if not nm:
            continue
        cls = nm.group(1)
        mid = nm.group(2) + (" / " + nm.group(3) if nm.group(3) else "")
        if seg[nm.end():nm.end() + 3].lstrip().startswith("+"):
            mid += "…"
        mfile, ver, purpose = "", "", ""
        for f in files:
            t = open(f, encoding="utf-8").read()
            if re.search(r"class " + cls + r"\b", t):
                mfile = os.path.basename(f)
                head = "\n".join(t.split("\n")[:20])
                hv = re.search(r"v\d+\.\d+(?:\.\d+)?\s*\(\d{4}-\d\d-\d\d\)", head)
                ver = hv.group(0) if hv else ""
                hd = re.search(r"//\s+DZ_SW_\w+\s+—\s+([^\n,\[]+)", t)
                purpose = hd.group(1).strip() if hd else ""
                break
        en = f"Slot{m.group(1)}Enabled"
        rows.append((int(m.group(1)), mid, cls, mfile, ver, purpose, defaults.get(en, "")))
    seen, uniq = set(), []
    for r in sorted(rows):
        if (r[0], r[1]) not in seen:
            seen.add((r[0], r[1])); uniq.append(r)
    lines = ["# DZ_SW_S021 — перечень модулей", "",
             f"**Сборка:** `{hub_ver}` · **Модулей в слотах:** {len(uniq)} · сгенерировано `{VERSION}` из `BuildSlots`.", "",
             "| Слот | Включён по умолчанию | Идентификатор | Класс | Файл | Версия | Назначение |", "|---|---|---|---|---|---|---|"]
    for r in uniq:
        lines.append(f"| [MOD{r[0]}] | {r[6]} | {r[1]} | `{r[2]}` | `{r[3]}` | {r[4]} | {md_cell(r[5])} |")
    open(os.path.join(a.out, "DZ_SW_S021_12_Перечень_Модулей.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

    # ---------------------------------------------------------------- 11 карта связей
    label_of = {p["name"]: p["label"] for p in props}
    wiring = []
    for m in re.finditer(r"\b(\w+)\.(\w+)\s*=\s*(\w+)\b[^;]*;", build):
        obj, field, prop = m.groups()
        if prop in label_of:
            wiring.append((obj, field, label_of[prop], prop))
    vm = re.search(r"private (?:void|int) ValidateSlotReferences\(\)", hub)
    v = hub[vm.start(): hub.find("private int CheckSlot", vm.start())] if vm else ""
    slots = re.findall(r'CheckSlot\("([^"]+)",\s*(\w+)\)', v)
    conflicts = []
    for pm in re.finditer(r'Print\(("\[HUB-ВНИМАНИЕ\] \[.*?)\);', v, re.S):
        body, txt, last = pm.group(1), "", None
        for lm in re.finditer(r'"((?:[^"\\]|\\.)*)"', body):
            if last is not None:
                gap = body[last:lm.start()]
                txt += "" if re.fullmatch(r"\s*\+\s*", gap) else "…"
            txt += unesc(lm.group(1)); last = lm.end()
        if last is not None and body[last:].strip():
            txt += "…"
        txt = txt.replace("[HUB-ВНИМАНИЕ] ", "", 1)
        conflicts.append(re.sub(r"\s+", " ", txt).strip())
    lines = ["# DZ_SW_S021 — карта связей настроек", "",
             f"**Сборка:** `{hub_ver}` · сгенерировано `{VERSION}` из `BuildSlots` и `ValidateSlotReferences`.", "",
             "## Настройка → поле модуля", "", "| Объект конфигурации | Поле | Настройка | Свойство |", "|---|---|---|---|"]
    for w in wiring:
        lines.append(f"| `{w[0]}` | `{w[1]}` | {md_cell(w[2])} | `{w[3]}` |")
    lines += ["", "## Ссылки модулей на слоты пула [S50]–[S82]", "",
              "Невключённый слот уводит расчёт на серию графика; в боевом режиме такое замечание запрещает новые входы (сторож конфигурации v1.1).", "",
              "| Проверка | Свойство-ссылка |", "|---|---|"]
    for s in slots:
        lines.append(f"| {md_cell(s[0])} | `{s[1]}` |")
    lines += ["", "## Проверяемые конфликты и предупреждения", ""]
    for c in conflicts:
        lines.append(f"- {c}")
    open(os.path.join(a.out, "DZ_SW_S021_11_Карта_Связей_Настроек.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print(f"{VERSION}: настроек {len(props)}, в схеме {nmenu}, отпечаток {fp}, модулей {len(uniq)}, связей {len(wiring)}")


if __name__ == "__main__":
    main()
