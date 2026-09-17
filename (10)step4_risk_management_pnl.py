import pandas as pd
from pathlib import Path

# Configuración
FILE_SUFFIX  = "20190910_20220131"
WINDOW_ID    = 16       # ventana a simular

# Parámetros de la mejor configuración del paper (Tabla 3)
FAST_PERIOD   = 171
SLOW_PERIOD   = 356
ALPHA_LONG    = 0.972   # trailing stop-loss para LONG
ALPHA_SHORT   = 1.023   # trailing stop-loss para SHORT
BETA_LONG     = 3.447   # stop-win para LONG  (344% del precio de entrada)
BETA_SHORT    = 0.472   # stop-win para SHORT (47% del precio de entrada)

FEE_RATE      = 0.0004  # 0.04% por operación (Binance Futures)
INITIAL_CAPITAL = 1.0

# Rutas
project_root   = Path(__file__).resolve().parent.parent
processed_path = project_root / "data_processed"
results_path   = project_root / "results"
results_path.mkdir(exist_ok=True)

input_file    = processed_path / f"BTCUSDT_15m_{FILE_SUFFIX}_windows.csv"
output_trades = results_path   / f"trades_window{WINDOW_ID}_{FILE_SUFFIX}.csv"

# Carga de una ventana específica
df = pd.read_csv(input_file)
df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
df = df[df["window_id"] == WINDOW_ID].copy()

for col in ["open", "high", "low", "close"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df = (df.dropna(subset=["open_time", "open", "high", "low", "close"])
        .sort_values("open_time")
        .reset_index(drop=True))

# Cálculo de SMAs
df["sma_fast"] = df["close"].rolling(window=FAST_PERIOD, min_periods=FAST_PERIOD).mean()
df["sma_slow"] = df["close"].rolling(window=SLOW_PERIOD, min_periods=SLOW_PERIOD).mean()

df["signal_long"]  = (
    (df["sma_fast"].shift(1) <= df["sma_slow"].shift(1)) &
    (df["sma_fast"] > df["sma_slow"])
).fillna(False)

df["signal_short"] = (
    (df["sma_fast"].shift(1) >= df["sma_slow"].shift(1)) &
    (df["sma_fast"] < df["sma_slow"])
).fillna(False)

# FSM + Gestión de riesgo
WAITING_LONG  = "WAITING_LONG"
LONG_OPEN     = "LONG_OPEN"
WAITING_SHORT = "WAITING_SHORT"
SHORT_OPEN    = "SHORT_OPEN"

state   = WAITING_LONG
capital = INITIAL_CAPITAL
trades  = []

entry_time  = entry_price = entry_index = None
extreme_price = None   # max para long, min para short

for i, row in df.iterrows():
    if pd.isna(row["sma_fast"]) or pd.isna(row["sma_slow"]):
        continue

    t     = row["open_time"]
    close = row["close"]
    high  = row["high"]
    low   = row["low"]

    # ── WAITING_LONG ──────────────────────────────────────────────
    if state == WAITING_LONG:
        if row["signal_long"]:
            state        = LONG_OPEN
            entry_time   = t
            entry_price  = close
            entry_index  = i
            extreme_price = high
        continue

    # ── LONG_OPEN ─────────────────────────────────────────────────
    if state == LONG_OPEN:
        extreme_price = max(extreme_price, high)

        trailing_stop = ALPHA_LONG * extreme_price
        stop_win      = BETA_LONG  * entry_price

        exit_reason = exit_price = None

        if low <= trailing_stop:
            exit_reason = "trailing_stop_long"
            exit_price  = trailing_stop
        elif high >= stop_win:
            exit_reason = "stop_win_long"
            exit_price  = stop_win
        elif row["signal_short"]:
            exit_reason = "signal_short_close_long"
            exit_price  = close

        if exit_reason:
            gross  = exit_price / entry_price
            net    = gross * (1 - FEE_RATE) ** 2
            cap_before = capital
            capital    = capital * net

            trades.append({
                "side":               "long",
                "entry_index":        entry_index,
                "exit_index":         i,
                "entry_time":         entry_time,
                "exit_time":          t,
                "entry_price":        entry_price,
                "exit_price":         exit_price,
                "exit_reason":        exit_reason,
                "gross_return":       gross,
                "net_return":         net,
                "capital_before":     cap_before,
                "capital_after":      capital,
                "pnl":                capital - cap_before
            })

            entry_time = entry_price = entry_index = extreme_price = None
            state = WAITING_SHORT
        continue

    # ── WAITING_SHORT ─────────────────────────────────────────────
    if state == WAITING_SHORT:
        if row["signal_short"]:
            state         = SHORT_OPEN
            entry_time    = t
            entry_price   = close
            entry_index   = i
            extreme_price = low
        continue

    # ── SHORT_OPEN ────────────────────────────────────────────────
    if state == SHORT_OPEN:
        extreme_price = min(extreme_price, low)

        trailing_stop = ALPHA_SHORT * extreme_price
        stop_win      = BETA_SHORT  * entry_price

        exit_reason = exit_price = None

        if high >= trailing_stop:
            exit_reason = "trailing_stop_short"
            exit_price  = trailing_stop
        elif low <= stop_win:
            exit_reason = "stop_win_short"
            exit_price  = stop_win
        elif row["signal_long"]:
            exit_reason = "signal_long_close_short"
            exit_price  = close

        if exit_reason:
            gross  = entry_price / exit_price
            net    = gross * (1 - FEE_RATE) ** 2
            cap_before = capital
            capital    = capital * net

            trades.append({
                "side":               "short",
                "entry_index":        entry_index,
                "exit_index":         i,
                "entry_time":         entry_time,
                "exit_time":          t,
                "entry_price":        entry_price,
                "exit_price":         exit_price,
                "exit_reason":        exit_reason,
                "gross_return":       gross,
                "net_return":         net,
                "capital_before":     cap_before,
                "capital_after":      capital,
                "pnl":                capital - cap_before
            })

            entry_time = entry_price = entry_index = extreme_price = None
            state = WAITING_LONG
        continue

# Resultados
trades_df = pd.DataFrame(trades)
trades_df.to_csv(output_trades, index=False)

roi = capital / INITIAL_CAPITAL

print("=" * 50)
print(f"Ventana ID:        {WINDOW_ID}")
print(f"Trades cerrados:   {len(trades_df)}")
print(f"Capital inicial:   {INITIAL_CAPITAL:.4f}")
print(f"Capital final:     {capital:.4f}")
print(f"ROI:               {roi:.4f}  ({(roi - 1) * 100:.2f}%)")
print("=" * 50)

if len(trades_df) > 0:
    print("\nTrades por lado:")
    print(trades_df["side"].value_counts())
    print("\nRazones de cierre:")
    print(trades_df["exit_reason"].value_counts())
    print(f"\nPnL total: {trades_df['pnl'].sum():.6f}")

print(f"\nTrades guardados en: {output_trades}")