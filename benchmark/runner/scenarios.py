"""
Benchmark scenario implementations.

Each scenario function takes a server base_url (and optionally an open McpClient)
and returns a plain dict of metrics. All timing is wall-clock from the runner's
perspective (end-to-end including network within Docker).
"""

from __future__ import annotations

import asyncio
import statistics
import subprocess
import sys
import time
from typing import Any

import httpx
import psutil

from mcp_client import McpClient


# ---------------------------------------------------------------------------
# 1. Latency baseline (sequential echo)
# ---------------------------------------------------------------------------
async def scenario_latency(base_url: str, n_requests: int = 200) -> dict[str, Any]:
    """
    Send n_requests sequential echo calls on a single session.
    Returns p50 / p95 / p99 / mean / min / max latency in ms.
    """
    latencies: list[float] = []
    async with McpClient(base_url) as client:
        for i in range(n_requests):
            _, ms = await client.call_tool_timed("echo", {"text": f"ping-{i}"})
            latencies.append(ms)

    latencies.sort()
    n = len(latencies)
    return {
        "n_requests": n,
        "p50_ms": round(statistics.median(latencies), 3),
        "p95_ms": round(latencies[int(0.95 * n)], 3),
        "p99_ms": round(latencies[int(0.99 * n)], 3),
        "mean_ms": round(statistics.mean(latencies), 3),
        "min_ms": round(min(latencies), 3),
        "max_ms": round(max(latencies), 3),
        "stdev_ms": round(statistics.stdev(latencies), 3) if n > 1 else 0.0,
    }


# ---------------------------------------------------------------------------
# 2. Throughput (concurrent echo)
# ---------------------------------------------------------------------------
async def scenario_throughput(
    base_url: str,
    concurrency_levels: list[int] | None = None,
    duration_s: float = 10.0,
) -> dict[str, Any]:
    """
    For each concurrency level spawn that many parallel clients, each hammering
    echo in a tight loop for duration_s seconds. Returns requests/second per level.
    """
    if concurrency_levels is None:
        concurrency_levels = [1, 10, 50, 100]

    results = []

    for concurrency in concurrency_levels:
        stop = asyncio.Event()
        counts: list[int] = [0] * concurrency
        errors: list[int] = [0] * concurrency

        async def worker(idx: int) -> None:
            client = McpClient(base_url)
            await client.initialize()
            try:
                while not stop.is_set():
                    try:
                        await client.call_tool("echo", {"text": "throughput"})
                        counts[idx] += 1
                    except Exception:
                        errors[idx] += 1
            finally:
                await client.close()

        tasks = [asyncio.create_task(worker(i)) for i in range(concurrency)]
        await asyncio.sleep(duration_s)
        stop.set()
        await asyncio.gather(*tasks, return_exceptions=True)

        total = sum(counts)
        total_errors = sum(errors)
        rps = round(total / duration_s, 1)
        results.append({
            "concurrency": concurrency,
            "requests": total,
            "errors": total_errors,
            "rps": rps,
        })

    return {"duration_s": duration_s, "levels": results}


# ---------------------------------------------------------------------------
# 3. CPU performance (fibonacci)
# ---------------------------------------------------------------------------
async def scenario_cpu(base_url: str, n_value: int = 30, repeats: int = 100) -> dict[str, Any]:
    """
    Call fibonacci(n_value) `repeats` times sequentially.
    Measures end-to-end call latency (server compute + network).
    """
    latencies: list[float] = []
    async with McpClient(base_url) as client:
        for _ in range(repeats):
            _, ms = await client.call_tool_timed("fibonacci", {"n": n_value})
            latencies.append(ms)

    latencies.sort()
    n = len(latencies)
    return {
        "n_value": n_value,
        "repeats": repeats,
        "total_ms": round(sum(latencies), 1),
        "mean_ms": round(statistics.mean(latencies), 3),
        "p50_ms": round(statistics.median(latencies), 3),
        "p95_ms": round(latencies[int(0.95 * n)], 3),
        "p99_ms": round(latencies[int(0.99 * n)], 3),
    }


