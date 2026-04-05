"""
TOON (Token-Optimized Output Notation) encoder/decoder.

TOON is a compact, LLM-friendly serialization format designed to reduce token
consumption when MCP tool results are embedded in an LLM context window.

Compared to JSON, TOON eliminates structural overhead tokens (braces, colons,
redundant quotes) while remaining human-readable and unambiguous.

Format rules
------------
- Top-level structure is a flat sequence of ``key=value`` pairs.
- Pairs are separated by ``|`` (pipe).
- Nested dict keys use dot notation: ``parent.child=value``.
- Arrays use comma-separated items in brackets: ``key=[v1,v2,v3]``.
- Array of objects: ``key=[{k1=v1,k2=v2},{k1=v3}]``.
- Booleans:  ``T`` (true) / ``F`` (false).
- Null:      ``~``.
- Numbers:   unquoted (``42``, ``3.14``, ``-7``).
- Strings:   unquoted if they contain no special chars; otherwise
             backtick-quoted with internal backticks escaped as ``\\```.

Special characters that trigger quoting: ``| = [ ] { } ` , .``

Examples
--------
JSON  : {"status": "ok", "count": 42}
TOON  : status=ok|count=42

JSON  : {"valid": true, "errors": []}
TOON  : valid=T|errors=[]

JSON  : {"url": "https://example.com", "delay_ms": 50}
TOON  : url=`https://example.com`|delay_ms=50

JSON  : {"meta": {"elapsed_ms": 10.5, "cached": false}}
TOON  : meta.elapsed_ms=10.5|meta.cached=F

JSON  : {"rows": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]}
TOON  : rows=[{x=1,y=2},{x=3,y=4}]
"""

from __future__ import annotations

import json
from typing import Any


# Characters that require a string value to be backtick-quoted.
_SPECIAL: frozenset[str] = frozenset("|=[]{}`,.\\")


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

def _needs_quoting(s: str) -> bool:
    return not s or any(c in _SPECIAL for c in s)


def _quote(s: str) -> str:
    """Wrap a string in backticks, escaping any internal backticks."""
    return "`" + s.replace("\\", "\\\\").replace("`", "\\`") + "`"


def _encode_primitive(v: Any) -> str:
    if v is None:
        return "~"
    if isinstance(v, bool):
        return "T" if v else "F"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        # Avoid scientific notation for reasonable magnitudes.
        formatted = f"{v:.10g}"
        return formatted
    if isinstance(v, str):
        return _quote(v) if _needs_quoting(v) else v
    raise TypeError(f"Cannot encode primitive of type {type(v).__name__}")


def _encode_value(v: Any) -> str:
    """Recursively encode a value (primitive, list, or dict)."""
    if isinstance(v, dict):
        if not v:
            return "{}"
        inner = ",".join(
            f"{_encode_inner_key(k)}={_encode_value(val)}"
            for k, val in v.items()
        )
        return "{" + inner + "}"
    if isinstance(v, list):
        return "[" + ",".join(_encode_value(item) for item in v) + "]"
    return _encode_primitive(v)


def _encode_inner_key(k: str) -> str:
    """Encode a key that appears inside an array-of-objects or nested dict."""
    return _quote(k) if _needs_quoting(k) else k


def _flatten_dict(d: dict[str, Any], prefix: str, parts: list[str]) -> None:
    """Recursively flatten a dict into ``key=value`` parts using dot notation."""
    for k, v in d.items():
        full_key = f"{prefix}{k}" if prefix else k
        if isinstance(v, dict):
            _flatten_dict(v, f"{full_key}.", parts)
        else:
            parts.append(f"{_encode_inner_key(full_key)}={_encode_value(v)}")


# ---------------------------------------------------------------------------
# Public encode API
# ---------------------------------------------------------------------------

def encode(obj: Any) -> str:
    """
    Encode a Python object to a TOON string.

    Top-level dicts are flattened with dot-notation keys.
    Any other type is encoded as a single value.
    """
    if not isinstance(obj, dict):
        return _encode_value(obj)
    if not obj:
        return ""
    parts: list[str] = []
    _flatten_dict(obj, "", parts)
    return "|".join(parts)


# ---------------------------------------------------------------------------
# Decoding helpers
# ---------------------------------------------------------------------------

