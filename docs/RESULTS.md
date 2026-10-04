# Backtest results log

Baseline: Hunt V3 (config/experiments/lock-3-hunt-v3.md). Everything else is compared against it. Names and a one-table summary of every version: docs/VERSIONS.md. Latest lock: Hunt V4 (Hunt V3 + Floors), config/experiments/lock-4-hunt-v4.md, locked 2026-10-04T12:28:04Z.

**Correction (2026-10-04):** every Hunt V3 number below that used the box state (Hunt V3, "Hunt outside box", "Hunt inside box", the floors-in-the-engine Hunt V3 rows, and the box splits in the drawdown diagnosis) peeked at the 1h bar still forming, up to 1 hour of future. The fixed numbers are in the section "Box filter correction". Results that do not use the box (plain Hunt, the chop book, exits, floors on Hunt alone, throttle on all Hunt trades) are not affected.

Only results pasted from the PC runs or recorded in the lock files. `results/` and `backend/*.db` are gitignored, so raw trade files and databases are not here. Add new runs below.

All runs: fee 2 bp a side, same-bar stop wins, one position, stop 1.5 ATR, target 2.5 ATR for Hunt. Lock 1 (4h/1h/15m stack) has no numbers in the repo.

## Hunt V3 across all three files

Run 2026-10-03. Each file used its own Hunt run. Total R = trades x avg R (derived).

| File | Book | Trades | Avg R | Max dip | Total R |
|---|---|---|---|---|---|
| 2019-21 | Full Hunt | 3620 | +0.108 | -26.6 | +392 |
| | **Hunt V3** | 1526 | +0.152 | **-40.9** | +231 |
| 2022-25 | Full Hunt | 6427 | +0.124 | -27.9 | +798 |
| | **Hunt V3** | 2549 | +0.209 | -23.8 | +532 |
| 2025-26 | Full Hunt | 1981 | +0.107 | -32.3 | +211 |
| | **Hunt V3** | 950 | +0.191 | -15.8 | +182 |

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

## Hunt V3 on 2022-25, detail

- By book: Hunt 2294 trades +0.184R dip -18.3; chop 255 trades +0.433R dip -22.95.
- By side: long 1332 +0.191R dip -36.6; short 1217 +0.227R dip -26.8.
- Worst months: 2025-05 (-0.20R), 2024-06 (-0.08R), 2023-07 (-0.06R), 2022-04 (-0.10R). Most months positive.
- Max win streak 9, max loss streak 11.

## Hunt V3 on 2025-26, detail

- Matches lock 3 exactly: 950 trades, +0.1914R, dip -15.76R; Hunt 864 +0.171R, chop 86 +0.393R.
- Hole window (2026-07-16 to 08-15): 54 trades +0.10R. Hunt 48 trades -0.176R, chop 6 trades +2.32R.
- Weakest months: 2026-09 (-0.03R), 2025-11 (+0.02R), 2026-01 (+0.05R).

## Hunt V3 on 2022-25, by Hunt weather and year

Weather is the Hunt weather V1 label (SWING_UP, SWING_DOWN, CHOP). BOX is the chop book. Run with `scripts/diagnose_v3_regime.py`.

| Weather | Full Hunt | Hunt V3 |
|---|---|---|
| SWING_UP | 628, +0.113R, dip -27.6 | 344, +0.164R, dip -14.3 |
| SWING_DOWN | 480, +0.137R, dip -18.5 | 232, +0.281R, dip -10.0 |
| CHOP weather | 5319, +0.124R, dip -28.5 | 1718, +0.174R, dip -26.4 |
| BOX (chop book) | - | 255, +0.433R, dip -23.0 |

| Year | Full Hunt | Hunt V3 | Switch Hunt | Switch chop |
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

## Hunt V3 on 2019-21, by Hunt weather and year

| Weather | Full Hunt | Hunt V3 |
|---|---|---|
| SWING_UP | 358, +0.033R, dip -22.9 | 201, +0.127R, dip -11.0 |
| SWING_DOWN | 191, -0.066R, dip -29.5 | 81, -0.021R, dip -15.1 |
| CHOP weather | 3071, +0.128R, dip -22.9 | 1094, +0.127R, dip -21.1 |
| BOX (chop book) | - | 150, +0.455R, dip -28.5 |

| Year | Full Hunt | Hunt V3 | Switch Hunt | Switch chop |
|---|---|---|---|---|
| 2020 | 1747, +0.101R, dip -25.7 | 829, +0.166R, dip -40.9 | 752, +0.140R | 77, +0.421R |
| 2021 | 1873, +0.115R, dip -26.6 | 697, +0.134R, dip -17.7 | 624, +0.092R | 73, +0.490R |

