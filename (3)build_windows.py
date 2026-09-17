import pandas as pd
from pathlib import Path

# Configuración
FILE_SUFFIX    = "20190910_20220131"
WINDOW_DAYS    = 60
STEP_DAYS      = 30
EXPECTED_ROWS  = WINDOW_DAYS * 24 * 4   # 5760 velas de 15 min
MIN_ROWS       = int(EXPECTED_ROWS * 0.98)  # tolerancia del 2%

# Según el paper: 23 ventanas de entrenamiento, 8 de prueba
# Las últimas 8 ventanas del dataset se usan como test
N_TEST_WINDOWS = 8

# Rutas
project_root   = Path(__file__).resolve().parent.parent
processed_path = project_root / "data_processed"
results_path   = project_root / "results"
results_path.mkdir(exist_ok=True)

input_file  = processed_path / f"BTCUSDT_15m_{FILE_SUFFIX}_processed.csv"
output_file = processed_path / f"BTCUSDT_15m_{FILE_SUFFIX}_windows.csv"

# Carga
df = pd.read_csv(input_file)
df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
df = df.sort_values("open_time").reset_index(drop=True)

# Construcción de ventanas
start_date = pd.Timestamp("2019-09-08", tz="UTC")
end_date   = pd.Timestamp("2022-01-31", tz="UTC")

windows       = []
window_id     = 0
current_start = start_date

while current_start + pd.Timedelta(days=WINDOW_DAYS) <= end_date:
    current_end = current_start + pd.Timedelta(days=WINDOW_DAYS)

    w = df[(df["open_time"] >= current_start) & (df["open_time"] < current_end)].copy()

    if len(w) == EXPECTED_ROWS:
        w["window_id"]    = window_id
        w["window_start"] = current_start     # fecha límite, no el dato real
        w["window_end"]   = current_end
        w["row_count"]    = len(w)
        windows.append(w)
        window_id += 1

    current_start += pd.Timedelta(days=STEP_DAYS)

if not windows:
    print("No se generaron ventanas. Verifica el rango de fechas.")
else:
    out = pd.concat(windows, ignore_index=True)

    # Renumerar desde 0 por si quedaron IDs salteados
    unique_ids = sorted(out["window_id"].unique())
    id_map     = {old: new for new, old in enumerate(unique_ids)}
    out["window_id"] = out["window_id"].map(id_map)

    total_windows = out["window_id"].nunique()

    # ── Etiqueta train / test ──────────────────────────────────────
    # Las últimas N_TEST_WINDOWS ventanas son de prueba
    test_ids  = set(range(total_windows - N_TEST_WINDOWS, total_windows))
    out["split"] = out["window_id"].apply(
        lambda wid: "test" if wid in test_ids else "train"
    )

    out.to_csv(output_file, index=False)

    # Resumen
    summary = (
        out.groupby(["window_id", "split", "window_start", "window_end"])
           .size()
           .reset_index(name="row_count")
           .sort_values("window_id")
    )

    print("         VENTANAS GENERADAS — BTCUSDT 15m")
    print(summary.to_string(index=False))
    print(f"Total ventanas:      {total_windows}")
    print(f"  → train:           {(summary['split']=='train').sum()}")
    print(f"  → test:            {(summary['split']=='test').sum()}")
    print(f"Ventanas con < {EXPECTED_ROWS} filas: "f"{(summary['row_count'] < EXPECTED_ROWS).sum()} (toleradas si ≥ {MIN_ROWS})")
    print(f"\nArchivo guardado en: {output_file}")