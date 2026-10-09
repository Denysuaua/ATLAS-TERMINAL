# Плато, робастный профиль, эксперименты K61/K63/K64/Э45/[K55], время покрытия, TimeExit, взаимодействие — MOD9
import importlib.util, numpy as np, pandas as pd, json, math, time, sys
def load(n,f):
    s=importlib.util.spec_from_file_location(n,f); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
T=load('t9','DZ_MODTEST_MOD9_S021.py'); M=load('ms','DZ_MS_Market_S021.py'); R=load('reg','DZ_REG_Trades_S021.py'); P=load('port','DZ_PORT_Chains_S021.py')
reg=pd.read_csv('registry/registry_trades_mod1.csv',sep=';'); reg['t']=pd.to_datetime(reg['time_utc'],utc=True).values.astype('datetime64[ns]')
appr=reg[[((r.category,r.event,r.tf) in T.APPROVED) for r in reg.itertuples()]].copy(); wide=reg[reg.tf.isin([60,120,240])].copy()
base_exp=appr.pnl_usd.mean(); S=np.array(T.S_BW)
out={'plateau':{}}
for tf in (15,60,240):
    G=pd.read_csv(f'modtest/mod9/grid_tf{tf}.csv',sep=';'); ok=G[G.approved_pass_n>=100]
    pl={'доля точек выше базы':round(float((ok.approved_pass_exp>base_exp).mean()),3),'медиана ожидания':round(float(ok.approved_pass_exp.median()),2),'wide доля выше базы':round(float((ok.wide60_240_pass_exp>wide.pnl_usd.mean()).mean()),3),'wide медиана':round(float(ok.wide60_240_pass_exp.median()),2)}
    for col in ('kernel','regression','bw','adaptive','thr'):
        pl[f'по {col}']=ok.groupby(col).approved_pass_exp.mean().round(2).to_dict()
    out['plateau'][tf]=pl; print(tf,json.dumps(pl,ensure_ascii=False)[:900])
# робастный профиль — центр плато: 60m, Епанечников, LL, ширина 64, адаптация 0,5–2, порог 0,25 (и 240m аналог)
def evaluate(close,d,tfm,s):
    strict=(s.tf.to_numpy()!=tfm); pos=np.searchsorted(close,s['t'].to_numpy(),side='left')-1
    pos=np.where(strict,pos,np.searchsorted(close,s['t'].to_numpy(),side='right')-1); md=np.where(pos>=0,d[np.clip(pos,0,len(d)-1)],0)
    ok=(md==0)|(md==s.dir.to_numpy()); p=s[ok]; r=s[~ok]; pw=p.loc[p.pnl_usd>0,'pnl_usd'].sum(); pl=-p.loc[p.pnl_usd<0,'pnl_usd'].sum()
    return {'pass_n':int(len(p)),'pass_wr':round(float(p.win.mean()),3),'pass_exp':round(float(p.pnl_usd.mean()),2),'pass_pf':round(float(pw/pl),3) if pl>0 else None,'rej_n':int(len(r)),'rej_wr':round(float(r.win.mean()),3) if len(r) else None,
            'kept_winners':round(float(p.win.sum()/s.win.sum()),3),'cut_losers':round(float((1-r.win).sum()/(1-s.win).sum()),3),'capture_total':round(float(p.pnl_usd.sum()/p.mfe_ticks.sum()),3),'capture_win_med':round(float((p.loc[p.win==1,'ticks_move']/p.loc[p.win==1,'mfe_ticks'].replace(0,np.nan)).median()),3) if p.win.sum() else None,
            'hold_bars_mean':round(float(p.bars.mean()),2),'hold_minutes_mean':round(float((p.bars*p.tf).mean()),1),'time_dir_share':round(float(np.mean(d!=0)),3)}, ok
