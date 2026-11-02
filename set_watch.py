#!/usr/bin/env python3
r"""Today's watchlist board (data.json `watchlist`): the stocks the desk is interested in today.

  python3 set_watch.py add --ticker RIVN --side short --entry 12.79 --stop 13.12 --target 12.18 --shares 27 \
      --strategy "Gap fade >0.75ATR (RIVN untested)" --bot scanner [--journal-id 2026-11-02-RIVN-1] [--reason "..."]
  python3 set_watch.py add --journal-id 2026-11-02-QQC-1 --trigger 47.67 --zone-high 48.10 --not-before 10:05
  python3 set_watch.py add --ticker RIVN --tv-symbol NASDAQ:RIVN      # TradingView symbol for the live widget
  python3 set_watch.py price --ticker RIVN --last 12.91 [--time 2026-11-02T09:45:04-05:00]
  python3 set_watch.py status --ticker RIVN --status "in trade" [--fill 12.78]
  python3 set_watch.py list
  python3 set_watch.py reset            # start of a new day (drops every item not dated today)

`watchlist` is an array; every item carries its `date` (ET) and the site only shows items dated today,
so yesterday's list never shows as today's. Same ticker + same day = same item (add updates it).
--journal-id pulls side/entry/stop/target/shares/strategy/bot/currency and the after-fee plan from journal.json.
Without a journal id the after-fee numbers are computed with the same Questrade fee model as log_idea.py.
tvSymbol (--tv-symbol EXCHANGE:SYMBOL) is the TradingView symbol for the site's live price widget. If not given, .TO/.V/.NE/.CN
tickers get TSX:/TSXV:/NEO:/CSE: automatically; US tickers should be given explicitly (NASDAQ:RIVN, NYSE:CNQ, AMEX:SPY).
Entry, stop, target and shares are optional (e.g. a skipped idea); missing ones show as "-" on the site.

price: sets last + priceTime (default now) and moves the status automatically:
  watching  -> triggered   when the trigger is crossed (long: last >= trigger [and <= --zone-high];
                           short: last <= trigger [and >= --zone-low]); trigger defaults to entry; not before --not-before
  triggered / in trade -> target hit / stopped  when target or stop is crossed
  watching  -> expired     for a price at/after the 16:00 ET close
  In trade, openPnl = (last - fill) x shares (sign by side) minus estimated round-trip fees (fill defaults to entry).
  skipped / closed / target hit / stopped / expired are never changed by a price update.
status: watching | triggered | in trade | target hit | stopped | closed | skipped | expired
All times are ET (America/Toronto). Only real data goes in here.
"""
import argparse, json, os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import log_idea as L  # fee model, currency, json helpers

STATUSES = ['watching', 'triggered', 'in trade', 'target hit', 'stopped', 'closed', 'skipped', 'expired']
TERMINAL = {'target hit', 'stopped', 'closed', 'skipped', 'expired'}
CLOSE_BY = '16:00'


def today():
    return L.now_et().strftime('%Y-%m-%d')


def parse_time(s):
    if not s:
        return L.now_et()
    t = datetime.fromisoformat(s.replace('Z', '+00:00'))
    if t.tzinfo is None:
        t = t.replace(tzinfo=L.ET)
    return t.astimezone(L.ET)


def hm(s):
    h, m = s.split(':')
    return int(h) * 60 + int(m)


def load(a):
    ddir = L.desk_dir(a)
    data = L.load_json(os.path.join(ddir, 'data.json'), {})
    wl = data.get('watchlist')
    if not isinstance(wl, list):
        wl = []
    data['watchlist'] = wl
    return ddir, data


def save(ddir, data):
    now = L.now_et()
    data['watchlistUpdated'] = now.isoformat(timespec='seconds')
    data['lastUpdated'] = now.strftime('%a %b %-d, %Y %-I:%M %p ET')
    L.save_json(os.path.join(ddir, 'data.json'), data)


def find(data, ticker, date):
    for it in data['watchlist']:
        if it.get('ticker') == ticker and it.get('date') == date:
            return it
    return None


