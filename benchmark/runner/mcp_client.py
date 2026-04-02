"""
Minimal async MCP client for the Streamable HTTP transport.

Handles the three-step lifecycle:
  1. initialize()  — POST /mcp with no session header
                     → captures mcp-session-id response header
                     → sends notifications/initialized notification
  2. call_tool()   — POST /mcp with mcp-session-id header
  3. close()       — DELETE /mcp + client cleanup
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx


class McpClient:
    """One MCP session over Streamable HTTP."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.session_id: str | None = None
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._req_id = 0

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "McpClient":
        self._client = httpx.AsyncClient(timeout=self._timeout)
        await self.initialize()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Perform MCP handshake and capture the session ID."""
        self._client = self._client or httpx.AsyncClient(timeout=self._timeout)
        self._req_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "benchmark-runner", "version": "1.0.0"},
            },
        }
        resp = await self._client.post(f"{self.base_url}/mcp", json=payload)
        resp.raise_for_status()

        self.session_id = resp.headers.get("mcp-session-id")
        if not self.session_id:
            # Some servers return the ID in the JSON body instead
            body = resp.json()
            self.session_id = (
                body.get("result", {}).get("sessionId")
                or body.get("sessionId")
            )

        # Send initialized notification (fire-and-forget)
        await self._notify("notifications/initialized", {})

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool and return the parsed result."""
        if self._client is None:
            raise RuntimeError("Client not initialized — call initialize() first")

        self._req_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        headers: dict[str, str] = {}
        if self.session_id:
            headers["mcp-session-id"] = self.session_id

        resp = await self._client.post(
            f"{self.base_url}/mcp", json=payload, headers=headers
        )
        resp.raise_for_status()
        body = resp.json()

        if "error" in body:
            err = body["error"]
            raise RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}")

        # Result content is an array of {type, text} blocks
        result = body.get("result", {})
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            import json as _json
            try:
                return _json.loads(content[0]["text"])
            except Exception:
                return content[0]["text"]
        return result

    async def call_tool_timed(
        self, name: str, arguments: dict[str, Any]
    ) -> tuple[Any, float]:
        """call_tool() that also returns wall-clock latency in ms."""
        t0 = time.perf_counter()
        result = await self.call_tool(name, arguments)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return result, elapsed_ms

    async def close(self) -> None:
        if self._client is None:
            return
        if self.session_id:
            try:
                await self._client.delete(
                    f"{self.base_url}/mcp",
                    headers={"mcp-session-id": self.session_id},
                )
            except Exception:
                pass
        await self._client.aclose()
        self._client = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        headers: dict[str, str] = {}
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        try:
            await self._client.post(  # type: ignore[union-attr]
                f"{self.base_url}/mcp", json=payload, headers=headers
            )
        except Exception:
            pass  # notifications are fire-and-forget


async def wait_for_health(url: str, timeout_s: float = 60.0) -> bool:
    """Poll GET /health until 200 or timeout."""
    deadline = time.monotonic() + timeout_s
    async with httpx.AsyncClient(timeout=5.0) as client:
        while time.monotonic() < deadline:
            try:
                r = await client.get(f"{url}/health")
                if r.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(1.0)
    return False
