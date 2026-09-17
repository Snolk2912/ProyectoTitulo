import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# Configuración
FILE_SUFFIX  = "20190910_20220131"
FAST_PERIOD  = 17
SLOW_PERIOD  = 50
WINDOW_ID    = 5

if FAST_PERIOD >= SLOW_PERIOD:
    raise ValueError("FAST_PERIOD debe ser menor que SLOW_PERIOD")

# Rutas
project_root   = Path(__file__).resolve().parent.parent
processed_path = project_root / "data_processed"
results_path   = project_root / "results"
results_path.mkdir(exist_ok=True)

input_file   = processed_path / f"BTCUSDT_15m_{FILE_SUFFIX}_windows.csv"
output_plot  = results_path   / f"fsm_2sma_window{WINDOW_ID}_{FILE_SUFFIX}.png"
output_transitions = results_path / f"fsm_transitions_window{WINDOW_ID}_{FILE_SUFFIX}.csv"

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
df["signal_long"]  = (
    (df["sma_fast"].shift(1) <= df["sma_slow"].shift(1)) &
    (df["sma_fast"] > df["sma_slow"])
).fillna(False)

df["signal_short"] = (
    (df["sma_fast"].shift(1) >= df["sma_slow"].shift(1)) &
    (df["sma_fast"] < df["sma_slow"])
).fillna(False)

# FSM
WAITING_LONG  = "WAITING_LONG"
LONG_OPEN     = "LONG_OPEN"
WAITING_SHORT = "WAITING_SHORT"
SHORT_OPEN    = "SHORT_OPEN"

state       = WAITING_LONG
transitions = []

for i, row in df.iterrows():
    if not row["signal_long"] and not row["signal_short"]:
        continue

    event      = "signal_long" if row["signal_long"] else "signal_short"
    prev_state = state
    action     = None

    if state == WAITING_LONG  and event == "signal_long":
        state  = LONG_OPEN
        action = "open_long"
    elif state == LONG_OPEN   and event == "signal_short":
        state  = WAITING_SHORT
        action = "close_long"
    elif state == WAITING_SHORT and event == "signal_short":
        state  = SHORT_OPEN
        action = "open_short"
    elif state == SHORT_OPEN  and event == "signal_long":
        state  = WAITING_LONG
        action = "close_short"
    else:
        action = "ignored"

    transitions.append({
        "open_time":  row["open_time"],
        "close":      row["close"],
        "sma_fast":   row["sma_fast"],
        "event":      event,
        "prev_state": prev_state,
        "new_state":  state,
        "action":     action
    })

trans_df   = pd.DataFrame(transitions)
real_df    = trans_df[trans_df["action"] != "ignored"]
ignored_df = trans_df[trans_df["action"] == "ignored"]

# Resumen
print(f"Ventana ID:             {WINDOW_ID}")
print(f"Filas analizadas:       {len(df)}")
print(f"SMA rápida:             {FAST_PERIOD}")
print(f"SMA lenta:              {SLOW_PERIOD}")
print(f"Señales LONG:           {df['signal_long'].sum()}")
print(f"Señales SHORT:          {df['signal_short'].sum()}")
print(f"Transiciones reales:    {len(real_df)}")
print(f"Eventos ignorados:      {len(ignored_df)}")
print("\nConteo de acciones:")
print(real_df["action"].value_counts())
print("\nEventos ignorados por estado:")
print(ignored_df.groupby(["prev_state", "event"]).size()
                .reset_index(name="count"))

# Guardar transiciones reales
real_df.to_csv(output_transitions, index=False)
print(f"\nTransiciones guardadas en: {output_transitions}")

# Gráfico
fig, ax = plt.subplots(figsize=(18, 8))

ax.plot(df["open_time"], df["close"],
        color="steelblue", linewidth=0.8, alpha=0.75, label="Precio cierre")
ax.plot(df["open_time"], df["sma_fast"],
        color="orange", linewidth=1.2, label=f"SMA rápida ({FAST_PERIOD})")
ax.plot(df["open_time"], df["sma_slow"],
        color="green",  linewidth=1.4, label=f"SMA lenta ({SLOW_PERIOD})")

# Marcadores sobre sma_fast en el momento del cruce
for action, marker, color, label in [
    ("open_long",   "^", "green",   "Open LONG"),
    ("close_long",  "x", "darkgreen", "Close LONG"),
    ("open_short",  "v", "red",     "Open SHORT"),
    ("close_short", "x", "darkred", "Close SHORT"),
]:
    subset = real_df[real_df["action"] == action]
    ax.scatter(subset["open_time"], subset["sma_fast"],
               marker=marker, s=80, color=color,
               edgecolors="black", linewidths=0.5,
               zorder=4, label=label)

# Eventos ignorados en gris pequeño
ax.scatter(ignored_df["open_time"], ignored_df["sma_fast"],
           marker="o", s=15, color="gray", alpha=0.4,
           zorder=3, label="Ignorado")

ax.set_title(f"BTCUSDT 15m — FSM 2-SMA | Ventana {WINDOW_ID}\n"
             f"SMA fast={FAST_PERIOD}, SMA slow={SLOW_PERIOD}")
ax.set_xlabel("Tiempo (UTC)")
ax.set_ylabel("Precio (USDT)")
ax.legend()
plt.tight_layout()

plt.savefig(output_plot, dpi=200)
plt.show()
print(f"\nGráfico guardado en: {output_plot}")