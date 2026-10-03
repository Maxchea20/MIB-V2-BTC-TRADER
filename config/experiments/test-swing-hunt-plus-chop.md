# Test: swing Hunt plus the chop book

Written 2026-10-03. Not a live book. Hunt trades only in swing weather. The chop book trades only inside the 1-hour failed-push box. There is no Hunt in CHOP weather.

## Rule

- Hunt: the desktop Hunt C-FI file, kept only when the weather is SWING_UP (longs) or SWING_DOWN (shorts). CHOP-weather Hunt trades are dropped.
- Chop: the lock 3 chop book, unchanged. Entry on a line reject or an outer-quarter turn, stop on a close through the entry line, target is the other line.
- One position. If either book is in a trade, the other waits.
- Fee 2 bp a side. Same-bar stop wins.
- Step 8 (room to run) is not used. It lost on 2022-25.

## Evidence

Run with `scripts/run_swing_only.py`, on the saved Hunt file of each period.

| File | Trades | Avg R | Max dip | Total R | Hunt / chop |
|---|---|---|---|---|---|
| 2019-21 | 462 | +0.217 | -29.3 | +100 | 273 / 189 |
| 2022-25 | 891 | +0.251 | -24.4 | +224 | 568 / 323 |
| 2025-26 | 288 | +0.422 | -19.6 | +122 | 177 / 111 |

Per trade it beats both Hunt V3 (+0.152, +0.208, +0.191) and plain Hunt (+0.108, +0.124, +0.107) on every file. Total R is lower than Hunt V3 (231, 532, 182) because it takes fewer trades.

## Known weak points

- Swing Hunt alone is flat on 2019-21 (-0.002R, dip -36.2). The chop book carries that period.
- Swing is only 15-17% of Hunt trades, so the swing sample is small.
- Chop wins about 20% of the time on large targets. Its dip was -26 to -31R on the full files.
- Not tested: chop alone, both books open at once.
