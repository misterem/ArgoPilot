"""Measure fresh-forecast latency against a running weather-service (NFR-2.3).

Warms the cache with one request per path (not measured), then sends a steady 10 requests per
second, so every measured request is a fresh-cache hit with no provider call. Prints p50/p95/max
per path and overall.

    uv run python scripts/measure_latency.py --base-url http://127.0.0.1:8001 --seconds 60
"""

import argparse
import statistics
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

# The four demo plots' coordinates (registry-service demo.sql).
PATHS = [
    "/v1/forecast?lat=31.25&lon=34.79&days=7",
    "/v1/forecast?lat=31.26&lon=34.80&days=7",
    "/v1/forecast?lat=31.40&lon=34.60&days=7",
    "/v1/forecast?lat=31.41&lon=34.61&days=7",
]


def timed_get(url: str) -> float:
    start = time.perf_counter()
    with urllib.request.urlopen(url) as response:
        response.read()
        if response.status != 200:
            raise RuntimeError(f"{url} returned {response.status}")
    return (time.perf_counter() - start) * 1000


def p95(samples: list[float]) -> float:
    return statistics.quantiles(samples, n=100, method="inclusive")[94]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--rps", type=float, default=10)
    args = parser.parse_args()

    for path in PATHS:  # warm-up: fill the cache, not measured
        timed_get(args.base_url + path)

    total = int(args.seconds * args.rps)
    futures = []
    with ThreadPoolExecutor(max_workers=20) as pool:
        start = time.perf_counter()
        for i in range(total):
            # Fixed schedule, so a slow response does not lower the request rate.
            time.sleep(max(0.0, start + i / args.rps - time.perf_counter()))
            path = PATHS[i % len(PATHS)]
            futures.append((path, pool.submit(timed_get, args.base_url + path)))

    by_path: dict[str, list[float]] = defaultdict(list)
    for path, future in futures:
        by_path[path].append(future.result())
    everything = [ms for samples in by_path.values() for ms in samples]

    print(f"{total} requests at {args.rps:g} req/s over {args.seconds}s\n")
    print(f"{'endpoint':<52} {'n':>4} {'p50 ms':>8} {'p95 ms':>8} {'max ms':>8}")
    for path, samples in [*by_path.items(), ("ALL", everything)]:
        print(f"{path:<52} {len(samples):>4} {statistics.median(samples):>8.1f} {p95(samples):>8.1f} {max(samples):>8.1f}")


if __name__ == "__main__":
    main()
