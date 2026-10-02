# Desktop Hunt history, ported for a local compare

Source: https://github.com/Maxchea20/mib-trader-desktop

- Pre-S1/S2 Hunt is snapshot 3d98c41, weather V1, file backend/src/brain/weather.py.
- The 4h soften is commit 50fb74d on 2026-09-22. A 1 ATR retrace from the 8-bar 4h extreme turns SWING_UP or SWING_DOWN into CHOP. CHOP allows both sides.
- This port is not the whole C-FI brain. It keeps the weather gate, a fresh 15m CHoCH or BOS with the extended-BOS reject, the third 5m close through the prior 15m high or low, and the next 1m open. It does not copy the internal pivot-2 gate, the rearm, or the 5m tap.
- Stop is 1.5 ATR. Target is 2.5 ATR. Fee is 2 bp a side. Same-bar stop fills first.
- weather-v1 is the hard gate. weather-v1b is the soften. A higher number on one file is not a rule.
