#!/usr/bin/env python3
"""Sequentially download a URL ten times and report timing and throughput."""

from __future__ import annotations

import argparse
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

REQUEST_COUNT = 10
CHUNK_SIZE = 64 * 1024


def format_bytes(byte_count: int) -> str:
    """Format a byte count using decimal units (1 MB = 1,000,000 bytes)."""
    value = float(byte_count)
    for unit in ("B", "kB", "MB", "GB", "TB"):
        if value < 1000 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1000
    return f"{value:.2f} TB"


def download_once(url: str, timeout: float) -> tuple[float, int]:
    """Download the complete response body and return seconds and bytes."""
    request = Request(url, headers={"User-Agent": "SimpleInternetSpeedTest/1.0"})
    started = time.perf_counter()
    byte_count = 0
    with urlopen(request, timeout=timeout) as response:
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            byte_count += len(chunk)
    return time.perf_counter() - started, byte_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure download speed by fetching the same URL 10 times in a row."
    )
    parser.add_argument("url", help="URL to download, e.g. https://example.com/large-image.jpg")
    parser.add_argument(
        "--timeout", type=float, default=60.0,
        help="timeout for each request in seconds (default: 60)",
    )
    args = parser.parse_args()

    parsed = urlparse(args.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        parser.error("URL must start with http:// or https://")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    print(f"URL: {args.url}")
    print(f"Последовательных запросов: {REQUEST_COUNT}\n")

    durations: list[float] = []
    total_bytes = 0
    total_elapsed = 0.0

    for index in range(1, REQUEST_COUNT + 1):
        try:
            duration, byte_count = download_once(args.url, args.timeout)
        except HTTPError as exc:
            print(f"Ошибка HTTP при запросе {index}: {exc.code} {exc.reason}", file=sys.stderr)
            return 1
        except (URLError, TimeoutError, OSError) as exc:
            print(f"Ошибка при запросе {index}: {exc}", file=sys.stderr)
            return 1

        durations.append(duration)
        total_bytes += byte_count
        total_elapsed += duration
        print(
            f"Запрос {index:02}/{REQUEST_COUNT}: {format_bytes(byte_count)} за {duration:.3f} с"
        )

    average_time = sum(durations) / len(durations)
    # Aggregate throughput uses total downloaded bytes / sum of request durations.
    bytes_per_second = total_bytes / total_elapsed if total_elapsed else 0.0
    megabits_per_second = bytes_per_second * 8 / 1_000_000

    print("\nРезультат")
    print(f"Среднее время запроса:       {average_time:.3f} с")
    print(f"Всего скачано:               {format_bytes(total_bytes)} ({total_bytes:,} байт)")
    print(f"Суммарное время скачивания:  {total_elapsed:.3f} с")
    print(f"Средняя скорость скачивания: {megabits_per_second:.2f} Мбит/с")
    print(f"                             {bytes_per_second / 1_000_000:.2f} MB/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
