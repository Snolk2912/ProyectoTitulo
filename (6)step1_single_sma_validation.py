import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# Configuración
FILE_SUFFIX = "20190910_20220131"
SMA_PERIOD  = 50    # período de la SMA a graficar
WINDOW_ID   = 5     # ventana a visualizar

# Rutas
project_root   = Path(__file__).resolve().parent.parent
processed_path = project_root / "data_processed"
results_path   = project_root / "results"
results_path.mkdir(exist_ok=True)

input_file  = processed_path / f"BTCUSDT_15m_{FILE_SUFFIX}_windows.csv"
output_plot = results_path   / f"sma{SMA_PERIOD}_window{WINDOW_ID}_{FILE_SUFFIX}.png"

# Carga de una ventana específica
df = pd.read_csv(input_file)
df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
df = df[df["window_id"] == WINDOW_ID][["open_time", "close"]].copy()
df["close"] = pd.to_numeric(df["close"], errors="coerce")
df = df.dropna().sort_values("open_time").reset_index(drop=True)

# Cálculo de SMA
df["sma"] = df["close"].rolling(window=SMA_PERIOD, min_periods=SMA_PERIOD).mean()

# Resumen en consola
print(f"Ventana ID:        {WINDOW_ID}")
print(f"Filas:             {len(df)}")
print(f"Período SMA:       {SMA_PERIOD}")
print(f"Primer timestamp:  {df['open_time'].min()}")
print(f"Último timestamp:  {df['open_time'].max()}")
print(f"NaN en SMA:        {df['sma'].isna().sum()} (esperado: {SMA_PERIOD - 1})")

# Gráfico
fig, ax = plt.subplots(figsize=(16, 6))

ax.plot(df["open_time"], df["close"],
        color="steelblue", linewidth=0.8, label="Precio cierre")
ax.plot(df["open_time"], df["sma"],
        color="orange", linewidth=1.5, label=f"SMA ({SMA_PERIOD})")

ax.set_title(f"BTCUSDT 15m — SMA simple | Ventana {WINDOW_ID} | Período {SMA_PERIOD}")
ax.set_xlabel("Tiempo (UTC)")
ax.set_ylabel("Precio (USDT)")
ax.legend()
plt.tight_layout()

plt.savefig(output_plot, dpi=200)
plt.show()
print(f"\nGráfico guardado en: {output_plot}")