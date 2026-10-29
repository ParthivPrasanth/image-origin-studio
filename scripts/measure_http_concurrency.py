"""Measure the live two-model HTTP path with a checked-in public image.

This measures capacity and errors, never model accuracy. Run against a local
API or a loopback-bound container; do not point it at a public deployment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx


ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "frontend/public/gallery/candidates/bird-display.jpg"
MODELS = ("v3_e2", "community_forensics")


def request_once(url: str, image: bytes, timeout: float) -> dict[str, object]:
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{url}/api/analyze/compare",
                data={"models": list(MODELS)},
                files={"file": (IMAGE.name, image, "image/jpeg")},
            )
        result = response.json() if response.is_success else None
        returned = {
            item.get("model_key"): item.get("status")
            for item in result.get("models", [])
        } if isinstance(result, dict) else {}
        error = None if response.status_code == 200 and returned == {
            model: "success" for model in MODELS
        } else f"HTTP {response.status_code}; model states {returned}"
    except (httpx.HTTPError, ValueError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    return {
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "error": error,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--concurrency", nargs="+", type=int, default=[1, 2, 4])
    parser.add_argument("--requests-per-level", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / ".local" / "http-concurrency.json",
    )
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    if (parsed.scheme, parsed.hostname) != ("http", "127.0.0.1") or not parsed.port or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username:
        parser.error("Only a loopback-bound HTTP API is allowed for this local check.")
    args.url = args.url.rstrip("/")
    if any(level < 1 for level in args.concurrency) or args.requests_per_level < 1:
        parser.error("Concurrency and request count must be positive.")
    image = IMAGE.read_bytes()
    warmup = request_once(args.url, image, args.timeout)
    if warmup["error"]:
        raise RuntimeError(f"Warmup failed: {warmup['error']}")
    levels = []
    for concurrency in args.concurrency:
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            samples = list(pool.map(
                lambda _: request_once(args.url, image, args.timeout),
                range(args.requests_per_level),
            ))
        durations = sorted(sample["elapsed_ms"] for sample in samples)
        failures = [sample["error"] for sample in samples if sample["error"]]
        levels.append({
            "concurrency": concurrency,
            "requests": len(samples),
            "wall_ms": round((time.perf_counter() - started) * 1000, 1),
            "median_request_ms": round(statistics.median(durations), 1),
            "slowest_request_ms": durations[-1],
            "failures": failures,
        })
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": args.url,
        "input_sha256": hashlib.sha256(image).hexdigest(),
        "input_bytes": len(image),
        "models": MODELS,
        "timeout_seconds": args.timeout,
        "warmup_ms": warmup["elapsed_ms"],
        "levels": levels,
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(output)
    for level in levels:
        print(
            f"{level['concurrency']} concurrent: {level['requests']} requests, "
            f"median {level['median_request_ms']} ms, "
            f"slowest {level['slowest_request_ms']} ms, "
            f"{len(level['failures'])} failures"
        )


if __name__ == "__main__":
    main()
