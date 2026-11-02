#!/usr/bin/env python3
r"""Desk throughput counters: exact, real counts of what each bot processed (counters.json + runs.jsonl).

Nothing here is estimated or seeded. A routine calls this right after each real tool call; the desk scripts
(log_idea.py, risk_check.py, set_activity.py, bars.py, regime.py, /workspace/quant backtests) call it themselves.

  python3 count.py --bot scanner --quotes 1 --symbols RIVN,AMD          # after one Questrade get_quotes call for 2 symbols
  python3 count.py --bot scanner --bar-calls 1 --bars 78                # after get_historical_data (bars.py ingest does this itself)
  python3 count.py --bot options --option-calls 1 --contracts 42        # after an option chain / option quotes call
  python3 count.py --bot news --web-searches 1                          # after a web search
  python3 count.py --bot news --pages 1 --headline "Title|https://url|2026-11-03T09:41:00-05:00"   # after a fetch (+ headline)
  python3 count.py --bot whale --x-searches 1 --x-posts 25              # after an X search that returned 25 posts
  python3 count.py --bot scanner --ideas 1                              # idea generated (even if not logged)
  python3 count.py --bot kiwi --fills 1                                 # a real Questrade fill
  python3 count.py --bot scanner --run                                  # count one run (runs++, lastRun = now)
  python3 count.py --bot scanner --routine "scan 10:00" --run-start     # start of a run: snapshot
  python3 count.py --bot scanner --routine "scan 10:00" --run-end       # end: runs++, appends {bot,routine,start,end,delta} to runs.jsonl
  python3 count.py --show [--date 2026-11-03] [--bot scanner] [--json]  # print totals

Flags can be combined in one call. --headline may repeat; format "Title|url" or "Title|url|ISO time" (time defaults to now).
Headlines are de-duplicated per bot per day (by url, else title); the list keeps the latest 200, `count` keeps every unique one.
--symbols adds to the unique list and to `total` (every symbol in every quote call, repeats included).
Safe for concurrent runs: every write holds an exclusive lock on counters.json.lock and replaces the file atomically.
Env: DESK_COUNTERS=/path/counters.json (tests), DESK_COUNT=0 (scripts skip auto-counting), DESK_BOT=<id> (default bot for
bars.py / regime.py auto-counts).
"""
import argparse, fcntl, hashlib, json, os, sys
from contextlib import contextmanager
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo('America/Toronto')
except Exception:  # pragma: no cover
    ET = None

HERE = os.path.dirname(os.path.abspath(__file__))
BOTS = ['kiwi', 'scanner', 'news', 'whale', 'risk', 'quant', 'journal', 'options']
INT_FIELDS = ['quotesCalls', 'barCalls', 'bars', 'optionCalls', 'optionContracts', 'webSearches', 'pagesFetched',
              'xSearches', 'xPosts', 'ideasGenerated', 'ideasLogged', 'ideasRejected', 'ordersSent', 'fills',
              'backtestVariants', 'simulatedTrades', 'runs']
HEADLINE_CAP = 200


def now_et():
    return datetime.now(ET) if ET else datetime.now().astimezone()


def today():
    return now_et().strftime('%Y-%m-%d')


def counters_path(path=None):
    return path or os.environ.get('DESK_COUNTERS') or os.path.join(HERE, 'counters.json')


def empty_bot():
    b = {k: 0 for k in INT_FIELDS}
    b['symbolsQuoted'] = {'unique': [], 'total': 0}
    b['headlines'] = {'items': [], 'count': 0, 'seen': []}
    b['lastRun'] = None
    return b


def ensure_bot(day, bot):
    b = day.setdefault(bot, empty_bot())
    for k in INT_FIELDS:
        b.setdefault(k, 0)
    b.setdefault('symbolsQuoted', {'unique': [], 'total': 0})
    b.setdefault('headlines', {'items': [], 'count': 0, 'seen': []})
    b.setdefault('lastRun', None)
    return b


def empty_file():
    return {'_meta': {'version': 1, 'updated': None, 'tz': 'America/Toronto',
                      'note': 'Real counts only, written by count.py. Top-level YYYY-MM-DD keys -> bot id -> counters. '
                              '_audits holds reconstructed past totals that are NOT part of any day.'}}


