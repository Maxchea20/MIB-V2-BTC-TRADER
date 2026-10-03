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

Lock 3 switch (`backtest_hunt_chop.py`, matching Hunt file `20261003T024202Z`):

| Book | Trades | Avg R | Max dip | Total R |
|---|---|---|---|---|
| Full Hunt | 3620 | +0.1082R | -26.59R | +392 |
| Hunt outside the box | 1904 | +0.1258R | -21.72R | +240 |
| Hunt inside the box (dropped by the switch) | 1716 | +0.089R | - | +152 |
| Chop alone | 201 | +0.3928R | -26.38R | +79 |
| **Switch, one position** | 1526 (Hunt 1376, chop 150) | +0.1516R | **-40.89R** | +231 |

Total R and the inside-box line are derived (trades x avg R), not printed by the script.

Read: the switch lifts the average per trade (+0.108R to +0.152R) but it does not hold up as lock 3 claimed. Max dip is worse, -40.9R against -26.6R for plain Hunt, where 2025-26 had it halved. Total R falls about 41%. The box drops Hunt trades that are still positive on this file (+0.089R). One-position blocking costs a lot: 1904 outside-box Hunt trades shrink to 1376, and 51 of the 201 chop trades are lost to overlap. Chop alone is strong here (+0.39R), but its dip is -26.4R on 201 trades.

An earlier run of the same script (chop 201, one-position 2182 trades, +0.1329R) mixed in the 2025-26 Hunt file and is invalid.

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

- Lock 3 on 2022-25.
- Lock 2 on 2022-25.
