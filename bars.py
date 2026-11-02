#!/usr/bin/env python3
"""Daily/intraday bar cache for the desk (bars/<SYMBOL>_<granularity>.csv), fed from Questrade get_historical_data.

Python cannot call the Questrade connector itself, so a routine run does:
  1. call user-Questrade get_historical_data (write_to_file=true), e.g. SPY 1d for the last 5 days
  2. python3 bars.py ingest /workspace/agent-tools/<file>.txt [more files...]
Then regime.py and risk_check.py read the cache.

  python3 bars.py ingest FILE [FILE...]     # merge MCP outputs (dedup by bar start)
  python3 bars.py seed                      # copy /workspace/quant/data + eod daily CSVs into the cache (one-off)
  python3 bars.py list                      # symbols, bar counts, first/last date
"""
import csv, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BARS = os.path.join(HERE, 'bars')
COLS = ['start', 'end', 'open', 'high', 'low', 'close', 'volume', 'vwap']


def path(sym, gran='1d'):
    return os.path.join(BARS, f"{sym.upper().replace('.', '_')}_{gran}.csv")


def load(sym, gran='1d'):
    """List of dict bars (floats), sorted by start; [] if not cached. Adds 'date' (YYYY-MM-DD of start)."""
    p = path(sym, gran)
    if not os.path.exists(p):
        return []
    out = []
    with open(p) as f:
        for r in csv.DictReader(f):
            b = {'start': r['start'], 'end': r.get('end', '')}
            for k in ('open', 'high', 'low', 'close', 'volume', 'vwap'):
                try:
                    b[k] = float(r[k]) if r.get(k) not in (None, '') else None
                except ValueError:
                    b[k] = None
            b['date'] = r['start'][:10]
            out.append(b)
    out.sort(key=lambda b: b['start'])
    return out


def merge(sym, gran, candles):
    os.makedirs(BARS, exist_ok=True)
    p = path(sym, gran)
    rows = {}
    if os.path.exists(p):
        with open(p) as f:
            for r in csv.DictReader(f):
                rows[r['start']] = r
    for c in candles:
        rows[c['start']] = {k: c.get(k, '') for k in COLS}
    with open(p, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for k in sorted(rows):
            w.writerow({c: rows[k].get(c, '') for c in COLS})
    return len(rows)


def parse_mcp(text):
    return json.loads(text[text.index('{'):text.rindex('}') + 1])


def cmd_ingest(files):
    if not files:
        sys.exit('usage: bars.py ingest FILE [FILE...]')
    for fp in files:
        d = parse_mcp(open(fp).read())
        sym, gran = d.get('symbol'), d.get('granularity')
        if not sym or not gran or 'candles' not in d:
            print(f'SKIP {fp}: not a get_historical_data result')
            continue
        n = merge(sym, gran, d['candles'])
        last = d['candles'][-1]['start'][:16] if d['candles'] else '-'
        trunc = ' (TRUNCATED: narrow the window)' if d.get('candlesTruncated') else ''
        print(f"OK {sym} {gran}: +{len(d['candles'])} candles, cache now {n}, last {last}{trunc}")


def cmd_seed():
    src = sorted(glob.glob('/workspace/quant/data/*_1d.csv')) + sorted(glob.glob('/workspace/quant/eod/*/*_1d_thru_*.csv'))
    for fp in src:
        base = os.path.basename(fp).split('_1d')[0]
        parts = base.rsplit('_', 1)
        sym = parts[0] + '.' + parts[1] if len(parts) == 2 and parts[1] in ('TO', 'V', 'NE', 'CN') else base
        with open(fp) as f:
            candles = list(csv.DictReader(f))
        n = merge(sym, '1d', candles)
        print(f'seeded {sym} 1d from {fp}: cache {n}')


def cmd_list():
    for fp in sorted(glob.glob(os.path.join(BARS, '*.csv'))):
        with open(fp) as f:
            r = list(csv.DictReader(f))
        print(f"{os.path.basename(fp):<22} {len(r):>5} bars  {r[0]['start'][:10] if r else '-'} .. {r[-1]['start'][:10] if r else '-'}")


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] in ('-h', '--help'):
        print(__doc__)
    elif a[0] == 'ingest':
        cmd_ingest(a[1:])
    elif a[0] == 'seed':
        cmd_seed()
    elif a[0] == 'list':
        cmd_list()
    else:
        sys.exit(__doc__)
