# Backtest results log

Only results recorded in the repo lock files. `results/` and `backend/*.db` are gitignored, so raw trade files and the research database are not here. Add new runs below as they are made.

All runs: `research_binance.db`, fee 2 bp a side, same-bar stop wins, one position.

| Book | Data | Trades | Avg R | PF | Max dip | Notes |
|---|---|---|---|---|---|---|
| Lock 1: 4h/1h/15m stack | not recorded | - | - | - | - | No numbers in the repo |
| Lock 2: desktop Hunt C-FI (stop 1.5 ATR, target 2.5 ATR) | Sep 2025 - Sep 2026 | 1981 | +0.107R | 1.22 | -32.3R | Both sides positive. Source: `config/experiments/lock-2-hunt-cfi.md` |
| Lock 3: Hunt V3 (1h failed-push box switch), one position | 2025-26 | 950 (Hunt 864, chop 86) | +0.191R | - | -15.8R | $50 risk: $9.57 a trade, $9,092 on the year, $788 dip. Source: `config/experiments/lock-3-hunt-v3.md` |

## 2019-21 run (research_2019_21.db, run 2026-10-03)

Desktop Hunt C-FI on its own (`backtest_desktop_cfi.py`, file `exp-hunt-desktop-cfi-v1/20261003T024202Z`):

| Side | Trades | Avg R | PF | Max dip | Stops | Targets |
|---|---|---|---|---|---|---|
| Combined | 3620 | +0.1082R | 1.178 | -26.59R | 2035 | 1585 |
| LONG | 1962 | +0.1255R | 1.141 | -22.89R | 1090 | 872 |
| SHORT | 1658 | +0.0877R | 1.221 | -26.60R | 945 | 713 |

Hunt stays positive on 2019-21, so lock 2 holds out of sample on both sides.

**Invalid run, do not use:** `backtest_hunt_chop.py` on `research_2019_21.db` printed chop 201 trades, +0.3928R, dip -26.38R, and one-position 2182 trades, +0.1329R. It took the 2025-26 Hunt file (`20261002T090757Z`, 1981 trades) because the 2019-21 Hunt file did not exist yet. That mixes two years. Rerun it with the `20261003T024202Z` Hunt file. The chop-only line is still real 2019-21 data, but it was not measured against the right Hunt book.

## Lock 3 rule, short

- Box off: full desktop Hunt trades, chop does not.
- Box on: Hunt signal dropped, chop trade only.
- Chop entry: reject of a line, or a turn in the outer quarter before the line is touched.
- Chop stop: a close through the entry line (a wick is not a stop). Target: the other line.
- Chop fee 2 bp a side. The Hunt file is used as recorded.

## Rejected

- Chop line-touch fade and quarter fade: both lost.
- Chop middle target: not in the lock.

## Not yet tested

- Lock 3 on 2019-21 (rerun with the matching Hunt file) and on 2022-25.
- Lock 2 on 2022-25.
