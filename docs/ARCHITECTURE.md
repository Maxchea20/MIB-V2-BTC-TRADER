# Architecture

v1 is a local research runner. It is not a live bot. No strategy is assumed profitable.

## Data sources

- Research replay reads only `backend/research_binance.db`, or `RESEARCH_DB_PATH` / `--db`.
- Live/paper candles will read `backend/market_data_clean.db` later. The backtest process exits if that filename is passed.
- Schema is discovered. If 1m bars are missing, the run stops and names the gap. It does not switch databases.

## Folder layout

```text
config/default.json
config/experiments/exp-s1-structure-v1.json
backend/research_binance.db          # you place this, not committed
scripts/audit_research_data.py
scripts/backtest.py
src/btc_research/data
src/btc_research/features
src/btc_research/structure
src/btc_research/setups
src/btc_research/research
results/
```

Future packages, not in this milestone: regime, scanner, entry variants, risk, paper, mexc, safety, ui. Strategy code will not import an order client.

## Causal rules

- Higher-timeframe bars are built from 1m and emitted only when the bucket is complete.
- A swing is usable only after `right` bars have closed.
- Decision uses the closed 5m bar. Fill is the next 1m open, plus slippage.
- Same-bar stop and target fills the stop.
- Fees are 4 bp per side in the baseline. Slippage is 1 tick plus 0.5 bp, embedded in the fill.
- Funding is not invented. The summary flags `MISSING_NOT_APPLIED` until a funding table exists in the research database.

## Research loop

Grok designs the experiment. The PC runs it. You send `results/<experiment>/<run>/` back. Grok does not receive the candle file.

Promotion path is hypothesis, local backtest, validation, locked test, paper, then live. A no-edge result is a valid result.
