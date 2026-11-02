#!/usr/bin/env python3
r"""Set what a bot is doing right now (drives its desk CRT in bullpen-v2.html).

  python3 set_activity.py --bot scanner --state working --now "Pre-market scan" \
      --detail "Scanning gap-ups on the watchlist" --next "QQC check 10:05"
  python3 set_activity.py --bot risk --state waiting --now "QQC: 10 sh, \$6 risk OK" --log "10:05 QQC re-check passed"
  python3 set_activity.py --approved "QQC.TO gap-and-go"   # rings Kiwi's bell once (only when this value changes)

state: working | idle | waiting | done.  --now is at most 28 characters (it must fit the CRT).
'since' is set to the current time (America/Toronto) whenever --bot is given.
--log appends to the bot's log (only the last 3 are kept). --next "" clears next.
Only report real work here; nothing in the bullpen is simulated from this file.
"""
import argparse, json, sys
from datetime import datetime
from zoneinfo import ZoneInfo

STATES = ('working', 'idle', 'waiting', 'done')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--file', default='data.json')
    ap.add_argument('--bot')
    ap.add_argument('--state', choices=STATES)
    ap.add_argument('--now', dest='now_text')
    ap.add_argument('--detail')
    ap.add_argument('--next', dest='next_text')
    ap.add_argument('--log', action='append', default=[])
    ap.add_argument('--approved', help='set lastApprovedIdea (bell rings when it changes)')
    a = ap.parse_args()
    if not a.bot and a.approved is None:
        ap.error('give --bot (with --state/--now) and/or --approved')
    d = json.load(open(a.file))
    now = datetime.now(ZoneInfo('America/Toronto'))
    if a.bot:
        bots = {b['id']: b for b in d.get('bots', [])}
        if a.bot not in bots:
            sys.exit('unknown bot id: %s (have %s)' % (a.bot, ', '.join(bots)))
        b = bots[a.bot]
        act = b.get('activity') or {}
        if not act and (not a.state or not a.now_text):
            ap.error('a bot with no activity yet needs both --state and --now')
        if a.now_text is not None:
            if len(a.now_text) > 28:
                sys.exit('--now is %d chars; keep it to 28 or fewer' % len(a.now_text))
            act['now'] = a.now_text
        if a.state: act['state'] = a.state
        if a.detail is not None:
            act['detail'] = a.detail
            b['status'] = a.detail
        if a.next_text is not None:
            if a.next_text: act['next'] = a.next_text
            else: act.pop('next', None)
        if a.log:
            act['log'] = (act.get('log', []) + a.log)[-3:]
        act['since'] = now.isoformat(timespec='seconds')
        b['activity'] = act
    if a.approved is not None:
        d['lastApprovedIdea'] = a.approved or None
    d['lastUpdated'] = now.strftime('%a %b %-d, %Y %-I:%M %p ET')
    json.dump(d, open(a.file, 'w'), indent=2, ensure_ascii=False)
    print('updated', a.file, (a.bot or ''), json.dumps(d['bots'][[x['id'] for x in d['bots']].index(a.bot)]['activity']) if a.bot else '', ('approved=' + str(d['lastApprovedIdea'])) if a.approved is not None else '')

if __name__ == '__main__':
    main()
