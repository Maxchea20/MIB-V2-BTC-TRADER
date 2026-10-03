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

## Lock 3 on 2019-21, by Hunt weather and year

| Weather | Full Hunt | Switch |
|---|---|---|
| SWING_UP | 358, +0.033R, dip -22.9 | 201, +0.127R, dip -11.0 |
| SWING_DOWN | 191, -0.066R, dip -29.5 | 81, -0.021R, dip -15.1 |
| CHOP weather | 3071, +0.128R, dip -22.9 | 1094, +0.127R, dip -21.1 |
| BOX (chop book) | - | 150, +0.455R, dip -28.5 |

| Year | Full Hunt | Switch | Switch Hunt | Switch chop |
|---|---|---|---|---|
| 2020 | 1747, +0.101R, dip -25.7 | 829, +0.166R, dip -40.9 | 752, +0.140R | 77, +0.421R |
| 2021 | 1873, +0.115R, dip -26.6 | 697, +0.134R, dip -17.7 | 624, +0.092R | 73, +0.490R |

Read:
- Swing is weak here. Hunt in SWING_DOWN loses (-0.066R, 191 trades) and SWING_UP is flat (+0.033R). All of Hunt's +392R comes from CHOP weather (+393R). In 2022-25 swing was positive (+0.11R, +0.14R), so swing is not consistent across files.
- The switch does not fix SWING_DOWN (-0.021R, 81 trades). It lifts SWING_UP to +0.127R.
- The box chop book is positive again (+0.455R, 150 trades).
- The -40.9R dip is in 2020, bigger than either book's own 2020 dip (Hunt -23.7R, chop -28.5R). Both books lost at the same time.
- 2021: the switch Hunt book (+0.092R) is below plain Hunt (+0.115R), as in 2025.

## Lock 3 on 2025-26, by Hunt weather and year

| Weather | Full Hunt | Switch |
|---|---|---|
| SWING_UP | 175, +0.226R, dip -8.0 | 101, +0.312R, dip -10.0 |
| SWING_DOWN | 156, +0.236R, dip -15.8 | 92, +0.296R, dip -14.4 |
| CHOP weather | 1650, +0.082R, dip -29.4 | 671, +0.133R, dip -21.9 |
| BOX (chop book) | - | 86, +0.393R, dip -17.8 |

| Year | Full Hunt | Switch | Switch Hunt | Switch chop |
|---|---|---|---|---|
| 2025 (Sep-Dec) | 572, +0.113R, dip -10.3 | 343, +0.178R, dip -11.9 | 322, +0.164R | 21, +0.400R |
| 2026 (Jan-Sep) | 1409, +0.104R, dip -32.3 | 607, +0.199R, dip -15.8 | 542, +0.176R | 65, +0.390R |

Read:
- Swing is strong here (+0.23R full Hunt, +0.30R in the switch), the opposite of 2019-21. Swing is 17% of Hunt trades.
- CHOP weather is the weakest Hunt label (+0.082R), and the switch lifts it to +0.133R.
- The switch beats plain Hunt in both years, per trade and on dip.

## Weather across all three files (full Hunt, avg R)

| Weather | 2019-21 | 2022-25 | 2025-26 |
|---|---|---|---|
| SWING_UP | +0.033 (358) | +0.113 (628) | +0.226 (175) |
| SWING_DOWN | -0.066 (191) | +0.137 (480) | +0.236 (156) |
| CHOP | +0.128 (3071) | +0.124 (5319) | +0.082 (1650) |

Swing swings from negative to the best label. CHOP is steady. Swing trades are only 15-17% of the book in every file, so the swing numbers are noisy.

## Step 8 room-to-run veto test, 2022-25

Optional swing veto from the user's doc: drop a swing to CHOP when price is within 0.25 ATR of the 7-bar 4h high (swing up) or low (swing down). `room` includes the newest bar in the 7; `room-ex` leaves it out; `-block` skips the vetoed trade instead of allowing both sides. Off by default. Run with `scripts/run_room_test.bat`.

| Variant | Hunt alone | Switch |
|---|---|---|
| Baseline (no Step 8) | 6427, +0.124R, dip -27.9 | 2549, +0.208R, dip -23.8 |
| room | 6429, +0.126R, dip -28.9 | 2577, +0.197R, dip -24.9 |
| room-ex | 6498, +0.123R, dip -28.9 | 2623, +0.186R, dip -31.2 |
| room-block | 6324, +0.121R, dip -30.9 | 2491, +0.203R, dip -26.6 |
| room-ex-block | 6276, +0.116R, dip -35.8 | 2463, +0.195R, dip -32.4 |

