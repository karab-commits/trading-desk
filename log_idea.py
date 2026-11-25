#!/usr/bin/env python3
"""Paper-track every idea the desk sends K (taken or not) in journal.json.

Every alert gets logged with `add` BEFORE it is sent, so the alert can quote the
after-fee numbers this script prints. Later `resolve` scores it as if it had been
traded exactly at the alert's plan (or at `loggedPrice` when `loggedLate` is set), and records whether K actually took it.

  python3 log_idea.py add --date 2026-11-03 --session premarket --ticker XIU.TO --side short \\
      --entry 54.31 --stop 54.84 --target 53.78 --shares 150 --strategy "Big-gap fade XIU" --bot scanner
  python3 log_idea.py resolve --id 2026-11-03-XIU-1 --outcome target --exit 53.78 --taken no
  python3 log_idea.py resolve --id 2026-11-03-XIU-1 --outcome stop --exit 54.84 --taken yes --real-pnl -79.50
  python3 log_idea.py list --date 2026-11-03 --open

Fees come from data.json `fees` (Questrade schedule; see README). Money is kept in the
idea's own currency (CAD or USD) and also converted to CAD with fees.usdcad for totals.
Every `add` also records the strategy's `mode` from strategies.json: a paper-only (retired) strategy such as Quant
Lab's VWAP reclaim/loss is logged with mode=paper, taken=no and the run must not send an order.
Every `add` also tags the idea with today's market mood (`regime`: calm|volatile, from regime.py).
After every add/resolve, data.json `paper` (by-date paper P&L for the wall board) is refreshed.
"""
import argparse, csv, fcntl, json, os, sys
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo('America/Toronto')
except Exception:  # pragma: no cover
    ET = None

HERE = os.path.dirname(os.path.abspath(__file__))
CAD_SUFFIXES = ('.TO', '.V', '.CN', '.NE', '.TSX', '.VN')


def desk_dir(args=None):
    d = getattr(args, 'dir', None) if args else None
    return d or os.environ.get('DESK_DIR') or HERE


def now_et():
    return datetime.now(ET) if ET else datetime.now()


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def save_json(path, obj):
    tmp = f'{path}.tmp{os.getpid()}'
    with open(tmp, 'w') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write('\n')
    os.replace(tmp, path)


def r2(x):
    return None if x is None else round(x + 0.0, 2)


def infer_currency(ticker):
    return 'CAD' if ticker.upper().endswith(CAD_SUFFIXES) else 'USD'


def to_cad(amount, currency, fees_cfg):
    if amount is None:
        return None
    if currency == 'USD':
        return amount * float(fees_cfg.get('usdcad', {}).get('rate', 1.0))
    return amount


# ---------------------------------------------------------------- fees
def trade_fees(side, entry, exit_px, shares, currency, cfg):
    """Fees for one round trip (open at entry, close at exit), in the trade currency.

    commission (per order) + ECN (per share, both legs) + SEC fee (US sells only)
    + FX spread per cfg.fx.mode: 'none' | 'pnl' (only the P&L is converted to CAD)
    | 'round_trip' (CAD converted to USD to buy and back after selling).
    """
    st = cfg.get('stocksEtfs', {})
    comm = float(st.get('commissionPerOrder', 0)) * 2
    ecn = float(st.get('ecnPerShare', {}).get(currency, 0)) * shares * 2
    sec = 0.0
    if currency == 'USD':
        rate = float(cfg.get('secFee', {}).get('rate', 0))
        sell_px = exit_px if side == 'long' else entry
        sec = rate * sell_px * shares
    fx = 0.0
    if currency == 'USD' and cfg.get('accountCurrency', 'CAD') == 'CAD':
        f = cfg.get('fx', {})
        spread = float(f.get('spreadPct', 0)) / 100.0
        mode = f.get('mode', 'pnl')
        gross = (exit_px - entry) * shares * (1 if side == 'long' else -1)
        if mode == 'pnl':
            fx = spread * abs(gross)
        elif mode == 'round_trip':
            fx = spread * (entry + exit_px) * shares
    total = comm + ecn + sec + fx
    return {'commission': r2(comm), 'ecn': r2(ecn), 'sec': round(sec, 4), 'fx': r2(fx), 'total': round(total, 4)}


