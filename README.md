# MIB-V2 BTC research framework

Local research system for BTC USDT perpetual setups. The Windows PC runs every historical replay. This repo does not ship a profitable strategy. `exp-s1-structure-v1` is a baseline hypothesis.

Datasets stay separate:

| Role | Default path | Used by |
|---|---|---|
| Historical research | `backend/research_binance.db` | audit, backtest |
| Live / paper candles | `backend/market_data_clean.db` | future paper/live only |

Backtest refuses to open `market_data_clean.db`.

## Place the research database

Copy your Binance SQLite file to:

```text
backend/research_binance.db
```

Override with `RESEARCH_DB_PATH` or `--db`. Do not point research at the live database.

## Setup (Windows)

```bat
cd MIB-V2-BTC-TRADER
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

No third-party packages are required for the first milestone.

## Commands

Audit the Binance file. This does not run a strategy.

```bat
py scripts\audit_research_data.py
```

Run the first experiment. This is the only strategy run in v1.

```bat
py scripts\backtest.py --experiment exp-s1-structure-v1
```

Side splits:

```bat
py scripts\backtest.py --experiment exp-s1-structure-v1 --side LONG
py scripts\backtest.py --experiment exp-s1-structure-v1 --side SHORT
```

Optional window:

```bat
py scripts\backtest.py --experiment exp-s1-structure-v1 --start 2023-01-01 --end 2024-01-01
```

Install check, synthetic bars only, no database:

```bat
py scripts\self_check.py
```

## Results

Each run writes a folder under `results/`. Send that folder, not the database.

- `summary.json`
- `trades.csv`
- `equity_curve.csv`
- `experiment_config.json`
- `daily_stats.csv`
- `setup_stats.csv`
- `long_short_stats.csv`
- `failure_analysis.json`

## Scope of this milestone

Implemented: data audit, causal 1m replay, S1 pullback continuation, fees, slippage, stop-first same-bar rule, result files.

Not implemented yet: S2-S4, swing families, paper, MEXC live, UI. Those wait on the S1 baseline files.

Read `docs/ARCHITECTURE.md` and `docs/FIRST_EXPERIMENT.md`.
