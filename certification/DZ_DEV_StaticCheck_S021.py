#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_DEV_StaticCheck_S021.py — статический контроль исходников до компиляции, v1.0 (2026-10-04)

Дополняет DZ_DEV_MemberCheck.py (члены и аргументы вызовов). Ловит то, что компилятор
NinjaTrader покажет только после F5, и то, что компилятор не покажет вовсе:

  ЛЕКСИКА      незакрытые строки и символы, недопустимые escape-последовательности (CS1009),
               непарные скобки с номером строки.
  ЯЗЫК         конструкции C# 6 и новее: ?. и ?[, $"…", nameof, члены через =>, инициализаторы
               автосвойств, out var, шаблоны is. Код, который у руководителя уже
               компилировался, их не содержит; новый код — тоже не должен.
  ТИПЫ         один и тот же тип в двух файлах одного пространства имён (CS0101) — по всем
               файлам папки, включая чужие стратегии из bin\\Custom.
  МЕНЮ         повтор индекса [Xnn], повтор имени свойства, умолчание вне [Range] (окно
               настроек отклонит значение), повтор Order в группе, свойство схемы без умолчания.
  ССЫЛКИ (Э33) индексы [Xnn] в описаниях и комментариях, которых нет в меню: документация
               ссылается на несуществующую настройку.
  ПЕРЕДАЧА (Э34) поля классов конфигурации модулей, которые ядро ни разу не присваивает: модуль
               всегда работает на умолчании поля. Так в порции 2 нашёлся путь к календарю
               новостей, не доходивший до модуля охраны. Часть полей постоянна намеренно —
               список для разбора, не ошибка.

  python DZ_DEV_StaticCheck_S021.py --src <папка с .cs> [--extra DZ_SF_Guards_S019.cs]

