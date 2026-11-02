"""EOD re-check 2026-11-02 of the ACTIVE playbook (big-gap fade >0.75 ATR, daily) after Questrade fees.
Data: /workspace/quant/data/*_1d.csv (Questrade get_historical_data, Oct 2024-Oct 30 2026) + Nov 2 2026 daily bars
pulled today (read-only). Rule (same as /workspace/quant/backtest.py d_gapfade): gap = open - prior close;
trade if |gap| >= 0.75*ATR14 (ATR known before the open); fade at the open; stop = open +/- |gap| (1R);
target = prior close (1R); if the day's range touched the stop -> stop (also when both touched); else target
if touched; else exit at the close. Costs: 0.02%/side slippage + Questrade fees: CAD $0; USD SEC fee
0.0000206 x sale value on the selling leg + 1.5% FX on |P&L| (data.json fees, fx.mode=pnl)."""
import sys, pandas as pd, numpy as np
sys.path.insert(0,'/workspace/quant'); import backtest as B
B.SLIP=0.0002
NOV2={'XIU.TO':dict(open=53.87,high=54.4,low=53.82,close=54.07,volume=3425800),
      'HXT.TO':dict(open=96.66,high=97.67,low=96.65,close=97.1,volume=188700),
      'SOFI':dict(open=16.975,high=17.6,low=16.57,close=16.5999,volume=47938401)}
SEC=0.0000206; FX=0.015
def load(s):
    d=pd.read_csv(B.f(s,'1d')); r=NOV2[s]; d=pd.concat([d,pd.DataFrame([dict(start='2026-11-02T05:00:00.000Z',**r)])],ignore_index=True)
    d.to_csv(f"{s.replace('.','_')}_1d_thru_2026-11-02.csv",index=False)
    d['date']=d.start.str[:10]; d=d.sort_values('date').reset_index(drop=True)
    d['pc']=d.close.shift(1)
    tr=pd.concat([d.high-d.low,(d.high-d.pc).abs(),(d.low-d.pc).abs()],axis=1).max(axis=1)
    d['atr']=tr.rolling(14).mean().shift(1); return d
def trades(s):
    T=pd.DataFrame([x for x in B.d_gapfade(s,load(s),0.75) if x])
    usd=not s.endswith('.TO'); risk=(T.entry-T.stop).abs()
    sell=np.where(T.side=='long',T.exit,T.entry)
    T['feeR']=np.where(usd,SEC*sell/risk+FX*T.grossR.abs(),0.0)
    T['netR']=T.R-T.feeR; return T
def st(t,label):
    t=t.sort_values('date'); n=len(t)
    if n==0: return dict(slice=label,n=0)
    cum=t.netR.cumsum(); dd=(np.maximum.accumulate(np.maximum(cum,0))-cum).max()
    return dict(slice=label,n=n,winRate=round((t.netR>0).mean()*100,1),expR_net=round(t.netR.mean(),3),
                totalR=round(t.netR.sum(),2),maxDD_R=round(dd,2),t=round(t.netR.mean()/(t.netR.std(ddof=1)/np.sqrt(n)),2) if n>2 else None)
rows=[]; allT=[]
for s in ['XIU.TO','HXT.TO','SOFI']:
    T=trades(s); T['ticker']=s; allT.append(T)
    rows+=[st(T,f'{s} all'),st(T[T.date<'2025-10-31'],f'{s} H1 <2025-10-31'),st(T[T.date>='2025-10-31'],f'{s} H2'),
           st(T[T.date>='2026-05-01'],f'{s} last 6m'),st(T[T.date>='2026-08-01'],f'{s} last 3m')]
A=pd.concat(allT)
# one desk trade a day: if several actives signal on one day take XIU first, then HXT, then SOFI
pri={'XIU.TO':0,'HXT.TO':1,'SOFI':2}; P=A.assign(p=A.ticker.map(pri)).sort_values(['date','p']).drop_duplicates('date')
rows+=[st(P,'Portfolio 1/day all'),st(P[P.date>='2026-05-01'],'Portfolio 1/day last 6m'),st(P[P.date>='2026-08-01'],'Portfolio 1/day last 3m')]
X=A[A.ticker=='XIU.TO']; H=A[A.ticker=='HXT.TO']
ov=len(set(X.date)&set(H.date))
R=pd.DataFrame(rows); pd.set_option('display.width',200); print(R.to_string(index=False))
print(f'XIU/HXT same-day signals: {ov} of {len(H)} HXT trades (same TSX-60 basket)')
print('Last 8 XIU signals:'); print(X.tail(8)[['date','side','entry','stop','exit','reason','netR']].to_string(index=False))
A.to_csv('recheck_trades.csv',index=False); R.to_csv('recheck_results.csv',index=False)