Read:
- Step 8 does not help on 2022-25. Every variant is at or below baseline on the switch, and every dip is worse.
- The blocked trades were good ones. Blocking removes 103 trades (room-block) and 151 trades (room-ex-block) worth about +33R and +70R (about +0.32R and +0.47R each, approximate because the trade sequence shifts). Swings near the recent high or low tend to keep going.
- Letting a vetoed swing become CHOP (both sides) adds trades but lowers the average.
- Only 2022-25 tested. 2019-21 and 2025-26 not run.

## Doc steps 1-9 in full: swing-only Hunt + box chop

Hunt only in SWING_UP / SWING_DOWN weather, chop only in the box, nothing else. Uses the saved Hunt file (no new Hunt run). Run with `scripts/run_swing_only.py`. The doc's "Chop Engine" is not defined, so the box chop book stands in for it.

| File | Swing Hunt (all) | Chop (all) | Combined, one position | Total R |
|---|---|---|---|---|
| 2025-26 | 331, +0.231R, dip -15.0 | 114, +0.580R, dip -16.8 | 288 (Hunt 177 / chop 111), +0.422R, dip -19.6 | +122 |
| 2022-25 | 1108, +0.124R, dip -19.9 | 347, +0.593R, dip -31.2 | 891 (Hunt 568 / chop 323), +0.251R, dip -24.4 | +224 |
| 2019-21 | 549, -0.002R, dip -36.2 | 201, +0.393R, dip -26.4 | 462 (Hunt 273 / chop 189), +0.217R, dip -29.3 | +100 |

2019-21 read: swing Hunt on its own is flat (-0.002R, dip -36.2R), so the +0.217R comes mostly from chop (about 189 trades at roughly +0.39R is about +74R of the +100R, approximate). Dip -29.3R is better than the switch (-40.9R) and a bit worse than plain Hunt (-26.6R).

Across all three files, per trade (swing-only vs switch vs plain Hunt): 2019-21 +0.217 / +0.152 / +0.108; 2022-25 +0.251 / +0.208 / +0.124; 2025-26 +0.422 / +0.191 / +0.107. Total R: 100 / 224 / 122 against switch 231 / 532 / 182, so it keeps only about 40-65% of the switch's total R. Positive on every file.

2022-25 read: per trade +0.251R beats the switch (+0.208R) but total R is +224 against +532 (switch) and +798 (plain Hunt). Dip -24.4R is about the same as the switch (-23.8R). Chop is 323 of the 891 trades, so about 36% of the book.

2025-26 read: per-trade average doubles (+0.422R vs +0.191R for the switch), but total R falls to +122 against +182 (switch) and +211 (plain Hunt), because only 288 trades are taken. Dip -19.6R is worse than the switch (-15.8R) and better than plain Hunt (-32.3R). 2025-26 is the file where swing was strongest (+0.23R); in 2019-21 swing lost money, so that file is the real test.

## Side by side: every strategy tested (2026-10-03)

Total R = trades x avg R. R/dip = total R divided by the max dip, so it scales for risk.

| File | Strategy | Trades | Avg R | Total R | Max dip | R/dip |
|---|---|---|---|---|---|---|
| 2019-21 | Plain Hunt | 3620 | +0.108 | +392 | -26.6 | **14.7** |
| | Lock 3 (V3) | 1526 | +0.152 | +231 | -40.9 | 5.7 |
| | Swing Hunt + chop | 462 | +0.217 | +100 | -29.3 | 3.4 |
| 2022-25 | Plain Hunt | 6427 | +0.124 | +798 | -27.9 | **28.7** |
| | Lock 3 (V3) | 2549 | +0.208 | +531 | -23.8 | 22.3 |
| | Swing Hunt + chop | 891 | +0.251 | +224 | -24.4 | 9.2 |
| | V3 + Step 8 (room) | 2577 | +0.197 | +508 | -24.9 | 20.4 |
| 2025-26 | Plain Hunt | 1981 | +0.106 | +211 | -32.3 | 6.5 |
| | Lock 3 (V3) | 950 | +0.191 | +182 | -15.8 | **11.5** |
| | Swing Hunt + chop | 288 | +0.422 | +122 | -19.6 | 6.2 |

Read:
- Lock 3 has the best average per trade of the three whole-engine versions except swing+chop, but plain Hunt makes more total R on every file and a better R/dip on two of three (2019-21, 2022-25).
- Lock 3 wins only on 2025-26, the file it was locked on. On the two other files it is worse than plain Hunt on R/dip.
- Swing Hunt + chop has the highest avg R and the lowest total R everywhere.
- Step 8 made V3 slightly worse.

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
