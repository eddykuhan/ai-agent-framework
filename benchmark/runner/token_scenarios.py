"""
Token-consumption scenarios: JSON vs TOON.

Each scenario produces a representative MCP tool result payload and measures
how many tokens that payload consumes when serialized as:

  1. **Bare JSON** – the tool result dict serialized with json.dumps (compact).
  2. **Bare TOON** – the tool result dict serialized with toon_formatter.encode.
  3. **MCP JSON envelope** – full JSON-RPC 2.0 response as sent over the wire.
  4. **MCP TOON envelope** – compact ``[r:id]<toon>`` envelope.

Token counts use ``tiktoken`` with the ``cl100k_base`` encoding, which is a
widely-used approximation for modern LLM tokenizers (including Claude).

Each scenario function returns a ``ScenarioResult`` dict with the following keys:

  name          – human-readable scenario name
  description   – what the payload represents
  tool_result   – the raw Python dict (the tool output)
  bare_json     – JSON string (compact, no whitespace)
  bare_toon     – TOON string
  mcp_json      – full MCP JSON-RPC envelope string
  mcp_toon      – compact TOON envelope string
  tokens        – dict with keys: bare_json, bare_toon, mcp_json, mcp_toon
  chars         – dict with keys: bare_json, bare_toon, mcp_json, mcp_toon
  savings       – dict with keys: toon_vs_json (%), mcp_toon_vs_mcp_json (%)
"""

from __future__ import annotations

import json
from typing import Any

import tiktoken

from toon_formatter import encode as toon_encode, mcp_envelope_json, mcp_envelope_toon

# Shared tokenizer – cl100k_base is used by GPT-4 / text-embedding-3 and is a
# reasonable proxy for Claude's BPE tokenizer.
_ENC = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_ENC.encode(text))


def _build_result(
    name: str,
    description: str,
    tool_result: Any,
    request_id: int = 1,
) -> dict[str, Any]:
    bare_json = json.dumps(tool_result, separators=(",", ":"))
    bare_toon = toon_encode(tool_result)
    mcp_json = mcp_envelope_json(tool_result, request_id)
    mcp_toon = mcp_envelope_toon(tool_result, request_id)

    tokens = {
        "bare_json":  _count_tokens(bare_json),
        "bare_toon":  _count_tokens(bare_toon),
        "mcp_json":   _count_tokens(mcp_json),
        "mcp_toon":   _count_tokens(mcp_toon),
    }
    chars = {
        "bare_json":  len(bare_json),
        "bare_toon":  len(bare_toon),
        "mcp_json":   len(mcp_json),
        "mcp_toon":   len(mcp_toon),
    }

    def _pct_saved(larger: int, smaller: int) -> float:
        if larger == 0:
            return 0.0
        return round((1 - smaller / larger) * 100, 1)

    savings = {
        "toon_vs_json":           _pct_saved(tokens["bare_json"],  tokens["bare_toon"]),
        "mcp_toon_vs_mcp_json":   _pct_saved(tokens["mcp_json"],   tokens["mcp_toon"]),
        "chars_toon_vs_json":     _pct_saved(chars["bare_json"],   chars["bare_toon"]),
        "chars_mcp_toon_vs_json": _pct_saved(chars["mcp_json"],    chars["mcp_toon"]),
    }

    return {
        "name":        name,
        "description": description,
        "tool_result": tool_result,
        "bare_json":   bare_json,
        "bare_toon":   bare_toon,
        "mcp_json":    mcp_json,
        "mcp_toon":    mcp_toon,
        "tokens":      tokens,
        "chars":       chars,
        "savings":     savings,
    }


# ---------------------------------------------------------------------------
# Individual scenarios
# ---------------------------------------------------------------------------

def scenario_echo_small() -> dict[str, Any]:
    """echo tool with a short string — baseline / minimal payload."""
    return _build_result(
        name="echo_small",
        description="echo tool: 5-char string",
        tool_result={"echo": "hello", "length": 5},
    )


def scenario_echo_medium() -> dict[str, Any]:
    """echo tool with a 100-character string — moderate text payload."""
    text = "The quick brown fox jumps over the lazy dog. " * 3  # ~135 chars, trimmed
    text = text[:100]
    return _build_result(
        name="echo_medium",
        description="echo tool: 100-char string",
        tool_result={"echo": text, "length": len(text)},
    )


