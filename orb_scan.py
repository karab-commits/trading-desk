#!/usr/bin/env python3
"""Opening-range break finder (added Nov 23 2026 by Kiwi; fixes late ORB/SIP logging seen Nov 18, 20 and 23).

Reads the 5-min bar cache (bars/<SYM>_5m.csv, fed by `bars.py ingest` from Questrade get_historical_data 5m RTH)
and, for each symbol, prints the 9:30-9:45 ET opening range, the first-15-min candle direction, and the FIRST 5-min
bar that CLOSED beyond the range high / low (time ET, close, bar VWAP, volume). It never places orders and applies
no strategy filter (RVOL / VWAP side / trend stay the routine's job): it only says WHEN the break happened, so the
idea is logged on that bar, not 10-150 minutes later.

  python3 orb_scan.py NVDA QQQ MU            # today (ET)
  python3 orb_scan.py --date 2026-11-23 NVDA QQQ
  python3 orb_scan.py --json NVDA            # machine-readable
Exit code 0 always; 'no bars' if the symbol's 5m cache has nothing for the date (fetch + ingest first).
"""
import argparse, datetime as dt, json, sys
from zoneinfo import ZoneInfo
import bars as B

ET = ZoneInfo('America/Toronto')

def et(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(ET)

def scan(sym, date):
    rows = [b for b in B.load(sym, '5m') if et(b['start']).date().isoformat() == date]
    rows = [b for b in rows if dt.time(9, 30) <= et(b['start']).time() < dt.time(16, 0)]
    if not rows:
        return {'symbol': sym, 'date': date, 'error': 'no bars'}
    orb = [b for b in rows if et(b['start']).time() < dt.time(9, 45)]
    if len(orb) < 3:
        return {'symbol': sym, 'date': date, 'error': f'opening range incomplete ({len(orb)}/3 bars)'}
    hi = max(b['high'] for b in orb); lo = min(b['low'] for b in orb)
    o, c = orb[0]['open'], orb[-1]['close']
    first = 'long' if c > o else 'short' if c < o else 'doji'
    out = {'symbol': sym, 'date': date, 'orHigh': hi, 'orLow': lo, 'width': round(hi - lo, 4),
           'firstCandle': first, 'lastBar': et(rows[-1]['start']).strftime('%H:%M'), 'breakUp': None, 'breakDown': None}
    for b in rows:
        if et(b['start']).time() < dt.time(9, 45):
            continue
        rec = {'barStartET': et(b['start']).strftime('%H:%M'), 'closedET': (et(b['start']) + dt.timedelta(minutes=5)).strftime('%H:%M'),
               'close': b['close'], 'vwap': b['vwap'], 'volume': b['volume']}
        if out['breakUp'] is None and b['close'] > hi:
            out['breakUp'] = rec
        if out['breakDown'] is None and b['close'] < lo:
            out['breakDown'] = rec
    return out

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('symbols', nargs='+'); ap.add_argument('--date'); ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    date = a.date or dt.datetime.now(ET).date().isoformat()
    res = [scan(s, date) for s in a.symbols]
    if a.json:
        print(json.dumps(res, indent=1)); return
    for r in res:
        if 'error' in r:
            print(f"{r['symbol']:8} {date}: {r['error']}"); continue
        def f(x):
            return f"closed {x['closedET']} ET @ {x['close']} (bar VWAP {x['vwap']}, vol {int(x['volume'] or 0)})" if x else '-'
        print(f"{r['symbol']:8} OR {r['orLow']}-{r['orHigh']} first15 {r['firstCandle']:5} | up: {f(r['breakUp'])} | down: {f(r['breakDown'])} | bars to {r['lastBar']}")

if __name__ == '__main__':
    main()
