#!/usr/bin/env python3
"""Missed trades: hypothetical P&L of every desk idea that was NOT traded with real money.

Reads journal.json (every idea, paper-tracked at its plan), data.json (fees, USDCAD, watchlist prices, real desk P&L)
and counters.json (risk_check.py BLOCK keys), and writes missed.json. Nothing is invented: an idea's P&L is either the
journal's paper result, a mark to the latest Questrade price in data.json watchlist[] (open, triggered ideas), or $0
(never triggered / not scored yet).

  python3 missed.py              # recompute missed.json and print the summary
  python3 missed.py --show       # print only (no write)
  python3 missed.py --json       # print missed.json to stdout (no write)

Included: ideas with taken != "yes" and no real P&L (skipped, blocked by risk_check, vetoed by debate.py, expired,
untaken, paper-only). Excluded: real fills (taken "yes", realPnl set, or the watchlist item is "in trade"/has a fill)
and K's own manual orders (idea.manual true or bot "k"/"manual"; Questrade orders that are not desk ideas, e.g. SPCX,
are never in journal.json).

Fees: same model as log_idea.py (data.json `fees`): $0 commission, SEC fee on US sells, 1.5% FX on the USD P&L,
USD converted to CAD at fees.usdcad.rate (default 1.3960).
"""
import argparse, json, os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from log_idea import trade_fees, gross_pnl, to_cad, iso_week, r2, now_et, load_json, save_json, desk_dir  # noqa: E402

MANUAL_BOTS = {'k', 'manual', 'K'}
DEFAULT_USDCAD = 1.396


def market_open(now):
    m = now.hour * 60 + now.minute
    return now.weekday() < 5 and 570 <= m < 960


def why_not_real(i, w, blocked):
    """Why the idea was not traded with real money (first match wins)."""
    if i.get('mode') == 'paper':
        return 'paper-only'
    if (i.get('debate') or {}).get('verdict') == 'skip':
        return 'vetoed'
    if i['id'] in blocked or f"{i.get('bot')}:{i['ticker']}:{i['side']}" in blocked:
        return 'blocked'
    st = (w or {}).get('status')
    if st == 'expired':
        return 'expired'
    if st == 'skipped' or i.get('taken') == 'no':
        return 'skipped'
    return 'untaken'


def blocked_keys(counters):
    out = set()
    for k, day in (counters or {}).items():
        if k.startswith('_') or not isinstance(day, dict):
            continue
        for key in (day.get('risk') or {}).get('keys', []):
            if key.startswith('rejected:'):
                out.add(key[len('rejected:'):])
    return out


