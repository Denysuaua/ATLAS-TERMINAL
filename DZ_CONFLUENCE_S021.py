# Парное схождение сигналов на реальных данных — проверка таблицы спецификации каскада (2026-10-05)
import importlib.util, numpy as np, pandas as pd, json, math, time, pickle
def load(n,f):
    s=importlib.util.spec_from_file_location(n,f); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
M=load('ms','DZ_MS_Market_S021.py'); P=load('port','DZ_PORT_Chains_S021.py'); T9=load('t9','DZ_MODTEST_MOD9_S021.py'); T11=load('t11','DZ_MODTEST_MOD11_S021.py')
t0=time.time()
reg=pd.read_csv('registry/registry_trades_mod1.csv',sep=';'); reg['t']=pd.to_datetime(reg['time_utc'],utc=True).values.astype('datetime64[ns]')
APPROVED=[(1,'CHOCH+',120),(1,'CHOCH+',60),(2,'BOS swing',120),(2,'BOS',240)]
appr=reg[[((r.category,r.event,r.tf) in APPROVED) for r in reg.itertuples()]].copy().reset_index(drop=True); dr=appr.dir.to_numpy()
def at(close,d,tfm):
    strict=(appr.tf.to_numpy()!=tfm); pos=np.searchsorted(close,appr['t'].to_numpy(),side='left')-1; pos=np.where(strict,pos,np.searchsorted(close,appr['t'].to_numpy(),side='right')-1); return np.where(pos>=0,d[np.clip(pos,0,len(d)-1)],0)
V={}
# MOD9 профиль 60m
z=np.load('modtest/mod9/cache_tf60.npz'); close=z['close'].astype('datetime64[ns]'); ratio=z['ratio']; n=len(close); S=np.array(T9.S_BW)
hb=np.clip(np.round(64*np.clip(np.nan_to_num(ratio,nan=1.0),0.5,2.0)),3,160); j=np.abs(S[None,:]-hb[:,None]).argmin(1); B=np.column_stack([z[f'beta_Epanechnikov_{h}'] for h in T9.S_BW]); sl=B[np.arange(n),j]
d9=np.where(np.isnan(sl),0,np.where(np.abs(sl)>=0.25,np.sign(sl),0)).astype(np.int8); V['MOD9']=at(close,d9,60)
# MOD10 профиль 240m
z=np.load('modtest/mod10/cache_tf240.npz'); c10=z['close'].astype('datetime64[ns]'); SL=z['slopes']; H=z['H256']; S10=np.array([4,6,8,10,12,14,16,20,24,28,32,40,48,56,64,80,96,112,128,160])
tt=np.clip((H-0.37)/0.2,0,1); hb10=np.clip(np.round(16+tt*64),3,160); j10=np.abs(S10[None,:]-hb10[:,None]).argmin(1); sl10=SL[np.arange(len(H)),j10]
d10=np.where(np.isnan(sl10)|np.isnan(H),0,np.where(np.abs(sl10)>=0.25,np.sign(sl10),0)).astype(np.int8); V['MOD10']=at(c10,d10,240)
# MOD11 умолчания 15m
m1=M.load_npz('/home/claude/atlas/terminal/Atlas_terminal/certification/data_certified/MGC/MGC_M1.npz'); m1=m1[(m1.index>='2015-01-01')&(m1.index<'2019-01-01')]
nt=M.load_nt_volume('/home/claude/atlas/nt','2015-01-01','2019-01-01'); jj=m1.join(nt[['v']],how='left',rsuffix='_nt'); m1['v']=jj['v_nt'].fillna(0.0).to_numpy()
bars=M.resample_all(m1,[5,15,60]); b15=bars[15].reset_index(drop=True); c15=b15['c'].to_numpy(float); cl15=pd.DatetimeIndex(b15['close_utc']).to_numpy('datetime64[ns]')
raw,params=pickle.load(open('modtest/mod11/features_tf15.pkl','rb')); atr=raw[:,0]*c15
pos=np.searchsorted(cl15,appr['t'].to_numpy(),side='left')-1
def v11(i):
    r=T11.classify_at(i,raw,c15,atr,params,2000,4,4)
    if r is None: return 0
    d,lab,backs,y=r; take=lab[:16]; vote=take.sum(); st=abs(vote)/len(take); return int(np.sign(vote)) if st>=0.5 else 0