TV_EXCH = {'TO': 'TSX', 'V': 'TSXV', 'NE': 'NEO', 'CN': 'CSE'}


def default_tv_symbol(ticker):
    root, dot, suf = ticker.rpartition('.')
    if dot and suf in TV_EXCH and root:
        return '%s:%s' % (TV_EXCH[suf], root)
    return None


def complete(it, cfg):
    """(Re)compute R:R and after-fee projections when the plan is complete."""
    need = ('side', 'entry', 'stop', 'target', 'shares')
    if not all(it.get(k) is not None for k in need) or not cfg:
        for k in ('rr', 'rrNet', 'netProfitAtTarget', 'netLossAtStop', 'netProfitAtTargetCAD', 'netLossAtStopCAD'):
            it.setdefault(k, None)
        return
    if it.get('planFrom') == 'journal' and it.get('netProfitAtTarget') is not None:
        return
    p = L.plan_numbers({'side': it['side'], 'entry': it['entry'], 'stop': it['stop'], 'target': it['target'],
                        'shares': it['shares'], 'currency': it['currency']}, cfg)
    for k in ('rr', 'rrNet', 'netProfitAtTarget', 'netLossAtStop', 'netProfitAtTargetCAD', 'netLossAtStopCAD'):
        it[k] = p[k]
    it['planFrom'] = 'fees model'


def open_pnl(it, cfg):
    if it.get('status') != 'in trade' or it.get('last') is None or it.get('shares') is None:
        it['openPnl'] = None
        it['openPnlCAD'] = None
        return
    fill = it.get('fill') if it.get('fill') is not None else it.get('entry')
    if fill is None:
        it['openPnl'] = None
        return
    g = L.gross_pnl(it['side'], fill, it['last'], it['shares'])
    fees = L.trade_fees(it['side'], fill, it['last'], it['shares'], it['currency'], cfg or {})['total'] if cfg else 0
    it['openPnl'] = L.r2(g - fees)
    it['openPnlCAD'] = L.r2(L.to_cad(g - fees, it['currency'], cfg or {}))


def cmd_add(a):
    ddir, data = load(a)
    cfg = data.get('fees')
    date = a.date or today()
    src = {}
    if a.journal_id:
        j = L.load_json(os.path.join(ddir, 'journal.json'), {'ideas': []})
        src = next((i for i in j['ideas'] if i['id'] == a.journal_id), None)
        if not src:
            sys.exit('journal id not found: %s' % a.journal_id)
    ticker = (a.ticker or src.get('ticker') or '').upper()
    if not ticker:
        sys.exit('give --ticker (or --journal-id)')
    it = find(data, ticker, date)
    new = it is None
    if new:
        it = {'date': date, 'ticker': ticker, 'status': 'watching', 'closeBy': CLOSE_BY,
              'addedAt': L.now_et().isoformat(timespec='seconds')}
    if src:
        for k in ('side', 'entry', 'stop', 'target', 'shares', 'strategy', 'bot', 'currency'):
            it[k] = src.get(k)
        p = src.get('plan') or {}
        for k in ('rr', 'rrNet', 'netProfitAtTarget', 'netLossAtStop', 'netProfitAtTargetCAD', 'netLossAtStopCAD'):
            it[k] = p.get(k)
        it['planFrom'] = 'journal'
        it['journalId'] = src['id']
    vals = {'side': a.side, 'entry': a.entry, 'stop': a.stop, 'target': a.target, 'shares': a.shares,
            'strategy': a.strategy, 'bot': a.bot, 'reason': a.reason, 'trigger': a.trigger, 'zoneLow': a.zone_low,
            'zoneHigh': a.zone_high, 'notBefore': a.not_before, 'entryNote': a.entry_note, 'testNote': a.test_note,
            'currency': a.currency.upper() if a.currency else None, 'session': a.session}
    changed_plan = False
    for k, v in vals.items():
        if v is not None:
            if k in ('side', 'entry', 'stop', 'target', 'shares') and it.get(k) != v:
                changed_plan = True
            it[k] = v if v != '' else None
    if changed_plan and it.get('planFrom') == 'journal':
        it['planFrom'] = 'override'
    if a.tv_symbol is not None:
        it['tvSymbol'] = a.tv_symbol.upper() or None
    if not it.get('tvSymbol') and default_tv_symbol(ticker):
        it['tvSymbol'] = default_tv_symbol(ticker)
    if a.tested is not None:
        it['tested'] = a.tested == 'yes'
    it.setdefault('tested', False)
    it.setdefault('currency', L.infer_currency(ticker))
    if a.status:
        it['status'] = a.status
    s, e, st, tg = it.get('side'), it.get('entry'), it.get('stop'), it.get('target')
    if s and None not in (e, st, tg):
        if s == 'long' and not (st < e < tg):
            sys.exit('long needs stop < entry < target')
        if s == 'short' and not (tg < e < st):
            sys.exit('short needs target < entry < stop')
    complete(it, cfg)
    if a.last is not None:
        apply_price(it, a.last, parse_time(a.time), cfg)
    open_pnl(it, cfg)
    if new:
        data['watchlist'].append(it)
    save(ddir, data)
    print(('added ' if new else 'updated ') + line(it))


