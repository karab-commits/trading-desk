#!/usr/bin/env python3
"""Weekly scorecard from journal.json (Trade Journal's Friday report).

  python3 scorecard.py                 # current ISO week (ET) + all-time, writes data.json `scorecard`
  python3 scorecard.py --week 2026-W45 # a specific week
  python3 scorecard.py --all           # print the all-time summary (data.json still gets week + all-time)

Two books, both scored net of fees and converted to CAD:
  paper = every idea sent to K that would have filled (no-fill ideas are counted but not scored),
          traded exactly at the alert's plan;
  real  = ideas K actually took (taken=yes) with a real P&L recorded (--real-pnl, net of fees).
R = P&L / the plan's gross risk (|entry - stop| x shares).
"""
import argparse, os, sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from log_idea import load_json, save_json, refresh_paper, iso_week, now_et, desk_dir, r2  # noqa: E402


def week_bounds(label):
    y, w = label.split('-W')
    mon = date.fromisocalendar(int(y), int(w), 1)
    return mon, mon + timedelta(days=6)


def book(ideas, real):
    """Stats for one book. Each item: (pnlCAD, R, strategy, bot)."""
    rows = []
    nofill = 0
    for i in ideas:
        if real:
            if i.get('taken') != 'yes' or i.get('realPnlCAD') is None:
                continue
            rows.append((i['realPnlCAD'], i.get('realR'), i['strategy'], i['bot']))
        else:
            r = i.get('result')
            if not r:
                continue
            if r['outcome'] == 'no-fill':
                nofill += 1
                continue
            rows.append((r['netCAD'], r.get('netR'), i['strategy'], i['bot']))
    n = len(rows)
    out = {'trades': n}
    if not real:
        out['noFill'] = nofill
    if not n:
        return out
    wins = [p for p, *_ in rows if p > 0]
    losses = [p for p, *_ in rows if p <= 0]
    rs = [x[1] for x in rows if x[1] is not None]
    out.update({
        'wins': len(wins), 'losses': len(losses),
        'winRate': round(100.0 * len(wins) / n, 1),
        'avgWin': r2(sum(wins) / len(wins)) if wins else None,
        'avgLoss': r2(sum(losses) / len(losses)) if losses else None,
        'expectancyR': round(sum(rs) / len(rs), 3) if rs else None,
        'netPnl': r2(sum(p for p, *_ in rows)),
    })

    def group(idx):
        g = {}
        for row in rows:
            k = row[idx]
            e = g.setdefault(k, {'name': k, 'trades': 0, 'wins': 0, 'netPnl': 0.0, '_r': []})
            e['trades'] += 1
            e['wins'] += 1 if row[0] > 0 else 0
            e['netPnl'] += row[0]
            if row[1] is not None:
                e['_r'].append(row[1])
        res = []
        for e in g.values():
            e['netPnl'] = r2(e['netPnl'])
            e['winRate'] = round(100.0 * e['wins'] / e['trades'], 1)
            e['expectancyR'] = round(sum(e['_r']) / len(e['_r']), 3) if e['_r'] else None
            del e['_r']
            res.append(e)
        res.sort(key=lambda e: (-e['netPnl'], -e['trades'], e['name']))
        return res

    strat = group(2)
    out['bestStrategy'] = strat[0]
    out['worstStrategy'] = strat[-1] if len(strat) > 1 else None
    out['byStrategy'] = strat
    out['byBot'] = group(3)
    return out


def summarize(ideas):
    return {'ideas': len(ideas), 'open': sum(1 for i in ideas if not i.get('result')),
            'paper': book(ideas, False), 'real': book(ideas, True)}


def money(x):
    return '-' if x is None else f"{'+' if x > 0 else '-' if x < 0 else ''}${abs(x):.2f}"


def line(label, b):
    if not b.get('trades'):
        return f'  {label}: no scored trades'
    s = (f"  {label}: {b['trades']} trades, win {b['winRate']}%, avg win {money(b['avgWin'])} / avg loss {money(b['avgLoss'])}, "
         f"exp {b['expectancyR']:+.2f}R, net {money(b['netPnl'])} CAD after fees")
    s += f"\n    best: {b['bestStrategy']['name']} ({money(b['bestStrategy']['netPnl'])})"
    if b.get('worstStrategy'):
        s += f" | worst: {b['worstStrategy']['name']} ({money(b['worstStrategy']['netPnl'])})"
    s += '\n    bots: ' + ', '.join(f"{e['name']} {money(e['netPnl'])} ({e['trades']})" for e in b['byBot'])
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--week', help='ISO week like 2026-W45 (default: current week, ET)')
    g.add_argument('--all', action='store_true', help='print the all-time summary')
    ap.add_argument('--dir', help="folder with data.json + journal.json (default: this script's folder)")
    a = ap.parse_args()
    ddir = desk_dir(a)
    journal = load_json(os.path.join(ddir, 'journal.json'), {'version': 1, 'ideas': []})
    data = load_json(os.path.join(ddir, 'data.json'), {})
    ideas = journal.get('ideas', [])
    wk = a.week or iso_week(now_et().strftime('%Y-%m-%d'))
    try:
        mon, sun = week_bounds(wk)
    except Exception:
        sys.exit('--week must look like 2026-W45')
    wideas = [i for i in ideas if iso_week(i['date']) == wk]
    fri = mon + timedelta(days=4)
    weekly = summarize(wideas)
    weekly.update({'label': wk, 'from': mon.isoformat(), 'to': sun.isoformat(),
                   'title': f"Week of {mon.strftime('%b')} {mon.day} - {fri.strftime('%b')} {fri.day}, {fri.year}"})
    alltime = summarize(ideas)
    data['scorecard'] = {'updated': now_et().isoformat(timespec='seconds'), 'currency': 'CAD',
                         'basis': 'net of Questrade fees (data.json fees); R = P&L / planned risk',
                         'week': weekly, 'allTime': alltime}
    refresh_paper(data, journal)
    save_json(os.path.join(ddir, 'data.json'), data)
    if a.all:
        print(f"All time · {alltime['ideas']} ideas logged, {alltime['open']} open")
        print(line('Paper', alltime['paper']))
        print(line('Real ', alltime['real']))
    else:
        print(f"Scorecard {weekly['title']} ({wk}) · {weekly['ideas']} ideas logged, {weekly['open']} open")
        print(line('Paper', weekly['paper']))
        print(line('Real ', weekly['real']))
        print(f"All time: paper {money(alltime['paper'].get('netPnl', 0))} over {alltime['paper']['trades']} | "
              f"real {money(alltime['real'].get('netPnl', 0))} over {alltime['real']['trades']}")


if __name__ == '__main__':
    main()