def gross_pnl(side, entry, exit_px, shares):
    return (exit_px - entry) * shares * (1 if side == 'long' else -1)


def paper_entry(idea):
    """Price used to score paper P&L.

    The journal `entry` stays the original signal price. If the idea was logged after
    the signal bar (`loggedLate`) and `loggedPrice` is set, paper P&L is scored from
    that log-time price, not the signal.
    """
    if idea.get('loggedLate') and idea.get('loggedPrice') is not None:
        return float(idea['loggedPrice'])
    return idea['entry']


def score_paper(idea, outcome, exit_px, cfg):
    """Build a journal `result` using paper_entry (logged price when late)."""
    cur = idea['currency']
    e = paper_entry(idea)
    if outcome == 'no-fill':
        return {'outcome': 'no-fill', 'exit': None, 'gross': 0.0,
                'fees': trade_fees(idea['side'], e, e, 0, cur, cfg),
                'net': 0.0, 'grossR': 0.0, 'netR': 0.0, 'netCAD': 0.0}
    g = gross_pnl(idea['side'], e, exit_px, idea['shares'])
    f = trade_fees(idea['side'], e, exit_px, idea['shares'], cur, cfg)
    net = g - f['total']
    risk = (idea.get('plan') or {}).get('riskGross') or None
    res = {'outcome': outcome, 'exit': exit_px, 'gross': r2(g), 'fees': f, 'net': r2(net),
           'grossR': round(g / risk, 3) if risk else None, 'netR': round(net / risk, 3) if risk else None,
           'netCAD': r2(to_cad(net, cur, cfg))}
    if idea.get('loggedLate'):
        res['entryUsed'] = e
    return res


def plan_numbers(idea, cfg):
    s, e, st, tg, n, cur = idea['side'], idea['entry'], idea['stop'], idea['target'], idea['shares'], idea['currency']
    risk = abs(e - st) * n
    reward = abs(tg - e) * n
    fw = trade_fees(s, e, tg, n, cur, cfg)
    fl = trade_fees(s, e, st, n, cur, cfg)
    net_win = reward - fw['total']
    net_loss = -risk - fl['total']
    return {
        'riskGross': r2(risk), 'rewardGross': r2(reward),
        'rr': round(reward / risk, 2) if risk else None,
        'feesAtTarget': fw, 'feesAtStop': fl,
        'netProfitAtTarget': r2(net_win), 'netLossAtStop': r2(net_loss),
        'rrNet': round(net_win / -net_loss, 2) if net_loss else None,
        'netProfitAtTargetCAD': r2(to_cad(net_win, cur, cfg)), 'netLossAtStopCAD': r2(to_cad(net_loss, cur, cfg)),
    }


# ---------------------------------------------------------------- paper board summary
def iso_week(date_str):
    y, w, _ = datetime.strptime(date_str, '%Y-%m-%d').isocalendar()
    return f'{y}-W{w:02d}'


def refresh_paper(data, journal):
    """data.json `paper`: per-date paper P&L (CAD, net of fees) so the site can show today/week/all."""
    by = {}
    for i in journal.get('ideas', []):
        d = by.setdefault(i['date'], {'net': 0.0, 'ideas': 0, 'resolved': 0, 'open': 0, 'filled': 0, 'wins': 0,
                                       'real': 0.0, 'taken': 0})
        d['ideas'] += 1
        res = i.get('result')
        if not res:
            d['open'] += 1
            continue
        d['resolved'] += 1
        if res['outcome'] != 'no-fill':
            d['filled'] += 1
            d['net'] += res.get('netCAD') or 0
            if (res.get('net') or 0) > 0:
                d['wins'] += 1
        if i.get('taken') == 'yes' and i.get('realPnlCAD') is not None:
            d['taken'] += 1
            d['real'] += i['realPnlCAD']
    for d in by.values():
        d['net'] = r2(d['net'])
        d['real'] = r2(d['real'])
    data['paper'] = {'currency': 'CAD', 'basis': 'net of fees, resolved ideas only',
                     'updated': now_et().isoformat(timespec='seconds'),
                     'ideasLogged': len(journal.get('ideas', [])),
                     'byDate': dict(sorted(by.items()))}
    return data


