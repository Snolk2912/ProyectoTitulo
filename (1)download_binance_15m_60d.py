import requests
import pandas as pd
from datetime import datetime, timezone
import time
from pathlib import Path

# Configuración
BASE_URL  = "https://fapi.binance.com/fapi/v1/klines"
SYMBOL    = "BTCUSDT"
INTERVAL  = "15m"
LIMIT     = 1500

# Fechas del paper (septiembre 2019 – enero 2022)
START_DATE = datetime(2019, 9, 10,  tzinfo=timezone.utc)
END_DATE   = datetime(2022, 1, 31, tzinfo=timezone.utc)

# Rutas
project_root   = Path(__file__).resolve().parent.parent
raw_path       = project_root / "data_raw"
processed_path = project_root / "data_processed"
raw_path.mkdir(exist_ok=True)
processed_path.mkdir(exist_ok=True)

FILE_SUFFIX = f"{START_DATE.strftime('%Y%m%d')}_{END_DATE.strftime('%Y%m%d')}"

# Descarga paginada
def to_millis(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)

def download_klines(symbol, interval, start_dt, end_dt):
    start_ms = to_millis(start_dt)
    end_ms   = to_millis(end_dt)
    all_rows = []

    while start_ms < end_ms:
        params = {
            "symbol":    symbol,
            "interval":  interval,
            "startTime": start_ms,
            "endTime":   end_ms,
            "limit":     LIMIT,
        }
        resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if not data:
            break

        all_rows.extend(data)
        start_ms = data[-1][0] + 1
        print(f"  Filas acumuladas: {len(all_rows)}")
        time.sleep(0.2)

    return all_rows

# Construcción del DataFrame
COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_asset_volume", "number_of_trades",
    "taker_buy_base_volume", "taker_buy_quote_volume", "ignore"
]

NUMERIC = ["open", "high", "low", "close", "volume",
           "quote_asset_volume", "taker_buy_base_volume", "taker_buy_quote_volume"]

def build_dataframe(rows):
    df = pd.DataFrame(rows, columns=COLUMNS)
    df = df.drop(columns=["ignore"])

    for col in NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["number_of_trades"] = pd.to_numeric(df["number_of_trades"], errors="coerce")

    df["open_time"]  = pd.to_datetime(df["open_time"],  unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

    df = (df.drop_duplicates(subset=["open_time"])
            .sort_values("open_time")
            .reset_index(drop=True))
    return df

# Validación de huecos
def check_gaps(df, interval_minutes=15):
    expected = pd.Timedelta(minutes=interval_minutes)
    diffs    = df["open_time"].diff().dropna()
    gaps     = diffs[diffs != expected]

    if gaps.empty:
        print("  Sin huecos temporales detectados.")
    else:
        print(f"  ⚠️  {len(gaps)} huecos detectados:")
        for idx, val in gaps.items():
            print(f"     Índice {idx}: salto de {val} en {df.loc[idx, 'open_time']}")

# Main
if __name__ == "__main__":
    rows = download_klines(SYMBOL, INTERVAL, START_DATE, END_DATE)
    df   = build_dataframe(rows)

    check_gaps(df)

    raw_file       = raw_path       / f"BTCUSDT_15m_{FILE_SUFFIX}_raw.csv"
    processed_file = processed_path / f"BTCUSDT_15m_{FILE_SUFFIX}_processed.csv"

    df.to_csv(raw_file, index=False)
    df[["open_time", "open", "high", "low", "close", "volume"]].to_csv(
        processed_file, index=False
    )

    print(f"\nArchivo raw:       {raw_file}")
    print(f"Archivo processed: {processed_file}")
    print(f"Total filas:       {len(df)}")
    print(f"Primer timestamp:  {df['open_time'].min()}")
    print(f"Último timestamp:  {df['open_time'].max()}")
    print(df.head())