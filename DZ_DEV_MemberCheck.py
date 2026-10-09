# Проверка членов наших типов с учётом областей видимости и числа аргументов вызовов цепочки
import re, glob, collections, sys
def lex(t):
    out=[];i=0;n=len(t)
    while i<n:
        c=t[i]; d=t[i:i+2]
        if d=="//": j=t.find("\n",i); i=n if j<0 else j; continue
        if d=="/*": j=t.find("*/",i+2); i=n if j<0 else j+2; continue
        if t[i:i+3] in ('$@"','@$"'): i+=3; verb=True
        elif d=='@"': i+=2; verb=True
        elif d=='$"': i+=2; verb=False
        elif c=='"': i+=1; verb=False
        elif c=="'":
            j=i+1
            while j<n and t[j]!="'": j+= 2 if t[j]=="\\" else 1
            out.append("'x'"); i=j+1; continue
        else: out.append(c); i+=1; continue
        while i<n:
            if verb and t[i:i+2]=='""': i+=2; continue
            if not verb and t[i]=="\\": i+=2; continue
            if t[i]=='"': i+=1; break
            i+=1
        out.append('""')
    return "".join(out)
code={f:lex(open(f,encoding="utf-8").read()) for f in sorted(glob.glob(sys.argv[1] if len(sys.argv)>1 else "*.cs"))}
if not code or any(a in ("-h","--help") for a in sys.argv[1:]):
    print('использование: python DZ_DEV_MemberCheck.py "DZ_SW_*.cs"  — проверка членов и аргументов вызовов; файлов по маске: %d' % len(code))
    sys.exit(0 if any(a in ("-h","--help") for a in sys.argv[1:]) else 2)
allc="\n".join(code.values())
def body(name):
    m=re.search(r"\b(?:struct|class)\s+"+name+r"\b[^{]*\{", allc); i=m.end(); d=1; j=i
    while d: d+= allc[j]=="{"; d-= allc[j]=="}"; j+=1
    return allc[i:j]
def members(b):
    names=set(); meth=collections.defaultdict(set)
    for m in re.finditer(r"\bpublic\s+(?:static\s+|readonly\s+|const\s+)*([\w<>\[\]\.]+)\s+([\w\s,]+?)\s*(;|=[^;]*;)", b):
        for nm in m.group(2).split(","): names.add(nm.strip())
    for m in re.finditer(r"\bpublic\s+(?:static\s+|virtual\s+|override\s+|abstract\s+)*[\w<>\[\]\.]+\s+(\w+)\s*(\{|=>)", b): names.add(m.group(1))
    for m in re.finditer(r"\bpublic\s+(?:static\s+|virtual\s+|override\s+|abstract\s+)*[\w<>\[\]\.]+\s+(\w+)\s*\(([^)]*)\)", b):
        meth[m.group(1)].add(0 if not m.group(2).strip() else m.group(2).count(",")+1); names.add(m.group(1))
    return names, meth
M={t:members(body(t)) for t in ("SwSignal","SwAction","SwVisualEvent","SwHostView")}
def scope_end(c,p):
    d=0
    for j in range(p,len(c)):
        if c[j]=="{": d+=1
        elif c[j]=="}":
            d-=1
            if d<0: return j
    return len(c)
def argc(s,k):
    d=0;n=0;any_=False;j=k
    while True:
        ch=s[j]
        if ch in "([{": d+=1
        elif ch in ")]}":
            d-=1
            if d==0: return n+1 if any_ else 0
        elif ch=="," and d==1: n+=1
        elif d==1 and not ch.isspace(): any_=True
        j+=1
errs=[]
for f,c in code.items():
    for m in re.finditer(r"\b(SwSignal|SwAction|SwVisualEvent)\s+(\w+)\s*(?=[=;,)])", c):
        t,v=m.group(1),m.group(2); end=scope_end(c,m.end())
        for u in re.finditer(r"(?<![\w.])"+v+r"\.(\w+)", c[m.end():end]):
            # объявление той же переменной другого типа внутри области — затенение, дальше не проверяем
            if u.group(1) not in M[t][0]: errs.append(f"{f}: {t} {v}.{u.group(1)}")
    if "Hub" not in f:
        for m in re.finditer(r"\bHost\.(\w+)", c):
            if m.group(1) not in M["SwHostView"][0]: errs.append(f"{f}: Host.{m.group(1)} — нет в SwHostView")
    for m in re.finditer(r"(SwVisualEvent|SwSignal|SwAction)\.(\w+)\s*\(|\)\s*\.\s*(As\w+|With\w+|InRing)\s*\(", c):
        t=m.group(1) or "SwVisualEvent"; name=m.group(2) or m.group(3); a=argc(c,m.end()-1); meth=M[t][1]
        if name not in meth: errs.append(f"{f}: {t}.{name} — нет метода")
        elif a not in meth[name]: errs.append(f"{f}: {t}.{name}({a} арг.) — есть {sorted(meth[name])}")
print("проверка членов и аргументов:", "ошибок нет" if not errs else f"ошибок {len(set(errs))}")
for e in sorted(set(errs))[:40]: print("  ", e)