def write_back(ddir, journal, data):
    save_json(os.path.join(ddir, 'journal.json'), journal)
    refresh_paper(data, journal)
    save_json(os.path.join(ddir, 'data.json'), data)


# ---------------------------------------------------------------- commands
def fmt_money(x, cur):
    return f"{'+' if x > 0 else '-' if x < 0 else ''}${abs(x):.2f} {cur}"


def _count(ddir, bot, inc, key=None):
    """Desk throughput counter (count.py); never breaks logging."""
    try:
        sys.path.insert(0, HERE)
        import count as _c
        _c.quiet_record(bot, inc, key=key, path=None if os.path.abspath(ddir) == HERE else os.path.join(ddir, 'counters.json'))
    except Exception as e:
        print(f'(not counted: {e})', file=sys.stderr)


def cmd_add(a):
    ddir = desk_dir(a)
    data = load_json(os.path.join(ddir, 'data.json'), {})
    cfg = data.get('fees')
    if not cfg:
        sys.exit('data.json has no `fees` config')
    journal = load_json(os.path.join(ddir, 'journal.json'), {'version': 1, 'ideas': []})
    datetime.strptime(a.date, '%Y-%m-%d')
    t = a.ticker.upper()
    if a.side == 'long' and not (a.stop < a.entry < a.target):
        sys.exit('long idea needs stop < entry < target')
    if a.side == 'short' and not (a.target < a.entry < a.stop):
        sys.exit('short idea needs target < entry < stop')
    if a.shares <= 0:
        sys.exit('shares must be > 0')
    root = t.split('.')[0]
    n = 1 + sum(1 for i in journal['ideas'] if i['date'] == a.date and i['ticker'].split('.')[0] == root)
    iid = f'{a.date}-{root}-{n}'
    while any(i['id'] == iid for i in journal['ideas']):
        n += 1
        iid = f'{a.date}-{root}-{n}'
    idea = {'id': iid, 'date': a.date, 'session': a.session, 'ticker': t, 'side': a.side,
            'entry': a.entry, 'stop': a.stop, 'target': a.target, 'shares': a.shares,
            'strategy': a.strategy, 'bot': a.bot, 'currency': (a.currency or infer_currency(t)).upper(),
            'note': a.note or '', 'loggedAt': now_et().isoformat(timespec='seconds')}
    if getattr(a, 'logged_late', False) or getattr(a, 'logged_price', None) is not None:
        if not getattr(a, 'logged_late', False) or a.logged_price is None:
            sys.exit('--logged-late requires --logged-price (the price at log time)')
        idea['loggedLate'] = True
        idea['loggedPrice'] = a.logged_price
    idea['plan'] = plan_numbers(idea, cfg)
    # strategy mode from strategies.json (live | paper, or a long/short map): paper-only strategies/sides are logged but never traded
    mode, mlabel, raw_mode = 'live', None, None
    try:
        sys.path.insert(0, HERE)
        import risk_check as _rc
        _S = load_json(os.path.join(ddir, 'strategies.json'), {})
        _r = _rc.resolve_strategy(_S, a.bot, a.strategy_id or a.strategy, side=a.side)
        if _r:
            mode, mlabel = _r['mode'], _r['label']
            raw_mode = _r.get('modeRaw')
    except Exception:
        pass
    if a.paper:
        mode = 'paper'
    idea['mode'] = mode
    if mode == 'paper':
        if isinstance(raw_mode, dict):
            idea['paperReason'] = f'paper-only for {a.side}s ({mlabel})'
        else:
            idea['paperReason'] = f'paper-only: retired ({mlabel})' if mlabel else 'paper-only'
    # market-mood tag (regime.py): tag only, never a filter
    try:
        sys.path.insert(0, HERE)
        import regime as _regime
        rg = _regime.tag_for(a.date)
    except Exception:
        rg = None
    idea['regime'] = rg['regime'] if rg else None
    idea['regimeDetail'] = ({'spy_rv10': rg['spy_rv10'], 'median': rg['median'], 'asOfClose': rg['asOfClose'],
                             'stale': rg.get('stale', False)} if rg else {'error': 'no SPY bars cached (run regime.py)'})
    idea['feesSource'] = {'url': cfg.get('source'), 'checked': cfg.get('checked')}
    idea['result'] = None
    idea['taken'] = 'no' if idea.get('mode') == 'paper' else None
    idea['realPnl'] = None
    idea['realPnlCAD'] = None
    journal['ideas'].append(idea)
    write_back(ddir, journal, data)
    _count(ddir, a.bot, {'ideasLogged': 1}, key='logged:' + iid)
    p, cur = idea['plan'], idea['currency']
    print(f'id: {iid}')
    if idea.get('mode') == 'paper':
        print(f"PAPER-ONLY: {idea['paperReason']} - logged for paper scoring; do NOT send a real order")
    print(f"regime: {idea['regime'] or 'unknown'}" + (f" (SPY rv10 {rg['spy_rv10']}% vs median {rg['median']}%)" if rg else ''))
    print(f"{t} {a.side} {a.shares} @ {a.entry} stop {a.stop} target {a.target} ({cur})")
    print(f"risk {fmt_money(-p['riskGross'], cur)} | reward {fmt_money(p['rewardGross'], cur)} | R:R {p['rr']}")
    print(f"fees est: {p['feesAtTarget']['total']:.2f} at target / {p['feesAtStop']['total']:.2f} at stop {cur}")
    print(f"NET after fees: target {fmt_money(p['netProfitAtTarget'], cur)} | stop {fmt_money(p['netLossAtStop'], cur)} | net R:R {p['rrNet']}")
    if cur != 'CAD':
        print(f"  in CAD @ {cfg['usdcad']['rate']}: target {fmt_money(p['netProfitAtTargetCAD'], 'CAD')} | stop {fmt_money(p['netLossAtStopCAD'], 'CAD')}")
    print(f"alert line: Profit after fees {fmt_money(p['netProfitAtTarget'], cur)} at target, loss after fees {fmt_money(p['netLossAtStop'], cur)} at stop")


