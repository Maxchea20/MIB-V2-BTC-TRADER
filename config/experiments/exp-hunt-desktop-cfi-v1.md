# Desktop Hunt C-FI, one backtest

Source snapshot 3d98c41 in mib-trader-desktop, before S1 and S2.

Gates, in order:
- C-fast: fresh 15m CHoCH, or a BOS that is not the third in a row. Pivot is 5.
- Internal: the same event on pivot 2.
- Rearm: the last valid 15m event is still in force. A later 5m may answer it.

Answer, from Hunt V3:
- A 5m close through the prior 15m high or low by at least 0.15 ATR fires.
- Slot 2 or 3 can fire if an earlier 5m only wicked and this close holds the level.
- Fill is the broken 15m level. If that same 5m also hits the stop, the stop wins.

Weather is V1. SWING_UP allows long only. SWING_DOWN allows short only. CHOP allows both. The 22 September 1 ATR unlock is not in this run.

Stop 1.5 ATR. Target 2.5 ATR. Fee 2 bp a side. One position. This is the rule port, not a line copy of the desktop brain.
