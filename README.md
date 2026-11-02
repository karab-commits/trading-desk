# Bullpen v2 preview (not live)

`bullpen-v2.html` is self-contained (data is inlined as a fallback); when hosted it reads `data.json` every 60 s.
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