Read:
- Swing is weak here. Hunt in SWING_DOWN loses (-0.066R, 191 trades) and SWING_UP is flat (+0.033R). All of Hunt's +392R comes from CHOP weather (+393R). In 2022-25 swing was positive (+0.11R, +0.14R), so swing is not consistent across files.
- The switch does not fix SWING_DOWN (-0.021R, 81 trades). It lifts SWING_UP to +0.127R.
- The box chop book is positive again (+0.455R, 150 trades).
- The -40.9R dip is in 2020, bigger than either book's own 2020 dip (Hunt -23.7R, chop -28.5R). Both books lost at the same time.
- 2021: the switch Hunt book (+0.092R) is below plain Hunt (+0.115R), as in 2025.

## Hunt V3 on 2025-26, by Hunt weather and year

| Weather | Full Hunt | Hunt V3 |
|---|---|---|
| SWING_UP | 175, +0.226R, dip -8.0 | 101, +0.312R, dip -10.0 |
| SWING_DOWN | 156, +0.236R, dip -15.8 | 92, +0.296R, dip -14.4 |
| CHOP weather | 1650, +0.082R, dip -29.4 | 671, +0.133R, dip -21.9 |
| BOX (chop book) | - | 86, +0.393R, dip -17.8 |

| Year | Full Hunt | Hunt V3 | Switch Hunt | Switch chop |
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

## Hunt V3 trade path (how far trades go before they end)

Run with `scripts/diagnose_v3_path.py`. R = stop distance. For Hunt, 1 ATR in favor = +0.67R. The exit bar is left out. Reached-share is the share of trades that were at that level at some point before ending.

| File | Hunt stopped | Hunt target | Stopped that reached +0.67R | Winners dipped past -0.5R / -0.8R |
|---|---|---|---|---|
| 2025-26 | 455 | 397 | 49% | 25% / 7% |
| 2022-25 | 1209 | 1050 | 48% | 27% / 10% |
| 2019-21 | 769 | 588 | 47% | 30% / 11% |

Median MFE/MAE: Hunt winners MFE 1.54-1.55R, MAE 0.20-0.25R. Hunt losers MFE 0.63-0.65R. Median time about 100-130 minutes for both.

Derived odds (approximate, from the counts above), compared with a coin flip at the same distances:

| File | Reach +1 ATR before stop | Coin flip | Target given +1 ATR reached | Coin flip |
|---|---|---|---|---|
| 2025-26 | 72% | 60% | 64% | 62.5% |
| 2022-25 | 72% | 60% | 65% | 62.5% |
| 2019-21 | 69% | 60% | 63% | 62.5% |

Read:
- Hunt entries have an edge in the first 1 ATR (69-72% against 60%). After +1 ATR reached, the trade behaves like a coin flip (63-65% against 62.5%).
- About half of stopped Hunt trades were +1 ATR up first, but moving the stop to break-even there would not add expectancy by itself in a coin-flip walk. It only lowers the dip.
- Winners barely dip (median 0.2R), so entry timing works when the trade works. About 28% of trades go straight against and never reach +1 ATR.
- A tighter stop does not help in the same arithmetic (estimated -0.5R stop gives about the same expectancy).
- Chop: winners take 50-60 hours and reach median 3.6-4.3R; chop losers last 7.5-17 hours. 52-65% of chop losers were +1R up first and 44-53% were +1.5R up, so chop gives back a lot of open profit. Chop win rate is about 19-29%.

## Hunt V3 feature scan (Hunt trades inside Hunt V3, avg R by feature)

Run with `scripts/diagnose_hunt_features.py` on the three files (2019-21, 2022-25, 2025-26). Hunt V3 Hunt trades: 1376, 2294, 864, avg +0.119R, +0.183R, +0.171R.

| Bucket | 2019-21 | 2022-25 | 2025-26 |
|---|---|---|---|
| **12-16h UTC** | 260, +0.311R | 516, +0.304R | 212, +0.308R |
| other hours (best other) | 20-24h +0.204R | 00-04h +0.248R | 08-12h +0.220R |
| CHoCH / BOS | +0.111 / +0.146 | +0.201 / +0.116 | +0.175 / +0.159 |
| gate cfast / internal / rearm | +0.182 / +0.111 / +0.112 | +0.235 / +0.242 / +0.156 | +0.005 / +0.282 / +0.162 |
| vol low / mid / high | +0.134 / +0.041 / +0.181 | +0.042 / +0.186 / +0.323 | +0.257 / +0.102 / +0.155 |
| side long / short | +0.115 / +0.124 | +0.146 / +0.225 | +0.168 / +0.175 |