def first_touch(ddir, idea):
    """Kiwi Nov 25 2026: walk the cached Questrade 5-min bars (bars/<SYM>_5m.csv) from the bar containing loggedAt
    on the idea's date; return (outcome, bar_start) for the first bar touching the stop or target (both = stop), or
    (None, last_bar_start) if neither was touched, or None when the cache has no bars for that day."""
    sym = idea['ticker'].replace('.', '_')
    path = os.path.join(ddir, 'bars', f'{sym}_5m.csv')
    if not os.path.exists(path):
        return None
    try:
        t0 = datetime.fromisoformat(idea.get('loggedAt')).astimezone(ZoneInfo('UTC'))
    except Exception:
        return None
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                st = datetime.fromisoformat(r['start'].replace('Z', '+00:00'))
                en = datetime.fromisoformat(r['end'].replace('Z', '+00:00'))
            except Exception:
                continue
            if en > t0 and st.astimezone(ET).strftime('%Y-%m-%d') == idea['date']:
                rows.append((st, float(r['high']), float(r['low'])))
    if not rows:
        return None
    rows.sort()
    long_ = idea['side'] == 'long'
    for st, hi, lo in rows:
        hit_stop = lo <= idea['stop'] if long_ else hi >= idea['stop']
        hit_tgt = hi >= idea['target'] if long_ else lo <= idea['target']
        if hit_stop:
            return ('stop', st)
        if hit_tgt:
            return ('target', st)
    return (None, rows[-1][0])