# ---------------------------------------------------------------------------
# 4. Async I/O performance (concurrent fetch_mock)
# ---------------------------------------------------------------------------
async def scenario_async_io(
    base_url: str,
    concurrency: int = 100,
    delay_ms: int = 50,
) -> dict[str, Any]:
    """
    Fire `concurrency` concurrent fetch_mock calls simultaneously on separate sessions.
    Ideal wall time = delay_ms. Ratio = ideal / actual measures async efficiency.
    """
    async def single_call() -> float:
        client = McpClient(base_url)
        await client.initialize()
        try:
            _, ms = await client.call_tool_timed("fetch_mock", {"delay_ms": delay_ms})
            return ms
        finally:
            await client.close()

    wall_start = time.perf_counter()
    latencies = await asyncio.gather(*[single_call() for _ in range(concurrency)])
    wall_ms = (time.perf_counter() - wall_start) * 1000
    latencies_sorted = sorted(latencies)

    ideal_ms = delay_ms
    concurrency_ratio = round(ideal_ms / (wall_ms / concurrency), 3) if wall_ms > 0 else 0

    return {
        "concurrency": concurrency,
        "delay_ms": delay_ms,
        "wall_ms": round(wall_ms, 1),
        "ideal_ms": ideal_ms,
        "mean_call_ms": round(statistics.mean(latencies), 3),
        "p95_call_ms": round(latencies_sorted[int(0.95 * len(latencies_sorted))], 3),
        "concurrency_ratio": concurrency_ratio,
        "throughput_rps": round(concurrency / (wall_ms / 1000), 1),
    }


# ---------------------------------------------------------------------------
# 5. Memory under load
# ---------------------------------------------------------------------------
async def scenario_memory(
    base_url: str,
    n_requests: int = 1000,
    sample_every: int = 50,
) -> dict[str, Any]:
    """
    Send n_requests echo calls on a single session and sample the benchmark
    runner's own memory (RSS) every sample_every requests as a relative proxy.
    Also sends periodic large payloads to stress serialization.
    """
    process = psutil.Process()
    rss_samples: list[float] = []

    async with McpClient(base_url) as client:
        for i in range(n_requests):
            # Every 10th request send a slightly larger payload (512 bytes)
            text = ("x" * 512) if i % 10 == 0 else f"ping-{i}"
            await client.call_tool("echo", {"text": text})
            if i % sample_every == 0:
                rss_mb = process.memory_info().rss / (1024 * 1024)
                rss_samples.append(rss_mb)

    baseline = rss_samples[0] if rss_samples else 0
    peak = max(rss_samples) if rss_samples else 0
    return {
        "n_requests": n_requests,
        "baseline_rss_mb": round(baseline, 2),
        "peak_rss_mb": round(peak, 2),
        "growth_rss_mb": round(peak - baseline, 2),
        "samples": [round(s, 2) for s in rss_samples],
    }


# ---------------------------------------------------------------------------
# 6. Cold start
# ---------------------------------------------------------------------------
async def scenario_cold_start(
    image_name: str,
    port: int,
    env: dict[str, str] | None = None,
    max_wait_s: float = 30.0,
) -> dict[str, Any]:
    """
    Start a fresh Docker container and measure time until /health returns 200.
    Requires Docker to be available in the runner environment.

    NOTE: In docker-compose mode the servers are already running; this scenario
    is best run standalone. Returns 'skipped' if Docker is unavailable.
    """
    import shutil
    if not shutil.which("docker"):
        return {"skipped": True, "reason": "Docker not available in runner"}

    env_args: list[str] = []
    for k, v in (env or {}).items():
        env_args += ["-e", f"{k}={v}"]

    cmd = [
        "docker", "run", "--rm", "-d",
        "-p", f"{port}:{port}",
        *env_args,
        image_name,
    ]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return {"skipped": True, "reason": f"docker run failed: {proc.stderr.strip()}"}

    container_id = proc.stdout.strip()
    url = f"http://localhost:{port}"
    deadline = time.monotonic() + max_wait_s

    ready = False
    async with httpx.AsyncClient(timeout=3.0) as hc:
        while time.monotonic() < deadline:
            try:
                r = await hc.get(f"{url}/health")
                if r.status_code == 200:
                    ready = True
                    break
            except Exception:
                pass
            await asyncio.sleep(0.1)

    cold_start_ms = (time.perf_counter() - t0) * 1000

    # Cleanup
    subprocess.run(["docker", "stop", container_id], capture_output=True)

    return {
        "image": image_name,
        "ready": ready,
        "cold_start_ms": round(cold_start_ms, 1),
    }


