# Экономика цепочек решений на доверенных сигналах: сделок в год, PnL на контракт, худший год, просадка — против целевой доходности
import json, numpy as np, pandas as pd, argparse
ap=argparse.ArgumentParser(); ap.add_argument('--target',type=float,default=0.66); ap.add_argument('--capitals',nargs='*',type=float,default=[1000,2500,5000]); ap.add_argument('--maxdd-share',type=float,default=0.25); a=ap.parse_args()
V={k:np.array(v) for k,v in json.load(open('modtest/confluence_verdicts.json')).items()}
reg=pd.read_csv('registry/registry_trades_mod1.csv',sep=';'); reg['t']=pd.to_datetime(reg['time_utc'],utc=True)
APPROVED=[(1,'CHOCH+',120),(1,'CHOCH+',60),(2,'BOS swing',120),(2,'BOS',240)]
appr=reg[[((r.category,r.event,r.tf) in APPROVED) for r in reg.itertuples()]].copy().reset_index(drop=True); dr=appr.dir.to_numpy(); appr['year']=appr.t.dt.year
def passes(x): return (x==0)|(x==dr)
chains={'MOD1 база':np.ones(len(appr),bool),'MOD1 + MOD9':passes(V['MOD9']),'MOD1 + MOD10':passes(V['MOD10']),'MOD1 + MOD9 + MOD10':passes(V['MOD9'])&passes(V['MOD10']),
        'MOD1 + все пять':passes(V['MOD9'])&passes(V['MOD10'])&passes(V['MOD11'])&passes(V['MOD13'])&passes(V['MOD14']),'строгое MOD9 + MOD14 (Э68)':(V['MOD9']==dr)&(V['MOD14']==dr)}
rows=[]
for name,m in chains.items():
    p=appr[m].sort_values('t'); cum=p.pnl_usd.cumsum().to_numpy(); dd=float((np.maximum.accumulate(cum)-cum).max()) if len(p) else 0
    yr=p.groupby('year').pnl_usd.sum()
    rows.append({'цепочка':name,'сделок/год':round(len(p)/4),'$/сделку':round(p.pnl_usd.mean(),2),'PnL/год':round(yr.mean()),'худший год':round(yr.min()),'лучший год':round(yr.max()),'MaxDD $':round(dd),'PnL/MaxDD':round(yr.mean()/dd,2) if dd else None,'WinRate':round(p.win.mean(),3)})
T=pd.DataFrame(rows); print(T.to_string(index=False)); T.to_csv('modtest/chain_economics.csv',sep=';',index=False)
best=T.loc[T['PnL/год'].idxmax()]
for cap in a.capitals:
    need=a.target*cap; print(f'капитал {cap:.0f} $/контракт: нужно {need:.0f} $/год; лучшая цепочка {best["PnL/год"]:.0f} $/год → дефицит ×{need/max(1,best["PnL/год"]):.1f}; её MaxDD {best["MaxDD $"]:.0f} $ = {best["MaxDD $"]/cap:.0%} капитала (лимит {a.maxdd_share:.0%})')
print('требование к связке при лимите просадки: PnL/год ≥', a.target/a.maxdd_share, '× MaxDD — сейчас', best['PnL/MaxDD'])
