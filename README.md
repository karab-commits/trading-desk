# K's AI Trading Desk · Bullpen

Live at https://karab-commits.github.io/trading-desk/ (GitHub Pages, `main`). `index.html` is self-contained (data is inlined as a fallback); when hosted it reads `data.json` every 30 s.
Nothing on the floor is simulated. Every desk CRT, packet, and bell ring comes from `data.json` (bots' `activity`, `lastApprovedIdea`). The animated mini-charts on the desk monitors are decoration only.

## New data.json fields
| key | type | notes |
|---|---|---|
| `sources[]` | `{type, name, feeds[]}` | one entry per real source the desk watches. `type` groups watcher clusters in the "under the desk" swarm; `feeds` lists bot ids the stream flows into. **"Watching N sources" = `sources.length`.** Decorative particles are not counted |
| `desk` | `{strategiesTested, variantsTested, tradesJournaled, sourcesWatched, daysRunning}` | progress stats. `sourcesWatched` is recomputed from `sources.length` when `sources` exists |
| `playbook[].status` | `testing` / `active` / `retired` | each `active` strategy adds a trophy to the wall (level 3+) |

## Desk level rules
XP = strategiesTested×10 + variantsTested×3 + tradesJournaled×2 + sourcesWatched×2 + daysRunning

| Level | XP needed | Unlocks |
|---|---|---|
| 1 | 0 | 8-desk bullpen, source swarm, Kiwi's bell |
| 2 | 60 | Big LED ticker board on the wall |
| 3 | 150 | Trophy wall (one trophy per active strategy) + extra watcher pods |
| 4 | 300 | Junior desks row |
| 5 | 500 | Kiwi corner office |

Current data: 9 strategies, 72 variants (strategy × ticker runs in `/workspace/quant/playbook.json`), 0 journaled, 7 sources, 1 day → 90+216+0+14+1 = 321 XP → Level 4 (179 XP to level 5). The junior desks row adds 50 px of floor.
Edit `data.json` and the office grows on the next refresh.

## Bot network (who talks to whom)
News Desk → Scanner → Risk Manager → Kiwi · Whale Tracker → Options Desk → Kiwi · Trade Journal → Quant Lab → Kiwi · Kiwi → Risk Manager.
Packets only travel along these lines from a bot whose `activity.state` is `working`. Each packet is labelled with a short form of that bot's `activity.now`. Source streams from the under-desk swarm only flow into bots that are `working` or `waiting`.
The bell rings (and Kiwi says "Ding! …") only when `lastApprovedIdea` changes between two data.json loads. It never rings on first load and never at random.

## Live activity (desk CRTs)
Each bot has `activity` in data.json:

| key | notes |
|---|---|
| `now` | ≤ 28 chars. Shown in green monospace on the bot's desk CRT, typed out whenever it changes |
| `state` | `working` (pulsing green light, typing, cursor blinks) · `waiting` (amber) · `idle` (grey; leans back and sips coffee) · `done` (blue) |
| `since` | ISO time. The CRT shows `updated Xm ago`. During market hours (Mon–Fri 9:30–4:00 ET), if it is older than 90 min the text dims and adds `stale` |
| `next` | optional. Shown as `Next: …` when idle, waiting, or done |
| `detail` | shown when you tap the card (along with state, since, and next) |
| `log` | optional, last 3 entries, shown in the tap card |

Each CRT card also shows the bot's P&L line. Only phone desks that are `working` have the phone at the ear; nobody walks around delivering tickets, and there are no canned speech bubbles.

Update with `set_activity.py`. It sets `since` to now and also copies `--detail` into the bot's `status`:
```
python3 set_activity.py --bot scanner --state working --now "Pre-market scan" --next "QQC check 10:05"
python3 set_activity.py --bot quant --state done --now "Found: XIU big-gap fade" --detail "..." --log "Tested 9 strategies"
python3 set_activity.py --bot news --next ""                      # clear next
python3 set_activity.py --approved "QQC.TO gap-and-go"            # ring the bell once
```

## P&L (per bot + desk) — real data only

Every value comes from real Questrade executions and positions. Nothing is simulated. Right now everything is seeded at 0 and shows as `$0.00 · 0 trades`.

**data.json fields**
- Per bot: `pnlToday`, `tradesToday`, `pnlWeek`, `tradesWeek`, `pnlAllTime`, `tradesAllTime` (CAD, integer trade counts). Risk Manager also has `rejectedToday` / `rejectedWeek` / `rejectedAllTime`.
- Desk: `pnlToday`, `pnlWeek`, `pnlAllTime`, each `{realized, unrealized, total, trades}`. `total` = realized + unrealized.

**Where it shows up**
- On each bot's desk CRT card: a P&L line (green if positive, red if negative, cream if $0.00).
- Kiwi's left monitor: a "DESK P&L" screen showing today's desk total and the trade count.
- Header: a "P&L today" chip under the clock. Account card: "P&L today" plus realized / unrealized.
- **P&L board** on the bullpen wall: an old-school sales board in navy and gold with split-flap rows. The desk total (Kiwi) is on top, then the other 7 bots ranked best first (ties keep desk order). It rotates TODAY → WEEK → ALL TIME every 7 s; tap the board to switch. A row flips when its value changes or the period switches.

**Attribution rule**
- A trade's P&L counts for the bot(s) whose idea it was. That means Scanner for its setups, Options Desk for options trades, and Whale Tracker when its flow signal triggered the trade. If an idea is shared, split the amount between those bots yourself.
- Kiwi always shows the whole desk total.
- Risk Manager shows `losses avoided: N rejected` (N = rejected ideas) unless it has P&L or trades of its own.
- Quant Lab and Trade Journal show the desk total (labelled `desk` / `(desk)`), because they rank or record every strategy.
- News Desk only gets P&L when a trade was its idea.

**Updating**: `set_pnl.py` (there was no `set_activity.py` to extend, so this is a new script). It only edits data.json and never contacts Questrade.
```
python3 set_pnl.py --desk --realized 11.50 --unrealized -2.10 --trades 1
python3 set_pnl.py --bot scanner --pnl 11.50 --trades 1
python3 set_pnl.py --bot whale --pnl 5.75 --trades 1 --bot options --pnl 5.75 --trades 1
python3 set_pnl.py --rejected 2                 # Risk Manager, today
python3 set_pnl.py --period week --desk --realized 40 --desk-trades 3
python3 set_pnl.py --reset today                # start of a new day
```

## Paper-tracking every alert (journal.json + log_idea.py)

Every idea the desk sends K is logged **before** the alert goes out, taken or not, then scored later as if it had been traded exactly at the alert's plan. Nothing in `journal.json` is invented: ideas come from real alerts, exits from real prices, real P&L from Questrade.

`journal.json` = `{"version": 1, "ideas": [...]}`. Each idea:

| key | notes |
|---|---|
| `id` | `YYYY-MM-DD-ROOT-n`, e.g. `2026-11-03-XIU-1` |
| `date`, `session` | alert date (ET) and `premarket` / `midday` / `adhoc` |
| `ticker`, `side`, `entry`, `stop`, `target`, `shares` | the plan in the alert |
| `strategy`, `bot` | playbook strategy name and the bot id whose idea it was (scorecard groups by both) |
| `currency` | `CAD` / `USD`. Default: CAD for `.TO .V .CN .NE` tickers, else USD |
| `plan` | `riskGross`, `rewardGross`, `rr`, `feesAtTarget`, `feesAtStop`, `netProfitAtTarget`, `netLossAtStop`, `rrNet` (+ `…CAD`) |
| `result` | `null` while open; then `outcome` (`target`/`stop`/`time`/`no-fill`), `exit`, `gross`, `fees`, `net`, `grossR`, `netR`, `netCAD` |
| `taken`, `realPnl`, `realPnlCAD`, `realR` | whether K took it and the real P&L (net of fees, idea currency) |

```
# log an idea (prints the id and the after-fee numbers to quote in the alert)
python3 log_idea.py add --date 2026-11-03 --session premarket --ticker XIU.TO --side short \
    --entry 54.31 --stop 54.84 --target 53.78 --shares 150 --strategy "Big-gap fade XIU" --bot scanner [--currency CAD] [--note "..."]
# score it at the plan (time = closed at the close / time stop at PRICE)
python3 log_idea.py resolve --id 2026-11-03-XIU-1 --outcome target|stop|time|no-fill --exit 53.78 [--taken yes|no] [--real-pnl 75.10]
# unresolved ideas
python3 log_idea.py list --date 2026-11-03 --open
```
`add` output ends with an `alert line:` like `Profit after fees +$79.50 CAD at target, loss after fees -$79.50 CAD at stop` for the alert (rule: **profit is shown after fees in every alert**).
R = P&L ÷ planned gross risk (|entry − stop| × shares). `no-fill` ideas are counted but not scored.
After every add/resolve, `data.json.paper` is refreshed: `{currency, basis, updated, ideasLogged, byDate: {"YYYY-MM-DD": {net, ideas, resolved, open, filled, wins, real, taken}}}` (CAD, net of fees, resolved ideas only). The site works out today / this ISO week / all time from `byDate` in ET, so it never goes stale overnight.
All scripts take `--dir PATH` (or `DESK_DIR=PATH`) to work on a copy, e.g. for tests.

## Weekly scorecard (scorecard.py) — Fridays

```
python3 scorecard.py                  # current ISO week (ET) + all time
python3 scorecard.py --week 2026-W45  # a given week
python3 scorecard.py --all            # print all-time (data.json still gets week + all time)
```
Writes `data.json.scorecard = {updated, currency: "CAD", basis, week: {label, from, to, title, ideas, open, paper, real}, allTime: {ideas, open, paper, real}}` and prints a short summary.
Each book (`paper` = every filled idea at its plan; `real` = ideas with `taken: yes` and a `realPnl`) has `trades, wins, losses, winRate, avgWin, avgLoss, expectancyR, netPnl, bestStrategy, worstStrategy, byStrategy[], byBot[]` (all CAD, after fees; win = net > 0). `byBot` answers "which bot's ideas actually paid".

## Fees (data.json `fees`)

Checked 2026-11-02 on Questrade's own pages: [Transaction fees](https://www.questrade.com/pricing/self-directed-commissions-plans-fees/transaction), [Pricing](https://www.questrade.com/pricing-fees), [$0 commissions FAQ](https://www.questrade.com/learning/using-questrade/0-commissions-faq).

| item | Questrade (self-directed, online) | used in scripts |
|---|---|---|
| Stock / ETF commission, buy and sell (Canadian + US listed) | **Free** ($0 since Feb 10 2025) | `stocksEtfs.commissionPerOrder: 0` |
| ECN fees | None on Canadian orders. None on US orders unless **direct-routed** (remove liquidity: NASDAQ $0.003/sh; ARCA, NYSE, BATS, EDGX $0.004/sh; IEX $0.0012/sh; add liquidity: EDGA $0.004/sh), US OTC ($0.000005/sh), or overnight session 8pm-2am ET ($0.003/sh) | `0` (desk uses smart routing) |
| SEC fee | US-listed sales only: 0.0000206 × sale value ($20.60 per $1M, SEC FY2026 rate from Apr 4 2026, [SEC advisory](https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2)) | `secFee.rate` on the selling leg (exit for longs, entry for shorts) |
| Currency conversion USD/CAD | **1.5%** | `fx.spreadPct: 1.5`, `fx.mode: "pnl"` |
| Options (not used yet) | US equity options $0; CAD options $0.99/contract; US index $0.99/contract | — |

`fx.mode`: `pnl` (default) assumes a same-day USD trade in the margin account settles in USD (no forced conversion) and only the P&L is converted back, costing 1.5% of |P&L|; `round_trip` charges 1.5% on entry + exit notional (CAD converted to buy and back after selling); `none` keeps USD.
USD amounts are shown in CAD at `fees.usdcad.rate` (Bank of Canada daily average; 1.3960 on 2026-10-30). Update `rate`/`asOf` when it moves.
Not included: short borrow fees (charged on overnight shorts; the desk is flat by the close), margin interest, FINRA TAF (not on Questrade's schedule).

## Rules added Nov 2 2026 (approved by K)
- **One trade a day max**: routines must not send a second trade alert once one is taken that day. Shown in Desk rules and as `Trades today N / 1` in the Account card (`account.maxTradesPerDay`, default 1; count = `pnlToday.trades`).
- **Profit shown after fees**: every alert quotes `log_idea.py add`'s net numbers. If `todayTrade` has `projectedNet` / `maxLossNet`, the Today's trade card shows those as "Profit / Loss after fees".

## Site additions (v3)
- Wall P&L board desk row shows **REAL** (Questrade) and **PAPER** (all logged ideas, net of fees) side by side for the board's period (TODAY / WEEK / ALL TIME). Empty paper state: `--  no ideas`.
- Account card: `Trades today N / 1` and `Paper ideas today`.
- **Weekly scorecard** card under Account (from `data.json.scorecard`): paper vs real table, whose ideas paid, all-time line. Empty state: "First scorecard Friday".
- Desk rules card lists the two new rules plus a fee footnote linking the Questrade schedule.

## Today's watchlist (data.json `watchlist` + set_watch.py)

The stocks the desk is interested in today, shown on a **Today's watchlist** board right below the office (above Account), one row per stock: split-flap ticker, LONG/SHORT badge, status light, last price + `as of H:MM ET`, a stop–entry–target ladder with the current price marker, entry/stop/target, profit/loss **after fees**, shares · R:R, strategy with a `tested`/`untested` tag, the bot that found it, the reason, the journal id, open P&L when in trade, and `close by 4:00 PM ET` (flat by the close). Empty state: "No stocks on the watchlist yet today".
The page re-fetches `data.json?t=<now>` (no-store) every 30 s, so open tabs update without reload; the board header shows `desk prices updated H:MM ET`, and during market hours a price older than 20 min is marked **STALE**.

**Live price (TradingView widget).** Each row with a ticker embeds TradingView's free **Single Ticker** web component (`<tv-single-ticker symbol="TSX:QQC" theme="dark" transparent>`, loaded once from `https://widgets.tradingview-widget.com/w/en/tv-single-ticker.js`), labelled `Live price: TradingView`. It streams price and day change by itself in the browser (Questrade can't be called from the page: private auth).
- **It is delayed, not real-time.** TradingView's widget docs ([markets: North America](https://www.tradingview.com/widget-docs/markets/north-america/), [data FAQ](https://www.tradingview.com/widget-docs/faq/data/), checked 2026-11-02) list TSX/TSXV as *Delayed* (~15 min) and NASDAQ/NYSE/Arca (Cboe One) as *Delayed* too; only forex and crypto are real-time, and a paid TradingView plan does not change widget data. The widget shows a `D` next to delayed symbols, so during the session the Questrade desk price can be newer than the widget.
- The widget is a closed shadow-DOM component and exposes no price to the page's JS, so the **ladder marker, status light, trigger distance and triggers stay on the Questrade price** in data.json, shown as `Desk price (Questrade) as of H:MM ET · used for triggers`.
- The board is a persistent `<section id="watchlist">`: rows (and widgets) are only rebuilt when the set of tickers changes; the 30 s refresh only updates the Questrade numbers, so widgets don't reload.
- Symbol mapping: item `tvSymbol` wins; otherwise `.TO` → `TSX:`, `.V` → `TSXV:`, `.NE` → `NEO:`, `.CN` → `CSE:` (e.g. `QQC.TO` → `TSX:QQC`, `XIU.TO` → `TSX:XIU`); US tickers use a small built-in map (`RIVN` → `NASDAQ:RIVN`, `SPY` → `AMEX:SPY`, `CNQ` → `NYSE:CNQ`, …) or the bare ticker. Set `tvSymbol` explicitly for any new US ticker: `python3 set_watch.py add --ticker SOFI --tv-symbol NASDAQ:SOFI`. `set_watch.py add` fills `tvSymbol` automatically for Canadian suffixes.
- Mockup: `/workspace/desk-mockups/watchlist-live.png` (430 px wide, 2x).

`watchlist` is an array; each item has its own `date` (ET) and the site only shows items dated today, so yesterday's list never shows as today's. Item keys: `date, ticker, side, status, entry, entryNote, trigger, zoneLow, zoneHigh, notBefore, stop, target, shares, currency, netProfitAtTarget, netLossAtStop (+CAD), rr, rrNet, strategy, tested, testNote, bot, reason, journalId, last, priceTime, fill, openPnl, openPnlCAD, closeBy ("16:00"), statusAt, tvSymbol` (`tvSymbol` = TradingView `EXCHANGE:SYMBOL` for the live widget). Any of entry/stop/target/shares/side can be missing (shown as `-`; no ladder).
Status: `watching | triggered | in trade | target hit | stopped | closed | skipped | expired`.

```
python3 set_watch.py add --ticker RIVN --side short --entry 12.79 --stop 13.12 --target 12.18 --shares 27 --strategy "Gap fade" --bot scanner [--journal-id ID] [--reason "..."]
python3 set_watch.py add --journal-id 2026-11-02-QQC-1 --trigger 47.67 --zone-high 48.10 --not-before 10:05 --tested no --test-note "backtest found no edge"
python3 set_watch.py price --ticker RIVN --last 12.91 [--time 2026-11-02T09:45:04-05:00]
python3 set_watch.py status --ticker RIVN --status "in trade" [--fill 12.78]
python3 set_watch.py list
python3 set_watch.py reset                 # new day: drop every item not dated today (--all drops today too)
```
- `--journal-id` pulls side, entry, stop, target, shares, strategy, bot, currency and the after-fee plan from journal.json (log the idea with `log_idea.py add` first). Without it, after-fee numbers use the same Questrade fee model.
- `add` on a ticker already on today's list updates it. Extra flags: `--trigger` (defaults to entry), `--zone-low/--zone-high`, `--not-before HH:MM`, `--entry-note`, `--tested yes|no` (default no), `--test-note`, `--tv-symbol EXCHANGE:SYMBOL`, `--status`, `--last/--time`.
- `price` moves the status by itself: watching → triggered when the trigger is crossed (long ≥ trigger and ≤ zone high; short ≤ trigger and ≥ zone low; not before `--not-before`); triggered / in trade → target hit or stopped when the target or stop is crossed; watching → expired for a price at/after 16:00 ET. `triggered` is a signal, not a fill; set `in trade` by hand once K's order fills. In trade, `openPnl` = (last − fill) × shares (by side) minus estimated fees. Skipped / closed / target hit / stopped / expired are never changed by a price update.
- Prices come from the Questrade connector (`get_quotes`, read only).
