# K's AI Trading Desk · Neon City

Live at https://karab-commits.github.io/trading-desk/ (GitHub Pages, `main`). `index.html` is the Neon City view (three.js from unpkg; falls back to a 2D dashboard if WebGL/three.js fails, or force it with `?flat`). It reads `data.json`, `journal.json` and `strategies.json` on load and every 60 s; it has no inlined data, so it must be served over http(s).
The classic pixel bullpen is kept at `bullpen.html` (self-contained, inlined fallback data, reads `data.json` every 30 s).

### Neon City: what drives what (all from data.json / journal.json)
- Vault: `pnlAllTime.total`, `pnlToday`, `account`, `desk.daysRunning`; progress bar = daily loss budget used = max(0, −`pnlToday.total`) / `account.dailyLossStop` (150 CAD; turns red at the stop); subtitle adds trades today (`pnlToday.trades`) and open positions `account.openPositions` / `account.maxOpenPositions` (4). Green/red days and the daily bar chart use `paper.byDate[date].real` (chart shows an empty state under 5 days).
- Towers: one per `bots[]`; banner = category · the bot's strategy `short` name from `strategies.json`; height = number of `journal.json` ideas with that `bot`; beam brightness = `activity.state`. Kiwi's centre panel shows the desk total.
- Pulses fire only for new journal events (idea `loggedAt`, `result.resolvedAt`) seen on refresh, or via "Replay today's events".
- Money board: `pnlToday/pnlWeek/pnlAllTime` plus per-bot `pnlToday/Week/AllTime`, `tradesToday/Week/AllTime`. Paper results are always labelled not-real.
- Watchlist: today's `watchlist[]` items with TradingView `tv-single-ticker` widgets (`tvSymbol` wins) and a ticker tape.
- Approvals waiting on K: optional `approvals[]` = `{from, date, title, status}` (status `pending` or absent = shown). The field now exists: the three Nov 2 items are kept with `status: resolved/superseded` plus a `resolution`, so the panel shows **None pending**. `STATIC_PENDING_APPROVALS` (used only if the field is missing) is now empty.

## Classic bullpen (bullpen.html)
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

## Multi-strategy desk (K's choice, Nov 2 2026) + strategies.json
**Rules card (data.json `rules`)**: Kiwi leads: orders are sent without waiting for K's go; K approves each one in Questrade. Every bot trades its strategy on every valid signal. $40 max risk per trade, $150 daily loss stop, max 4 open positions, flat by close. (`account.maxRiskPerTrade: 40`, `account.dailyLossStop: 150`, `account.maxOpenPositions: 4`; `account.maxTradesPerDay` removed.)

