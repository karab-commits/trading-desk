# K's AI Trading Desk (pixel floor + dashboard)

Single self-contained `index.html` (inline CSS/JS, pixel art drawn on a 240x230 `<canvas>`).
All live values come from `data.json`, fetched every 60 s with `?t=<timestamp>` cache-busting.
To update the desk, just rewrite `data.json` (keep it valid JSON). No rebuild needed.

## data.json schema
| key | type | notes |
|---|---|---|
| `lastUpdated` | string | shown in header/footer, e.g. `"Mon Nov 2, 2026 6:55 AM ET"` |
| `deskName` | string | header title |
| `tickers[]` | `{symbol, price?, changePct?}` | ticker strip. `price`/`changePct` are optional numbers; if missing only the symbol is shown |
| `bots[]` | `{id, name, role, status, bubbles[]}` | `id` must be one of `scanner, news, whale, risk, kiwi`. `bubbles` rotate as speech bubbles; `status` shows in the tap card |
| `account` | `{equity, buyingPower, currency, maxRiskPerTrade, maxRiskPct, openPositions, accountLabel, accountLast4}` | only the last 4 digits are ever shown |
| `todayTrade` | `{symbol, side, qty, entry, stop, target, maxLoss, projected, status, condition}` | status containing "wait" shows amber; buy zone band is parsed from the first two prices in `condition` |
| `watching[]` | `{symbol, idea, near, stop, target, note}` | |
| `schedule[]` | `{time:"9:00 AM", label}` | ET; next item highlighted from the viewer's clock converted to ET |
| `backtest` | `{title, shares, sample, basis, rows[{name, winRate, pnl}], note}` | |
| `rules[]` | string[] | |

Charts on the pixel monitors are decorative animation only; no prices are invented anywhere.

## Run / host
`./start.sh` restarts `python3 -m http.server 8787` and a Cloudflare quick tunnel
(`bin/cloudflared`), writes `server.pid`, `tunnel.pid`, `url.txt`, logs to `server.log` / `tunnel.log`, and prints the public URL.