@contextmanager
def locked(path=None):
    """Exclusive lock around a read-modify-write of counters.json. Yields the parsed dict; writes it back atomically."""
    p = counters_path(path)
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p + '.lock', 'a+') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            try:
                with open(p) as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                data = empty_file()
            state = {'write': True}
            yield data, state
            if state['write']:
                data.setdefault('_meta', {})['updated'] = now_et().isoformat(timespec='seconds')
                tmp = f'{p}.tmp{os.getpid()}'
                with open(tmp, 'w') as f:
                    json.dump(data, f, indent=1, ensure_ascii=False)
                    f.write('\n')
                os.replace(tmp, p)
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)


def _hkey(title, url):
    k = (url or '').strip() or (title or '').strip().lower()
    return hashlib.sha1(k.encode()).hexdigest()[:12]


def parse_headline(s):
    parts = [x.strip() for x in s.split('|')]
    title = parts[0]
    url = parts[1] if len(parts) > 1 else ''
    t = parts[2] if len(parts) > 2 and parts[2] else now_et().isoformat(timespec='seconds')
    if not title:
        raise ValueError(f'empty headline title: {s!r}')
    return {'title': title, 'url': url, 'time': t}


def apply(b, inc=None, symbols=None, headlines=None, key=None):
    """Apply increments to one bot's counters (in place). key: idempotency key for this event (skip if already seen).
    Returns True if anything was applied."""
    if key:
        keys = b.setdefault('keys', [])
        if key in keys:
            return False
        keys.append(key)
    for k, v in (inc or {}).items():
        if k not in INT_FIELDS:
            raise KeyError(f'unknown counter {k}')
        v = int(v)
        if v < 0:
            raise ValueError(f'{k} must be >= 0')
        b[k] += v
    if symbols:
        sq = b['symbolsQuoted']
        for s in symbols:
            s = s.strip().upper()
            if not s:
                continue
            sq['total'] += 1
            if s not in sq['unique']:
                sq['unique'].append(s)
    for h in headlines or []:
        hd = b['headlines']
        hk = _hkey(h['title'], h['url'])
        if hk in hd['seen']:
            continue
        hd['seen'].append(hk)
        hd['count'] += 1
        hd['items'].append(h)
        if len(hd['items']) > HEADLINE_CAP:
            hd['items'] = hd['items'][-HEADLINE_CAP:]
    return True


def record(bot, inc=None, symbols=None, headlines=None, date=None, key=None, run=False, path=None):
    """Library entry point used by the desk scripts. Never raises into the caller's work when quiet=True is wanted:
    callers wrap it in try/except. Returns True if applied."""
    if os.environ.get('DESK_COUNT', '1') == '0':
        return False
    if bot not in BOTS:
        raise ValueError(f'unknown bot {bot!r} (use {", ".join(BOTS)})')
    date = date or today()
    with locked(path) as (data, st):
        b = ensure_bot(data.setdefault(date, {}), bot)
        ok = apply(b, inc, symbols, headlines, key)
        if run and ok:
            b['runs'] += 1
            b['lastRun'] = now_et().isoformat(timespec='seconds')
        st['write'] = ok
        return ok


def quiet_record(*a, **k):
    """record() that only warns on failure, so counting can never break a desk script."""
    try:
        return record(*a, **k)
    except Exception as e:  # pragma: no cover
        print(f'(count.py: not counted: {e})', file=sys.stderr)
        return False


def default_bot(fallback='kiwi'):
    b = os.environ.get('DESK_BOT', '').strip().lower()
    return b if b in BOTS else fallback


def snapshot(b):
    s = {k: b.get(k, 0) for k in INT_FIELDS if k != 'runs'}
    s['symbolsQuoted'] = b['symbolsQuoted']['total']
    s['headlines'] = b['headlines']['count']
    return s


def runstate_path(path, bot, routine):
    d = os.path.join(os.path.dirname(os.path.abspath(counters_path(path))), '.runstate')
    os.makedirs(d, exist_ok=True)
    safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in routine)
    return os.path.join(d, f'{bot}__{safe}.json')


def runs_log_path(path):
    return os.path.join(os.path.dirname(os.path.abspath(counters_path(path))), 'runs.jsonl')


def total_of(day, bots=None):
    """Desk totals for one day dict."""
    t = {k: 0 for k in INT_FIELDS}
    syms, hl = set(), 0
    symtot = 0
    for bid, b in day.items():
        if bots and bid not in bots:
            continue
        for k in INT_FIELDS:
            t[k] += b.get(k, 0)
        syms.update(b.get('symbolsQuoted', {}).get('unique', []))
        symtot += b.get('symbolsQuoted', {}).get('total', 0)
        hl += b.get('headlines', {}).get('count', 0)
    t['symbolsUnique'] = len(syms)
    t['symbolsQuotedTotal'] = symtot
    t['headlines'] = hl
    return t