def series(tf,kernel,regr,bw,adapt,thr,tgate=0.0,fastslow=False,skill=False,tau=0.0):
    z=np.load(f'modtest/mod9/cache_tf{tf}.npz'); close=z['close'].astype('datetime64[ns]'); ratio=z['ratio']; c=z['c']; n=len(close)
    on,amin,amax=adapt
    if on: hb=np.clip(np.round(bw*np.clip(np.nan_to_num(ratio,nan=1.0),amin,amax)),3,160); j=np.abs(S[None,:]-hb[:,None]).argmin(1)
    else: j=np.full(n,T.S_BW.index(bw)); hb=np.full(n,bw)
    idx=np.arange(n)
    B=np.column_stack([z[f'beta_{kernel}_{h}'] for h in T.S_BW]); A=np.column_stack([z[f'alpha_{kernel}_{h}'] for h in T.S_BW]); TT=np.column_stack([z[f't_{kernel}_{h}'] for h in T.S_BW]); NW=np.column_stack([z[f'nw_{kernel}_{h}'] for h in T.S_BW])
    sl=B[idx,j] if regr=='LL' else np.diff(NW[idx,j],prepend=np.nan)/0.1
    al=A[idx,j]; ts=TT[idx,j]
    if tau>0 and regr=='LL':
        se=np.abs(sl/np.where(np.abs(ts)>1e-12,ts,np.nan)); sl=np.where(np.isnan(se),sl,sl*tau*tau/(tau*tau+se*se))
    if fastslow:
        jf=np.abs(S[None,:]-np.maximum(3,hb//2)[:,None]).argmin(1); af=A[idx,jf]; diff=(af-al)/0.1
        d=np.where(np.isnan(diff),0,np.where(np.abs(diff)>=thr,np.sign(diff),0)).astype(np.int8)
    else: d=np.where(np.isnan(sl),0,np.where(np.abs(sl)>=thr,np.sign(sl),0)).astype(np.int8)
    if tgate>0 and regr=='LL': d=np.where(np.abs(np.nan_to_num(ts))<tgate,0,d).astype(np.int8)
    if skill:
        fc=al+(sl*0.1 if regr=='LL' else 0.0); fc_prev=np.r_[np.nan,fc[:-1]]; c_prev=np.r_[np.nan,c[:-1]]
        ek=np.abs(c-fc_prev); en=np.abs(c-c_prev); a=2.0/101.0; emaK=np.full(n,np.nan); emaN=np.full(n,np.nan); k0=n0=np.nan; cnt=0
        for i in range(n):
            if np.isnan(ek[i]) or np.isnan(en[i]): continue
            if cnt==0: k0,n0=ek[i],en[i]
            else: k0+=a*(ek[i]-k0); n0+=a*(en[i]-n0)
            cnt+=1; emaK[i]=k0; emaN[i]=n0
        sk=np.where(emaN>0,1-emaK/emaN,0.0); d=np.where((sk<=0)&(np.arange(n)>=100),0,d).astype(np.int8)
    return close,d,hb
prof={'60m':(60,'Epanechnikov','LL',64,(1,0.5,2.0),0.25),'240m':(240,'Epanechnikov','LL',64,(1,0.5,2.0),0.25),'15m':(15,'Epanechnikov','LL',64,(1,0.5,2.0),0.25)}
out['profiles']={}; out['experiments']={}
for name,(tf,k,rg,bw,ad,thr) in prof.items():
    close,d,hb=series(tf,k,rg,bw,ad,thr); e,okm=evaluate(close,d,tf,appr); ew,_=evaluate(close,d,tf,wide); out['profiles'][name]={'approved':e,'wide':ew,'params':{'tf':tf,'kernel':k,'regression':rg,'bw':bw,'adaptive':ad,'thr':thr}}
    print('профиль',name,e,'| wide',{k2:ew[k2] for k2 in ('pass_n','pass_wr','pass_exp')})
    if name=='60m':
        for lab,kw in [('K61 t-порог 1',dict(tgate=1.0)),('K61 t-порог 2',dict(tgate=2.0)),('K61 t-порог 3',dict(tgate=3.0)),('K63 быстрая/медленная',dict(fastslow=True)),('K64 самопроверка',dict(skill=True)),('Э45 τ 0,25',dict(tau=0.25)),('Э45 τ 0,5',dict(tau=0.5)),('Э45 τ 1',dict(tau=1.0)),('Э45 τ 2',dict(tau=2.0))]:
            close,d,hb=series(tf,k,rg,bw,ad,thr,**kw); ee,_=evaluate(close,d,tf,appr); out['experiments'][lab]=ee; print('  ',lab,ee)
        # [K55] веса по объёму — прямой перенос FillVolumeWeights на профиле (γ 1, робастная шкала, окно 50)
        m1=M.load_npz('/home/claude/atlas/terminal/Atlas_terminal/certification/data_certified/MGC/MGC_M1.npz'); m1=m1[(m1.index>='2015-01-01')&(m1.index<'2019-01-01')]
        nt=M.load_nt_volume('/home/claude/atlas/nt','2015-01-01','2019-01-01'); jj=m1.join(nt[['v']],how='left',rsuffix='_nt'); m1['v']=jj['v_nt'].fillna(0.0).to_numpy()
        b=M.resample_all(m1,[60])[60].reset_index(drop=True); c=b['c'].to_numpy(float); v=b['v'].to_numpy(float); n=len(c); slv=np.full(n,np.nan)
        for i in range(60,n):
            h=min(int(hb[i]),i+1); win=v[i-49:i+1]; cen=np.median(win); sc=1.4826*np.median(np.abs(win-cen))
            mult=np.ones(h)
            if sc>0: zz=(v[i::-1][:h]-cen)/sc; mult=np.clip(1.0+1.0*zz,0.1,4.0)
            y=c[i::-1][:h]; x=-np.arange(h,dtype=float); w=T.kweights('Epanechnikov',h)*mult
            s0=w.sum(); s1=(w*x).sum(); s2=(w*x*x).sum(); t0=(w*y).sum(); t1=(w*x*y).sum(); dd=s0*s2-s1*s1
            if dd>1e-12*s0*s0: slv[i]=(s0*t1-s1*t0)/dd/0.1
        d=np.where(np.isnan(slv),0,np.where(np.abs(slv)>=thr,np.sign(slv),0)).astype(np.int8); ee,_=evaluate(close,d,60,appr); out['experiments']['[K55] веса по объёму γ=1']=ee; print('   [K55]',ee)
# рубежи времени на пропущенных сделках профиля 60m, по ТФ сигналов
tf,k,rg,bw,ad,thr=prof['60m']; close,d,hb=series(tf,k,rg,bw,ad,thr); e,okm=evaluate(close,d,tf,appr); passed=appr[okm]
m1=M.load_npz('/home/claude/atlas/terminal/Atlas_terminal/certification/data_certified/MGC/MGC_M1.npz'); m1=m1[(m1.index>='2015-01-01')&(m1.index<'2019-01-01')]
bars=M.resample_all(m1,[60,120,240]); te={}
for stf in (60,120,240):
    sub=passed[passed.tf==stf]
    if len(sub)==0: continue
    te[stf]=R.time_exit_variants(bars[stf].reset_index(drop=True),sub,stf)
out['time_exits_passed']=te; print('TimeExit',json.dumps(te,ensure_ascii=False)[:800])
# взаимодействие с MOD10 (профиль 240m) и MOD13 (M60 направление) на утверждённых
z10=np.load('modtest/mod10/cache_tf240.npz'); c10=z10['close'].astype('datetime64[ns]'); SL=z10['slopes']; H=z10['H256']; S10=np.array([4,6,8,10,12,14,16,20,24,28,32,40,48,56,64,80,96,112,128,160])
tt=np.clip((H-0.37)/0.2,0,1); hb10=np.clip(np.round(16+tt*64),3,160); j10=np.abs(S10[None,:]-hb10[:,None]).argmin(1); sl10=SL[np.arange(len(H)),j10]
d10=np.where(np.isnan(sl10)|np.isnan(H),0,np.where(np.abs(sl10)>=0.25,np.sign(sl10),0)).astype(np.int8)
def at(close,d,s,tfm):
    strict=(s.tf.to_numpy()!=tfm); pos=np.searchsorted(close,s['t'].to_numpy(),side='left')-1; pos=np.where(strict,pos,np.searchsorted(close,s['t'].to_numpy(),side='right')-1); return np.where(pos>=0,d[np.clip(pos,0,len(d)-1)],0)
a9=at(close,d,appr,60); a10=at(c10,d10,appr,240); dr=appr.dir.to_numpy()
both=(a9!=0)&(a10!=0); p9=(a9==0)|(a9==dr); p10=(a10==0)|(a10==dr)
inter={'оба определены':round(float(both.mean()),3),'согласие направления при обоих':round(float((a9[both]==a10[both]).mean()),3),'совпадение решений пропуск/вето':round(float((p9==p10).mean()),3),'пропуск MOD9':round(float(p9.mean()),3),'пропуск MOD10':round(float(p10.mean()),3),'пропуск оба':round(float((p9&p10).mean()),3),
       'сделок, где решения разошлись':int((p9!=p10).sum()),'WinRate где MOD9 пропускает, MOD10 вето':round(float(appr[p9&~p10].win.mean()),3) if (p9&~p10).any() else None,'WinRate где MOD10 пропускает, MOD9 вето':round(float(appr[~p9&p10].win.mean()),3) if (~p9&p10).any() else None}
out['interaction_MOD9_60m_x_MOD10_240m']=inter; print(inter)
json.dump(out,open('modtest/mod9/mod9_experiments_interaction.json','w',encoding='utf-8'),ensure_ascii=False,indent=2,default=str)
