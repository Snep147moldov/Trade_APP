"""Download public Dukascopy monthly hourly bid/ask archives for offline audit.

Example: python -m app.tools.market_history --output /tmp/fx-history
The raw archives and SHA256 manifest are retained. Closed-market zero-volume
placeholder bars are removed; nonzero Saturday quotes are rejected.
"""

import argparse
import asyncio
import hashlib
import json
import lzma
import struct
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .sweep import DEFAULT_INSTRUMENTS


def decode(raw: bytes, year: int, month: int, symbol: str, day: int = 1) -> dict[int, dict]:
    data = lzma.decompress(raw)
    if len(data) % 24:
        raise ValueError("invalid hourly archive length")
    origin = int(datetime(year, month, day, tzinfo=timezone.utc).timestamp())
    scale = 1000 if symbol.endswith("_JPY") else 100000
    out = {}
    # Dukascopy hourly candles: seconds since month start, O/C/L/H, volume.
    for offset, op, cl, lo, hi, vol in struct.iter_unpack(">5If", data):
        out[origin + offset] = dict(open=op / scale, high=hi / scale,
                                    low=lo / scale, close=cl / scale, volume=vol)
    return out


async def download(output: Path, symbols: list[str], year: int,
                   first_month: int, last_month: int, recent_month: int = 0,
                   through_day: int = 0) -> None:
    output.mkdir(parents=True, exist_ok=True)
    rawdir = output / "raw"
    rawdir.mkdir(exist_ok=True)
    semaphore = asyncio.Semaphore(1)
    manifest = {}
    async with httpx.AsyncClient(timeout=30) as client:
        async def fetch(symbol, month, side, day=0):
            name = f"{symbol}_{year}_{month:02}_{day:02}_{side}.bi5" if day else f"{symbol}_{year}_{month:02}_{side}.bi5"
            path = rawdir / name
            url = (f"https://datafeed.dukascopy.com/datafeed/{symbol.replace('_', '')}/"
                   f"{year}/{month - 1:02}/"
                   + (f"{day:02}/{side}_candles_min_1.bi5" if day else f"{side}_candles_hour_1.bi5"))
            async with semaphore:
                if not path.exists():
                    for attempt in range(4):
                        try:
                            await asyncio.sleep(.7)
                            response = await client.get(url)
                            if response.status_code == 429 and attempt < 3:
                                print("provider rate limit; retrying in 30s", flush=True)
                                await asyncio.sleep(30)
                                continue
                            break
                        except httpx.TransportError:
                            if attempt == 3:
                                raise
                            await asyncio.sleep(attempt + 1)
                    response.raise_for_status()
                    path.write_bytes(response.content)
                raw = path.read_bytes()
            manifest[name] = {"url": url, "sha256": hashlib.sha256(raw).hexdigest()}
            return decode(raw, year, month, symbol, day or 1)

        def hourly(minutes):
            groups = {}
            for ts, row in sorted(minutes.items()):
                groups.setdefault(ts // 3600 * 3600, []).append(row)
            return {ts: {"open": rows[0]["open"], "close": rows[-1]["close"],
                         "high": max(r["high"] for r in rows), "low": min(r["low"] for r in rows),
                         "volume": sum(r["volume"] for r in rows)}
                    for ts, rows in groups.items() if len(rows) == 60}

        for symbol in symbols:
            bars = []
            removed = 0
            periods = [(m, 0) for m in range(first_month, last_month + 1)]
            if recent_month:
                periods += [(recent_month, d) for d in range(1, through_day + 1)
                            if datetime(year, recent_month, d).weekday() < 5]
            for month, day in periods:
                bid, ask = await asyncio.gather(fetch(symbol, month, "BID", day),
                                                fetch(symbol, month, "ASK", day))
                if day:
                    bid, ask = hourly(bid), hourly(ask)
                if bid.keys() != ask.keys():
                    raise ValueError(f"{symbol}: unmatched bid/ask timestamps")
                for ts in sorted(bid):
                    if ts + 3600 > time.time():
                        continue
                    b, a = bid[ts], ask[ts]
                    if b["volume"] == 0 and a["volume"] == 0:
                        removed += 1
                        continue
                    if datetime.fromtimestamp(ts, timezone.utc).weekday() == 5:
                        raise ValueError(f"{symbol}: nonempty Saturday candle")
                    if a["open"] < b["open"] or a["close"] < b["close"]:
                        raise ValueError(f"{symbol}: crossed bid/ask")
                    row = {k: (b[k] + a[k]) / 2 for k in ("open", "high", "low", "close")}
                    row.update(time=ts, volume=b["volume"] + a["volume"], complete=True,
                               source="dukascopy", simulated=False,
                               **{f"bid_{k}": b[k] for k in ("open", "high", "low", "close")},
                               **{f"ask_{k}": a[k] for k in ("open", "high", "low", "close")})
                    bars.append(row)
            payload = json.dumps(bars, separators=(",", ":"))
            (output / f"{symbol}.json").write_text(payload)
            manifest[symbol] = {"bars": len(bars), "removed_placeholders": removed,
                                "sha256": hashlib.sha256(payload.encode()).hexdigest()}
            print(symbol, len(bars), "bars; removed", removed, "placeholders", flush=True)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--symbols", default=",".join(DEFAULT_INSTRUMENTS))
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--first-month", type=int, default=2)
    parser.add_argument("--last-month", type=int, default=8)
    parser.add_argument("--recent-month", type=int, default=0)
    parser.add_argument("--through-day", type=int, default=0)
    args = parser.parse_args()
    asyncio.run(download(args.output, args.symbols.split(","), args.year,
                         args.first_month, args.last_month, args.recent_month,
                         args.through_day))
