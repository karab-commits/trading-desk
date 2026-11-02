"""Paper-resolve Nov 2 2026 alerts on Questrade 5-min RTH bars (read-only pull, raw_*.txt).
Rules: entry fills at trigger (or bar open if gapped through); on the entry bar only the stop is checked;
if one bar touches both stop and target -> stop; else exit at 16:00 close (last 5m bar close)."""
import pandas as pd
def load(s):
    b=pd.read_csv(f"{s.replace('.','_')}_5m.csv")
    b['et']=pd.to_datetime(b.start,utc=True).dt.tz_convert('America/Toronto'); return b.reset_index(drop=True)
def sim(s,side,entry,stop,target,after,cond=None,show=False):
    b=load(s); b=b[b.et.dt.strftime('%H:%M')>=after].reset_index(drop=True)
    sgn=1 if side=='long' else -1; i0=None; fill=None
    for i,r in b.iterrows():
        if sgn==-1 and r.low<=entry: i0=i; fill=min(entry,r.open); break
        if sgn==1 and r.high>=entry: i0=i; fill=max(entry,r.open); break
    if i0 is None: return dict(ticker=s,outcome='no-fill',hi=b.high.max(),lo=b.low.min())
    for j in range(i0,len(b)):
        r=b.iloc[j]
        hs=(r.low<=stop) if sgn==1 else (r.high>=stop)
        ht=(r.high>=target) if sgn==1 else (r.low<=target)
        if hs: return dict(ticker=s,outcome='stop',fill=fill,fillAt=b.et[i0].strftime('%H:%M'),exit=stop if j>i0 or True else stop,exitAt=r.et.strftime('%H:%M'),ambig=bool(ht and j>i0))
        if ht and j>i0: return dict(ticker=s,outcome='target',fill=fill,fillAt=b.et[i0].strftime('%H:%M'),exit=target,exitAt=r.et.strftime('%H:%M'))
    return dict(ticker=s,outcome='time',fill=fill,fillAt=b.et[i0].strftime('%H:%M'),exit=b.close.iloc[-1],exitAt='16:00')
if __name__=='__main__':
    for s in ['RIVN','QQC.TO','XIU.TO','AMD']:
        b=load(s); print(s,'open',b.open[0],'hi',b.high.max(),'lo',b.low.min(),'close',b.close.iloc[-1])
    # RIVN: before 9:45 and from 9:45
    b=load('RIVN'); print(b[['et','open','high','low','close']].head(12).to_string())
    print(load('QQC.TO')[['et','open','high','low','close']].head(10).to_string())
