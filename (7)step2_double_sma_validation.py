import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# Configuración
FILE_SUFFIX  = "20190910_20220131"
FAST_PERIOD  = 17    # ejemplo de la Figura 1 del paper
SLOW_PERIOD  = 50
WINDOW_ID    = 5     # ventana a visualizar

if FAST_PERIOD >= SLOW_PERIOD:
    raise ValueError("FAST_PERIOD debe ser menor que SLOW_PERIOD")

# Rutas
project_root   = Path(__file__).resolve().parent.parent
processed_path = project_root / "data_processed"
results_path   = project_root / "results"
results_path.mkdir(exist_ok=True)

input_file  = processed_path / f"BTCUSDT_15m_{FILE_SUFFIX}_windows.csv"
output_plot = results_path   / f"2sma_validation_window{WINDOW_ID}_{FILE_SUFFIX}.png"

# Carga de una ventana específica
df = pd.read_csv(input_file)
df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
df = df[df["window_id"] == WINDOW_ID][["open_time", "close"]].copy()
df["close"] = pd.to_numeric(df["close"], errors="coerce")
df = df.dropna().sort_values("open_time").reset_index(drop=True)

# Cálculo de SMAs
df["sma_fast"] = df["close"].rolling(window=FAST_PERIOD, min_periods=FAST_PERIOD).mean()
df["sma_slow"] = df["close"].rolling(window=SLOW_PERIOD, min_periods=SLOW_PERIOD).mean()

# Detección de cruces
df["signal_long"] = (
    (df["sma_fast"].shift(1) <= df["sma_slow"].shift(1)) &
    (df["sma_fast"] > df["sma_slow"])
)
df["signal_short"] = (
    (df["sma_fast"].shift(1) >= df["sma_slow"].shift(1)) &
    (df["sma_fast"] < df["sma_slow"])
)
df["signal_long"]  = df["signal_long"].fillna(False)
df["signal_short"] = df["signal_short"].fillna(False)

long_df  = df[df["signal_long"]].copy()
short_df = df[df["signal_short"]].copy()

# Resumen
print(f"Ventana ID:          {WINDOW_ID}")
print(f"Filas analizadas:    {len(df)}")
print(f"SMA rápida (fast):   {FAST_PERIOD}")
print(f"SMA lenta  (slow):   {SLOW_PERIOD}")
print(f"NaN en sma_fast:     {df['sma_fast'].isna().sum()}")
print(f"NaN en sma_slow:     {df['sma_slow'].isna().sum()}")
print(f"Señales LONG:        {df['signal_long'].sum()}")
print(f"Señales SHORT:       {df['signal_short'].sum()}")

print("\nPrimeras señales LONG:")
print(long_df[["open_time", "close", "sma_fast", "sma_slow"]].head())
print("\nPrimeras señales SHORT:")
print(short_df[["open_time", "close", "sma_fast", "sma_slow"]].head())

# Gráfico
fig, ax = plt.subplots(figsize=(16, 7))

ax.plot(df["open_time"], df["close"],
        color="steelblue", linewidth=0.8, alpha=0.8, label="Precio cierre")
ax.plot(df["open_time"], df["sma_fast"],
        color="orange", linewidth=1.4, label=f"SMA rápida ({FAST_PERIOD})")
ax.plot(df["open_time"], df["sma_slow"],
        color="green",  linewidth=1.6, label=f"SMA lenta ({SLOW_PERIOD})")

# Marcadores en el punto de cruce real (valor de sma_fast)
ax.scatter(long_df["open_time"],  long_df["sma_fast"],
           marker="^", s=80, color="green", edgecolors="black",
           linewidths=0.5, zorder=4, label="Señal LONG")
ax.scatter(short_df["open_time"], short_df["sma_fast"],
           marker="v", s=80, color="red",   edgecolors="black",
           linewidths=0.5, zorder=4, label="Señal SHORT")

ax.set_title(f"BTCUSDT 15m — Validación 2-SMA | Ventana {WINDOW_ID}\n"
             f"SMA fast={FAST_PERIOD}, SMA slow={SLOW_PERIOD}")
ax.set_xlabel("Tiempo (UTC)")
ax.set_ylabel("Precio (USDT)")
ax.legend()
plt.tight_layout()

plt.savefig(output_plot, dpi=200)
plt.show()
print(f"\nGráfico guardado en: {output_plot}")