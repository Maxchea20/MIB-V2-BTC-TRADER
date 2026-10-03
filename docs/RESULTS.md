# Backtest results log

Only results pasted from the PC runs or recorded in the lock files. `results/` and `backend/*.db` are gitignored, so raw trade files and databases are not here. Add new runs below.

All runs: fee 2 bp a side, same-bar stop wins, one position, stop 1.5 ATR, target 2.5 ATR for Hunt. Lock 1 (4h/1h/15m stack) has no numbers in the repo.

## Lock 3 (Hunt V3) across all three files

Run 2026-10-03. Each file used its own Hunt run. Total R = trades x avg R (derived).

| File | Book | Trades | Avg R | Max dip | Total R |
|---|---|---|---|---|---|
| 2019-21 | Full Hunt | 3620 | +0.108 | -26.6 | +392 |
| | **Switch** | 1526 | +0.152 | **-40.9** | +231 |
| 2022-25 | Full Hunt | 6427 | +0.124 | -27.9 | +798 |
| | **Switch** | 2549 | +0.209 | -23.8 | +532 |
| 2025-26 | Full Hunt | 1981 | +0.107 | -32.3 | +211 |
| | **Switch** | 950 | +0.191 | -15.8 | +182 |

Pieces of the switch:

| File | Hunt outside box | Hunt inside box (dropped) | Chop alone | Switch Hunt / chop trades |
|---|---|---|---|---|
| 2019-21 | 1904, +0.126R, dip -21.7 | 1716, +0.089R | 201, +0.393R, dip -26.4 | 1376 / 150 |
| 2022-25 | 2867, +0.193R, dip -18.9 | 3560, +0.069R | 347, +0.593R, dip -31.2 | 2294 / 255 |
| 2025-26 | 1007, +0.152R, dip -20.5 | 974, +0.060R | 114, +0.580R, dip -16.8 | 864 / 86 |

Read:
- Avg R per trade rises on every file (about +0.08R).
- Total R falls on every file (-41%, -33%, -14%). The switch trades half as often.
- Max dip is better on two files and clearly worse on 2019-21 (-40.9 vs -26.6). The halved dip on 2025-26 is not typical.
- Hunt inside the box is still positive on all three files (+0.06 to +0.09R) but weaker than outside (+0.13 to +0.19R). Dropping it raises quality and costs total R.
- Chop alone is positive on all three files (+0.39, +0.59, +0.58R). In the switch (2022-25) chop made +0.433R on 255 trades but hit its target only 52 times to 203 stops, so it lives on a few big wins.
- One-position blocking removes a lot: chop goes 201 to 150, 347 to 255, 114 to 86; Hunt outside-box trades shrink 1904 to 1376, 2867 to 2294.
- Max loss streak in the switch: 11 on 2022-25 and on 2025-26.

## Hunt alone (lock 2)

| File | Trades | Avg R | PF | Max dip | Long avg R | Short avg R |
|---|---|---|---|---|---|---|
| 2019-21 | 3620 | +0.108 | 1.178 | -26.6 | +0.126 | +0.088 |
| 2022-25 | 6427 | +0.124 | 1.245 | -27.9 | +0.117 | +0.132 |
| 2025-26 | 1981 | +0.107 | 1.224 | -32.3 | +0.104 | +0.109 |

Hunt is positive on both sides in all three periods.

## Lock 3 on 2022-25, detail

- By book: Hunt 2294 trades +0.184R dip -18.3; chop 255 trades +0.433R dip -22.95.
- By side: long 1332 +0.191R dip -36.6; short 1217 +0.227R dip -26.8.
- Worst months: 2025-05 (-0.20R), 2024-06 (-0.08R), 2023-07 (-0.06R), 2022-04 (-0.10R). Most months positive.
- Max win streak 9, max loss streak 11.

## Lock 3 on 2025-26, detail

- Matches lock 3 exactly: 950 trades, +0.1914R, dip -15.76R; Hunt 864 +0.171R, chop 86 +0.393R.
- Hole window (2026-07-16 to 08-15): 54 trades +0.10R. Hunt 48 trades -0.176R, chop 6 trades +2.32R.
- Weakest months: 2026-09 (-0.03R), 2025-11 (+0.02R), 2026-01 (+0.05R).

## Lock 3 on 2022-25, by Hunt weather and year

Weather is the Hunt weather V1 label (SWING_UP, SWING_DOWN, CHOP). BOX is the chop book. Run with `scripts/diagnose_v3_regime.py`.

| Weather | Full Hunt | Switch |
|---|---|---|
| SWING_UP | 628, +0.113R, dip -27.6 | 344, +0.164R, dip -14.3 |
| SWING_DOWN | 480, +0.137R, dip -18.5 | 232, +0.281R, dip -10.0 |
| CHOP weather | 5319, +0.124R, dip -28.5 | 1718, +0.174R, dip -26.4 |
| BOX (chop book) | - | 255, +0.433R, dip -23.0 |

| Year | Full Hunt | Switch | Switch Hunt | Switch chop |
|---|---|---|---|---|
| 2022 | 1805, +0.154R | 753, +0.233R | 681, +0.233R | 72, +0.237R |
| 2023 | 1523, +0.116R | 516, +0.312R | 457, +0.265R | 59, +0.679R |
| 2024 | 1824, +0.101R | 742, +0.182R | 664, +0.148R | 78, +0.468R |
| 2025 (to Aug) | 1275, +0.125R | 538, +0.111R | 492, +0.087R | 46, +0.368R |

Read:
- Hunt is about +0.12R in every weather label. 83% of Hunt trades are CHOP weather and only 17% are swing, so swing is a small sample here (480 and 628 trades).
- The switch is positive in all three weather labels and in the box. SWING_DOWN is best (+0.281R, dip -10.0).
- Positive every year, but fading. The switch Hunt book falls from +0.233R (2022) to +0.087R (2025).
- In 2025 the switch is no better than plain Hunt per trade (+0.111R vs +0.125R), and total R is 60 vs 159. The box filter helped in 2022-24 and not in 2025. Chop stays positive in 2025 (+0.368R, 46 trades).
- Weather and year splits for 2019-21 and 2025-26 not run yet.

## Lock 3 rule, short

- Box off: full desktop Hunt trades, chop does not.
- Box on: Hunt signal dropped, chop trade only.
- Chop entry: reject of a line, or a turn in the outer quarter before the line is touched.
- Chop stop: a close through the entry line (a wick is not a stop). Target: the other line.
- One position. Chop fee 2 bp a side. The Hunt file is used as recorded.

## Rejected

- Chop line-touch fade and quarter fade: both lost.
- Chop middle target: not in the lock.
- Invalid run: `backtest_hunt_chop.py` on 2019-21 with the 2025-26 Hunt file (2182 trades, +0.1329R). Ignore it.

## Not yet tested

- Lock 1 numbers. Chop-only book. Hunt and chop both open at once (no one-position rule).