def cmd_resolve(a):
    ddir = desk_dir(a)
    data = load_json(os.path.join(ddir, 'data.json'), {})
    cfg = data.get('fees') or {}
    journal = load_json(os.path.join(ddir, 'journal.json'), {'version': 1, 'ideas': []})
    idea = next((i for i in journal['ideas'] if i['id'] == a.id), None)
    if not idea:
        sys.exit(f'no idea with id {a.id}')
    if idea.get('mode') == 'paper' and (a.taken == 'yes' or a.real_pnl is not None):
        sys.exit(f"{a.id} is paper-only ({idea.get('paperReason')}); it can't be marked taken / given real P&L")
    cur = idea['currency']
    if a.outcome != 'no-fill' and a.exit is None:
        sys.exit('--exit PRICE is required unless --outcome no-fill')
    # Guard added by Kiwi Nov 24 2026: the 3:15-3:20 PM close-out scored paper 'time' exits at ~3:17 prices on
    # Nov 20, 23 and 24, and each had to be re-scored at the 4:00 PM close. A paper time exit can only be scored
    # after 16:00 ET on the idea's date (from the 3:55 5-min bar close). Real trades (taken yes / --real-pnl) are
    # exempt: they record the actual exit.
    now = now_et()
    if (a.outcome == 'time' and a.real_pnl is None and a.taken != 'yes' and not getattr(a, 'early', False)
            and idea['date'] == now.strftime('%Y-%m-%d') and now.strftime('%H:%M') < '16:00'):
        sys.exit(f"{a.id}: paper time exits are scored at the 4:00 PM ET close; it's {now.strftime('%H:%M')} ET. "
                 "Leave it open (the after-close review scores it from the 3:55 5-min bar), or pass --early if this is a real exit.")
    # Guard added by Kiwi Nov 25 2026: the 3:13 PM close-out scored HXT.TO a 'time' exit at 92.63 although the
    # 1:15 PM 5-min bar had touched the 92.37 target. Paper outcomes must match the first touch in the cached
    # 5-min bars (stop first when both). Real trades are exempt; --force overrides (say why in the desk log).
    if a.real_pnl is None and a.taken != 'yes' and a.outcome in ('time', 'target', 'stop') and not getattr(a, 'force', False):
        ft = first_touch(ddir, idea)
        if ft is not None:
            want, when = ft
            when_et = when.astimezone(ET).strftime('%H:%M') if ET else str(when)
            if want and a.outcome != want:
                sys.exit(f"{a.id}: cached 5-min bars show the {want} touched first (bar {when_et} ET), not '{a.outcome}'. "
                         "Fetch fresh bars if the cache is stale, or pass --force with a reason.")
            if want is None and a.outcome != 'time':
                sys.exit(f"{a.id}: cached 5-min bars (through {when_et} ET) show neither stop nor target touched; "
                         "refresh bars first, or pass --force.")
    res = score_paper(idea, a.outcome, a.exit, cfg)
    res['resolvedAt'] = now_et().isoformat(timespec='seconds')
    idea['result'] = res
    if a.taken:
        idea['taken'] = a.taken
    if a.real_pnl is not None:
        if idea.get('taken') != 'yes':
            idea['taken'] = 'yes'
        idea['realPnl'] = r2(a.real_pnl)
        idea['realPnlCAD'] = r2(to_cad(a.real_pnl, cur, cfg))
        risk = idea['plan']['riskGross']
        idea['realR'] = round(a.real_pnl / risk, 3) if risk else None
    elif idea.get('taken') == 'no':
        idea['realPnl'] = None
        idea['realPnlCAD'] = None
    write_back(ddir, journal, data)
    print(f"{idea['id']} {idea['ticker']} {idea['side']}: {a.outcome}" + (f" @ {a.exit}" if res['exit'] is not None else ''))
    print(f"paper: gross {fmt_money(res['gross'], cur)} | fees {res['fees']['total']:.2f} | NET {fmt_money(res['net'], cur)} | {res['netR']:+.2f}R net ({res['grossR']:+.2f}R gross)")
    if idea.get('taken'):
        line = f"taken: {idea['taken']}"
        if idea.get('realPnl') is not None:
            line += f" | real P&L {fmt_money(idea['realPnl'], cur)}"
        print(line)