def show(a):
    p = counters_path(a.file)
    try:
        data = json.load(open(p))
    except FileNotFoundError:
        data = empty_file()
    date = a.date or today()
    day = data.get(date, {})
    if a.json:
        out = {'date': date, 'desk': total_of(day), 'bots': {k: v for k, v in day.items() if not a.bot or k == a.bot}}
        for v in out['bots'].values():
            v.get('headlines', {}).pop('seen', None)
            v.pop('keys', None)
        print(json.dumps(out, indent=1, ensure_ascii=False))
        return
    cols = [('runs', 'runs'), ('quotesCalls', 'quotes'), ('symbols', 'syms'), ('barCalls', 'barCalls'), ('bars', 'bars'),
            ('optionCalls', 'optCalls'), ('optionContracts', 'contracts'), ('webSearches', 'search'), ('pagesFetched', 'pages'),
            ('headlines', 'heads'), ('xSearches', 'xSrch'), ('xPosts', 'xPosts'), ('ideasGenerated', 'ideas'),
            ('ideasLogged', 'logged'), ('ideasRejected', 'rej'), ('ordersSent', 'orders'), ('fills', 'fills'),
            ('backtestVariants', 'variants'), ('simulatedTrades', 'simTrades')]
    print(f'Desk throughput {date} ({p})')
    print(f"{'bot':<8} " + ' '.join(f'{h:>9}' for _, h in cols) + '  lastRun')

    def row(name, b, uniq):
        vals = []
        for k, _ in cols:
            if k == 'symbols':
                vals.append(uniq)
            elif k == 'headlines':
                vals.append(b['headlines']['count'] if isinstance(b.get('headlines'), dict) else b.get('headlines', 0))
            else:
                vals.append(b.get(k, 0))
        lr = b.get('lastRun') or '-'
        print(f'{name:<8} ' + ' '.join(f'{v:>9,}' for v in vals) + f'  {lr}')
    for bid in BOTS:
        if a.bot and bid != a.bot:
            continue
        b = ensure_bot(dict(day), bid) if bid not in day else day[bid]
        row(bid, b, len(b['symbolsQuoted']['unique']))
    if not a.bot:
        t = total_of(day)
        t['headlines'] = {'count': t['headlines']}
        row('DESK', t, t['symbolsUnique'])
        if not day:
            print('(no counts yet for this date)')
    for au in data.get('_audits', []) if not a.bot else []:
        ap = au.get('approx', [])
        print(f"\n{au.get('label')}: " + ', '.join(f"{k} {'~' if k in ap else ''}{v:,}" for k, v in au.get('totals', {}).items()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bot', choices=BOTS)
    ap.add_argument('--date', help='YYYY-MM-DD (default today ET)')
    ap.add_argument('--file', help='counters.json path (default: next to this script, or $DESK_COUNTERS)')
    ap.add_argument('--quotes', type=int, default=0, help='Questrade get_quotes calls (quotesCalls)')
    ap.add_argument('--symbols', default='', help='comma list of symbols quoted (symbolsQuoted)')
    ap.add_argument('--bar-calls', type=int, default=0, help='get_historical_data calls (barCalls)')
    ap.add_argument('--bars', type=int, default=0, help='candles received (bars)')
    ap.add_argument('--option-calls', type=int, default=0, help='option chain / option quote calls (optionCalls)')
    ap.add_argument('--contracts', type=int, default=0, help='option contracts received (optionContracts)')
    ap.add_argument('--web-searches', type=int, default=0)
    ap.add_argument('--pages', type=int, default=0, help='pages fetched (pagesFetched)')
    ap.add_argument('--headline', action='append', default=[], help='"Title|url[|ISO time]" (repeatable)')
    ap.add_argument('--x-searches', type=int, default=0)
    ap.add_argument('--x-posts', type=int, default=0, help='X posts read (xPosts)')
    ap.add_argument('--ideas', type=int, default=0, help='ideas generated (ideasGenerated)')
    ap.add_argument('--logged', type=int, default=0, help='ideas logged (log_idea.py add counts this itself)')
    ap.add_argument('--rejected', type=int, default=0, help='ideas rejected (risk_check.py BLOCK counts this itself)')
    ap.add_argument('--orders', type=int, default=0, help='orders sent (set_activity.py --approved counts this itself)')
    ap.add_argument('--fills', type=int, default=0)
    ap.add_argument('--variants', type=int, default=0, help='backtest variants (backtestVariants)')
    ap.add_argument('--sim-trades', type=int, default=0, help='simulated trades (simulatedTrades)')
    ap.add_argument('--key', help='idempotency key: the same key is counted once per bot per day')
    ap.add_argument('--run', action='store_true', help='count one run now (runs++, lastRun)')
    ap.add_argument('--run-start', action='store_true')
    ap.add_argument('--run-end', action='store_true')
    ap.add_argument('--routine', default='manual', help='routine name for --run-start/--run-end')
    ap.add_argument('--show', action='store_true')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    if a.show:
        return show(a)
    if not a.bot:
        ap.error('--bot is required (or use --show)')
    inc = {'quotesCalls': a.quotes, 'barCalls': a.bar_calls, 'bars': a.bars, 'optionCalls': a.option_calls,
           'optionContracts': a.contracts, 'webSearches': a.web_searches, 'pagesFetched': a.pages,
           'xSearches': a.x_searches, 'xPosts': a.x_posts, 'ideasGenerated': a.ideas, 'ideasLogged': a.logged,
           'ideasRejected': a.rejected, 'ordersSent': a.orders, 'fills': a.fills, 'backtestVariants': a.variants,
           'simulatedTrades': a.sim_trades}
    for k, v in inc.items():
        if v < 0:
            ap.error(f'{k} must be >= 0')
    inc = {k: v for k, v in inc.items() if v}
    syms = [s for s in a.symbols.split(',') if s.strip()]
    try:
        heads = [parse_headline(h) for h in a.headline]
    except ValueError as e:
        ap.error(str(e))
    date = a.date or today()
    nowiso = now_et().isoformat(timespec='seconds')
    with locked(a.file) as (data, st):
        day = data.setdefault(date, {})
        b = ensure_bot(day, a.bot)
        applied = apply(b, inc, syms, heads, a.key) if (inc or syms or heads or a.key) else True
        if a.run_start:
            rp = runstate_path(a.file, a.bot, a.routine)
            json.dump({'bot': a.bot, 'routine': a.routine, 'start': nowiso, 'date': date, 'snap': snapshot(b)}, open(rp, 'w'))
        line = None
        if a.run_end:
            rp = runstate_path(a.file, a.bot, a.routine)
            try:
                rs = json.load(open(rp))
            except FileNotFoundError:
                rs = None
            cur = snapshot(b)
            if rs:
                base = rs['snap']
                if rs.get('date') != date and rs.get('date') in data:   # run crossed midnight
                    prev = snapshot(ensure_bot(data[rs['date']], a.bot))
                    delta = {k: cur[k] + prev.get(k, 0) - base.get(k, 0) for k in cur}
                else:
                    delta = {k: cur[k] - base.get(k, 0) for k in cur}
                os.remove(rp)
            else:
                delta = None
            line = {'bot': a.bot, 'routine': a.routine, 'start': rs['start'] if rs else None, 'end': nowiso,
                    'date': date, 'counts': {k: v for k, v in (delta or {}).items() if v} if delta is not None else None}
            if delta is None:
                line['note'] = 'no --run-start found; delta unknown'
        if (a.run or a.run_end) and applied:
            b['runs'] += 1
            b['lastRun'] = nowiso
        st['write'] = applied or a.run_start or a.run_end or a.run
        if line:
            with open(runs_log_path(a.file), 'a') as f:
                f.write(json.dumps(line, ensure_ascii=False) + '\n')
    parts = [f'{k}+{v}' for k, v in inc.items()] + ([f'symbols+{len(syms)}'] if syms else []) + ([f'headlines+{len(heads)}'] if heads else [])
    if a.run or a.run_end:
        parts.append('runs+1')
    msg = f"counted {a.bot} {date}: " + ', '.join(parts) if parts else None
    if not applied:
        msg = f'already counted (key {a.key}) - skipped'
    if msg:
        print(msg)
    if a.run_start:
        print(f'run start {a.bot} / {a.routine} at {nowiso}')
    if line:
        print('runs.jsonl +', json.dumps(line))


if __name__ == '__main__':
    main()
