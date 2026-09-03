"""
Quick Performance Benchmark Script
====================================
Measures endpoint response times and throughput without external dependencies.
Runs directly against a running server.

Usage:
    python backend/tests/perf_benchmark.py [--url http://localhost:8002] [--requests 100] [--concurrency 10]
"""

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENDPOINTS = [
    ("GET", "/"),
    ("GET", "/api/v1/jobs/public"),
    ("GET", "/api/v1/courses/public"),
    ("GET", "/api/v1/monitoring/health"),
    ("GET", "/pricing.html"),
]

AUTH_ENDPOINTS = [
    (
        "POST",
        "/api/v1/auth/login",
        {"email": "candidate@test.com", "password": "testpass123", "role": "candidate"},
    ),
]


def make_request(url: str, method: str = "GET", body: dict = None) -> tuple[int, float]:
    start = time.perf_counter()
    try:
        data = json.dumps(body).encode() if body else None
        req = Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json") if body else None
        with urlopen(req, timeout=10) as resp:
            status = resp.status
    except HTTPError as e:
        status = e.code
    except URLError:
        status = 0
    elapsed = time.perf_counter() - start
    return status, elapsed


def benchmark_endpoint(
    base_url: str,
    method: str,
    path: str,
    body: dict = None,
    num_requests: int = 50,
    concurrency: int = 5,
) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    timings = []
    statuses = {}
    errors = 0

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(make_request, url, method, body)
            for _ in range(num_requests)
        ]
        for future in as_completed(futures):
            status, elapsed = future.result()
            timings.append(elapsed)
            statuses[status] = statuses.get(status, 0) + 1
            if status == 0 or status >= 500:
                errors += 1

    timings.sort()
    return {
        "path": path,
        "method": method,
        "requests": num_requests,
        "concurrency": concurrency,
        "ok": statuses.get(200, 0) + statuses.get(201, 0),
        "errors": errors,
        "status_distribution": dict(sorted(statuses.items())),
        "min_ms": round(min(timings) * 1000, 1),
        "max_ms": round(max(timings) * 1000, 1),
        "avg_ms": round(statistics.mean(timings) * 1000, 1),
        "median_ms": round(statistics.median(timings) * 1000, 1),
        "p50_ms": round(timings[len(timings) // 2] * 1000, 1),
        "p95_ms": round(timings[int(len(timings) * 0.95)] * 1000, 1),
        "p99_ms": round(timings[int(len(timings) * 0.99)] * 1000, 1),
        "throughput_rps": round(num_requests / sum(timings), 1),
    }


def main():
    parser = argparse.ArgumentParser(description="Candway Performance Benchmark")
    parser.add_argument(
        "--url", default="http://localhost:8002", help="Base URL of running server"
    )
    parser.add_argument(
        "--requests", type=int, default=50, help="Requests per endpoint"
    )
    parser.add_argument(
        "--concurrency", type=int, default=5, help="Concurrent requests"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Candway Performance Benchmark")
    print("  Target: %s" % args.url)
    print(
        "  Requests/endpoint: %d  Concurrency: %d" % (args.requests, args.concurrency)
    )
    print("=" * 60)
    print()

    # Sanity check: server is alive
    try:
        req = Request("%s/api/v1/monitoring/health" % args.url.rstrip("/"))
        with urlopen(req, timeout=5) as resp:
            health = resp.read().decode()
        print("  [OK] Server reachable (health: %s)" % health[:50])
        print()
    except Exception as e:
        print("  [FAIL] Server not reachable at %s: %s" % (args.url, e))
        print(
            "         Start the server first, e.g.: uvicorn backend.app:create_app() --port 8002"
        )
        sys.exit(1)

    all_results = []
    for entry in ENDPOINTS + AUTH_ENDPOINTS:
        method, path = entry[0], entry[1]
        body = entry[2] if len(entry) > 2 else None
        print("  [%s] %s  ..." % (method, path), end=" ", flush=True)
        result = benchmark_endpoint(
            args.url,
            method,
            path,
            body,
            num_requests=args.requests,
            concurrency=args.concurrency,
        )
        all_results.append(result)

        status_str = "OK=%d/%d" % (result["ok"], result["requests"])
        if result["errors"]:
            status_str += "  ERR=%d" % result["errors"]

        print(status_str)
        print("     |- avg: %8.1f ms" % result["avg_ms"])
        print(
            "     |- p50: %8.1f ms  p95: %8.1f ms  p99: %8.1f ms"
            % (result["p50_ms"], result["p95_ms"], result["p99_ms"])
        )
        print(
            "     |- min: %8.1f ms  max: %8.1f ms"
            % (result["min_ms"], result["max_ms"])
        )
        print(
            "     |- rps: %8.1f  statuses: %s"
            % (result["throughput_rps"], result["status_distribution"])
        )
        print()

    # Summary
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print("  %-45s %8s %8s %8s %6s" % ("Endpoint", "Avg(ms)", "P95(ms)", "RPS", "OK%"))
    print("  %-45s %8s %8s %8s %6s" % ("-" * 45, "-" * 8, "-" * 8, "-" * 8, "-" * 6))
    for r in all_results:
        ok_pct = round(r["ok"] / r["requests"] * 100, 1) if r["requests"] else 0
        print(
            "  %-45s %8.1f %8.1f %8.1f %6.1f%%"
            % (
                r["method"] + " " + r["path"],
                r["avg_ms"],
                r["p95_ms"],
                r["throughput_rps"],
                ok_pct,
            )
        )
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