V['MOD11']=np.array([v11(i) if i>=0 and i+4<len(c15) else 0 for i in pos]); print('MOD11 готов',round(time.time()-t0),flush=True)
# MOD13 направление M60 (порт)
b60=bars[60].reset_index(drop=True); st60,lo60,up60,z60,cor60,rd60,zf=P.kalman_tracks(b60,20,30,120,confirm=5); d13=np.where(st60=='T+',1,np.where(st60=='T-',-1,0)).astype(np.int8)
V['MOD13']=at(pd.DatetimeIndex(b60['close_utc']).to_numpy('datetime64[ns]'),d13,60); print('MOD13 готов',round(time.time()-t0),flush=True)
# MOD14 рычаг (порт, свеча M5 из M1, умолчания)
m1b=bars[1].reset_index(drop=True); m5=bars[5].reset_index(drop=True); lv,_=P.lever_series(m5,m1b); lv_avail=np.r_[0,lv[:-1]]
V['MOD14']=at(pd.DatetimeIndex(m5['close_utc']).to_numpy('datetime64[ns]'),lv_avail,5); print('MOD14 готов',round(time.time()-t0),flush=True)
def passes(x): return (x==0)|(x==dr)
def stat(mask,name):
    p=appr[mask]; pw=p.loc[p.pnl_usd>0,'pnl_usd'].sum(); pl=-p.loc[p.pnl_usd<0,'pnl_usd'].sum()
    return {'комбинация':name,'сделок':int(len(p)),'снижение частоты':round(1-len(p)/len(appr),3),'WinRate':round(float(p.win.mean()),3) if len(p) else None,'PF':round(float(pw/pl),2) if pl>0 else None,'$/сделку':round(float(p.pnl_usd.mean()),2) if len(p) else None}
rows=[stat(np.ones(len(appr),bool),'MOD1 (база доверенных сигналов)')]
for k in V: rows.append(stat(passes(V[k]),f'MOD1 + {k}'))
pairs={'MOD1 + MOD11 (спец.: 53,5 → 70 %)':['MOD11'],'MOD10 + MOD11 (спец.: 52 → 69 %)':['MOD10','MOD11'],'MOD9 + MOD14 (спец.: 51,5 → 66 %)':['MOD9','MOD14'],'MOD11 + контекст старшего ТФ MOD13 (спец. «MOD15»: 54 → 67,5 %)':['MOD11','MOD13'],'MOD1 + MOD11 + MOD14 (спец.: 53,5 → 78 %)':['MOD11','MOD14'],'MOD9 + MOD10 (измерено ранее)':['MOD9','MOD10'],'MOD9 + MOD10 + MOD13':['MOD9','MOD10','MOD13'],'все пять':['MOD9','MOD10','MOD11','MOD13','MOD14']}
for name,mods in pairs.items():
    m=np.ones(len(appr),bool)
    for k in mods: m&=passes(V[k])
    rows.append(stat(m,name))
# строгое схождение: модули не нейтральны, а согласны по направлению
def agrees(x): return (x==dr)
for name,mods in {'строгое MOD1 + MOD11 (Agree, не нейтраль)':['MOD11'],'строгое MOD10 + MOD11':['MOD10','MOD11'],'строгое MOD9 + MOD14':['MOD9','MOD14'],'строгое MOD1 + MOD11 + MOD14':['MOD11','MOD14']}.items():
    m=np.ones(len(appr),bool)
    for k in mods: m&=agrees(V[k])
    rows.append(stat(m,name))
R=pd.DataFrame(rows); pd.set_option('display.width',220); print(R.to_string(index=False))
R.to_csv('modtest/confluence_real.csv',sep=';',index=False); json.dump({k:[int(x) for x in v] for k,v in V.items()},open('modtest/confluence_verdicts.json','w'))
print('время',round(time.time()-t0))