def compute(journal, data, counters, now=None):
    now = now or now_et()
    today = now.strftime('%Y-%m-%d')
    cfg = dict(data.get('fees') or {})
    cfg.setdefault('usdcad', {}).setdefault('rate', DEFAULT_USDCAD)
    if not cfg['usdcad'].get('rate'):
        cfg['usdcad']['rate'] = DEFAULT_USDCAD
    wl = {}
    for w in data.get('watchlist') or []:
        if w.get('journalId'):
            wl[w['journalId']] = w
    blocked = blocked_keys(counters)
    mopen = market_open(now)
    rows, excluded = [], []
    for i in journal.get('ideas', []):
        w = wl.get(i['id'])
        if i.get('manual') or str(i.get('bot', '')).lower() in MANUAL_BOTS:
            excluded.append({'id': i['id'], 'why': 'manual order by K'}); continue
        if i.get('taken') == 'yes' or i.get('realPnl') is not None or i.get('realPnlCAD') is not None:
            excluded.append({'id': i['id'], 'why': 'filled with real money'}); continue
        if w and (w.get('status') == 'in trade' or w.get('fill') is not None):
            excluded.append({'id': i['id'], 'why': 'in trade (real fill)'}); continue
        cur = i.get('currency') or 'USD'
        row = {k: i.get(k) for k in ('id', 'date', 'bot', 'ticker', 'side', 'entry', 'stop', 'target', 'shares', 'strategy', 'currency')}
        row['size'] = i.get('shares')
        row['loggedAt'] = i.get('loggedAt')
        row['why'] = why_not_real(i, w, blocked)
        res = i.get('result')
        mark = None
        if res:
            if res.get('outcome') == 'no-fill':
                row.update(state='not triggered', outcome='no-fill', exit=None, net=0.0, netCAD=0.0)
            else:
                ex = res['exit']
                f = trade_fees(i['side'], i['entry'], ex, i['shares'], cur, cfg)
                net = gross_pnl(i['side'], i['entry'], ex, i['shares']) - f['total']
                row.update(state='final', outcome=res['outcome'], exit=ex, fees=round(f['total'], 4), net=r2(net),
                           netCAD=r2(to_cad(net, cur, cfg)), resolvedAt=res.get('resolvedAt'))
        else:
            st = (w or {}).get('status')
            last, pt = (w or {}).get('last'), (w or {}).get('priceTime')
            if st in ('target hit', 'stopped'):
                mark, row['state'], row['outcome'] = (i['target'] if st == 'target hit' else i['stop']), 'final', ('target' if st == 'target hit' else 'stop')
            elif st == 'triggered' and isinstance(last, (int, float)):
                # still open: unrealized while the market is open that day; after the close it is flat at the close
                closed = i['date'] < today or (not mopen and now.hour >= 16)
                mark, row['state'], row['outcome'] = last, ('final' if closed else 'unrealized'), ('time' if closed else None)
                row['priceTime'] = pt
            elif st in ('watching', 'expired') and (i['date'] < today or now.hour >= 16):
                row.update(state='not triggered', outcome='expired')
            elif st == 'watching':
                row.update(state='waiting', outcome=None)
            else:
                row.update(state='pending', outcome=None, note='not scored yet (journal has no result; no triggered watchlist price)')
            if mark is not None:
                f = trade_fees(i['side'], i['entry'], mark, i['shares'], cur, cfg)
                net = gross_pnl(i['side'], i['entry'], mark, i['shares']) - f['total']
                row.update(exit=mark, fees=round(f['total'], 4), net=r2(net), netCAD=r2(to_cad(net, cur, cfg)))
            else:
                row.update(exit=None, net=0.0, netCAD=0.0)
        rows.append(row)

    wk = iso_week(today)
    def per(f):
        sel = [r for r in rows if f(r['date'])]
        t = {'net': 0.0, 'final': 0.0, 'unrealized': 0.0, 'ideas': len(sel), 'scored': 0, 'open': 0, 'notTriggered': 0, 'pending': 0, 'wins': 0, 'losses': 0}
        for r in sel:
            t['net'] += r['netCAD'] or 0
            if r['state'] == 'final':
                t['final'] += r['netCAD']; t['scored'] += 1
                t['wins' if r['netCAD'] > 0 else 'losses'] += 1 if r['netCAD'] else 0
            elif r['state'] == 'unrealized':
                t['unrealized'] += r['netCAD']; t['open'] += 1
            elif r['state'] == 'not triggered':
                t['notTriggered'] += 1
            else:
                t['pending'] += 1
        for k in ('net', 'final', 'unrealized'):
            t[k] = r2(t[k])
        return t, sel
    periods = {'today': lambda d: d == today, 'week': lambda d: iso_week(d) == wk, 'allTime': lambda d: True}
    totals, by_bot = {}, {}
    for p, f in periods.items():
        totals[p], sel = per(f)
        for r in sel:
            b = by_bot.setdefault(r['bot'], {}).setdefault(p, {'net': 0.0, 'ideas': 0, 'scored': 0, 'open': 0})
            b['net'] = r2(b['net'] + (r['netCAD'] or 0)); b['ideas'] += 1
            b['scored'] += r['state'] == 'final'; b['open'] += r['state'] == 'unrealized'
    for b in by_bot.values():
        for p in periods:
            b.setdefault(p, {'net': 0.0, 'ideas': 0, 'scored': 0, 'open': 0})
    def real(key):
        o = data.get(key) or {}
        if isinstance(o, (int, float)):
            return r2(o)
        return r2(o.get('total') if isinstance(o.get('total'), (int, float)) else (o.get('realized') or 0) + (o.get('unrealized') or 0))
    bots_real = {b['id']: {'today': b.get('pnlToday') or 0, 'week': b.get('pnlWeek') or 0, 'allTime': b.get('pnlAllTime') or 0}
                 for b in data.get('bots', []) if b.get('id')}
    return {
        'version': 1, 'updated': now.isoformat(timespec='seconds'), 'date': today, 'isoWeek': wk, 'marketOpen': mopen,
        'currency': 'CAD',
        'basis': 'hypothetical, net of Questrade fees (data.json fees: $0 commission, SEC fee on US sells, 1.5% FX on USD P&L), '
                 'USD at fees.usdcad.rate; final = journal paper result, unrealized = marked to the latest data.json watchlist price',
        'usdcad': cfg['usdcad']['rate'],
        'totals': totals, 'byBot': by_bot,
        'real': {'today': real('pnlToday'), 'week': real('pnlWeek'), 'allTime': real('pnlAllTime'), 'byBot': bots_real},
        'ideas': sorted(rows, key=lambda r: (r['date'], r.get('loggedAt') or '', r['id']), reverse=True),
        'excluded': excluded,
    }


def money(x):
    return f"{'+' if x > 0 else '-' if x < 0 else ''}${abs(x):,.2f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir'); ap.add_argument('--show', action='store_true'); ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    d = desk_dir(a)
    M = compute(load_json(os.path.join(d, 'journal.json'), {'ideas': []}), load_json(os.path.join(d, 'data.json'), {}),
                load_json(os.path.join(d, 'counters.json'), {}))
    if a.json:
        print(json.dumps(M, indent=2)); return
    if not a.show:
        save_json(os.path.join(d, 'missed.json'), M)
    for p, lab in (('today', 'Today'), ('week', 'Week'), ('allTime', 'All time')):
        t = M['totals'][p]
        print(f"{lab:9} Real: {money(M['real'][p])} · Missed: {money(t['net'])}  ({t['ideas']} ideas: {t['scored']} scored, "
              f"{t['open']} unrealized {money(t['unrealized'])}, {t['notTriggered']} not triggered, {t['pending']} pending)")
    for b, v in sorted(M['byBot'].items()):
        print(f"  {b:8} today {money(v['today']['net'])} · week {money(v['week']['net'])} · all {money(v['allTime']['net'])}")
    for r in M['ideas']:
        print(f"  {r['id']:20} {r['side']:5} {r['state']:13} {r['why']:10} {money(r['netCAD'])}")
    if M['excluded']:
        print('excluded: ' + ', '.join(f"{x['id']} ({x['why']})" for x in M['excluded']))
    print(('wrote missed.json' if not a.show else '(not written)') + f" · {M['updated']}")


if __name__ == '__main__':
    main()
