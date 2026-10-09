#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DZ_RUNNER_Prepare.py — сборка исходников исполнителя модулей на ПК, v1.0 (2026-10-01)

Исполнитель компилирует ТЕ ЖЕ исходники модулей, что торгуют в NinjaTrader, без единой правки.
Из исходника коммутатора извлекается, а не переписывается руками:
  Contracts.g.cs   SwRole, SwHealth, SwVerdict, SwActionKind, SwSignal, SwAction, SwModule — текстом, как есть;
  HostView.g.cs    SwHostView с ТЕМИ ЖЕ сигнатурами; тела перенаправлены в среду исполнителя;
  config_map.json  «поле конфигурации ← свойство меню» по блокам BuildSlots — проводка коммутатора.
Модули копируются из папки NinjaTrader или из снимка DZ_SYS_Bridge (тогда идентичность доказана отпечатком).

  python DZ_RUNNER_Prepare.py --src "<…>\\bin\\Custom\\Strategies" --out build
  cd build && dotnet build -c Release
"""
import argparse, json, os, re, shutil, hashlib

VERSION = "DZ_RUNNER_Prepare-v1.0 (2026-10-01)"
HERE = os.path.dirname(os.path.abspath(__file__))
SKIP = ("DZ_SW_Hub_S021.cs", "DZ_SW_Financial_S021.cs", "DZ_SW_WsBridge_S021.cs")
CONTRACTS = ("SwRole", "SwHealth", "SwVerdict", "SwActionKind", "SwSignal", "SwAction", "SwModule")


def block(src, start):
    """Текст от позиции объявления до парной закрывающей скобки, с учётом строк и комментариев."""
    i = src.index("{", start); d = 0; j = i; n = len(src)
    while j < n:
        c = src[j]
        if src.startswith("//", j): j = src.find("\n", j); continue
        if src.startswith("/*", j): j = src.find("*/", j) + 2; continue
        if c == '"':
            j += 1
            while src[j] != '"': j += 2 if src[j] == "\\" else 1
        elif c == "'":
            j += 1
            while src[j] != "'": j += 2 if src[j] == "\\" else 1
        elif c == "{": d += 1
        elif c == "}":
            d -= 1
            if d == 0: return src[start:j + 1]
        j += 1
    raise ValueError("нет парной скобки")


def decl_start(src, kind_name):
    m = re.search(r"(?m)^[ \t]*(?:///[^\n]*\n[ \t]*)*(?:\[[^\]]*\]\s*)*public\s+(?:abstract\s+|sealed\s+)?(?:enum|struct|class)\s+" + kind_name + r"\b", src)
    if not m: raise ValueError(f"не найдено объявление {kind_name}")
    return m.start()


def ns_of(src, pos):
    return re.findall(r"namespace\s+([\w\.]+)", src[:pos])[-1]


def main():
    ap = argparse.ArgumentParser(description=VERSION)
    ap.add_argument("--src", required=True); ap.add_argument("--out", default="build")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    hub = open(os.path.join(a.src, "DZ_SW_Hub_S021.cs"), encoding="utf-8").read()
    files = {}
    # 1. модули — копии без правки
    for f in sorted(os.listdir(a.src)):
        if f.startswith("DZ_SW_") and f.endswith(".cs") and f not in SKIP:
            shutil.copy2(os.path.join(a.src, f), os.path.join(a.out, f))
            files[f] = hashlib.sha256(open(os.path.join(a.src, f), "rb").read()).hexdigest()
    # 2. контракты — текстом из коммутатора
    parts = {}
    for name in CONTRACTS:
        p = decl_start(hub, name); parts.setdefault(ns_of(hub, p), []).append(block(hub, p))
    with open(os.path.join(a.out, "Contracts.g.cs"), "w", encoding="utf-8") as f:
        f.write("// СГЕНЕРИРОВАНО DZ_RUNNER_Prepare из DZ_SW_Hub_S021.cs — не править руками\nusing System;\nusing System.Collections.Generic;\nusing NinjaTrader.NinjaScript;\n\n")
        for ns, blocks in parts.items(): f.write(f"namespace {ns}\n{{\n" + "\n\n".join(blocks) + "\n}\n\n")
    # 3. SwHostView — те же сигнатуры, тела в среду исполнителя
    p = hub.index("public sealed class SwHostView"); body = block(hub, p); inner = body[body.index("{") + 1:-1]
    members, out = [], []
    depth = 0; k = 0; top = []
    for m in re.finditer(r"[{}]|\n", inner):
        if m.group(0) == "{": depth += 1
        elif m.group(0) == "}": depth -= 1
        elif depth == 0: top.append(inner[k:m.start()]); k = m.end()
    text = "\n".join(top) + "\n" + inner[k:]
    for m in re.finditer(r"(?:public|internal)\s+((?:[\w<>\[\]\.]+))\s+(\w+)\s*(\(([^)]*)\))?\s*(?=\{|=>)", inner):
        typ, name, params = m.group(1), m.group(2), m.group(4)
        if name == "SwHostView" or typ in ("sealed", "class"): continue
        if params is None:
            members.append(name); out.append(f"        public {typ} {name} {{ get {{ return rt.{name}; }} }}")
        else:
            args = ", ".join(x.strip().split()[-1].split("=")[0].strip() for x in params.split(",") if x.strip())
            members.append(name)
            out.append(f"        {'internal' if inner[m.start():m.start()+8]=='internal' else 'public'} {typ} {name}({params}) {{ {'' if typ == 'void' else 'return '}rt.{name}({args}); }}")
    with open(os.path.join(a.out, "HostView.g.cs"), "w", encoding="utf-8") as f:
        f.write("// СГЕНЕРИРОВАНО DZ_RUNNER_Prepare: сигнатуры SwHostView коммутатора, тела — среда исполнителя\nusing System;\nusing NinjaTrader.NinjaScript;\n\n"
                "namespace NinjaTrader.NinjaScript.Strategies\n{\n    public sealed class SwHostView\n    {\n        private readonly DzRunner.RunnerRuntime rt;\n"
                "        internal SwHostView(DzRunner.RunnerRuntime r) { rt = r; }\n" + "\n".join(out) + "\n    }\n}\n")
    # 4. проводка конфигураций из BuildSlots
    cmap = {}
    for m in re.finditer(r"(Sw\w+Config)\s+(\w+)\s*=\s*new\s+\1\s*\(\s*\)\s*;", hub):
        cls, var = m.group(1), m.group(2); seg = hub[m.end():m.end() + 4000]; seg = seg[:seg.find("modules.Add")]
        cmap[cls] = {f: pr for f, pr in re.findall(r"\b" + var + r"\.(\w+)\s*=\s*(\w+)\s*;", seg)}
    json.dump({"generator": VERSION, "modules_sha256": files, "host_members": members, "config_map": cmap},
              open(os.path.join(a.out, "config_map.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 5. исполнитель и проект
    for f in ("Program.cs", "DZ_SW_Host_Runner.csproj"):
        shutil.copy2(os.path.join(HERE, f), os.path.join(a.out, f))
    runtime = open(os.path.join(HERE, "Program.cs"), encoding="utf-8").read()
    missing = [n for n in members if not re.search(r"public\s+[\w<>\[\]\.]+\s+" + n + r"\b", runtime)]
    print(f"[исполнитель] модулей {len(files)}, контракты {sum(len(v) for v in parts.values())}, членов хоста {len(members)}, конфигураций {len(cmap)}")
    print("  в среде исполнителя нет членов хоста:", missing or "нет — сигнатуры покрыты")


if __name__ == "__main__":
    main()
