#!/usr/bin/env python3
"""Risk Manager gate: run before EVERY order. Prints ALLOW or BLOCK with reasons. Never contacts Questrade or places
orders; it reads journal.json, data.json, strategies.json and the bar cache, and writes data.json paused[] and
riskBudgets (unless --no-write).

  python3 risk_check.py --bot scanner --ticker XIU.TO --side short --risk 38.50
  python3 risk_check.py --bot news --ticker SOFI --side long --risk 20 --idea 2026-11-03-SOFI-1
  python3 risk_check.py --bot quant --strategy orb --ticker QQQ --side long --risk 30 --open SPY:long:35:quant --open XIU.TO:short
  python3 risk_check.py --update          # start of every routine run: refresh pauses + budget bars, print status
  python3 risk_check.py --status          # print budgets / pauses, write nothing
  python3 risk_check.py --unpause whale   # K lifts a pause by hand

Checks (any failure = BLOCK):
  desk:    risk <= 40 CAD per trade; desk realized loss today + open risk + this risk <= 150; open positions < 4;
           no new entries after 15:15 ET (today only)
  bot:     not paused; bot realized loss today + bot open risk + this risk <= the bot's budget (strategies.json
           risk.botBudgetsCAD; prints the largest risk still allowed so the run can resize and re-check)
  pauses:  set automatically when a bot (a) has realized loss today >= its budget -> paused until next trading day;
           (b) has >= 3 stop-outs in its last 5 trading days -> 2 trading days; (c) its last 20 real trades sum to
           <= -4R -> 5 trading days. Stored in data.json paused[] with reason + until.
  groups:  an open or pending position in the same correlation group (strategies.json risk.correlation.groups) and
           the same direction; or 20-day daily-return correlation > 0.8 with an open same-direction position
           (only when both tickers are in bars/*.csv; else groups only)
  mode:    strategies.json mode/modes: 'paper' strategies are BLOCKed ('paper-only: retired'; Quant Lab VWAP).
           Bots with several strategies must pass --strategy (Quant Lab: orb | vwap | sip_orb)
  debate:  strategies with devils_advocate.required (News Desk; Quant Lab's Stocks-in-play ORB, pass
           --strategy sip_orb) need --idea <journal id> whose debate verdict is 'take' (debate.py)
Real trades = journal ideas with taken == 'yes' (log_idea.py resolve --taken yes --real-pnl X). Open/pending =
taken ideas without a result, today's watchlist items with status 'triggered' or 'in trade', plus every --open.
Pass --open TICKER:side[:riskCAD[:bot]] for each live Questrade position/working entry (get_positions / get_orders)
so the check sees positions the journal does not. Unknown open risk counts as 40 CAD.
Exit code: 0 = ALLOW, 2 = BLOCK, 1 = usage error.
"""
import argparse, json, math, os, sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bars  # noqa: E402
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo('America/Toronto')
except Exception:  # pragma: no cover
    ET = None

DEFAULT_BUDGETS = {'scanner': 50, 'quant': 35, 'news': 25, 'whale': 20, 'options': 20}


def now_et():
    return datetime.now(ET) if ET else datetime.now()


def load(name, default):
    p = os.path.join(HERE, name)
    return json.load(open(p)) if os.path.exists(p) else default


def save(name, obj):
    p = os.path.join(HERE, name)
    with open(p + '.tmp', 'w') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False); f.write('\n')
    os.replace(p + '.tmp', p)


def root(t):
    return t.upper().split('.')[0]


def d2s(d):
    return d.strftime('%Y-%m-%d')


def add_trading_days(ds, n):
    d = datetime.strptime(ds, '%Y-%m-%d')
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d2s(d)


def last_trading_days(ds, n):
    d = datetime.strptime(ds, '%Y-%m-%d'); out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d2s(d))
        d -= timedelta(days=1)
    return out


def cad(x, cur, data):
    return x * float(data.get('fees', {}).get('usdcad', {}).get('rate', 1.0)) if cur == 'USD' else x


# ------------------------------------------------------------------ state from journal / data
def real_trades(journal):
    return [i for i in journal.get('ideas', []) if i.get('taken') == 'yes']


def idea_risk_cad(i, data):
    p = i.get('plan') or {}
    if p.get('netLossAtStopCAD') is not None:
        return abs(p['netLossAtStopCAD'])
    if p.get('riskGross') is not None:
        return cad(p['riskGross'], i.get('currency', 'CAD'), data)
    return 40.0