def apply_price(it, last, t, cfg):
    it['last'] = last
    it['priceTime'] = t.isoformat(timespec='seconds')
    st, side = it.get('status', 'watching'), it.get('side')
    mins = t.hour * 60 + t.minute
    if st in TERMINAL or not side:
        return
    stop, tgt = it.get('stop'), it.get('target')
    if st == 'watching':
        if mins >= hm(it.get('closeBy') or CLOSE_BY):
            it['status'] = 'expired'
            it['statusAt'] = it['priceTime']
            return
        trig = it.get('trigger') if it.get('trigger') is not None else it.get('entry')
        if trig is None or (it.get('notBefore') and mins < hm(it['notBefore'])):
            return
        if side == 'long':
            hit = last >= trig and (it.get('zoneHigh') is None or last <= it['zoneHigh'])
        else:
            hit = last <= trig and (it.get('zoneLow') is None or last >= it['zoneLow'])
        if hit:
            it['status'] = 'triggered'
            it['statusAt'] = it['priceTime']
            it['triggeredAt'] = it['priceTime']
            it['triggerPrice'] = last
        return
    if st in ('triggered', 'in trade') and stop is not None and tgt is not None:
        if (side == 'long' and last >= tgt) or (side == 'short' and last <= tgt):
            it['status'] = 'target hit'
        elif (side == 'long' and last <= stop) or (side == 'short' and last >= stop):
            it['status'] = 'stopped'
        else:
            return
        it['statusAt'] = it['priceTime']
        it['exitSeen'] = last


def cmd_price(a):
    ddir, data = load(a)
    it = find(data, a.ticker.upper(), a.date or today())
    if not it:
        sys.exit('%s is not on the %s watchlist' % (a.ticker.upper(), a.date or today()))
    before = it.get('status')
    apply_price(it, a.last, parse_time(a.time), data.get('fees'))
    open_pnl(it, data.get('fees'))
    save(ddir, data)
    print(line(it) + ('' if before == it['status'] else '   (status %s -> %s)' % (before, it['status'])))


def cmd_status(a):
    ddir, data = load(a)
    it = find(data, a.ticker.upper(), a.date or today())
    if not it:
        sys.exit('%s is not on the %s watchlist' % (a.ticker.upper(), a.date or today()))
    it['status'] = a.status
    it['statusAt'] = L.now_et().isoformat(timespec='seconds')
    if a.fill is not None:
        it['fill'] = a.fill
    if a.reason is not None:
        it['reason'] = a.reason
    open_pnl(it, data.get('fees'))
    save(ddir, data)
    print(line(it))


def cmd_reset(a):
    ddir, data = load(a)
    d = a.date or today()
    old = len(data['watchlist'])
    data['watchlist'] = [] if a.all else [i for i in data['watchlist'] if i.get('date') == d]
    save(ddir, data)
    print('watchlist reset: kept %d item(s) dated %s, dropped %d' % (len(data['watchlist']), d, old - len(data['watchlist'])))