def cmd_list(a):
    journal = load_json(os.path.join(desk_dir(a), 'journal.json'), {'version': 1, 'ideas': []})
    rows = [i for i in journal['ideas'] if (not a.date or i['date'] == a.date) and (not a.open or not i.get('result'))]
    if not rows:
        print('no ideas' + (' open' if a.open else '') + (f' on {a.date}' if a.date else ''))
        return
    for i in rows:
        r = i.get('result')
        st = 'OPEN' if not r else f"{r['outcome']} net {r['net']:+.2f}"
        p = i['plan']
        print(f"{i['id']:<22} {i['session']:<9} {i['ticker']:<8} {i['side']:<5} {i['shares']:>5} @ {i['entry']:<8} "
              f"stop {i['stop']:<8} tgt {i['target']:<8} net {p['netProfitAtTarget']:+.2f}/{p['netLossAtStop']:+.2f} {i['currency']} "
              f"[{i['bot']} · {i['strategy']}] {st}")


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--dir', help='folder with data.json + journal.json (default: this script\'s folder, or $DESK_DIR)')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('add', parents=[common], help='log a new idea (before the alert goes out)')
    p.add_argument('--date', required=True)
    p.add_argument('--session', required=True, choices=['premarket', 'midday', 'adhoc'])
    p.add_argument('--ticker', required=True)
    p.add_argument('--side', required=True, choices=['long', 'short'])
    p.add_argument('--entry', required=True, type=float)
    p.add_argument('--stop', required=True, type=float)
    p.add_argument('--target', required=True, type=float)
    p.add_argument('--shares', required=True, type=int)
    p.add_argument('--strategy', required=True)
    p.add_argument('--bot', required=True)
    p.add_argument('--currency', choices=['CAD', 'USD', 'cad', 'usd'])
    p.add_argument('--note')
    p.add_argument('--strategy-id', help='strategy id/alias for the mode lookup (e.g. vwap, orb, sip_orb); default: match --strategy text')
    p.add_argument('--paper', action='store_true', help='force paper-only (never traded)')
    p.add_argument('--logged-late', action='store_true',
                   help='idea was logged after the signal bar; paper P&L uses --logged-price')
    p.add_argument('--logged-price', type=float,
                   help='price at log time (required with --logged-late); used as the paper entry')
    p.set_defaults(fn=cmd_add)
    p = sp.add_parser('resolve', parents=[common], help='score an idea at its plan')
    p.add_argument('--id', required=True)
    p.add_argument('--outcome', required=True, choices=['target', 'stop', 'time', 'no-fill'])
    p.add_argument('--exit', type=float)
    p.add_argument('--taken', choices=['yes', 'no'])
    p.add_argument('--real-pnl', type=float, help="K's actual P&L on it, net of fees, in the idea's currency")
    p.add_argument('--early', action='store_true', help='allow a paper time exit before 16:00 ET (normally refused)')
    p.add_argument('--force', action='store_true', help='skip the 5-min bar first-touch check (explain why in the desk log)')
    p.set_defaults(fn=cmd_resolve)
    p = sp.add_parser('list', parents=[common], help='list ideas')
    p.add_argument('--date')
    p.add_argument('--open', action='store_true')
    p.set_defaults(fn=cmd_list)
    a = ap.parse_args()
    if a.cmd == 'list':
        a.fn(a)
        return
    # Kiwi Nov 25 2026: exclusive lock for add/resolve. Parallel resolves in the 3:13 PM close-out raced on
    # journal.json and one lost update left XIU.TO open. Read-modify-write now happens under journal.json.lock.
    with open(os.path.join(desk_dir(a), 'journal.json.lock'), 'a') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            a.fn(a)
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)


if __name__ == '__main__':
    main()