def is_stopout(i):
    r = i.get('result') or {}
    return r.get('outcome') == 'stop' or (i.get('realR') is not None and i['realR'] <= -0.8)


def open_positions(journal, data, today, extra):
    pos = []
    for i in real_trades(journal):
        if not i.get('result'):
            pos.append(dict(ticker=i['ticker'], side=i['side'], risk=idea_risk_cad(i, data), bot=i.get('bot'), src=f"journal {i['id']}"))
    for w in data.get('watchlist', []):
        if w.get('date') == today and str(w.get('status', '')).lower() in ('triggered', 'in trade') and w.get('side'):
            if not any(root(p['ticker']) == root(w['ticker']) and p['side'] == w['side'] for p in pos):
                r = abs(w['netLossAtStopCAD']) if w.get('netLossAtStopCAD') is not None else 40.0
                pos.append(dict(ticker=w['ticker'], side=w['side'], risk=r, bot=w.get('bot'), src=f"watchlist {w.get('status')}"))
    for e in extra:
        parts = e.split(':')
        if len(parts) < 2 or parts[1] not in ('long', 'short'):
            sys.exit(f'bad --open {e!r}: use TICKER:long|short[:riskCAD[:bot]]')
        t, s = parts[0], parts[1]
        r = float(parts[2]) if len(parts) > 2 and parts[2] else 40.0
        b = parts[3] if len(parts) > 3 else None
        pos = [p for p in pos if not (root(p['ticker']) == root(t) and p['side'] == s)]
        pos.append(dict(ticker=t, side=s, risk=r, bot=b, src='--open'))
    return pos


def realized_today(journal, data, today, bot=None):
    j = sum(i.get('realPnlCAD') or 0 for i in real_trades(journal) if i['date'] == today and i.get('result')
            and (bot is None or i.get('bot') == bot))
    if bot is None:
        d = (data.get('pnlToday') or {}).get('realized')
    else:
        b = next((x for x in data.get('bots', []) if x['id'] == bot), {})
        d = b.get('pnlToday')
    if (data.get('pnlToday') or {}).get('date') not in (None, today):
        d = None
    return min(j, d) if isinstance(d, (int, float)) else j


# ------------------------------------------------------------------ pauses
def cutoff(data, bot, rule):
    """Trades on/before the start of the last expired pause for (bot, rule) no longer count."""
    h = [p for p in data.get('pausedHistory', []) if p['bot'] == bot and p['rule'] == rule]
    return max((p['since'] for p in h), default='0000-00-00')


def evaluate_pauses(journal, data, strategies, today):
    budgets = strategies.get('risk', {}).get('botBudgetsCAD', DEFAULT_BUDGETS)
    paused = [p for p in data.get('paused', [])]
    hist = data.setdefault('pausedHistory', [])
    still = []
    for p in paused:                         # expire
        if p['until'] <= today:
            p['expiredOn'] = today; hist.append(p)
        else:
            still.append(p)
    paused = still; new = []
    real = real_trades(journal)
    for bot, budget in budgets.items():
        def add(rule, reason, until):
            if not any(p['bot'] == bot and p['rule'] == rule for p in paused):
                p = dict(bot=bot, rule=rule, reason=reason, since=today, until=until, setBy='risk_check.py',
                         setAt=now_et().isoformat(timespec='seconds'))
                paused.append(p); new.append(p)
        lost = -realized_today(journal, data, today, bot)
        if lost >= budget:
            add('dailyBudget', f'hit its {budget:.0f} CAD daily budget (lost {lost:.2f} today)', add_trading_days(today, 1))
        days5 = set(last_trading_days(today, 5)); c = cutoff(data, bot, 'stopoutGuard')
        so = [i for i in real if i.get('bot') == bot and i['date'] in days5 and i['date'] > c and i.get('result') and is_stopout(i)]
        if len(so) >= 3:
            add('stopoutGuard', f'{len(so)} stop-outs in its last 5 trading days', add_trading_days(today, 2))
        c = cutoff(data, bot, 'drawdownGuard')
        mine = sorted([i for i in real if i.get('bot') == bot and i.get('result') and i['date'] > c and i.get('realR') is not None],
                      key=lambda i: (i['date'], i.get('loggedAt', '')))[-20:]
        tot = sum(i['realR'] for i in mine)
        if mine and tot <= -4:
            add('drawdownGuard', f'running real loss {tot:+.2f}R over its last {len(mine)} trades (limit -4R)', add_trading_days(today, 5))
    data['paused'] = paused
    return paused, new


