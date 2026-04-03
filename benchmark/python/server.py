"""
Python MCP benchmark server using FastMCP (mcp[cli]).
Transport: Streamable HTTP on port 8001 at /mcp
"""

import os

from mcp.server.fastmcp import FastMCP

from tools import batch_process, echo, fetch_mock, fibonacci, validate_schema

mcp = FastMCP(name="mcp-benchmark-python", version="1.0.0")


@mcp.tool()
async def echo_tool(text: str) -> dict:
    """Returns input text as-is. Used for baseline latency measurement."""
    return await echo(text)


@mcp.tool()
async def fibonacci_tool(n: int) -> dict:
    """
    CPU-bound naive recursive Fibonacci.
    n must be between 0 and 35 (inclusive) to prevent excessive computation.
    """
    if not (0 <= n <= 35):
        raise ValueError("n must be between 0 and 35")
    return await fibonacci(n)


@mcp.tool()
async def fetch_mock_tool(delay_ms: int = 50, url: str = "https://example.com") -> dict:
    """
    Simulated async HTTP fetch with configurable delay.
    delay_ms must be between 0 and 5000.
    """
    if not (0 <= delay_ms <= 5000):
        raise ValueError("delay_ms must be between 0 and 5000")
    return await fetch_mock(delay_ms, url)


@mcp.tool()
async def batch_process_tool(items: list, concurrency: int = 10) -> dict:
    """
    Process a list of items concurrently using asyncio.Semaphore.
    Maximum 1000 items per call. concurrency defaults to 10.
    """
    if len(items) > 1000:
        raise ValueError("Maximum 1000 items per batch")
    if not (1 <= concurrency <= 100):
        raise ValueError("concurrency must be between 1 and 100")
    return await batch_process(items, concurrency)


@mcp.tool()
async def validate_schema_tool(data: object, schema: object) -> dict:
    """
    Validate arbitrary data against a JSON Schema object.
    Returns {valid: bool, errors: list[str]}.
    """
    if not isinstance(schema, dict):
        raise ValueError("schema must be a JSON object")
    return await validate_schema(data, schema)


if __name__ == "__main__":
    host = os.getenv("FASTMCP_HOST", "0.0.0.0")
    port = int(os.getenv("FASTMCP_PORT", "8001"))
    mcp.run(transport="streamable-http", host=host, port=port, path="/mcp")
