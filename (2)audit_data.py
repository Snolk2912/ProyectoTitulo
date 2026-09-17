import pandas as pd
from pathlib import Path
from datetime import timezone

# Rutas
project_root   = Path(__file__).resolve().parent.parent
processed_path = project_root / "data_processed"
results_path   = project_root / "results"
results_path.mkdir(exist_ok=True)

# Mismo sufijo de fechas que el script de descarga
FILE_SUFFIX    = "20190910_20220131"
input_file     = processed_path / f"BTCUSDT_15m_{FILE_SUFFIX}_processed.csv"
report_file    = results_path   / f"auditoria_{FILE_SUFFIX}.txt"

INTERVAL_EXPECTED = pd.Timedelta(minutes=15)

# Carga
df = pd.read_csv(input_file)
df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
df = df.sort_values("open_time").reset_index(drop=True)

# Análisis
total_rows  = len(df)
first_ts    = df["open_time"].min()
last_ts     = df["open_time"].max()
duplicates  = df["open_time"].duplicated().sum()

df["delta"] = df["open_time"].diff()
gap_mask    = (df["delta"] != INTERVAL_EXPECTED) & df["delta"].notna()
gaps        = df[gap_mask][["open_time", "delta"]].copy()

null_counts = df[["open", "high", "low", "close", "volume"]].isnull().sum()

# Reporte en consola
lines = []
lines.append("         AUDITORÍA DE DATOS — BTCUSDT 15m")
lines.append(f"Archivo:            {input_file.name}")
lines.append(f"Filas totales:      {total_rows:,}")
lines.append(f"Primer timestamp:   {first_ts}")
lines.append(f"Último timestamp:   {last_ts}")
lines.append(f"Duplicados:         {duplicates}")
lines.append("")
lines.append("── Valores nulos por columna ──")
for col, n in null_counts.items():
    lines.append(f"  {col:<10}: {n}")
lines.append("")
lines.append(f"── Huecos temporales detectados: {len(gaps)} ──")
if not gaps.empty:
    for _, row in gaps.iterrows():
        lines.append(f"  {row['open_time']}  →  salto de {row['delta']}")
else:
    lines.append("  Sin huecos. Serie completa ✓")

report = "\n".join(lines)
print(report)

# ── Guardar reporte ───────────────────────────────────────────────
with open(report_file, "w", encoding="utf-8") as f:
    f.write(report)

print(f"\nReporte guardado en: {report_file}")

# ── Limpieza ──────────────────────────────────────────────────────
df.drop(columns=["delta"], inplace=True)