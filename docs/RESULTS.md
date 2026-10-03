# Backtest results log

Only results recorded in the repo lock files. `results/` and `backend/*.db` are gitignored, so raw trade files and the research database are not here. Add new runs below as they are made.

All runs: `research_binance.db`, fee 2 bp a side, same-bar stop wins, one position.

| Book | Data | Trades | Avg R | PF | Max dip | Notes |
|---|---|---|---|---|---|---|
| Lock 1: 4h/1h/15m stack | not recorded | - | - | - | - | No numbers in the repo |
| Lock 2: desktop Hunt C-FI (stop 1.5 ATR, target 2.5 ATR) | Sep 2025 - Sep 2026 | 1981 | +0.107R | 1.22 | -32.3R | Both sides positive. Source: `config/experiments/lock-2-hunt-cfi.md` |
| Lock 3: Hunt V3 (1h failed-push box switch), one position | 2025-26 | 950 (Hunt 864, chop 86) | +0.191R | - | -15.8R | $50 risk: $9.57 a trade, $9,092 on the year, $788 dip. Source: `config/experiments/lock-3-hunt-v3.md` |

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

- Lock 2 and lock 3 on 2019-21 and 2022-25. Both results above are one-year, in-sample.
