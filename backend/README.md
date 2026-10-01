Place the Binance research database here:

    backend/research_binance.db

Place the live/paper candle database here when that adapter exists:

    backend/market_data_clean.db

Do not commit either file. Backtests must use the Binance file only.
The audit script prints the discovered schema. Do not rename columns by hand
until the audit report shows the loader cannot identify them.