# ---------------------------------------------------------------------------
# 7. Security / error handling
# ---------------------------------------------------------------------------
async def scenario_security(base_url: str) -> dict[str, Any]:
    """
    Probe the server with adversarial inputs and verify it returns proper errors
    without crashing. Tests:
      a) oversized text payload (10 KB)
      b) fibonacci n out of range (n=999)
      c) invalid JSON schema
      d) batch with 1001 items (over limit)
      e) missing required argument
    """
    results: list[dict[str, Any]] = []

    async with McpClient(base_url) as client:

        # a) Oversized payload (10 KB)
        try:
            r = await client.call_tool("echo", {"text": "A" * 10_240})
            results.append({
                "test": "oversized_payload_10kb",
                "outcome": "accepted",
                "error": r.get("error") if isinstance(r, dict) else None,
            })
        except Exception as e:
            results.append({
                "test": "oversized_payload_10kb",
                "outcome": "rejected",
                "error": str(e),
            })

        # b) Out-of-range fibonacci
        try:
            r = await client.call_tool("fibonacci", {"n": 999})
            results.append({
                "test": "fibonacci_n_out_of_range",
                "outcome": "accepted",
                "error": r.get("error") if isinstance(r, dict) else None,
            })
        except Exception as e:
            results.append({
                "test": "fibonacci_n_out_of_range",
                "outcome": "rejected",
                "error": str(e),
            })

        # c) Invalid JSON schema (schema is a string, not object)
        try:
            r = await client.call_tool("validate_schema", {
                "data": {"key": "value"},
                "schema": "not-an-object",
            })
            results.append({
                "test": "invalid_schema_type",
                "outcome": "accepted",
                "error": r.get("error") if isinstance(r, dict) else None,
                "valid": r.get("valid") if isinstance(r, dict) else None,
            })
        except Exception as e:
            results.append({
                "test": "invalid_schema_type",
                "outcome": "rejected",
                "error": str(e),
            })

        # d) Batch over limit
        try:
            r = await client.call_tool("batch_process", {
                "items": list(range(1001)),
                "concurrency": 5,
            })
            results.append({
                "test": "batch_over_limit",
                "outcome": "accepted",
                "error": r.get("error") if isinstance(r, dict) else None,
            })
        except Exception as e:
            results.append({
                "test": "batch_over_limit",
                "outcome": "rejected",
                "error": str(e),
            })

        # e) Missing required argument
        try:
            r = await client.call_tool("echo", {})  # text is required
            results.append({
                "test": "missing_required_arg",
                "outcome": "accepted",
                "error": r.get("error") if isinstance(r, dict) else None,
            })
        except Exception as e:
            results.append({
                "test": "missing_required_arg",
                "outcome": "rejected",
                "error": str(e),
            })

        # Verify server is still alive after all probes
        try:
            await client.call_tool("echo", {"text": "post-security-check"})
            still_alive = True
        except Exception:
            still_alive = False

    # Score: count tests where server correctly rejected or handled the bad input
    handled = sum(
        1 for r in results
        if r["outcome"] == "rejected"
        or (r["outcome"] == "accepted" and r.get("error"))
        or (r.get("valid") is False)
    )

    return {
        "tests": results,
        "tests_handled_correctly": handled,
        "total_tests": len(results),
        "server_alive_after": still_alive,
    }
