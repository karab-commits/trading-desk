# K's AI Trading Desk (trading floor + dashboard)

A single self-contained `index.html` (inline CSS/JS, no CDNs). The trading floor is smooth vector art drawn on a `<canvas>`
at the device pixel ratio: 8 AI agent bots at their desks, with glowing monitors, a walk-a-note-to-Kiwi animation, speech bubbles,
and tap-for-status cards. All live values come from `data.json`, fetched every 60 s with `?t=<timestamp>` cache-busting.
To update the desk, rewrite `data.json` (keep it valid JSON). No rebuild needed.

## data.json schema
| key | type | notes |
|---|---|---|
| `lastUpdated` | string | header/footer, e.g. `"Mon Nov 2, 2026 7:23 AM ET"` |
| `deskName` | string | header title |
| `tickers[]` | `{symbol, price?, changePct?}` | ticker strip; `price`/`changePct` optional numbers, otherwise only the symbol is shown |
| `bots[]` | `{id, name, role, status, bubbles[]}` | `id` is one of `scanner, news, whale, quant, kiwi, options, journal, risk` (each has a fixed desk). `bubbles` rotate as speech bubbles; `status` shows in the tap card |
| `account` | `{equity, buyingPower, currency, maxRiskPerTrade, maxRiskPct?, openPositions, accountLabel, accountLast4}` | `maxRiskPct` optional (omit to show only the dollar amount); only the last 4 account digits are ever shown |
| `todayTrade` | `{symbol, side, qty, entry, stop, target, maxLoss, projected, status, condition}` | status containing "wait" shows amber; buy-zone band is parsed from the first two prices in `condition` |
| `watching[]` | `{symbol, idea, near, stop, target, note}` | |
| `schedule[]` | `{time:"9:00 AM", label}` | ET; next item highlighted from the viewer's clock converted to ET |
| `backtest` | `{title, shares, sample, basis, rows[{name, winRate, pnl}], note}` | |
| `playbook[]` | `{name, status, trades, winRate, expectancyR, note}` | strategy list. `status` is `testing` (amber), `active` (green) or `retired` (grey); `trades` = sample size; `winRate` in %; `expectancyR` in R per trade |
| `rules[]` | string[] | |
| `deskLog[]` | `{date, text}` | latest desk improvements, **newest first** (put new entries at the top of the array) |

Charts on the floor monitors are decorative animation only; no prices are invented anywhere.

## Hosting
Published via GitHub Pages from this repo (`main`): https://karab-commits.github.io/trading-desk/
Local copy: `/workspace/desk-site` (`./start.sh` there runs a local server on :8787).
