import importlib.util, numpy as np, pandas as pd, json, math, time
def load(n,f):
    s=importlib.util.spec_from_file_location(n,f); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
T=load('t','DZ_MODTEST_MOD10_S021.py'); M=load('ms','DZ_MS_Market_S021.py'); P=load('port','DZ_PORT_Chains_S021.py')
reg=pd.read_csv('registry/registry_trades_mod1.csv',sep=';'); reg['t']=pd.to_datetime(reg['time_utc'],utc=True).values.astype('datetime64[ns]')
appr=reg[[((r.category,r.event,r.tf) in T.APPROVED) for r in reg.itertuples()]].copy()
S=np.array(T.S_BW)
def module_dir(tf, period, bw, band, thr, gate=0.0, inverse=False, prior=0, rw=0.47):
    z=np.load(f'modtest/mod10/cache_tf{tf}.npz'); close=z['close'].astype('datetime64[ns]'); SL=z['slopes']; H=z[f'H{period}'].copy()
    if prior>0: H=rw+(H-rw)*period/(period+prior)
    t=np.clip((H-band[0])/max(1e-9,band[1]-band[0]),0,1)
    if inverse: t=1-t
    hb=np.clip(np.round(bw[0]+t*(bw[1]-bw[0])),3,160); j=np.abs(S[None,:]-hb[:,None]).argmin(1); sl=SL[np.arange(len(H)),j]
    d=np.where(np.isnan(sl)|np.isnan(H),0,np.where(np.abs(sl)>=thr,np.sign(sl),0)).astype(np.int8)
    if gate>0: d=np.where(np.abs(H-rw)<gate,0,d).astype(np.int8)
    return close,d,H,hb
def evaluate(close,d,tfm,s):
    strict=(s.tf.to_numpy()!=tfm); pos=np.searchsorted(close,s['t'].to_numpy(),side='left')-1
    pos=np.where(strict,pos,np.searchsorted(close,s['t'].to_numpy(),side='right')-1); md=np.where(pos>=0,d[np.clip(pos,0,len(d)-1)],0)
    ok=(md==0)|(md==s.dir.to_numpy()); p=s[ok]; r=s[~ok]
    pw=p.loc[p.pnl_usd>0,'pnl_usd'].sum(); pl=-p.loc[p.pnl_usd<0,'pnl_usd'].sum()
    return {'pass_n':int(len(p)),'pass_wr':round(p.win.mean(),3),'pass_exp':round(p.pnl_usd.mean(),2),'pass_pf':round(pw/pl,3) if pl>0 else None,'rej_n':int(len(r)),'rej_wr':round(r.win.mean(),3) if len(r) else None,
            'kept_winners':round(p.win.sum()/s.win.sum(),3),'cut_losers':round((1-r.win).sum()/(1-s.win).sum(),3),'capture_total':round(p.pnl_usd.sum()/(p.mfe_ticks.sum()),3),'time_dir_share':round(float(np.mean(d!=0)),3)}, md
