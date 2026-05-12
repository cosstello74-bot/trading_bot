"""
Download DAX (DEU.IDX) 1-min OHLC from Dukascopy.

Dukascopy serves free historical tick data as hourly LZMA-compressed
.bi5 files at:

    https://datafeed.dukascopy.com/datafeed/{INSTR}/{YYYY}/{MM0}/{DD}/{HH}h_ticks.bi5

where MM0 is the month 0-indexed (January = 00).

Each .bi5 decompresses to an array of 20-byte tick records (big-endian):
    uint32  time offset in ms from the file's hour
    uint32  ask price scaled by point factor
    uint32  bid price scaled by point factor
    float32 ask volume (millions)
    float32 bid volume (millions)

The script downloads hours in parallel, parses ticks, mid-prices them,
resamples to 1-min OHLC, and writes a single CSV. Weekend hours and
404s are silently skipped.

Usage:
    python fetch_dax_data.py --start 2020-01-01 --end 2025-01-01 --out data/dax_1m.csv
"""
import argparse
import lzma
import struct
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://datafeed.dukascopy.com/datafeed"
INSTRUMENT = "DEUIDXEUR"
POINT_DIVISOR_CANDIDATES = (1000.0, 100.0, 10.0, 1.0)


def fetch_hour(date_utc):
    url = (
        f"{BASE_URL}/{INSTRUMENT}/"
        f"{date_utc.year:04d}/{date_utc.month - 1:02d}/{date_utc.day:02d}/"
        f"{date_utc.hour:02d}h_ticks.bi5"
    )
    try:
        r = requests.get(url, timeout=30)
    except requests.RequestException:
        return []
    if r.status_code != 200 or not r.content:
        return []
    try:
        raw = lzma.decompress(r.content)
    except lzma.LZMAError:
        return []
    ticks = []
    for i in range(0, len(raw) - 19, 20):
        ms, ask, bid, ask_vol, bid_vol = struct.unpack(">IIIff", raw[i:i + 20])
        ts = date_utc + timedelta(milliseconds=ms)
        ticks.append((ts, ask, bid, ask_vol + bid_vol))
    return ticks


def pick_divisor(prices):
    """Auto-detect the point divisor by checking which one puts the median
    price in a sensible DAX range (roughly 2000-40000)."""
    median = prices.median()
    for div in POINT_DIVISOR_CANDIDATES:
        scaled = median / div
        if 2000 <= scaled <= 40000:
            return div
    return POINT_DIVISOR_CANDIDATES[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="UTC start date YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="UTC end date YYYY-MM-DD (exclusive)")
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)

    hours = []
    cur = start
    while cur < end:
        if cur.weekday() != 5:
            hours.append(cur)
        cur += timedelta(hours=1)

    print(f"Fetching {len(hours)} hours with {args.workers} workers ...", file=sys.stderr)

    all_ticks = []
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(fetch_hour, h): h for h in hours}
        for fut in as_completed(futures):
            ticks = fut.result()
            all_ticks.extend(ticks)
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(hours)} hours, {len(all_ticks):,} ticks", file=sys.stderr)

    if not all_ticks:
        print("No data returned. Check date range and network.", file=sys.stderr)
        sys.exit(1)

    df = pd.DataFrame(all_ticks, columns=["timestamp", "ask_raw", "bid_raw", "volume"])
    df = df.set_index("timestamp").sort_index()

    divisor = pick_divisor((df["ask_raw"] + df["bid_raw"]) / 2)
    print(f"Detected point divisor: {divisor}", file=sys.stderr)
    df["price"] = (df["ask_raw"] + df["bid_raw"]) / 2 / divisor

    ohlc = df["price"].resample("1min").ohlc()
    vol = df["volume"].resample("1min").sum()
    out = pd.concat([ohlc, vol.rename("volume")], axis=1).dropna(subset=["open"])

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out)
    print(f"Saved {len(out):,} 1-min bars to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