Read:
- Only one bucket has the same sign on all three files: 12-16h UTC (about +0.31R, 0.12-0.19R above each file's average). It is the top hour bucket of six in every file. Chance of that by luck is small (about (1/6)^3 for a given bucket, a few percent for any bucket), but it was found by scanning, so it needs an out-of-sample check.
- 12-16h is 22% of Hunt V3 Hunt trades (988 of 4534) and about 41% of their total R (about +303R of +731R). The other hours average about +0.12R.
- Event, gate, weather, side, volatility and weekday: nothing consistent across files.
- Weak negatives: 04-08h UTC is below average on all three (-0.05, 0.00, +0.15R).

## Hunt V3 with Hunt limited to 12-16h UTC (chop any hour)

Run with `scripts/run_hours_test.py`. The 12-16h bucket was found by scanning these same three files, so the gain is in-sample.

| File | Strategy | Trades | Avg R | Total R | Max dip | R/dip |
|---|---|---|---|---|---|---|
| 2019-21 | Hunt V3 | 1526 | +0.152 | +231 | -40.9 | 5.7 |
| | Hunt only 12-16h | 450 (Hunt 257 / chop 193) | +0.351 | +158 | -22.1 | **7.2** |
| 2022-25 | Hunt V3 | 2549 | +0.208 | +531 | -23.8 | **22.3** |
| | Hunt only 12-16h | 826 (Hunt 495 / chop 331) | +0.322 | +266 | -25.9 | 10.3 |
| 2025-26 | Hunt V3 | 950 | +0.191 | +182 | -15.8 | **11.5** |
| | Hunt only 12-16h | 310 (Hunt 201 / chop 109) | +0.380 | +118 | -17.4 | 6.8 |

Read:
- Avg R per trade rises on all three files (+0.20, +0.11, +0.19R).
- Total R falls 32%, 50% and 35%. The dip is much better on 2019-21 and slightly worse on the other two. R/dip is better only on 2019-21.
- So 12-16h makes each trade better but does not beat Hunt V3 per unit of risk. It would matter more if live costs per trade turn out higher than the 2 bp fee modeled here.
- Chop trades taken rise (86 to 109, 150 to 193, 255 to 331) because Hunt blocks it less.

## Hunt V3 with Hunt limited to 08-24h UTC (cuts 00-08h; chop any hour)

| File | Strategy | Trades | Avg R | Total R | Max dip | R/dip |
|---|---|---|---|---|---|---|
| 2019-21 | Hunt V3 | 1526 | +0.152 | +231 | -40.9 | 5.7 |
| | Hunt only 08-24h | 1104 (Hunt 937 / chop 167) | +0.226 | +250 | -21.0 | **11.9** |
| 2022-25 | Hunt V3 | 2549 | +0.208 | +531 | -23.8 | **22.3** |
| | Hunt only 08-24h | 1954 (Hunt 1681 / chop 273) | +0.228 | +445 | -29.2 | 15.2 |
| 2025-26 | Hunt V3 | 950 | +0.191 | +182 | -15.8 | **11.5** |
| | Hunt only 08-24h | 717 (Hunt 627 / chop 90) | +0.195 | +139 | -22.1 | 6.3 |

Read:
- Better than Hunt V3 on 2019-21 only (more total R, half the dip). On 2022-25 and 2025-26 it has less total R and a worse dip, with avg R barely changed (+0.02R, +0.004R).
- Neither hours filter (12-16h or 08-24h) beats Hunt V3 on all three files. Hunt V3 stays the baseline.
- Dips move in both directions when trades are removed, because the one-position sequence reshuffles; a single dip number is noisy.

## Hunt V3: TP/SL counts, move after the exit, and swing size

Run with `scripts/diagnose_v3_after_exit.py`. After-exit window = 24 hours of 1m bars. Swing run = best price from entry until it pulls back 1R from its peak (max 7 days). Hunt in ATR (stop = 1.5 ATR), chop in R (stop distance).

TP / SL counts:

| File | Hunt TP | Hunt SL | Chop TP | Chop SL |
|---|---|---|---|---|
| 2019-21 | 607 (44%) | 769 (56%) | 26 (17%) | 124 (83%) |
| 2022-25 | 1084 (47%) | 1210 (53%) | 52 (20%) | 203 (80%) |
| 2025-26 | 409 (47%) | 455 (53%) | 23 (27%) | 63 (73%) |

Hunt swing run from entry (median / p75 / p90 / max):

| File | ATR | Price |
|---|---|---|
| 2019-21 | 1.31 / 2.33 / 3.68 / 16.2 | $148 / $412 / $850 / $5,019 |
| 2022-25 | 1.42 / 2.54 / 4.02 / 29.6 | $275 / $547 / $1,065 / $5,167 |
| 2025-26 | 1.40 / 2.65 / 4.23 / 20.1 | $388 / $748 / $1,359 / $5,307 |

Chop swing run (R): median 0.75-0.79, p75 1.23-1.38, p90 2.30-2.49, max 4.9-8.5. Price median $187 / $279 / $367.

After the exit (24h), medians:

| File | Hunt after TP: beyond target | Hunt after SL: kept going / bounced | Chop after TP: beyond target | Chop after SL: kept going / bounced |
|---|---|---|---|---|
| 2019-21 | 4.14 ATR | 3.89 / 3.51 ATR | 1.03R | 2.80R / 1.15R |
| 2022-25 | 3.99 ATR | 3.61 / 4.14 ATR | 2.00R | 2.37R / 1.32R |
| 2025-26 | 5.06 ATR | 3.91 / 4.59 ATR | 1.33R | 2.92R / 1.12R |

Read:
- Hunt after TP and after SL look alike (about 4 ATR further each way). A 24h window is long next to a 1.5 ATR stop, so these mostly show BTC's normal daily range, not anything specific to Hunt. A random-time baseline and shorter windows (2h, 4h) are needed to say more.
- After a Hunt SL, price got back to entry in 24h in 80-81% of cases and reached the original target in 44-54%. After a Hunt TP it came all the way back to entry in 63-67%.
- Chop is consistent across all three files: after a chop SL (close through the line) price kept going past it about 2.4-2.9R, about twice the bounce back (1.1-1.3R), and the target was reached only 3-5% of the time. After a chop TP the move continued 1.0-2.0R and only 12-22% came back to entry. Chop stops look like real breakouts.
- In ATR, the Hunt swing run is stable across eras (median about 1.3-1.4 ATR, p90 about 3.7-4.2 ATR). Price distances grow with BTC's price level.

## Breakout trade after a chop stop (2025-26 only)

Run with `scripts/run_breakout_test.py`. After a chop trade is stopped by a close through the line, trade the break direction, entry at the next 1h open, one position with Hunt V3.

| Breakout TP/SL set | Breakout alone | Hunt V3 + it |
|---|---|---|
| (Hunt V3 baseline) | | 950, +0.191R, total +182, dip -15.8 |
| ATR: stop 1.5 ATR, target 2.5 ATR (1h ATR) | 81, -0.121R, total -10, dip -16.1 | 926, +0.189R, total +175, dip -16.6 (54 taken) |
| Line stop, target 2R | 81, -0.299R, total -24, dip -29.8 | 945, +0.179R, total +169, dip -18.2 (62 taken) |
| Line stop, 1R trail, no target | 81, -0.803R, total -65, dip -72.7 | 986, +0.136R, total +134, dip -22.3 (65 taken) |

Read:
- All three breakout versions lose on their own and make Hunt V3 worse. The idea does not work on this file.
- The 24h after-SL study (price kept going about 2.4-2.9R past the chop stop, twice the bounce) was a maximum-excursion measure with no stop and no entry delay. Once the trade enters after the break candle closes and has a stop, the edge is gone.
- Not run on 2019-21 or 2022-25. Three losing versions on one file is not a reason to spend more runs.

## Hunt V3 Hunt trades with different exits (same entries)

Run with `scripts/test_hunt_exits.py`. Same entries, stop 1.5 ATR, fee 2 bp a side per fill. Header check passed on all three files (file average vs "base 2.5" replay: +0.171/+0.168, +0.119/+0.117, +0.183/+0.184). Total R / dip is R/dip. Entries are fixed, so extra trades from shorter exits are not counted.

| Exit | 2019-21 avg / total / dip | 2022-25 avg / total / dip | 2025-26 avg / total / dip |
|---|---|---|---|
| base 2.5 (Hunt V3 now) | +0.117 / +161 / -23.7 | +0.184 / +422 / -18.3 | +0.168 / +145 / -18.2 |
| target 1.0 | +0.116 / +160 / -12.1 | +0.135 / +310 / -11.2 | +0.124 / +107 / -11.1 |
| target 1.5 | +0.117 / +162 / -22.4 | +0.141 / +324 / -16.2 | +0.148 / +128 / -12.0 |
| half@1.0, stop to entry | +0.114 / +157 / -13.7 | +0.149 / +342 / -11.3 | +0.149 / +129 / -9.5 |
| half@1.0, stop stays | +0.116 / +160 / -14.5 | +0.160 / +366 / -12.1 | +0.146 / +126 / -9.9 |
| half@1.4, stop to entry | +0.113 / +155 / -18.4 | +0.156 / +358 / -16.5 | +0.163 / +141 / -11.2 |
| trail 1.4/1.0 | +0.109 / +150 / -25.8 | +0.160 / +368 / -15.8 | +0.161 / +139 / -11.0 |
| giveback 40% | +0.117 / +161 / -22.8 | +0.162 / +371 / -15.1 | +0.171 / +148 / -10.9 |
| eye structure | +0.114 / +157 / -22.7 | +0.167 / +383 / -16.3 | +0.167 / +144 / -13.3 |
| eye stall | +0.129 / +178 / -21.2 | +0.173 / +396 / -15.6 | +0.171 / +148 / -12.3 |
| eye reversal | +0.120 / +164 / -27.0 | +0.166 / +380 / -16.1 | +0.175 / +151 / -10.7 |
| eye any | +0.116 / +160 / -26.1 | +0.167 / +383 / -15.7 | +0.175 / +151 / -10.4 |
| eye hold 0.7 | +0.117 / +161 / -26.8 | +0.152 / +348 / -15.5 | +0.153 / +133 / -12.0 |
| eye hold 1.0 | +0.104 / +143 / -26.4 | +0.155 / +355 / -15.3 | +0.173 / +149 / -11.1 |

R/dip (total R / dip) for the main candidates:

| Exit | 2019-21 | 2022-25 | 2025-26 |
|---|---|---|---|
| base 2.5 | 6.8 | 23.1 | 8.0 |
| half@1.0, stop to entry | **11.5** | **30.3** | **13.6** |
| half@1.0, stop stays | 11.0 | 30.2 | 12.7 |
| target 1.0 | 13.2 | 27.7 | 9.6 |
| giveback 40% | 7.1 | 24.6 | 13.6 |
| eye stall | 8.4 | 25.4 | 12.0 |
| eye any | 6.1 | 24.4 | 14.5 |

Read:
- No exit raises average R or total R in a way beyond noise. Past +1 ATR a trade behaves like a coin flip, so catching the 1.4-2.5 ATR trades also gives up the bigger winners.
- Early profit-taking (sell half at 1 ATR, or a 1 ATR target) cuts the dip by 35-50% on all three files, at a cost of 0-19% of total R. R/dip improves on all three files. It is the most consistent result.
- The eye rules do not beat the simple ones. Eye any/reversal cut the dip on 2022-25 and 2025-26 but make it worse on 2019-21. Eye stall (1h with no new best, after +1.4 ATR) is the steadiest eye rule: dip lower on all three files, total R +10%, -6%, +2%.
- Choosing among 16 exits on three files has some selection risk; the exit families are simple and the pattern repeats across files.
- Still to do: run the chosen exit inside the full Hunt V3 sequence (one position, chop, new entries after shorter trades).

## Eye v2: two zones with floors (Hunt V3 Hunt trades, same entries)

Run with `scripts/test_hunt_eye2.py`. TP fixed at 2.5 ATR, stop 1.5 ATR. Zone B: best price 1.5-2.0 ATR, close at least +1R. Zone A: best price 2.0 ATR and up, close at least +2.0 ATR. "Cushion" arms the 1R floor at 1.75 ATR and the 2.0 ATR floor at 2.25 ATR, so a floor is not hit by the first pullback. The eye adds an early exit (closed 15m candle rules, and the forming candle on each 1m close: pullback of pb ATR from the best price, or a sell candle).

Avg R / total R / dip:

| Exit | 2019-21 | 2022-25 | 2025-26 |
|---|---|---|---|
| base 2.5 (Hunt V3 now) | +0.117 / +161 / -23.7 | +0.184 / +422 / -18.3 | +0.168 / +145 / -18.2 |
| target 2.0 | +0.125 / +171 / -24.4 | +0.170 / +389 / -18.5 | +0.165 / +143 / -12.8 |
| target 1.5 | +0.117 / +162 / -22.4 | +0.141 / +324 / -16.2 | +0.148 / +128 / -12.0 |
| floor 2.0 + eye .2 | +0.137 / +189 / -23.3 | +0.175 / +401 / -17.6 | +0.178 / +154 / -11.3 |
| zones + eye .2 (no cushion) | +0.130 / +180 / -21.8 | +0.160 / +367 / -15.9 | +0.179 / +155 / -11.4 |
| **zones cushion, floors only** | +0.134 / +185 / -24.6 | +0.180 / +412 / -15.1 | +0.181 / +156 / -11.9 |
| zones cushion + eye .1 | +0.126 / +173 / -24.2 | +0.157 / +359 / -15.9 | +0.159 / +137 / -12.8 |
| zones cushion + eye .2 | +0.123 / +169 / -24.4 | +0.156 / +359 / -15.8 | +0.161 / +139 / -12.8 |
| zones cushion + eye .25 | +0.123 / +169 / -24.8 | +0.156 / +358 / -15.8 | +0.163 / +140 / -12.5 |

Total R / dip: base 6.8 / 23.1 / 8.0; zones cushion floors only 7.5 / 27.3 / 13.1; floor 2.0 + eye .2 8.1 / 22.8 / 13.6.

Read:
- The floors do the work, not the eye. Zones cushion with floors only keeps avg R and total R about the same (+8%, +15%, -2% total R) and cuts the dip on 2022-25 (-17%) and 2025-26 (-35%); on 2019-21 the dip is slightly worse (-24.6 vs -23.7). R/dip is better on all three files.
- Adding the eye's early exit on top lowers avg R on all three files (for example +0.181 to +0.161 on 2025-26) because it sells trades that would have kept running.
- Stops fall from 455 to 369 (2025-26), 768 to 624 (2019-21), 1206 to 988 (2022-25): the floors turn many -1R trades into about +1R or better.
- Reporting issues in this run: the "reached 2.5 ATR 0" figure and the "wins >= 1R" counts were wrong (the best price was not updated on the exit bar, and a 1R floor fill nets about +0.97R). The script is fixed; avg R, total R and dip are not affected. True reach counts from the other rows: 62% / 59% / 61% of trades reach 1.5 ATR, about 54% reach 2.0 ATR, about 47% reach 2.5 ATR.
- Still to do: put the floors inside the full Hunt V3 sequence (one position, chop, new entries after shorter trades).

## Floors inside the full engine (real entry order, one position, chop book)

Run with `scripts/run_floor_v3.py <file> floors`. Floors: stop moves to +1R (1.5 ATR) once the best price reaches 1.75 ATR, and to +2.0 ATR once it reaches 2.25 ATR. TP stays 2.5 ATR, stop 1.5 ATR. Code: `src/btc_research/setups/hunt_exits.py`, tested against the replay (`tests/test_hunt_exits.py`). Closing trades sooner frees the engine, so it takes about 30% more trades.

| File | Strategy | Trades | Avg R | Total R | Dip | R/dip |
|---|---|---|---|---|---|---|
| 2019-21 | Hunt alone, now | 3620 | +0.108 | +392 | -26.6 | 14.7 |
| | Hunt alone, floors | 4901 | +0.109 | +536 | -28.5 | 18.8 |
| | Hunt V3, now | 1526 | +0.152 | +231 | -40.9 | 5.7 |
| | **Hunt V3, floors** | 1976 (Hunt 1799 / chop 177) | +0.133 | **+263** | **-28.1** | **9.4** |
| 2022-25 | Hunt alone, now | 6427 | +0.124 | +798 | -27.9 | 28.7 |
| | Hunt alone, floors | 8773 | +0.132 | +1155 | -41.4 | 27.9 |
| | Hunt V3, now | 2549 | +0.208 | +531 | -23.8 | 22.3 |
| | **Hunt V3, floors** | 3353 (Hunt 3067 / chop 286) | +0.211 | **+709** | **-19.6** | **36.1** |
| 2025-26 | Hunt alone, now | 1981 | +0.106 | +211 | -32.3 | 6.5 |
| | Hunt alone, floors | 2655 | +0.122 | +325 | -28.9 | 11.3 |
| | Hunt V3, now | 950 | +0.191 | +182 | -15.8 | 11.5 |
| | **Hunt V3, floors** | 1211 (Hunt 1121 / chop 90) | +0.188 | **+228** | -21.2 | 10.7 |

Hunt V3 with floors vs Hunt V3 now:
- Total R is higher on all three files: +14%, +34%, +25%.
- Dip is better on two files (-40.9 to -28.1, -23.8 to -19.6) and worse on 2025-26 (-15.8 to -21.2).
- R/dip is higher on two files (+65%, +62%) and about equal on 2025-26 (-7%).
- Avg R per trade is about the same (-0.019, +0.003, -0.003). The gain comes from about 30% more trades.
- At $50 risk, R per year (Hunt V3 now to floors): 2019-21 115R to 131R ($5,800 to $6,600); 2022-25 145R to 193R ($7,200 to $9,700); 2025-26 169R to 211R ($8,500 to $10,600).
- Worst dip at $50: $1,405 / $980 / $1,060 (now: $2,045 / $1,190 / $790).
- Not yet tested: eye2 in the engine (only floors), fee and slippage stress, and live order handling.

## Hunt alone with floors: where the drawdown is, and risk rules (no chop book)

Run with `scripts/diagnose_hunt_drawdown.py`. Reads the floors Hunt trade file for each period. Rules: day cap (no new trade once the UTC day is down 3R), pause (skip 12h after 4 losses in a row), throttle (half size while the equity is 10R or more below its peak).

| | 2019-21 | 2022-25 | 2025-26 |
|---|---|---|---|
| A all trades | 4901, +0.109, +536R, dip -28.5, R/dip 18.8 | 8773, +0.132, +1156R, dip -41.4, 27.9 | 2655, +0.122, +325R, dip -28.9, 11.3 |
| B outside box (Hunt V3's Hunt book, no chop) | 2527, +0.117, +297R, -25.8, 11.5 | 3889, +0.161, +627R, -20.4, 30.7 | 1311, +0.158, +208R, -16.2, 12.8 |
| C inside box | 2374, +0.101, +239R, -22.2, 10.8 | 4884, +0.108, +528R, -47.0, 11.2 | 1344, +0.087, +117R, -20.9, 5.6 |
| A + day cap | 4474, +0.113, +504R, -29.0, 17.4 | 8036, +0.125, +1004R, -30.5, 32.9 | 2442, +0.126, +306R, -20.8, 14.8 |
| A + pause | 4515, +0.116, +522R, -29.7, 17.6 | 8139, +0.134, +1088R, -35.3, 30.8 | 2452, +0.122, +298R, -24.1, 12.4 |
| **A + throttle** | 4901, +0.097, +474R, **-22.2**, **21.3** | 8773, +0.122, +1074R, **-31.0**, **34.7** | 2655, +0.110, +292R, **-20.1**, **14.5** |
| B + throttle | 2527, +0.099, +250R, -18.4, 13.5 | 3889, +0.155, +604R, -16.7, 36.2 | 1311, +0.143, +188R, -14.4, 13.0 |

3 worst drawdowns in A: 2019-21: 2020-08-16 to 2020-10-05 -28.5R (321 trades), 2021-08-12 to 08-27 -20.5R, 2021-02-03 to 02-09 -18.8R. 2022-25: 2023-08-08 to 08-29 -41.4R (106 trades), 2025-06-26 to 07-21 -27.7R, 2024-09-20 to 10-10 -25.7R. 2025-26: 2026-04-20 to 05-15 -28.9R (189 trades), 2026-01-17 to 01-27 -17.1R, 2025-11-06 to 11-28 -15.2R.

Read:
- Losses do not cluster: 44-47% of trades lose, and after 3 losses in a row 44-46% still lose. A pause rule has nothing to work with (and it does little).
- Throttle is the best simple rule. It cuts the dip by 22-30% on all three files and keeps 88-93% of the profit. R/dip rises on all three (+13% to +28%).
- Day cap helps on two files (dip -28% and -26%) and does nothing on 2019-21.
- Outside the box, trades are better (+0.12 to +0.16R vs +0.09 to +0.11R inside) and the drop is smaller, but total R is about half. Inside-box trades hold the worst drop on 2022-25 (-47R).
- Hunt alone + floors + throttle vs Hunt V3 + floors (R/dip): 21.3 vs 9.4, 34.7 vs 36.1, 14.5 vs 10.7. It earns about 1.5-2x the profit.
- At $50 risk, per year, Hunt alone + floors + throttle: about $11,850 / $14,650 / $13,500 with worst drops $1,110 / $1,550 / $1,005.

## Box filter correction (closed 1h bars only)

The Hunt V3 filter read the box state of the 1h bar that contains the entry, which is not finished. Fixed to use the last closed 1h bar (what you see live). Run with `scripts/run_box_lag_check.py`, Hunt V3 Hunt file (no floors).

| File | Reading | Hunt outside the box | Hunt V3 |
|---|---|---|---|
| 2025-26 | old (peeks) | 1007, +0.151, +153R, dip -20.5, R/dip 7.5 | 950, +0.191, +182R, dip -15.8, 11.5 |
| | fixed | 977, +0.119, +117R, dip -23.2, 5.0 | 954, +0.169, +161R, dip -16.6, 9.7 |
| 2019-21 | old | 1904, +0.126, +240R, dip -21.7, 11.0 | 1526, +0.152, +231R, dip -40.9, 5.7 |
| | fixed | 1886, +0.096, +182R, dip -29.7, 6.1 | 1560, +0.112, +174R, dip -54.4, 3.2 |
| 2022-25 | old | 2867, +0.193, +552R, dip -18.9, 29.2 | 2549, +0.208, +531R, dip -23.8, 22.3 |
| | fixed | 2808, +0.169, +475R, dip -22.7, 21.0 | 2602, +0.200, +520R, dip -21.9, 23.7 |

Read:
- The peek flattered the box filter. Hunt outside the box loses 0.024-0.032R per trade when fixed. Hunt V3 total R falls 12%, 25% and 2%; the 2019-21 dip gets worse (-40.9 to -54.4R).
- Fixed outside-box Hunt vs plain Hunt (avg R, 2019-21 / 2022-25 / 2025-26): +0.096 vs +0.108, +0.169 vs +0.124, +0.119 vs +0.106. The box filter helps only on 2022-25.
- Fixed Hunt V3 at $50 risk per year: about $4,350 / $7,100 / $7,450, with worst drops $2,720 / $1,095 / $830.
- Not affected: Hunt alone with floors (+536R, +1156R, +325R) and Hunt alone with floors and throttle (+474R, +1074R, +292R; dips -22.2, -31.0, -20.1). Hunt alone + floors + throttle is now ahead of Hunt V3 on every file.
- The lock file `config/experiments/lock-3-hunt-v3.md` still shows the old 2025-26 numbers (950 trades, +0.191R, dip -15.8R). Corrected: 954 trades, +0.169R, dip -16.6R.

Hunt V3 + Floors with the fixed box (`scripts/run_box_lag_check.py <file> floors`, floors Hunt file):

| File | Reading | Hunt outside the box | Hunt V3 + Floors |
|---|---|---|---|
| 2025-26 | old (peeks) | 1311, +0.158, +208R, dip -16.2, R/dip 12.8 | 1211, +0.188, +228R, dip -21.2, 10.7 |
| | fixed | 1293, +0.135, +174R, dip -19.0, 9.2 | 1229, +0.165, +203R, dip -22.7, 8.9 |
| 2019-21 | old | 2527, +0.117, +297R, dip -25.8, 11.5 | 1976, +0.133, +263R, dip -28.1, 9.4 |
| | fixed | 2516, +0.093, +234R, dip -27.7, 8.5 | 2027, +0.114, +230R, dip -39.9, 5.8 |
| 2022-25 | old | 3889, +0.161, +627R, dip -20.4, 30.7 | 3353, +0.211, +709R, dip -19.6, 36.1 |
| | fixed | 3837, +0.133, +511R, dip -20.1, 25.5 | 3420, +0.186, +636R, dip -19.1, 33.4 |

- The "old" rows match the earlier floors-in-the-engine numbers, so the check is wired correctly.
- Fixed Hunt V3 + Floors vs fixed Hunt V3 (no floors): total R +32%, +22%, +26% (+174 to +230, +520 to +636, +161 to +203). Dip better on 2019-21 (-54.4 to -39.9) and 2022-25 (-21.9 to -19.1), worse on 2025-26 (-16.6 to -22.7).
- Hunt V3 + Floors (fixed) vs Hunt + Floors + Throttle, R/dip: 5.8 vs 21.3, 33.4 vs 34.7, 8.9 vs 14.5. Hunt + Floors + Throttle is ahead or equal on every file and earns about 2x on 2019-21 and 2025-26.
- Fixed Hunt V3 + Floors at $50 risk per year: about $5,750 / $8,700 / $9,400, worst drops $1,995 / $955 / $1,135.

## Step 8 room-to-run veto test, 2022-25

Optional swing veto from the user's doc: drop a swing to CHOP when price is within 0.25 ATR of the 7-bar 4h high (swing up) or low (swing down). `room` includes the newest bar in the 7; `room-ex` leaves it out; `-block` skips the vetoed trade instead of allowing both sides. Off by default. Run with `scripts/run_room_test.bat`.

| Variant | Hunt alone | Hunt V3 |
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
| | Hunt V3 | 1526 | +0.152 | +231 | -40.9 | 5.7 |
| | Swing Hunt + chop | 462 | +0.217 | +100 | -29.3 | 3.4 |
| 2022-25 | Plain Hunt | 6427 | +0.124 | +798 | -27.9 | **28.7** |
| | Hunt V3 | 2549 | +0.208 | +531 | -23.8 | 22.3 |
| | Swing Hunt + chop | 891 | +0.251 | +224 | -24.4 | 9.2 |
| | V3 + Step 8 (room) | 2577 | +0.197 | +508 | -24.9 | 20.4 |
| 2025-26 | Plain Hunt | 1981 | +0.106 | +211 | -32.3 | 6.5 |
| | Hunt V3 | 950 | +0.191 | +182 | -15.8 | **11.5** |
| | Swing Hunt + chop | 288 | +0.422 | +122 | -19.6 | 6.2 |

Read:
- Hunt V3 has the best average per trade of the three whole-engine versions except swing+chop, but plain Hunt makes more total R on every file and a better R/dip on two of three (2019-21, 2022-25).
- Hunt V3 wins only on 2025-26, the file it was locked on. On the two other files it is worse than plain Hunt on R/dip.
- Swing Hunt + chop has the highest avg R and the lowest total R everywhere.
- Step 8 made V3 slightly worse.

## Hunt V3 rule, short

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