out={}
chosen={'240':(240,256,(16,80),(0.37,0.57),0.25),'60':(60,128,(16,80),(0.42,0.52),0.25)}
for name,(tf,per,bw,band,thr) in chosen.items():
    close,d,H,hb=module_dir(tf,per,bw,band,thr); base,md_base=evaluate(close,d,tf,appr); out[f'{name}m база']=base
    print(name,'база',base)
    for g in (0.02,0.03,0.05):
        close,d,H,hb=module_dir(tf,per,bw,band,thr,gate=g); e,_=evaluate(close,d,tf,appr); out[f'{name}m H11 шлюз {g}']=e; print(' H11',g,e)
    close,d,H,hb=module_dir(tf,per,bw,band,thr,inverse=True); e,_=evaluate(close,d,tf,appr); out[f'{name}m H13 обратное']=e; print(' H13',e)
    for pr in (64,128,256,512):
        close,d,H,hb=module_dir(tf,per,bw,band,thr,prior=pr); e,_=evaluate(close,d,tf,appr); out[f'{name}m Э46 приор {pr}']=e; print(' Э46',pr,e)
    # покрытие по состояниям и статистика H/окна
    close,d,H,hb=module_dir(tf,per,bw,band,thr)
    out[f'{name}m покрытие']={'вверх':round(float(np.mean(d>0)),3),'вниз':round(float(np.mean(d<0)),3),'плоско':round(float(np.mean((d==0)&~np.isnan(H))),3),'прогрев':round(float(np.mean(np.isnan(H))),3),'H медиана':round(float(np.nanmedian(H)),3),'H 10–90%':[round(float(np.nanpercentile(H,10)),3),round(float(np.nanpercentile(H,90)),3)],'окно медиана':float(np.nanmedian(hb))}
    print(' покрытие',out[f'{name}m покрытие'])
# взаимодействие: согласие направления MOD10(240m) с MOD13 M60 и MOD9 M15 на утверждённых сигналах
t0=time.time()
m1=M.load_npz('/home/claude/atlas/terminal/Atlas_terminal/certification/data_certified/MGC/MGC_M1.npz'); m1=m1[(m1.index>='2015-01-01')&(m1.index<'2019-01-01')]
bars=M.resample_all(m1,[15,60]); m15=bars[15].reset_index(drop=True); m60=bars[60].reset_index(drop=True)
kd15,_=P.kernel_series(m15['h'].to_numpy(float),m15['l'].to_numpy(float),m15['c'].to_numpy(float))
st60,lo60,up60,z60,cor60,rd60,zf=P.kalman_tracks(m60,20,30,120,confirm=5); kal=np.where(st60=='T+',1,np.where(st60=='T-',-1,0)).astype(np.int8)
c15=pd.DatetimeIndex(m15['close_utc']).to_numpy('datetime64[ns]'); c60=pd.DatetimeIndex(m60['close_utc']).to_numpy('datetime64[ns]')
tf,per,bw,band,thr=chosen['240']; close,d10,H,hb=module_dir(tf,per,bw,band,thr)
def at(close,d,s,tfm):
    strict=(s.tf.to_numpy()!=tfm); pos=np.searchsorted(close,s['t'].to_numpy(),side='left')-1
    pos=np.where(strict,pos,np.searchsorted(close,s['t'].to_numpy(),side='right')-1); return np.where(pos>=0,d[np.clip(pos,0,len(d)-1)],0)
a10=at(close,d10,appr,240); a9=at(c15,kd15,appr,15); a13=at(c60,kal,appr,60); dr=appr.dir.to_numpy()
def agree(x,y):
    both=(x!=0)&(y!=0); return {'оба определены':round(float(both.mean()),3),'согласие при обоих':round(float((x[both]==y[both]).mean()),3) if both.any() else None}
inter={'MOD10×MOD13':agree(a10,a13),'MOD10×MOD9':agree(a10,a9),'MOD9×MOD13':agree(a9,a13)}
def passes(x): return (x==0)|(x==dr)
p10,p9,p13=passes(a10),passes(a9),passes(a13)
inter['пропуск: MOD10, MOD9, MOD13, все три']=[round(float(p10.mean()),3),round(float(p9.mean()),3),round(float(p13.mean()),3),round(float((p10&p9&p13).mean()),3)]
inter['совпадение решений пропуск/вето MOD10×MOD13']=round(float((p10==p13).mean()),3); inter['MOD10×MOD9']=round(float((p10==p9).mean()),3)
print(inter, round(time.time()-t0))
json.dump({'chosen':{k:{'tf':v[0],'period':v[1],'bw':v[2],'band':v[3],'thr':v[4]} for k,v in chosen.items()},'experiments':out,'interaction':inter},open('modtest/mod10/mod10_experiments_interaction.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
