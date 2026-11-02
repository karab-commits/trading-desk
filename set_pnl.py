#!/usr/bin/env python3
"""Update P&L fields in the desk data.json.

Feed this ONLY with numbers taken from real Questrade executions/positions.
It never contacts Questrade itself; it just writes the values you give it.

Examples
  # desk totals for today (realized + unrealized, CAD) and trade count
  python3 set_pnl.py --desk --realized 11.50 --unrealized -2.10 --trades 1
  # attribute a trade's P&L to the bot whose idea it was
  python3 set_pnl.py --bot scanner --pnl 11.50 --trades 1
  # several bots share one idea: split it yourself, e.g. half each
  python3 set_pnl.py --bot whale --pnl 5.75 --trades 1 --bot options --pnl 5.75 --trades 1
  # Risk Manager rejected ideas (shown as "losses avoided: N rejected")
  python3 set_pnl.py --rejected 2
  # weekly / all-time views
  python3 set_pnl.py --period week --desk --realized 40 --trades 3
  # start a new day (zero all "today" fields)
  python3 set_pnl.py --reset today
Kiwi, Quant Lab and Trade Journal always display the desk total, so they need no --bot values.
"""
import argparse, json, subprocess, sys
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

KEYS = {'today': ('pnlToday', 'tradesToday', 'rejectedToday'),
        'week': ('pnlWeek', 'tradesWeek', 'rejectedWeek'),
        'alltime': ('pnlAllTime', 'tradesAllTime', 'rejectedAllTime')}

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--file', default='data.json')
    ap.add_argument('--period', choices=KEYS, default='today')
    ap.add_argument('--bot', action='append', default=[], help='bot id (repeatable; pair with --pnl/--trades in order)')
    ap.add_argument('--pnl', action='append', type=float, default=[])
    ap.add_argument('--trades', action='append', type=int, default=[])
    ap.add_argument('--desk', action='store_true', help='set desk totals (use --realized/--unrealized/--trades)')
    ap.add_argument('--realized', type=float)
    ap.add_argument('--unrealized', type=float)
    ap.add_argument('--desk-trades', type=int, help='desk trade count (alternative to --trades when also passing --bot)')
    ap.add_argument('--rejected', type=int, help='Risk Manager rejected-idea count for the period')
    ap.add_argument('--reset', choices=KEYS, help='zero every P&L field for that period')
    a = ap.parse_args()
    d = json.load(open(a.file))
    bots = {b['id']: b for b in d.get('bots', [])}
    pk, tk, rk = KEYS[a.period]

    if a.reset:
        p2, t2, r2 = KEYS[a.reset]
        for b in bots.values():
            b[p2] = 0; b[t2] = 0
            if b['id'] == 'risk': b[r2] = 0
        d[p2] = {'realized': 0, 'unrealized': 0, 'total': 0, 'trades': 0}

    trades_iter = list(a.trades)
    if a.desk:
        desk = d.get(pk) if isinstance(d.get(pk), dict) else {}
        if a.realized is not None: desk['realized'] = round(a.realized, 2)
        if a.unrealized is not None: desk['unrealized'] = round(a.unrealized, 2)
        if a.desk_trades is not None: desk['trades'] = a.desk_trades
        elif trades_iter and not a.bot: desk['trades'] = trades_iter.pop(0)
        desk['total'] = round(desk.get('realized', 0) + desk.get('unrealized', 0), 2)
        desk.setdefault('trades', 0)
        d[pk] = desk

    for i, bid in enumerate(a.bot):
        if bid not in bots: sys.exit('unknown bot id: %s (have %s)' % (bid, ', '.join(bots)))
        if i < len(a.pnl): bots[bid][pk] = round(a.pnl[i], 2)
        if i < len(trades_iter): bots[bid][tk] = trades_iter[i]

    if a.rejected is not None:
        bots['risk'][rk] = a.rejected

    now = datetime.now(ZoneInfo('America/Toronto')) if ZoneInfo else datetime.now()
    d['lastUpdated'] = now.strftime('%a %b %-d, %Y %-I:%M %p ET')
    json.dump(d, open(a.file, 'w'), indent=2, ensure_ascii=False)
    print('updated', a.file, '| desk', a.period, d.get(pk))

if __name__ == '__main__':
    main()