`strategies.json` is read by the signal routine (every 15 min, 9:45 AM - 3:15 PM ET) on every run, and by index.html (tower banners + desk panel). Schema: `{version, updated, readBy, execution, risk{maxLossPerTradeCAD, dailyLossStopCAD, maxOpenPositions, sameDayOnly, flatByClose, noNewEntriesAfterET, flattenByET, sizing, dailyStopCheck, stopOrders, botBudgetsCAD, pauseRules, correlation{groups, threshold, lookbackDays}}, regime, promotionRule, strategies[]}`. A bot can own more than one strategy (Quant Lab: ORB + VWAP, then Stocks-in-play ORB); the tower banner shows the first, the desk panel lists all; each strategy = `{bot (data.json bot id), id?, scout?, name, short (banner label), tested, testedTag, stats|null (stats.outOfSample = walk-forward), citation?, devils_advocate?, untestedWhy?, universe[], entry, stop, target, timeStop, window{start,end,tz}, maxTradesPerDay, notes?}` (Quant Lab's entry/stop/target/window are split into `orb` and `vwap`; Risk Manager has `limits[]`).

| bot | strategy | status (Nov 2 promotion rule) | in-sample (after fees/slip) | walk-forward out-of-sample | max/day |
|---|---|---|---|---|---|
| scanner | Big-gap fade 0.75×ATR14 (XIU, SOFI, HXT) | all **testing** (XIU was active; 0–1 of 20 journal trades) | XIU +0.188R n=50; SOFI +0.175R n=33; HXT +0.115R n=49 | XIU +0.037R n=38 (3/5 windows +); SOFI +0.365R n=11 (4/5); HXT +0.055R n=39 (3/5). Live params in the same windows: +0.169 / +0.402 / +0.149R | 2 |
| quant | ORB 15-min (live) + VWAP reclaim/loss (**paper-only, retired Nov 2 — decided by Kiwi**) | ORB testing; VWAP `mode: paper` | ORB t2R +0.101R n=47; VWAP +0.063R n=57 (30-min proxy) | ORB +0.121R n=51 (3/4 windows +); VWAP −0.148R n=46 (1/4) | 2 |
| quant | **Stocks-in-play 15-min ORB** (new; scout = Whale Tracker; Zarattini, Barbon & Aziz 2024, SSRN 4729284); stop = other side of the 15-min range, target 2R (10%-ATR stop removed Nov 2, decided by Kiwi) | testing | quick 5-min test, 12 hand-picked trades: +0.54R (indicative only; the old 10%-ATR stop did −0.62R) | — | 2 |
| whale | SIP scout + **QQQ-only** RVOL breakout (all other tickers **retired**) | retired; QQQ testing | −0.280R n=97 overall; QQQ +0.179R n=17 | — | 2 |
| news | News-catalyst momentum, pullback hold + devil's-advocate veto | untested (no headline history) | — | — | 2 |
| options | Debit spreads, max loss $40, ≥1 DTE, legs <10% wide | untested (no chain history) | — | — | 2 |
| risk / journal / kiwi | enforcer / logging / approves only | n/a | — | — | 0 |

New-rule backtests: `/workspace/quant/multistrat-2026-11-02/backtest_new_rules.py` → `results_new_rules.csv/.txt`, `trades_new_rules.csv` (Questrade 30-min RTH bars, May 4 - Oct 30 2026, XIU.TO ZEB.TO QQC.TO QQQ). They are 30-min proxies of 15/5-min rules, not exact tests.

## Rules added Nov 2 2026 (approved by K; partly replaced above)
- ~~One trade a day max~~ and ~~nothing sent without K's go~~: **replaced Nov 2 2026 by the multi-strategy rules below.**
- **Profit shown after fees**: every alert quotes `log_idea.py add`'s net numbers. If `todayTrade` has `projectedNet` / `maxLossNet`, the Today's trade card shows those as "Profit / Loss after fees".

## Site additions (v3)
- Wall P&L board desk row shows **REAL** (Questrade) and **PAPER** (all logged ideas, net of fees) side by side for the board's period (TODAY / WEEK / ALL TIME). Empty paper state: `--  no ideas`.
- Account card: `Daily loss used $X / $150 · N trades today` (was `Trades today N / 1`) and `Paper ideas today`.
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

## Risk, mood, debate and walk-forward upgrades (K approved, Nov 2 2026)
Every routine run (9:45 AM–3:15 PM ET, every 15 min) uses these scripts. None of them contacts Questrade or places orders; the run fetches bars/quotes through the read-only Questrade connector and passes files or values in.

### `risk_check.py`: per-bot budgets, auto-pauses, one bet per group (run before EVERY order)
```
python3 risk_check.py --update                                    # first thing each run: refresh pauses + budget bars
python3 risk_check.py --bot scanner --ticker XIU.TO --side short --risk 38.50 [--open SPY:long:35:quant ...]
python3 risk_check.py --bot news --ticker SOFI --side long --risk 20 --idea 2026-11-03-SOFI-1
python3 risk_check.py --bot quant --strategy sip_orb --ticker AMD --side long --risk 30 --idea 2026-11-03-AMD-1
python3 risk_check.py --status          # print only
python3 risk_check.py --unpause whale   # K lifts a pause by hand
```
Prints `ALLOW …` (exit 0) or `BLOCK …` (exit 2) with one line per reason. Checks: $40/trade; desk realized loss + open risk + this risk ≤ $150; < 4 open/pending positions; no entries after 15:15 ET; the bot is not paused; the bot's own budget (`strategies.json risk.botBudgetsCAD`: Scanner 50, Quant Lab 35, News Desk 25, Whale Tracker 20, Options Desk 20 = 150) — when the trade is too big it prints `RESIZE to risk <= X CAD` so the run can resize and re-check; same ticker already open; **one bet per correlation group and direction** (`risk.correlation.groups`: tsx_index, us_index, cdn_banks, energy, us_megacap_tech, semis, ev_auto, gold_miners, fintech_brokers; root-symbol match, so CNQ = CNQ.TO); **20-day daily-return correlation > 0.8** with an open same-direction position when both tickers are in `bars/` (else groups only); and for strategies with `devils_advocate.required` a debate with verdict `take`.
- Real trades come from journal.json ideas with `taken: "yes"` (`log_idea.py resolve --taken yes --real-pnl X`), so no separate `--record-result` is needed. Open/pending = taken ideas with no result + today's watchlist items `triggered`/`in trade` + every `--open TICKER:side[:riskCAD[:bot]]` (pass each Questrade position / working entry; unknown risk counts as 40 CAD).
- **Auto-pauses** (freqtrade-style protections), written to data.json `paused[]` = `{bot, rule, reason, since, until, setBy, setAt}`: `dailyBudget` (realized loss today ≥ budget → until next trading day), `stopoutGuard` (≥ 3 stop-outs in the bot's last 5 trading days → 2 trading days), `drawdownGuard` (last 20 real trades sum ≤ −4R → 5 trading days). Expired pauses move to `pausedHistory[]`; trades before an expired pause no longer count for that rule. Trading days = weekdays (exchange holidays are not skipped).
- data.json `riskBudgets` = `{date, updated, bots{id:{budget, realizedLoss, openRisk, used, left}}, desk{…, openPositions}}` drives the site's budget bars.

### `regime.py` + `regime.json`: market-mood tag (tag only, no filter)
```
# once a day before 9:45 ET: Questrade get_historical_data SPY (05902721-1882-4522-0364-ad9650530625), 1d, from 7 days ago to tomorrow, write_to_file
python3 regime.py --ingest /workspace/agent-tools/<file>.txt
python3 regime.py                # recompute from the cache only
python3 regime.py --backfill     # tag old journal ideas
```
`regime.json` = `{date, spy_rv10, median, regime: calm|volatile, asOfClose, bars, stale, units, method, note, updated}`: SPY 10-day realized vol (annualized %) through the prior close vs its trailing 250-session median. `log_idea.py add` writes `regime` (+ `regimeDetail {spy_rv10, median, asOfClose, stale}`) on every new idea. Revisit as a filter after ~100 more trades (gap fade so far: calm +0.06R / volatile +0.24R on 116 trades).

### `bars.py` + `bars/`: Questrade bar cache
`python3 bars.py ingest FILE…` merges `get_historical_data` outputs into `bars/<SYMBOL>_<granularity>.csv`; `bars.py list` shows coverage. regime.py reads `bars/SPY_1d.csv`; risk_check.py's correlation check reads `bars/<ticker>_1d.csv`. Ingest a 1d bar for any ticker you hold so the correlation stays current.

### `debate.py`: devil's-advocate veto (News Desk; Stocks-in-play ORB while untested)
```
python3 debate.py --id <idea id> --bull "…" --bear "…" --bear "…" --bear "…" --verdict skip
python3 debate.py --id <idea id> --bull "…" --bear "…" --bear "…" --bear "…" --verdict take --why "why the bull case clearly wins"
python3 debate.py --show --bot news
```
Needs ≥ 3 bear reasons and ≥ 1 bull reason; `take` needs `--why`. Writes `idea.debate = {bull[], bear[], verdict, why, by, at, regime, rule:"veto only"}` in journal.json. Prints `VETO` (exit 3) or `PASS` (exit 0). risk_check.py blocks a News Desk (or `--strategy sip_orb`) order without a `take` debate.

### Walk-forward (`/workspace/quant/walkforward.py`)
`python3 /workspace/quant/walkforward.py` → `/workspace/quant/walkforward-YYYY-MM-DD/` (`windows.csv`, `neighbours.csv`, `lookahead_audit.csv`, `oos_trades.csv`, `walkforward_results.json`, `output.txt`). Gap fade: 12-month train / 3-month test rolled quarterly (5 test windows, Oct 2025 – Nov 2 2026), grid k × stop. Quant Lab ORB / VWAP: 2-month train / 1-month test rolled monthly on 30-min bars (Jul–Oct 2026). Look-ahead audit recomputes every signal from truncated data: 0 leaks. **Promotion rule** (`strategies.json promotionRule`): active only if OOS mean R > 0 in most test windows AND ≥ 20 paper/real journal trades.

### Site (index.html)
- **Mood badge** on the vault's top-right corner: `MOOD · CALM` (green) / `MOOD · VOLATILE` (orange), tooltip with SPY rv10 vs median; shows the date if regime.json is not today's.
- **Paused bots**: tower dimmed (grey, low beam) with a red `PAUSED` tag, the reason and the until date on its label; same tag on the org chart, flat view, desk panel and budget bar.
- **Loss budgets today** panel (left column): desk $150 bar plus one bar per bot (used = realized loss + open risk), orange at 60%, red at 100%.
- **News Desk · devil's advocate** panel (right column, under the watchlist) and in News Desk's desk panel: latest debate's verdict, bear case, bull case.
- Approvals: the VWAP retirement item is resolved (`decided by Kiwi`), so the panel shows None pending.

### Strategy modes: live vs paper (Nov 2 2026, decided by Kiwi)
`strategies.json` strategies carry `mode` (`live` | `paper` | `mixed`); a mixed entry has `modes{sub: live|paper}` and `aliases{sub: [...]}` (Quant Lab: `modes {orb: live, vwap: paper}`). A **paper** strategy is retired from real money: the routine still logs each signal (`log_idea.py add` matches the `--strategy` text or `--strategy-id` to the aliases, longest match wins, and writes `mode: "paper"`, `taken: "no"`, `paperReason`, printing `PAPER-ONLY … do NOT send a real order`; `--paper` forces it; `resolve --taken yes/--real-pnl` is refused). `risk_check.py` always BLOCKs it with `paper-only: retired`. Bots with more than one strategy must name it: `risk_check.py --bot quant --strategy orb|vwap|sip_orb …` (no or unknown `--strategy` = BLOCK).
