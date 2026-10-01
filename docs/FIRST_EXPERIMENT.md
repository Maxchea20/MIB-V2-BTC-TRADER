# exp-s1-structure-v1

Hypothesis: a 1H confirmed uptrend or downtrend, a 15M pullback that holds the last 1H swing, and a 5M close back through the pullback micro swing, has different net expectancy from a random entry with the same stop and target. This run does not answer that. It produces the structure-only sample.

Not in this run: volume, RSI, MACD, Bollinger, AI, order book, live orders.

## Rules

- Long bias: last two confirmed 1H highs are rising and last two confirmed 1H lows are rising. Short is the mirror. Pivot left=3, right=3. Unconfirmed pivots are ignored.
- Pullback: a confirmed 15M swing in the pullback direction holds beyond the last 1H invalidation swing.
- Trigger: 5M close through the last 5M micro swing formed after that 15M pullback was confirmed.
- Entry: next 1M open. Long fill adds 1 tick and 0.5 bp. Short fill subtracts them.
- Stop: 15M pullback extreme plus 0.15 x 15M ATR(14), on the invalidation side.
- Target: 1.5R from the filled entry to that stop.
- Skip if `(price - impulse origin) / 1H ATR > 1.5`.
- Skip if the 1M open has already moved more than 0.6R from the 5M close toward the target.
- One position at a time. Exit is stop, target, or end of data.
- Same-bar collision: stop.

## What to send back

The run folder under `results/exp-s1-structure-v1/`. Do not send `research_binance.db`.

Interpretation waits on those files. A large `EXTENSION` count means the 1.5 ATR cap rejected the sample. That is a measurement, not a failure of the loader.
