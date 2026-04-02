"""
Pure-Python tool implementations for the MCP benchmark server.
All tools are async-native and language-idiomatic.
"""

import asyncio
import json
import time
from typing import Any

import jsonschema


def _fib(n: int) -> int:
    """Naive recursive Fibonacci — intentionally CPU-bound for benchmarking."""
    if n <= 1:
        return n
    return _fib(n - 1) + _fib(n - 2)


async def echo(text: str) -> dict[str, Any]:
    """Return input text unchanged. Used for baseline latency measurement."""
    return {"echo": text, "length": len(text)}


async def fibonacci(n: int) -> dict[str, Any]:
    """CPU-bound recursive Fibonacci computation."""
    start = time.perf_counter()
    result = _fib(n)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return {"n": n, "result": result, "elapsed_ms": round(elapsed_ms, 3)}


async def fetch_mock(delay_ms: int = 50, url: str = "https://example.com") -> dict[str, Any]:
    """Simulate an async HTTP fetch with configurable latency."""
    await asyncio.sleep(delay_ms / 1000)
    return {
        "url": url,
        "delay_ms": delay_ms,
        "status": 200,
        "body_length": 1024,
    }


async def batch_process(items: list[Any], concurrency: int = 10) -> dict[str, Any]:
    """Process N items concurrently using an asyncio semaphore."""
    sem = asyncio.Semaphore(concurrency)

    async def process_one(item: Any) -> dict[str, Any]:
        async with sem:
            await asyncio.sleep(0.001)  # simulate minimal per-item work
            return {"item": item, "processed": True}

    start = time.perf_counter()
    results = await asyncio.gather(*[process_one(i) for i in items])
    elapsed_ms = (time.perf_counter() - start) * 1000
    return {
        "count": len(results),
        "elapsed_ms": round(elapsed_ms, 3),
        "concurrency": concurrency,
    }


async def validate_schema(data: Any, schema: dict[str, Any]) -> dict[str, Any]:
    """Validate arbitrary data against a JSON Schema."""
    errors: list[str] = []
    valid = True
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        valid = False
        errors = [e.message]
    except jsonschema.SchemaError as e:
        valid = False
        errors = [f"Invalid schema: {e.message}"]
    except Exception as e:
        valid = False
        errors = [str(e)]
    return {"valid": valid, "errors": errors}
