import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Configuración
FILE_SUFFIX = "20190910_20220131"
RANDOM_SEED = 42

# Parámetros 2-SMA optimizado (Tabla 3 del paper)
OPT_FAST = 171
OPT_SLOW = 356
OPT_ALPHA_LONG = 0.972
OPT_ALPHA_SHORT = 1.023
OPT_BETA_LONG = 3.447
OPT_BETA_SHORT = 0.472

# Parámetros 2-SMA fijo (baseline del paper)
FIX_FAST = 50
FIX_SLOW = 200
FIX_ALPHA_LONG = 0.95
FIX_ALPHA_SHORT = 1.05
FIX_BETA_LONG = 1.10
FIX_BETA_SHORT = 0.90

FEE_RATE = 0.0004
INITIAL_CAPITAL = 1.0

# Rutas
project_root = Path(__file__).resolve().parent.parent
processed_path = project_root / "data_processed"
results_path = project_root / "results"
results_path.mkdir(exist_ok=True)

input_file = processed_path / f"BTCUSDT_15m_{FILE_SUFFIX}_windows.csv"
output_csv = results_path / f"baselines_comparison_{FILE_SUFFIX}.csv"
output_plot_roi = results_path / f"baselines_roi_{FILE_SUFFIX}.png"
output_plot_cap = results_path / f"baselines_capital_{FILE_SUFFIX}.png"

