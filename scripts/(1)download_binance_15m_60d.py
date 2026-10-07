"""Utilidad manual de descarga, separada del experimento offline.

Importar este módulo no descarga ni crea carpetas. Ejecutarlo requiere
--allow-download; ningún comando de trading.cli invoca esta utilidad.
El rango es [start, end), en UTC. No necesita pandas.
"""

import argparse
import csv
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np

from trading.data import MarketData, iso_utc, timestamp_ms

BASE_URL = "https://fapi.binance.com/fapi/v1/klines"
SYMBOL = "BTCUSDT"
INTERVAL = "15m"
LIMIT = 1500
PROJECT_ROOT = Path(__file__).resolve().parent.parent
COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_asset_volume", "number_of_trades", "taker_buy_base_volume",
    "taker_buy_quote_volume", "ignore",
]


def download_klines(symbol, interval, start_ms, end_ms):
    """Explicit caller-only network operation; end is exclusive."""
    if start_ms >= end_ms:
        raise ValueError("start debe ser anterior a end")
    cursor, rows = start_ms, []
    while cursor < end_ms:
        query = urlencode({"symbol": symbol, "interval": interval, "startTime": cursor,
                           "endTime": end_ms - 1, "limit": LIMIT})
        with urlopen(Request(BASE_URL + "?" + query), timeout=30) as response:
            batch = json.load(response)
        if not isinstance(batch, list):
            raise ValueError("Binance no devolvió una lista de velas")
        if not batch:
            break
        if any(not isinstance(row, list) or len(row) != len(COLUMNS) for row in batch):
            raise ValueError("Respuesta de velas con formato inválido")
        if any(not cursor <= int(row[0]) < end_ms for row in batch):
            raise ValueError("Respuesta fuera del rango solicitado")
        next_cursor = int(batch[-1][0]) + 1
        if next_cursor <= cursor:
            raise ValueError("La paginación no avanzó")
        rows.extend(batch)
        cursor = next_cursor
        print(f"Filas recibidas: {len(rows)}")
        time.sleep(0.2)
    return rows


def build_market_data(rows):
    """Normalize original rows without silently sorting or deduplicating."""
    data = MarketData(np.asarray([int(row[0]) for row in rows], dtype=np.int64),
                      *(np.asarray([float(row[column]) for row in rows])
                        for column in (1, 2, 3, 4, 5)))
    data.validate()
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-download", action="store_true",
                        help="Habilita explícitamente acceso de red; no usar en este entorno")
    parser.add_argument("--start", default="2019-09-10")
    parser.add_argument("--end", default="2022-01-31", help="UTC, exclusivo")
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)
    if not args.allow_download:
        parser.error("Descarga deshabilitada. Usa un CSV local con python -m trading.cli.")
    start, end = timestamp_ms(args.start), timestamp_ms(args.end)
    if start % 900000 or end % 900000 or start >= end:
        parser.error("Fechas inválidas: deben alinearse a 15 minutos y start < end")
    rows = download_klines(SYMBOL, INTERVAL, start, end)
    if not rows:
        parser.error("No se recibieron datos; no se escribieron CSV")
    suffix = iso_utc(start)[:10].replace("-", "") + "_" + iso_utc(end)[:10].replace("-", "")
    raw_path = args.output_root / "data" / "raw" / f"BTCUSDT_15m_{suffix}_raw.csv"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with raw_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    # Keep raw evidence even when strict validation rejects the processed series.
    data = build_market_data(rows)
    if int(data.times[0]) != start or int(data.times[-1]) + data.interval_ms != end:
        raise ValueError("La descarga no cubre el rango completo; solo se conservó el raw")
    processed_path = args.output_root / "data" / "processed" / f"BTCUSDT_15m_{suffix}_processed.csv"
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    with processed_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["open_time", "open", "high", "low", "close", "volume"])
        for i in range(len(data)):
            writer.writerow([iso_utc(int(data.times[i])), data.open[i], data.high[i],
                             data.low[i], data.close[i], data.volume[i]])
    print(f"Raw: {raw_path}\nProcessed: {processed_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
