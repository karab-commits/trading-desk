# EOD review 2026-11-02 (Kiwi, head of desk)
All data read-only from Questrade (`get_historical_data`, `get_order_history`, `get_account_activities`, `get_balances`, `get_positions`).
* `raw_*.txt` 5-min RTH bars for RIVN, QQC.TO, XIU.TO, AMD (Nov 2). `*_5m.csv` parsed.
* `paper_resolve.py` scores each alert at its plan: entry at trigger (or bar open if gapped), only stop checked on the entry bar, stop wins if one bar touches both, else 4:00 PM close. Results written with `log_idea.py resolve`.
* `recheck_gapfade.py` re-checks the active playbook (big-gap fade >0.75 ATR, daily) after Questrade fees, through Nov 2; output `recheck_output.txt`, `recheck_results.csv`, `recheck_trades.csv`.
Reproduce: `cd /workspace/quant/eod/2026-11-02 && python3 paper_resolve.py && python3 recheck_gapfade.py`
