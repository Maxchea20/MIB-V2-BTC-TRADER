# The eye: exact logic

Code: `scripts/test_hunt_exits.py` (`replay` and `_eye_fires`). Long trade described; a short trade is the same with prices flipped.

## Inputs for one trade
- Entry E, stop S = E - 1.5 ATR, target T = E + 2.5 ATR. ATR is the 15m ATR at entry and stays fixed for the trade.
- 1-minute bars from the entry bar onward (up to 3 days).

## State kept
- best: the highest 1m high since entry (starts at E).
- candles: the closed 15m candles since entry. The first one is partial, because the trade starts inside it.
- last_high_idx: the index of the 15m candle in which best last increased.

## What happens on each 1-minute bar, in this order
1. 15m candle building. The bar belongs to the 15m block `open_time // 15 min`. If it starts a new block, the previous block is closed and added to `candles`.
2. Eye check, only on that moment (a 15m candle just closed). The eye is armed when best >= E + 1.4 ATR. If armed, test the candle that just closed:
   - structure: at least 4 closed candles, and this candle's close is below the lowest low of the 3 candles before it.
   - stall: 4 or more closed candles have finished since the candle that made the last new best.
   - reversal: the candle's body is at least half of its high-low range, it closed below its open, and it closed in its bottom third.
   - hold X (X = 0.7 or 1.0): best minus this candle's close is more than X ATR.
   - any: structure or stall or reversal.
3. If a rule fired, sell the whole position at the open of the current 1m bar (the next minute after the candle closed). The trade ends.
4. Otherwise the normal checks on this 1m bar, in this order:
   - low <= S: stopped out at S (the stop wins if the bar also touches T).
   - high >= T: target hit at T.
   - update best and last_high_idx.
5. Result: R = (sale price - E, minus 2 bp fee on entry and on exit) / (1.5 ATR). If nothing ends the trade in 3 days, it is sold at the last close.

## What the eye does not do
- It never moves the stop or the target.
- It only looks at closed 15m candles, so a drop inside one candle is seen only after that candle closes.
- It only starts after the trade is 1.4 ATR in profit.

## What is a guess
Every number (1.4 ATR, 3 candles, 4 candles, half body, bottom third, 0.7 and 1.0 ATR) was picked by hand and not measured.
