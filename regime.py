#!/usr/bin/env python3
"""Market-mood tag: SPY 10-day realized volatility vs its trailing 1-year median -> calm | volatile.

Tag only (no filter yet). Uses only information known before the session's open: for trading date D it uses SPY
daily closes BEFORE D (same definition as /workspace/quant/ideas-2026-11-02/regime_split.py):
  spy_rv10 = stdev of the last 10 daily log returns x sqrt(252)      (through the prior close)
  median   = median of spy_rv10 over the trailing 250 sessions (min 60)
  regime   = volatile if spy_rv10 > median else calm
Gap-fade history (116 trades with a regime, net of fees): calm +0.06R, volatile +0.24R -> revisit as a filter
after ~100 more trades.

Bars come from the desk cache bars/SPY_1d.csv (see bars.py). Routine run, once a day before 9:45 ET:
  1. Questrade get_historical_data SPY (uuid 05902721-1882-4522-0364-ad9650530625) granularity 1d,
     from = 7 days ago, to = tomorrow, write_to_file=true
  2. python3 regime.py --ingest /workspace/agent-tools/<that file>.txt
Other uses:
  python3 regime.py                    # recompute for today (ET) from the cache, write regime.json
  python3 regime.py --date 2026-11-03  # for another trading date
  python3 regime.py --backfill         # add `regime` to journal.json ideas that lack it
Writes regime.json: {date, spy_rv10, median, regime, asOfClose, bars, stale, method, updated}.
"""
import argparse, json, math, os, statistics, sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bars  # noqa: E402

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo('America/Toronto')
except Exception:  # pragma: no cover
    ET = None
OUT = os.path.join(HERE, 'regime.json')
METHOD = 'SPY 10-day realized vol (log returns, annualized) through the prior close vs its trailing 250-session median; volatile if above'


def now_et():
    return datetime.now(ET) if ET else datetime.now()


def prev_weekday(d):
    d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def compute(for_date=None):
    """Regime for trading date `for_date` (YYYY-MM-DD, default today ET) from closes strictly before it."""
    for_date = for_date or now_et().strftime('%Y-%m-%d')
    b = [x for x in bars.load('SPY', '1d') if x['date'] < for_date and x['close']]
    if len(b) < 75:
        return None
    closes = [x['close'] for x in b]
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    rv = [None] * len(closes)
    for i in range(10, len(closes)):
        rv[i] = statistics.stdev(rets[i - 10:i]) * math.sqrt(252)   # returns ending at close i
    cur = rv[-1]
    hist = [x for x in rv[-250:] if x is not None]
    if len(hist) < 60:
        return None
    med = statistics.median(hist)
    last = b[-1]['date']
    expected = prev_weekday(datetime.strptime(for_date, '%Y-%m-%d')).strftime('%Y-%m-%d')
    return {'date': for_date, 'spy_rv10': round(cur * 100, 2), 'median': round(med * 100, 2),
            'regime': 'volatile' if cur > med else 'calm', 'asOfClose': last, 'bars': len(b),
            'stale': last < expected, 'units': 'annualized %', 'method': METHOD,
            'note': 'Tag only, no filter yet. Revisit as a filter after ~100 more trades (gap fade: calm +0.06R / volatile +0.24R on 116 trades).',
            'updated': now_et().isoformat(timespec='seconds')}


def tag_for(date_str):
    """Used by log_idea.py: regime.json if it is for that date, else computed from the cache."""
    try:
        r = json.load(open(OUT))
        if r.get('date') == date_str:
            return r
    except Exception:
        pass
    return compute(date_str)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ingest', nargs='*', default=[], help='Questrade get_historical_data output file(s) to merge first')
    ap.add_argument('--date', help='trading date YYYY-MM-DD (default today ET)')
    ap.add_argument('--backfill', action='store_true', help='tag journal ideas that have no regime')
    ap.add_argument('--no-write', action='store_true')
    a = ap.parse_args()
    if a.ingest:
        bars.cmd_ingest(a.ingest)
    if a.backfill:
        jp = os.path.join(HERE, 'journal.json'); j = json.load(open(jp)); n = 0
        for i in j.get('ideas', []):
            if not i.get('regime'):
                r = compute(i['date'])
                if r:
                    i['regime'] = r['regime']; i['regimeDetail'] = {k: r[k] for k in ('spy_rv10', 'median', 'asOfClose')}; n += 1
        if not a.no_write:
            with open(jp + '.tmp', 'w') as f:
                json.dump(j, f, indent=2, ensure_ascii=False); f.write('\n')
            os.replace(jp + '.tmp', jp)
        print(f'backfilled regime on {n} idea(s)')
    r = compute(a.date)
    if not r:
        sys.exit('REGIME unavailable: need >= 75 SPY daily bars in bars/SPY_1d.csv (run bars.py ingest)')
    if not a.no_write:
        with open(OUT, 'w') as f:
            json.dump(r, f, indent=1); f.write('\n')
    print(f"REGIME {r['regime'].upper()} for {r['date']}: SPY rv10 {r['spy_rv10']:.2f}% vs 1y median {r['median']:.2f}% (closes through {r['asOfClose']})"
          + ('  WARNING: STALE - prior close missing, ingest fresh SPY bars' if r['stale'] else ''))
    nxt = (datetime.strptime(r['date'], '%Y-%m-%d') + timedelta(days=1))
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    p = compute(nxt.strftime('%Y-%m-%d'))
    if p and p['asOfClose'] != r['asOfClose']:
        print(f"preview {p['date']}: {p['regime'].upper()} (rv10 {p['spy_rv10']:.2f}% vs {p['median']:.2f}%, closes through {p['asOfClose']})")
    if not a.no_write:
        print(f'wrote {OUT}')


if __name__ == '__main__':
    main()