def scenario_echo_large() -> dict[str, Any]:
    """echo tool with a 1 KB string — large text payload."""
    text = ("x" * 64 + " ") * 16  # 1040 chars
    text = text[:1024]
    return _build_result(
        name="echo_large",
        description="echo tool: 1 024-char string",
        tool_result={"echo": text, "length": len(text)},
    )


def scenario_fibonacci() -> dict[str, Any]:
    """fibonacci(30) result — numeric values only."""
    return _build_result(
        name="fibonacci",
        description="fibonacci tool: n=30, result=832040",
        tool_result={"n": 30, "result": 832040, "elapsed_ms": 12.345},
    )


def scenario_fetch_mock() -> dict[str, Any]:
    """fetch_mock result — URL string + numeric fields."""
    return _build_result(
        name="fetch_mock",
        description="fetch_mock tool: simulated HTTP response metadata",
        tool_result={
            "url": "https://example.com",
            "delay_ms": 50,
            "status": 200,
            "body_length": 1024,
        },
    )


def scenario_batch_small() -> dict[str, Any]:
    """batch_process result for 10 items — flat numeric result."""
    return _build_result(
        name="batch_small",
        description="batch_process tool: 10 items",
        tool_result={"count": 10, "elapsed_ms": 5.231, "concurrency": 5},
    )


def scenario_batch_large() -> dict[str, Any]:
    """batch_process result for 500 items — larger numeric result."""
    return _build_result(
        name="batch_large",
        description="batch_process tool: 500 items",
        tool_result={"count": 500, "elapsed_ms": 234.567, "concurrency": 10},
    )


def scenario_validate_valid() -> dict[str, Any]:
    """validate_schema result: data is valid — boolean + empty array."""
    return _build_result(
        name="validate_valid",
        description="validate_schema tool: valid data",
        tool_result={"valid": True, "errors": []},
    )


def scenario_validate_invalid() -> dict[str, Any]:
    """validate_schema result: data is invalid — boolean + error strings."""
    return _build_result(
        name="validate_invalid",
        description="validate_schema tool: invalid data with two errors",
        tool_result={
            "valid": False,
            "errors": [
                "'name' is a required property",
                "42 is not of type 'string'",
            ],
        },
    )


def scenario_nested_metadata() -> dict[str, Any]:
    """
    Hypothetical rich tool result with nested metadata — tests dot-notation
    flattening and the compactness advantage for deeply nested structures.
    """
    return _build_result(
        name="nested_metadata",
        description="Rich result with nested metadata (simulated agent observation)",
        tool_result={
            "status": "success",
            "data": {
                "id": "record-42",
                "value": 99.9,
                "tags": ["alpha", "beta", "gamma"],
            },
            "meta": {
                "elapsed_ms": 18.7,
                "cached": False,
                "source": "db-primary",
                "version": 3,
            },
        },
    )


def scenario_repeated_keys() -> dict[str, Any]:
    """
    Result mimicking a multi-step agent observation log where the same
    structural keys repeat across many entries — JSON key repetition overhead
    is most visible here.
    """
    entries = [
        {"step": i, "tool": "echo", "tokens_in": 120 + i, "tokens_out": 30 + i, "ok": True}
        for i in range(1, 11)
    ]
    return _build_result(
        name="repeated_keys",
        description="Agent observation log: 10 entries with identical key structure",
        tool_result={"entries": entries, "total_steps": 10},
    )


# ---------------------------------------------------------------------------
# Run all scenarios
# ---------------------------------------------------------------------------

def run_all() -> list[dict[str, Any]]:
    """Execute every scenario and return a list of ScenarioResult dicts."""
    fns = [
        scenario_echo_small,
        scenario_echo_medium,
        scenario_echo_large,
        scenario_fibonacci,
        scenario_fetch_mock,
        scenario_batch_small,
        scenario_batch_large,
        scenario_validate_valid,
        scenario_validate_invalid,
        scenario_nested_metadata,
        scenario_repeated_keys,
    ]
    return [fn() for fn in fns]
