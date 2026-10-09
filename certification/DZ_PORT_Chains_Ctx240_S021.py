import importlib.util, numpy as np, pandas as pd, json, time
def load(name, path):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
M=load('ms','DZ_MS_Market_S021.py'); P=load('port','DZ_PORT_Chains_S021.py')
t0=time.time()
m1=M.load_npz('/home/claude/atlas/terminal/Atlas_terminal/certification/data_certified/MGC/MGC_M1.npz')
m1=m1[(m1.index>='2015-01-01')&(m1.index<'2019-01-01')]
bars=M.resample_all(m1,[5,15,240]); m5=bars[5].reset_index(drop=True); m15=bars[15].reset_index(drop=True); m240=bars[240].reset_index(drop=True)
c5=pd.DatetimeIndex(m5['close_utc']).to_numpy('datetime64[ns]'); c15=pd.DatetimeIndex(m15['close_utc']).to_numpy('datetime64[ns]'); c240=pd.DatetimeIndex(m240['close_utc']).to_numpy('datetime64[ns]')
ev5=P.pac_series(m5['h'].to_numpy(float),m5['l'].to_numpy(float),m5['c'].to_numpy(float))
ev15=P.pac_series(m15['h'].to_numpy(float),m15['l'].to_numpy(float),m15['c'].to_numpy(float),higher=True)
pos15=P.latest_before(c15,c5,True); evh={}; seen=set()
for i in range(len(m5)):
    p=pos15[i]
    if p>=0 and p not in seen and ev15[p]: evh[i]=ev15[p]; seen.add(p)
cand=P.pac_candidates(ev5,evh,len(m5)); n5=len(m5)
cd=np.zeros(n5,np.int8)
for i,v in cand.items(): cd[i]=v[1]
# контекст 240m: тренд структуры (разметка DZ_MS, метка действует с закрытия подтверждающего бара) и Хёрст R/S 128 баров (< t)
lab=M.load_labeled('train'); t240=lab['240m_trend'].to_numpy(np.int8); lidx=lab.index.values.astype('datetime64[ns]')
pos_l=np.searchsorted(lidx, c5, side='right')-1; ctx=np.where(pos_l>=0, t240[np.clip(pos_l,0,len(t240)-1)], 0)
c240v=m240['c'].to_numpy(float); r240=np.diff(c240v); H=np.full(len(c240v),np.nan)
for i in range(128,len(c240v)): H[i]=M.hurst_rs(r240[i-128:i])
pos240=P.latest_before(c240,c5,True); H5=np.where(pos240>=0, H[np.clip(pos240,0,len(H)-1)], np.nan)
F_ctx=(ctx==cd); F_h=np.nan_to_num(H5,nan=0.0)>0.5
win1=(60,8*60); win2=(9*60+30,18*60+30); until=21*60+30; hard=22*60+30
res={}; alltr=[]
for name,ok in {"H: PAC по тренду структуры 240m":F_ctx,"I: PAC по тренду 240m ∧ H(240m) > 0,5":F_ctx&F_h,"J: PAC ∧ H(240m) > 0,5":F_h}.items():
    tr=P.simulate(m5,cand,ok,None,hard,win1,win2,until,name=name); res[name]=P.summarize(tr); alltr.append(tr); print(name,res[name])
tr=pd.concat(alltr); tr['year']=pd.to_datetime(tr['time_utc'],utc=True).dt.year
print(tr.groupby(['chain','year']).agg(n=('pnl_usd','size'),pnl=('pnl_usd','sum')).unstack('year').round(0).to_string())
tr.to_csv('chains_train/chain_trades_ctx240.csv',sep=';',index=False,float_format='%.3f')
json.dump(res,open('chains_train/chains_ctx240.json','w',encoding='utf-8'),ensure_ascii=False,indent=2,default=str)
print('время',round(time.time()-t0))
