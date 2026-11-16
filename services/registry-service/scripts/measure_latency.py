"""Measure GET latency against a running registry-service (NFR-1.1).

Sends a steady 10 requests per second, cycling through the list and
get-by-id endpoints, then prints p50/p95/max per endpoint and overall.

    uv run python scripts/measure_latency.py --base-url http://127.0.0.1:8000 --seconds 60
"""

import argparse
import statistics
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

PATHS = [
    "/v1/farms",
    "/v1/farms/b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001",
    "/v1/plots",
    "/v1/plots/c8f3d1b0-4d2e-5a1b-8b22-1d6e3f702002",
    "/v1/crops",
    "/v1/crops/tomato",
    "/v1/soils",
    "/v1/soils/loam",
    "/v1/emitters",
    "/v1/emitters/dripnet-pc-1.0",
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
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--rps", type=float, default=10)
    args = parser.parse_args()

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