Код возврата 0 — ошибок нет (предупреждения допустимы), 1 — есть ошибки.
==========================================================================================
"""
import argparse, glob, os, re, sys

VERSION = "DZ_DEV_StaticCheck_S021-v1.0 (2026-10-04)"
VALID_ESC = set("'\"\\0abfnrtv")


def lex(src):
    """Код без комментариев и содержимого строк + ошибки лексики. Позиции строк сохраняются."""
    out, errs, i, n, line = [], [], 0, len(src), 1
    while i < n:
        c, d = src[i], src[i:i + 2]
        if c == "\n":
            line += 1; out.append(c); i += 1; continue
        if d == "//":
            j = src.find("\n", i); j = n if j < 0 else j
            out.append(" " * (j - i)); i = j; continue
        if d == "/*":
            j = src.find("*/", i + 2); j = n if j < 0 else j + 2
            seg = src[i:j]; out.append("".join("\n" if ch == "\n" else " " for ch in seg))
            line += seg.count("\n"); i = j; continue
        if d == '@"' or (d == '$"') or src[i:i + 3] in ('$@"', '@$"'):
            verb = "@" in src[i:i + 3].split('"')[0]
            interp = "$" in src[i:i + 3].split('"')[0]
            k = src.index('"', i) + 1
            start_line = line
            while k < n:
                if verb and src[k:k + 2] == '""': k += 2; continue
                if not verb and src[k] == "\\": k += 2; continue
                if src[k] == "\n":
                    if not verb: errs.append((start_line, "незакрытая строка")); break
                    line += 1
                if src[k] == '"': k += 1; break
                k += 1
            out.append(("$" if interp else "") + '""' + "\n" * (src[i:k].count("\n"))); i = k; continue
        if c == '"':
            k, start_line = i + 1, line
            while k < n and src[k] != '"':
                if src[k] == "\\":
                    e = src[k + 1] if k + 1 < n else ""
                    if e in VALID_ESC: k += 2; continue
                    if e in "uUx": k += 2; continue
                    errs.append((line, f"недопустимая escape-последовательность \\{e}"))
                    k += 2; continue
                if src[k] == "\n":
                    errs.append((start_line, "незакрытая строка")); break
                k += 1
            out.append('""'); i = k + 1; continue
        if c == "'":
            k = i + 1
            if k < n and src[k] == "\\":
                e = src[k + 1] if k + 1 < n else ""
                if e not in VALID_ESC and e not in "uUx":
                    errs.append((line, f"недопустимый символ '\\{e}'"))
                k += 2
            else:
                k += 1
            while k < n and src[k] != "'" and src[k] != "\n":
                k += 1
            if k >= n or src[k] != "'":
                errs.append((line, "незакрытый символьный литерал"))
            out.append("'x'"); i = k + 1; continue
        out.append(c); i += 1
    return "".join(out), errs


def brackets(code):
    st, errs, line = [], [], 1
    pairs = {")": "(", "]": "[", "}": "{"}
    for ch in code:
        if ch == "\n": line += 1
        elif ch in "([{": st.append((ch, line))
        elif ch in ")]}":
            if not st or st[-1][0] != pairs[ch]:
                errs.append((line, f"непарная «{ch}»")); return errs
            st.pop()
    if st: errs.append((st[-1][1], f"незакрытая «{st[-1][0]}»"))
    return errs


FEATURES = [
    (r"\w\s*\?\.\s*\w", "?. — C# 6"), (r"\w\s*\?\[", "?[ — C# 6"), (r'\$""', '$"…" — C# 6'),
    (r"\bnameof\s*\(", "nameof — C# 6"),
    (r"^\s*(public|private|protected|internal)[^=;{(]*\([^)]*\)\s*=>", "метод через => — C# 6"),
    (r"^\s*(public|private|protected|internal)[^=;{(]*\w\s*=>\s*[^;]*;", "свойство через => — C# 6"),
    (r"\{\s*get\s*;\s*(private\s+)?(set\s*;\s*)?\}\s*=", "инициализатор автосвойства — C# 6"),
    (r"\bout\s+var\b", "out var — C# 7"), (r"\bis\s+[A-Z]\w*\s+[a-z]\w*\s*[)&|;]", "шаблон is — C# 7"),
    (r"\bswitch\s*\{", "switch-выражение — C# 8"),
]


def types_of(code, path):
    ns_stack, res, depth = [], [], 0
    for m in re.finditer(r"\bnamespace\s+([\w.]+)|\b(class|struct|enum|interface)\s+(\w+)|[{}]", code):
        tok = m.group(0)
        if tok == "{": depth += 1; continue
        if tok == "}":
            depth -= 1
            while ns_stack and ns_stack[-1][1] > depth: ns_stack.pop()
            continue
        if m.group(1):
            ns_stack.append((m.group(1), depth + 1)); continue
        # только типы верхнего уровня пространства имён: вложенные классы не конфликтуют
        ns_depth = ns_stack[-1][1] if ns_stack else 0
        if depth == ns_depth:
            res.append((".".join(n for n, _ in ns_stack) or "<глобальное>", m.group(3), path))
    return res


def menu(src):
    """Свойства меню: блок атрибутов — от последней пустой строки до объявления (строки описаний
    содержат «]» и «;», поэтому атрибуты не разбираются регулярным выражением по скобкам)."""
    props = []
    for m in re.finditer(r"public\s+([\w.<>]+)\s+(\w+)\s*\{\s*get;\s*set;\s*\}", src):
        typ, name = m.group(1), m.group(2)
        head = src[max(0, m.start() - 3000):m.start()]
        cut = max(head.rfind("\n\n"), head.rfind("\n\r\n"), head.rfind("{ get; set; }"), head.rfind("#region"))
        attrs = head[cut + 1:] if cut >= 0 else head
        if "NinjaScriptProperty" not in attrs:
            continue
        d = re.search(r'Name\s*=\s*"\[([A-Z]+\d+)\][^"]*",\s*Order\s*=\s*(-?\d+),\s*GroupName\s*=\s*"([^"]+)"', attrs)
        r = re.search(r"Range\(\s*([-\d.eE]+)\s*,\s*([-\d.eE]+|double\.MaxValue|int\.MaxValue)\s*\)", attrs)
        props.append({"name": name, "type": typ, "index": d.group(1) if d else None,
                      "order": int(d.group(2)) if d else None, "group": d.group(3) if d else None,
                      "range": (r.group(1), r.group(2)) if r else None, "hidden": "Browsable(false)" in attrs,
                      "line": src[:m.start()].count("\n") + 1})
    return props


def defaults(src):
    i = src.find("State == State.SetDefaults")
    j = src.find("State == State.Configure", i)
    body = src[i:j] if i >= 0 else ""
    res = {}
    for m in re.finditer(r"\b([A-Z]\w*)\s*=\s*([^;=][^;]*);", body):
        res.setdefault(m.group(1), m.group(2).strip())
    return res


def num(v):
    try:
        return float(v.replace("double.MaxValue", "1e308").replace("int.MaxValue", "2147483647"))
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--src", required=True); ap.add_argument("--extra", nargs="*", default=[])
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.src, "*.cs"))) + list(a.extra)
    errors, warns, alltypes = [], [], []
    hub_src = None
    for f in files:
        src = open(f, encoding="utf-8").read()
        base = os.path.basename(f)
        code, lerr = lex(src)
        errors += [f"{base}:{l}: {t}" for l, t in lerr]
        errors += [f"{base}:{l}: {t}" for l, t in brackets(code)]
        for li, text in enumerate(code.split("\n"), 1):
            for pat, what in FEATURES:
                if re.search(pat, text):
                    errors.append(f"{base}:{li}: {what} — компилятор NinjaTrader может не принять: {text.strip()[:90]}")
        alltypes += types_of(code, base)
        if base == "DZ_SW_Hub_S021.cs":
            hub_src = src
    seen = {}
    for ns, t, p in alltypes:
        if (ns, t) in seen and seen[(ns, t)] != p:
            errors.append(f"тип {ns}.{t} объявлен в {seen[(ns, t)]} и в {p} (CS0101)")
        seen.setdefault((ns, t), p)

    info = {}
    if hub_src:
        props = menu(hub_src)
        dfl = defaults(hub_src)
        by_idx, by_name, by_grp = {}, {}, {}
        for p in props:
            if not p["index"]:
                warns.append(f"{p['name']}: свойство схемы без индекса [Xnn] в названии")
            if p["index"]:
                if p["index"] in by_idx:
                    errors.append(f"индекс [{p['index']}] у {by_idx[p['index']]} и у {p['name']}")
                by_idx.setdefault(p["index"], p["name"])
            if p["name"] in by_name:
                errors.append(f"свойство {p['name']} объявлено дважды (CS0102)")
            by_name[p["name"]] = p
            key = (p["group"], p["order"])
            if p["group"] and key in by_grp:
                warns.append(f"Order {p['order']} в группе «{p['group']}» у {by_grp[key]} и у {p['name']}")
            by_grp.setdefault(key, p["name"])
            v = dfl.get(p["name"])
            if v is None:
                warns.append(f"[{p['index']}] {p['name']}: нет умолчания в SetDefaults — будет значение типа по умолчанию")
            elif p["range"] and num(v) is not None:
                lo, hi = num(p["range"][0]), num(p["range"][1])
                if not (lo - 1e-12 <= num(v) <= hi + 1e-12):
                    errors.append(f"[{p['index']}] {p['name']} = {v} вне Range({p['range'][0]}, {p['range'][1]})")
        # все подписи меню, включая свойства вне схемы (цвета панели и т. п.)
        all_labels = {}
        for m in re.finditer(r'Display\(Name\s*=\s*"\[([A-Z]+\d+)\]([^"]*)"', hub_src):
            all_labels.setdefault(m.group(1), []).append(m.group(2).strip()[:40])
        for k, v in all_labels.items():
            if len(v) > 1:
                errors.append(f"индекс [{k}] у нескольких подписей: {' | '.join(v)}")
        known = set(all_labels) | {f"MOD{i}" for i in range(1, 16)}
        refs = {}
        for f in files:
            if f in a.extra:
                continue                                   # чужие стратегии со своими индексами
            for m in re.finditer(r"\[([A-Z]{1,3}\d{2,3})\]", open(f, encoding="utf-8").read()):
                if m.group(1) not in known and not re.match(r"MOD\d+$", m.group(1)):
                    refs.setdefault(m.group(1), set()).add(os.path.basename(f))
        for k, fs in sorted(refs.items()):
            warns.append(f"Э33: ссылка на [{k}] — такого индекса нет в меню ({', '.join(sorted(fs))})")
        info = {"настроек в схеме": len(props), "с индексом": len(by_idx), "умолчаний найдено": len(dfl)}

    if hub_src:
        assigned = set(re.findall(r"\.(\w+)\s*=(?!=)", hub_src))
        assigned |= set(re.findall(r"\.(\w+)\.(?:Add|AddRange|Clear)\s*\(", hub_src))   # заполнение списка
        assigned |= set(re.findall(r"\.(\w+)\.\w+\s*=(?!=)", hub_src))               # поля вложенного объекта
        for f in files:
            if f in a.extra:
                continue
            src = open(f, encoding="utf-8").read()
            for cm in re.finditer(r"public\s+class\s+(Sw\w+Config)\b", src):
                body = src[cm.end():]
                body = body[body.find("{") + 1:]
                depth, k = 1, 0
                while k < len(body) and depth:
                    depth += {"{": 1, "}": -1}.get(body[k], 0); k += 1
                for fm in re.finditer(r"public\s+(?!class|static|const|readonly)[\w.<>\[\]]+\s+(\w+)\s*(?:=|;)", body[:k]):
                    if fm.group(1) not in assigned:
                        warns.append(f"Э34: {cm.group(1)}.{fm.group(1)} ({os.path.basename(f)}) — ядро не передаёт, всегда умолчание")
    print(f"{VERSION}: файлов {len(files)}, типов верхнего уровня {len(alltypes)}" + (f", {info}" if info else ""))
    for e in errors: print("  ОШИБКА  " + e)
    for w in warns: print("  внимание " + w)
    print(f"ИТОГ: ошибок {len(errors)}, предупреждений {len(warns)}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
