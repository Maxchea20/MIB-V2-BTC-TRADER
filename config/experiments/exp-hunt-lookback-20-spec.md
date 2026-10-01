# Untested user rule. Not a result.

Compared with exp-hunt-cfi-v1, which used a 5-bar confirmed 15m pivot.

- 15m sign: highest high of the past 20 bars to the left. A close above that high is the long sign. Mirror for short. No right-side confirmation wait.
- Inside the current 15m bar, any of the three 5m bars may print a CHoCH or BOS.
- On that 5m event, the 1m bars look for the entry immediately.
- 5m scan looks about twice as far as the 15m scan, up to 50 candles to the left.
- Fill must be a traded price. Do not book the level after the bar closes.