def budgets_snapshot(journal, data, strategies, today, positions):
    budgets = strategies.get('risk', {}).get('botBudgetsCAD', DEFAULT_BUDGETS)
    out = {}
    for bot, budget in budgets.items():
        lost = max(0.0, -realized_today(journal, data, today, bot))
        orisk = sum(p['risk'] for p in positions if p.get('bot') == bot)
        out[bot] = dict(budget=budget, realizedLoss=round(lost, 2), openRisk=round(orisk, 2), used=round(lost + orisk, 2),
                        left=round(max(0.0, budget - lost - orisk), 2))
    lost = max(0.0, -realized_today(journal, data, today))
    orisk = sum(p['risk'] for p in positions)
    stop = strategies.get('risk', {}).get('dailyLossStopCAD', 150)
    return dict(date=today, updated=now_et().isoformat(timespec='seconds'), bots=out,
                desk=dict(budget=stop, realizedLoss=round(lost, 2), openRisk=round(orisk, 2), used=round(lost + orisk, 2),
                          left=round(max(0.0, stop - lost - orisk), 2), openPositions=len(positions)))


# ------------------------------------------------------------------ correlation
def groups_of(ticker, strategies):
    g = strategies.get('risk', {}).get('correlation', {}).get('groups', {})
    r = root(ticker)
    return [name for name, members in g.items() if r in {root(m) for m in members}]


def corr20(a, b, n=20):
    A = {x['date']: x['close'] for x in bars.load(a)}; B = {x['date']: x['close'] for x in bars.load(b)}
    if not A or not B:
        return None
    common = sorted(set(A) & set(B))[-(n + 1):]
    if len(common) < n + 1:
        return None
    ra = [math.log(A[common[i]] / A[common[i - 1]]) for i in range(1, len(common))]
    rb = [math.log(B[common[i]] / B[common[i - 1]]) for i in range(1, len(common))]
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = math.sqrt(sum((x - ma) ** 2 for x in ra)); vb = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return cov / (va * vb) if va and vb else None



# ------------------------------------------------------------------ strategy lookup + mode (live | paper)
def _aliases(st):
    out = []  # (alias, sub-key or None)
    al = st.get('aliases')
    if isinstance(al, dict):
        for k, v in al.items():
            out += [(x.lower(), k) for x in [k] + list(v)]
    else:
        out += [(x.lower(), None) for x in (al or [])]
    for x in (st.get('id'), st.get('short'), st.get('name')):
        if x:
            out.append((x.lower(), None))
    return out


def bot_strategies(strategies, bot):
    return [s for s in strategies.get('strategies', []) if s.get('bot') == bot]


def needs_name(strategies, bot):
    L = bot_strategies(strategies, bot)
    return len(L) > 1 or any(s.get('modes') for s in L)


def choices(strategies, bot):
    out = []
    for s in bot_strategies(strategies, bot):
        out += list(s['modes']) if s.get('modes') else [s.get('id') or s.get('short')]
    return out


def resolve_strategy(strategies, bot, text):
    """Match free text (or an id/alias) to one of the bot's strategies; the longest alias contained in the text wins.
    Returns {strategy, sub, mode, label} or None. Mode = sub-mode (modes{}) or the strategy's mode (default live)."""
    L = bot_strategies(strategies, bot)
    if not L:
        return None
    if not text:
        if needs_name(strategies, bot):
            return None
        st = L[0]; return dict(strategy=st, sub=None, mode=st.get('mode', 'live'), label=st.get('short') or st.get('name'))
    t = text.lower(); best = None
    for st in L:
        for al, sub in _aliases(st):
            if al and (al == t or al in t) and (best is None or len(al) > best[0]):
                best = (len(al), st, sub)
    if not best:
        return None
    _, st, sub = best
    if st.get('modes') and sub is None:
        return None if needs_name(strategies, bot) and len(st['modes']) > 1 else None
    mode = st['modes'][sub] if sub else st.get('mode', 'live')
    return dict(strategy=st, sub=sub, mode=mode, label=f"{st.get('short')} / {sub}" if sub else (st.get('short') or st.get('name')))

# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bot'); ap.add_argument('--ticker'); ap.add_argument('--side', choices=['long', 'short'])
    ap.add_argument('--risk', type=float, help='this trade\'s max loss to the stop in CAD, after fees')
    ap.add_argument('--idea', help='journal idea id (needed for strategies with a devil\'s-advocate debate)')
    ap.add_argument('--strategy', help='which strategy (required for Quant Lab: orb | vwap | sip_orb); paper-mode strategies always BLOCK')
    ap.add_argument('--open', action='append', default=[], metavar='TICKER:side[:riskCAD[:bot]]')
    ap.add_argument('--date', help='trading date (default today ET)')
    ap.add_argument('--now', help='HH:MM ET override for the 15:15 cutoff (testing)')
    ap.add_argument('--update', action='store_true', help='refresh pauses + budget bars, no trade check')
    ap.add_argument('--status', action='store_true', help='print state, write nothing')
    ap.add_argument('--unpause', metavar='BOT')
    ap.add_argument('--no-write', action='store_true')
    ap.add_argument('--dir', help='desk folder (default: this script\'s folder)')
    a = ap.parse_args()
    global HERE
    if a.dir:
        HERE = a.dir
    today = a.date or now_et().strftime('%Y-%m-%d')
    data = load('data.json', {}); journal = load('journal.json', {'ideas': []}); strategies = load('strategies.json', {})
    R = strategies.get('risk', {})
    budgets = R.get('botBudgetsCAD', DEFAULT_BUDGETS)

    if a.unpause:
        keep = []
        for p in data.get('paused', []):
            if p['bot'] == a.unpause:
                p['expiredOn'] = today; p['liftedBy'] = 'K (manual)'; data.setdefault('pausedHistory', []).append(p)
            else:
                keep.append(p)
        data['paused'] = keep; save('data.json', data); print(f'unpaused {a.unpause}'); return 0

    paused, new = evaluate_pauses(journal, data, strategies, today)
    positions = open_positions(journal, data, today, a.open)
    snap = budgets_snapshot(journal, data, strategies, today, positions)

    def show_state():
        print(f"desk {today}: realized loss {snap['desk']['realizedLoss']:.2f} + open risk {snap['desk']['openRisk']:.2f} = "
              f"{snap['desk']['used']:.2f} / {snap['desk']['budget']:.0f} CAD · open positions {len(positions)}/{R.get('maxOpenPositions', 4)}")
        for b, s in snap['bots'].items():
            pz = next((p for p in paused if p['bot'] == b), None)
            print(f"  {b:<8} budget {s['budget']:>3.0f}  used {s['used']:>6.2f}  left {s['left']:>6.2f}" + (f"  PAUSED until {pz['until']}: {pz['reason']}" if pz else ''))
        for p in positions:
            print(f"  open: {p['ticker']} {p['side']} risk {p['risk']:.2f} ({p.get('bot') or '?'}; {p['src']})")
        for p in new:
            print(f"NEW PAUSE: {p['bot']} until {p['until']} - {p['reason']}")

    if a.status or a.update or not a.bot:
        if not (a.status or a.update):
            ap.error('give --bot/--ticker/--side/--risk, or --update / --status')
        show_state()
        if a.update and not a.no_write:
            data['riskBudgets'] = snap; save('data.json', data); print('wrote data.json paused[] + riskBudgets')
        return 0
    if not (a.ticker and a.side and a.risk is not None):
        ap.error('--bot needs --ticker, --side and --risk')

    block, info = [], []
    bot, tk, side, risk = a.bot, a.ticker.upper(), a.side, float(a.risk)
    maxr = float((R.get('maxLossPerTradeCADByBot') or {}).get(bot, R.get('maxLossPerTradeCAD', 40))); stop = float(R.get('dailyLossStopCAD', 150)); mxo = int(R.get('maxOpenPositions', 4))
    # desk limits
    if risk <= 0:
        block.append('risk must be > 0 CAD')
    if risk > maxr:
        block.append(f'risk {risk:.2f} > {maxr:.0f} CAD per-trade max')
    if snap['desk']['used'] + risk > stop:
        block.append(f"desk daily stop: realized loss {snap['desk']['realizedLoss']:.2f} + open risk {snap['desk']['openRisk']:.2f} + this {risk:.2f} > {stop:.0f} CAD (room {snap['desk']['left']:.2f})")
    if len(positions) >= mxo:
        block.append(f'{len(positions)} open/pending positions (max {mxo})')
    hhmm = a.now or now_et().strftime('%H:%M')
    if today == now_et().strftime('%Y-%m-%d') or a.now:
        if hhmm > R.get('noNewEntriesAfterET', '15:15'):
            block.append(f"no new entries after {R.get('noNewEntriesAfterET', '15:15')} ET (now {hhmm})")
    # bot budget + pauses
    if bot in budgets:
        s = snap['bots'][bot]
        if s['used'] + risk > s['budget'] + 1e-9:
            block.append(f"{bot} daily budget: used {s['used']:.2f} (loss {s['realizedLoss']:.2f} + open {s['openRisk']:.2f}) + this {risk:.2f} > {s['budget']:.0f} CAD"
                         + (f" -> RESIZE to risk <= {s['left']:.2f} CAD and re-check" if s['left'] >= 1 else ' -> no room left today'))
        else:
            info.append(f"{bot} budget after this trade: {s['used'] + risk:.2f} / {s['budget']:.0f} CAD")
    else:
        block.append(f'{bot} has no trading budget in strategies.json risk.botBudgetsCAD (non-trading bot?)')
    for p in paused:
        if p['bot'] == bot:
            block.append(f"{bot} PAUSED until {p['until']} ({p['rule']}): {p['reason']}")
    # same ticker already open
    for p in positions:
        if root(p['ticker']) == root(tk):
            block.append(f"already {p['side']} {p['ticker']} ({p['src']})")
    # correlation groups
    mine = set(groups_of(tk, strategies))
    for p in positions:
        if p['side'] != side or root(p['ticker']) == root(tk):
            continue
        shared = mine & set(groups_of(p['ticker'], strategies))
        if shared:
            block.append(f"one bet per group: {p['side']} {p['ticker']} is open/pending in {', '.join(sorted(shared))} ({p['src']})")
            continue
        c = corr20(tk, p['ticker'])
        if c is None:
            info.append(f"corr {tk}/{p['ticker']}: no cached daily bars for both, groups only")
        elif c > float(R.get('correlation', {}).get('threshold', 0.8)):
            block.append(f"20-day return correlation {c:.2f} > 0.8 with open {p['side']} {p['ticker']}")
        else:
            info.append(f"corr {tk}/{p['ticker']} 20d = {c:.2f}")
    if not mine:
        info.append(f'{tk} is in no correlation group')
    # devil's advocate
    strats = []
    if bot_strategies(strategies, bot):
        rs = resolve_strategy(strategies, bot, a.strategy)
        if rs is None:
            block.append(f"name the strategy: --strategy {'|'.join(choices(strategies, bot))}" if not a.strategy
                         else f"unknown strategy {a.strategy!r} for {bot} (use {'|'.join(choices(strategies, bot))})")
        else:
            strats = [rs['strategy']]
            if rs['mode'] == 'paper':
                block.append(f"paper-only: retired ({rs['label']}) - log the signal with log_idea.py as a paper idea, never send a real order")
            elif rs['mode'] != 'live':
                block.append(f"strategy mode {rs['mode']!r} is not live ({rs['label']})")
            else:
                info.append(f"strategy {rs['label']}: mode live")
    need = [s for s in strats if (s.get('devils_advocate') or {}).get('required')]
    if need:
        idea = next((i for i in journal.get('ideas', []) if i['id'] == a.idea), None) if a.idea else None
        nm = need[0].get('short', need[0].get('name'))
        if not a.idea:
            block.append(f"{nm} trades need a devil's-advocate debate: log the idea, run debate.py, then pass --idea <id>")
        elif not idea:
            block.append(f'--idea {a.idea} not in journal.json')
        elif not idea.get('debate'):
            block.append(f'idea {a.idea} has no debate (run debate.py first)')
        elif idea['debate'].get('verdict') != 'take':
            block.append(f"devil's advocate VETO on {a.idea}: verdict {idea['debate'].get('verdict')}")
        else:
            info.append(f"debate on {a.idea}: bull case wins ({idea['debate'].get('why', '')[:80]})")
    if not a.no_write:
        data['riskBudgets'] = snap; save('data.json', data)
    verdict = 'BLOCK' if block else 'ALLOW'
    if block and not a.no_write:   # desk throughput: one rejection per idea per day (re-checks of the same idea count once)
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import count as _c
            _c.quiet_record('risk', {'ideasRejected': 1}, key='rejected:' + (a.idea or f'{bot}:{tk}:{side}'),
                            path=None if HERE == os.path.dirname(os.path.abspath(__file__)) else os.path.join(HERE, 'counters.json'))
        except Exception as e:
            print(f'(not counted: {e})', file=sys.stderr)
    print(f"{verdict} {bot} {side} {tk} risk {risk:.2f} CAD")
    for b in block:
        print(f'  - BLOCK: {b}')
    for i in info:
        print(f'  - ok: {i}')
    for p in new:
        print(f"  - NEW PAUSE: {p['bot']} until {p['until']} - {p['reason']}")
    return 2 if block else 0


if __name__ == '__main__':
    sys.exit(main())
