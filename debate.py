#!/usr/bin/env python3
"""Devil's-advocate check (veto only) for News Desk entries and untested strategies (strategies.json devils_advocate).

Before the entry: log the idea (log_idea.py add), then write the debate on it. The bear case needs at least 3
concrete reasons the trade fails (e.g. news already priced in / move extended vs ATR; broader market weak or
against the trade - SPY/QQQ, regime.json; wide spread or thin liquidity; event risk; stale or second-hand
headline). The bull case needs at least 1 reason. Verdict 'take' only when the bull case clearly wins, and then
--why must say why; anything else is 'skip'. The debate can only veto a valid signal: it never adds a trade or
changes size, stop or target.

  python3 debate.py --id 2026-11-03-SOFI-1 \\
     --bull "Guidance raise, fresh 8:05 ET PR, +4% on 3x RVOL" --bull "Holding above VWAP on the pullback" \\
     --bear "Up 9% pre-market: 2.1x ATR, much may be priced in" --bear "QQQ -0.8% and regime volatile" \\
     --bear "Spread 0.15% and thin size at the ask" --verdict skip
  python3 debate.py --id 2026-11-03-SOFI-1 ... --verdict take --why "catalyst is new and the market is risk-on"
  python3 debate.py --show --bot news           # latest debate for a bot

Writes idea.debate = {bull[], bear[], verdict, why, by, at, regime} in journal.json. Prints VETO (skip) or PASS
(take -> go on to risk_check.py --idea <id>). Exit code 0 = PASS, 3 = VETO, 1 = error.
"""
import argparse, json, os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo('America/Toronto')
except Exception:  # pragma: no cover
    ET = None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--id', help='journal idea id')
    ap.add_argument('--bull', action='append', default=[])
    ap.add_argument('--bear', action='append', default=[])
    ap.add_argument('--verdict', choices=['take', 'skip'])
    ap.add_argument('--why', default='')
    ap.add_argument('--by', default=None, help='who wrote it (default: the idea\'s bot)')
    ap.add_argument('--show', action='store_true'); ap.add_argument('--bot')
    a = ap.parse_args()
    jp = os.path.join(HERE, 'journal.json'); j = json.load(open(jp))
    if a.show:
        L = [i for i in j['ideas'] if i.get('debate') and (not a.bot or i.get('bot') == a.bot)]
        if not L:
            print('no debates yet'); return 0
        i = max(L, key=lambda x: x['debate']['at']); d = i['debate']
        print(f"{i['id']} {i['ticker']} {i['side']} - {d['verdict'].upper()} ({d['at']})")
        for x in d['bull']: print('  bull:', x)
        for x in d['bear']: print('  bear:', x)
        if d.get('why'): print('  why:', d['why'])
        return 0
    if not a.id or not a.verdict:
        ap.error('--id and --verdict are required')
    idea = next((i for i in j['ideas'] if i['id'] == a.id), None)
    if not idea:
        sys.exit(f'no idea {a.id} in journal.json (log it with log_idea.py add first)')
    bear = [b.strip() for b in a.bear if b.strip()]; bull = [b.strip() for b in a.bull if b.strip()]
    if len(bear) < 3:
        sys.exit(f'bear case needs >= 3 concrete reasons (got {len(bear)})')
    if not bull:
        sys.exit('bull case needs >= 1 reason')
    if a.verdict == 'take' and len(a.why.strip()) < 10:
        sys.exit('verdict take needs --why: say why the bull case clearly beats the bear case')
    idea['debate'] = {'bull': bull, 'bear': bear, 'verdict': a.verdict, 'why': a.why.strip(), 'by': a.by or idea.get('bot'),
                      'at': (datetime.now(ET) if ET else datetime.now()).isoformat(timespec='seconds'),
                      'regime': idea.get('regime'), 'rule': 'veto only'}
    with open(jp + '.tmp', 'w') as f:
        json.dump(j, f, indent=2, ensure_ascii=False); f.write('\n')
    os.replace(jp + '.tmp', jp)
    if a.verdict == 'skip':
        print(f"VETO {a.id} {idea['ticker']} {idea['side']}: skip the trade (bear {len(bear)} vs bull {len(bull)}). Keep it paper-tracked.")
        return 3
    print(f"PASS {a.id} {idea['ticker']} {idea['side']}: bull case wins - {a.why.strip()}. Next: risk_check.py --bot {idea['bot']} --idea {a.id} ...")
    return 0


if __name__ == '__main__':
    sys.exit(main())