def cmd_list(a):
    _, data = load(a)
    d = a.date or today()
    rows = [i for i in data['watchlist'] if i.get('date') == d]
    print('\n'.join(line(i) for i in rows) if rows else 'no stocks on the watchlist for %s' % d)


def fmt(x):
    return '-' if x is None else ('%g' % x)


def line(it):
    pt = it.get('priceTime')
    pts = parse_time(pt).strftime('%H:%M ET') if pt else '-'
    s = '%-7s %-5s %-10s last %s @ %s | entry %s stop %s target %s x%s' % (
        it['ticker'], it.get('side') or '-', it.get('status'), fmt(it.get('last')), pts,
        fmt(it.get('entry')), fmt(it.get('stop')), fmt(it.get('target')), fmt(it.get('shares')))
    if it.get('netProfitAtTarget') is not None:
        s += ' | net +%.2f / %.2f %s R:R %s' % (it['netProfitAtTarget'], it['netLossAtStop'], it.get('currency'), it.get('rr'))
    if it.get('openPnl') is not None:
        s += ' | open P&L %+.2f' % it['openPnl']
    if it.get('tvSymbol'):
        s += ' | tv %s' % it['tvSymbol']
    return s


def main():
    c = argparse.ArgumentParser(add_help=False)
    c.add_argument('--dir', help="folder with data.json + journal.json (default: this script's folder or $DESK_DIR)")
    c.add_argument('--date', help='watchlist day YYYY-MM-DD (default: today ET)')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('add', parents=[c], help='add or update a stock on today\'s list')
    p.add_argument('--ticker')
    p.add_argument('--side', choices=['long', 'short'])
    for k in ('entry', 'stop', 'target', 'trigger', 'last'):
        p.add_argument('--' + k, type=float)
    p.add_argument('--zone-low', type=float, help='lowest acceptable entry (shorts: no trigger below)')
    p.add_argument('--zone-high', type=float, help='highest acceptable entry (longs: no trigger above)')
    p.add_argument('--not-before', help='HH:MM ET; no trigger before this time')
    p.add_argument('--entry-note', help='e.g. "below 12.80"')
    p.add_argument('--shares', type=int)
    p.add_argument('--strategy')
    p.add_argument('--tested', choices=['yes', 'no'], help='strategy backtested with an edge? (default no)')
    p.add_argument('--test-note', help='e.g. "backtest found no edge"')
    p.add_argument('--bot')
    p.add_argument('--reason')
    p.add_argument('--journal-id')
    p.add_argument('--tv-symbol', help='TradingView EXCHANGE:SYMBOL for the live widget, e.g. NASDAQ:RIVN, TSX:QQC ("" clears)')
    p.add_argument('--currency', choices=['CAD', 'USD', 'cad', 'usd'])
    p.add_argument('--session')
    p.add_argument('--status', choices=STATUSES)
    p.add_argument('--time', help='price time (ISO) for --last')
    p.set_defaults(fn=cmd_add)
    p = sp.add_parser('price', parents=[c], help='update last price (auto status + open P&L)')
    p.add_argument('--ticker', required=True)
    p.add_argument('--last', required=True, type=float)
    p.add_argument('--time', help='ISO time of the quote (default now)')
    p.set_defaults(fn=cmd_price)
    p = sp.add_parser('status', parents=[c], help='set status by hand')
    p.add_argument('--ticker', required=True)
    p.add_argument('--status', required=True, choices=STATUSES)
    p.add_argument('--fill', type=float, help='real fill price (for "in trade")')
    p.add_argument('--reason')
    p.set_defaults(fn=cmd_status)
    p = sp.add_parser('reset', parents=[c], help='new day: drop items not dated today')
    p.add_argument('--all', action='store_true', help='drop everything, including today')
    p.set_defaults(fn=cmd_reset)
    p = sp.add_parser('list', parents=[c], help="print today's list")
    p.set_defaults(fn=cmd_list)
    a = ap.parse_args()
    a.fn(a)


if __name__ == '__main__':
    main()