# Carga
df = pd.read_csv(input_file)
df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
for col in ["open", "high", "low", "close"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

window_ids = sorted(df["window_id"].unique())


# Simulador 2-SMA
def simulate_2sma(
    df_win,
    fast,
    slow,
    alpha_long,
    alpha_short,
    beta_long,
    beta_short,
    fee_rate,
    initial_capital,
):
    w = df_win.copy().reset_index(drop=True)

    w["sma_fast"] = w["close"].rolling(window=fast, min_periods=fast).mean()
    w["sma_slow"] = w["close"].rolling(window=slow, min_periods=slow).mean()

    w["signal_long"] = (
        (w["sma_fast"].shift(1) <= w["sma_slow"].shift(1)) &
        (w["sma_fast"] > w["sma_slow"])
    ).fillna(False)
    w["signal_short"] = (
        (w["sma_fast"].shift(1) >= w["sma_slow"].shift(1)) &
        (w["sma_fast"] < w["sma_slow"])
    ).fillna(False)

    WAITING_LONG = "WAITING_LONG"
    LONG_OPEN = "LONG_OPEN"
    WAITING_SHORT = "WAITING_SHORT"
    SHORT_OPEN = "SHORT_OPEN"

    state = WAITING_LONG
    capital = initial_capital
    entry_price = None
    extreme_price = None

    for _, row in w.iterrows():
        if pd.isna(row["sma_fast"]) or pd.isna(row["sma_slow"]):
            continue

        high = row["high"]
        low = row["low"]
        close = row["close"]

        # Esperando señal LONG
        if state == WAITING_LONG:
            if row["signal_long"]:
                state = LONG_OPEN
                entry_price = close
                extreme_price = high
            continue

        # Long abierto
        if state == LONG_OPEN:
            extreme_price = max(extreme_price, high)
            t_stop = alpha_long * extreme_price
            t_win = beta_long * entry_price
            exit_price = None

            if low <= t_stop:
                exit_price = t_stop
            elif high >= t_win:
                exit_price = t_win
            elif row["signal_short"]:
                exit_price = close

            if exit_price:
                capital *= (exit_price / entry_price) * (1 - fee_rate) ** 2
                entry_price = None
                extreme_price = None
                state = WAITING_SHORT
            continue

        # Esperando señal SHORT
        if state == WAITING_SHORT:
            if row["signal_short"]:
                state = SHORT_OPEN
                entry_price = close
                extreme_price = low
            continue

        # Short abierto
        if state == SHORT_OPEN:
            extreme_price = min(extreme_price, low)
            t_stop = alpha_short * extreme_price
            t_win = beta_short * entry_price
            exit_price = None

            if high >= t_stop:
                exit_price = t_stop
            elif low <= t_win:
                exit_price = t_win
            elif row["signal_long"]:
                exit_price = close

            if exit_price:
                capital *= (entry_price / exit_price) * (1 - fee_rate) ** 2
                entry_price = None
                extreme_price = None
                state = WAITING_LONG
            continue

    return capital


# Buy and Hold
def simulate_buy_and_hold(df_win, fee_rate, initial_capital):
    w = df_win.dropna(subset=["close"]).reset_index(drop=True)
    entry_price = w.iloc[0]["close"]
    exit_price = w.iloc[-1]["close"]
    capital = initial_capital * (exit_price / entry_price) * (1 - fee_rate) ** 2
    return capital


# Random Walk
def simulate_random_walk(df_win, fee_rate, initial_capital, seed):
    rng = np.random.default_rng(seed)
    w = df_win.dropna(subset=["close"]).reset_index(drop=True)
    returns = w["close"].pct_change().dropna()

    mu = returns.mean()
    std = returns.std()

    n_steps = len(w)
    simulated_rets = rng.normal(mu, std, n_steps)

    simulated_price = initial_capital * np.prod(1 + simulated_rets)
    capital = simulated_price * (1 - fee_rate) ** 2
    return capital


# Loop sobre todas las ventanas
results = []

for wid in window_ids:
    df_win = df[df["window_id"] == wid].copy()
    split = df_win["split"].iloc[0]

    cap_opt = simulate_2sma(
        df_win, OPT_FAST, OPT_SLOW,
        OPT_ALPHA_LONG, OPT_ALPHA_SHORT,
        OPT_BETA_LONG, OPT_BETA_SHORT,
        FEE_RATE, INITIAL_CAPITAL,
    )

    cap_fix = simulate_2sma(
        df_win, FIX_FAST, FIX_SLOW,
        FIX_ALPHA_LONG, FIX_ALPHA_SHORT,
        FIX_BETA_LONG, FIX_BETA_SHORT,
        FEE_RATE, INITIAL_CAPITAL,
    )

    cap_bah = simulate_buy_and_hold(df_win, FEE_RATE, INITIAL_CAPITAL)
    cap_rw = simulate_random_walk(
        df_win, FEE_RATE, INITIAL_CAPITAL, seed=RANDOM_SEED,
    )

    results.append({
        "window_id": wid,
        "split": split,
        "roi_2sma_opt": cap_opt,
        "roi_2sma_fix": cap_fix,
        "roi_bah": cap_bah,
        "roi_rw": cap_rw,
    })

    print(
        f"Ventana {wid:>2} [{split:>5}] | "
        f"2SMA-opt: {cap_opt:.4f} | "
        f"2SMA-fix: {cap_fix:.4f} | "
        f"B&H: {cap_bah:.4f} | "
        f"RW: {cap_rw:.4f}"
    )

results_df = pd.DataFrame(results)
results_df.to_csv(output_csv, index=False)

# Resumen estadístico
strategies = {
    "2SMA-opt": "roi_2sma_opt",
    "2SMA-fix": "roi_2sma_fix",
    "Buy&Hold": "roi_bah",
    "RndWalk": "roi_rw",
}

print("\n" + "=" * 65)
print(f"{'RESUMEN — TODAS LAS VENTANAS':^65}")
print("=" * 65)
print(f"{'Estrategia':<12} {'Media':>8} {'Std':>8} {'Min':>8} "
      f"{'Max':>8} {'ROI%':>8}")
print("-" * 65)
for name, col in strategies.items():
    m = results_df[col].mean()
    s = results_df[col].std()
    mn = results_df[col].min()
    mx = results_df[col].max()
    roi = (m - 1) * 100
    print(f"{name:<12} {m:>8.4f} {s:>8.4f} {mn:>8.4f} {mx:>8.4f} {roi:>7.2f}%")

print("\n" + "=" * 65)
print(f"{'RESUMEN — SOLO VENTANAS TEST':^65}")
print("=" * 65)
print(f"{'Estrategia':<12} {'Media':>8} {'Std':>8} {'Min':>8} "
      f"{'Max':>8} {'ROI%':>8}")
print("-" * 65)
test_df = results_df[results_df["split"] == "test"]
for name, col in strategies.items():
    m = test_df[col].mean()
    s = test_df[col].std()
    mn = test_df[col].min()
    mx = test_df[col].max()
    roi = (m - 1) * 100
    print(f"{name:<12} {m:>8.4f} {s:>8.4f} {mn:>8.4f} {mx:>8.4f} {roi:>7.2f}%")

# Debug: señales 2SMA-opt por ventana
print("\n" + "=" * 55)
print("DEBUG — señales 2SMA-opt por ventana")
print("=" * 55)

for wid in window_ids:
    df_win = df[df["window_id"] == wid].copy()
    split = df_win["split"].iloc[0]

    w = df_win.copy().reset_index(drop=True)
    w["sma_fast"] = w["close"].rolling(
        window=OPT_FAST, min_periods=OPT_FAST
    ).mean()
    w["sma_slow"] = w["close"].rolling(
        window=OPT_SLOW, min_periods=OPT_SLOW
    ).mean()

    filas_utiles = w["sma_slow"].notna().sum()

    w["signal_long"] = (
        (w["sma_fast"].shift(1) <= w["sma_slow"].shift(1)) &
        (w["sma_fast"] > w["sma_slow"])
    ).fillna(False)
    w["signal_short"] = (
        (w["sma_fast"].shift(1) >= w["sma_slow"].shift(1)) &
        (w["sma_fast"] < w["sma_slow"])
    ).fillna(False)

    n_long = w["signal_long"].sum()
    n_short = w["signal_short"].sum()

    print(
        f"W{wid:>2} [{split:>5}] | "
        f"filas útiles: {filas_utiles:>4} | "
        f"señales long: {n_long:>2} | "
        f"señales short: {n_short:>2}"
    )

# Gráfico 1: ROI por ventana (barras)
fig, ax = plt.subplots(figsize=(18, 6))

x = np.arange(len(results_df))
width = 0.2
colors = ["steelblue", "orange", "green", "gray"]

for idx, (name, col) in enumerate(strategies.items()):
    roi_vals = (results_df[col] - 1) * 100
    ax.bar(x + idx * width, roi_vals, width,
           label=name, color=colors[idx], alpha=0.8)

test_start = results_df[results_df["split"] == "test"].index[0]
ax.axvline(x=test_start - 0.1, color="red", linestyle="--",
           linewidth=1.5, label="Inicio test")

ax.axhline(y=0, color="black", linewidth=0.8)
ax.set_xticks(x + width * 1.5)
ax.set_xticklabels([f"W{i}" for i in results_df["window_id"]], fontsize=8)
ax.set_xlabel("Ventana")
ax.set_ylabel("ROI (%)")
ax.set_title("Comparación de estrategias por ventana — ROI %")
ax.legend()
plt.tight_layout()
plt.savefig(output_plot_roi, dpi=150)
plt.show()

# Gráfico 2: capital acumulado en ventanas de test
fig, ax = plt.subplots(figsize=(12, 5))

for name, col in strategies.items():
    ax.plot(test_df["window_id"], test_df[col],
            marker="o", linewidth=1.5, label=name)

ax.axhline(y=1.0, color="black", linestyle="--", linewidth=0.8)
ax.set_xlabel("Ventana (test)")
ax.set_ylabel("Capital final (inicio = 1.0)")
ax.set_title("Capital final por ventana de test — comparación de estrategias")
ax.legend()
plt.tight_layout()
plt.savefig(output_plot_cap, dpi=150)
plt.show()

print(f"\nCSV guardado en: {output_csv}")
print(f"Gráfico ROI guardado: {output_plot_roi}")
print(f"Gráfico capital guardado: {output_plot_cap}")