def _split_on(s: str, sep: str) -> list[str]:
    """
    Split *s* on *sep* while respecting bracket nesting and backtick quoting.
    """
    parts: list[str] = []
    depth = 0
    in_backtick = False
    buf: list[str] = []

    i = 0
    while i < len(s):
        ch = s[i]

        if in_backtick:
            if ch == "\\" and i + 1 < len(s):
                buf.append(ch)
                buf.append(s[i + 1])
                i += 2
                continue
            if ch == "`":
                in_backtick = False
            buf.append(ch)
        elif ch == "`":
            in_backtick = True
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        else:
            buf.append(ch)
        i += 1

    if buf or (s and s[-1] == sep):
        parts.append("".join(buf))

    return parts


def _unquote(s: str) -> str:
    """Remove backtick quoting and unescape."""
    inner = s[1:-1]
    return inner.replace("\\`", "`").replace("\\\\", "\\")


def _decode_value(s: str) -> Any:
    """Decode a single TOON value token."""
    if s == "~":
        return None
    if s == "T":
        return True
    if s == "F":
        return False
    if s.startswith("`") and s.endswith("`"):
        return _unquote(s)

    # Array
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1]
        if not inner:
            return []
        return [_decode_value(item) for item in _split_on(inner, ",")]

    # Object (nested)
    if s.startswith("{") and s.endswith("}"):
        inner = s[1:-1]
        if not inner:
            return {}
        result: dict[str, Any] = {}
        for pair in _split_on(inner, ","):
            eq_idx = pair.find("=")
            if eq_idx == -1:
                continue
            k_raw, v_raw = pair[:eq_idx], pair[eq_idx + 1:]
            k = _unquote(k_raw) if k_raw.startswith("`") else k_raw
            result[k] = _decode_value(v_raw)
        return result

    # Number attempt
    try:
        if "." in s or "e" in s or "E" in s:
            return float(s)
        return int(s)
    except ValueError:
        pass

    # Plain string
    return s


def _set_nested(target: dict[str, Any], dot_key: str, value: Any) -> None:
    """Set *value* in *target* using a dot-separated key path."""
    keys = dot_key.split(".")
    d = target
    for part in keys[:-1]:
        if part not in d or not isinstance(d[part], dict):
            d[part] = {}
        d = d[part]
    d[keys[-1]] = value


# ---------------------------------------------------------------------------
# Public decode API
# ---------------------------------------------------------------------------

def decode(toon: str) -> Any:
    """
    Decode a TOON string back to a Python object.

    A string that was encoded from a flat dict is returned as a dict.
    A string with no ``|`` or ``=`` at the top level is decoded as a
    primitive value.
    """
    if not toon:
        return {}

    # Check whether this looks like a key=value sequence.
    pairs = _split_on(toon, "|")
    if len(pairs) == 1 and "=" not in pairs[0].split("`")[0]:
        # Single primitive
        return _decode_value(toon)

    result: dict[str, Any] = {}
    for pair in pairs:
        # Find first `=` not inside a backtick span
        eq_parts = _split_on(pair, "=")
        if len(eq_parts) < 2:
            continue
        k_raw = eq_parts[0]
        v_raw = "=".join(eq_parts[1:])  # value may contain = inside backticks
        k = _unquote(k_raw) if k_raw.startswith("`") else k_raw
        _set_nested(result, k, _decode_value(v_raw))

    return result


# ---------------------------------------------------------------------------
# Utility: wrap in a minimal MCP-like envelope
# ---------------------------------------------------------------------------

def mcp_envelope_json(tool_result: Any, request_id: int = 1) -> str:
    """
    Return the canonical MCP JSON-RPC response envelope for a tool result.
    The tool result is serialized as JSON and embedded in the text content block.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [
                {"type": "text", "text": json.dumps(tool_result, separators=(",", ":"))}
            ]
        },
    }
    return json.dumps(payload, separators=(",", ":"))


def mcp_envelope_toon(tool_result: Any, request_id: int = 1) -> str:
    """
    Return a compact TOON envelope for a tool result.
    Format:  [r:id]<toon-encoded-result>
    """
    return f"[r:{request_id}]{encode(tool_result)}"
