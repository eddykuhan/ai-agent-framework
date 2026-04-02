"""
Report generator — converts raw benchmark JSON into a human-readable Markdown
decision report covering all five evaluation dimensions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Developer onboarding static data
# (measured by counting lines / deps in the actual source files)
# ---------------------------------------------------------------------------
ONBOARDING_DATA: dict[str, dict[str, Any]] = {
    "python": {
        "runtime": "Python 3.12 + uvicorn",
        "sdk": "mcp[cli] (FastMCP)",
        "sdk_maturity": "Stable (official Anthropic SDK)",
        "type_safety": "Moderate (Pydantic type hints, runtime validated)",
        "server_loc": None,   # filled in dynamically
        "tools_loc": None,
        "prod_deps": 2,       # mcp[cli], jsonschema
        "dev_deps": 0,
        "setup_steps": [
            "python -m venv .venv && source .venv/bin/activate",
            "pip install -r requirements.txt",
            "python server.py",
        ],
        "ide_support": "Excellent (PyCharm, VS Code + Pylance)",
        "async_model": "asyncio (native coroutines)",
        "container_base": "python:3.12-slim (~50 MB)",
    },
    "typescript": {
        "runtime": "Node.js 22 + Express 4",
        "sdk": "@modelcontextprotocol/sdk",
        "sdk_maturity": "Stable (official Anthropic SDK)",
        "type_safety": "Strong (TypeScript strict mode, compile-time checked)",
        "server_loc": None,
        "tools_loc": None,
        "prod_deps": 3,       # @modelcontextprotocol/sdk, express, ajv
        "dev_deps": 4,        # typescript, tsx, @types/node, @types/express
        "setup_steps": [
            "npm install",
            "npm run build",
            "npm start",
        ],
        "ide_support": "Excellent (VS Code first-class, IntelliSense)",
        "async_model": "Promise / async-await (event loop)",
        "container_base": "node:22-slim (~70 MB, multi-stage build)",
    },
    "dotnet": {
        "runtime": ".NET 9 + ASP.NET Core Kestrel",
        "sdk": "ModelContextProtocol + ModelContextProtocol.AspNetCore",
        "sdk_maturity": "Pre-release (0.2.0-preview.3 — Microsoft official)",
        "type_safety": "Strong (statically compiled, nullable reference types)",
        "server_loc": None,
        "tools_loc": None,
        "prod_deps": 3,       # ModelContextProtocol, AspNetCore, NJsonSchema
        "dev_deps": 0,        # no dev-only packages needed
        "setup_steps": [
            "dotnet restore",
            "dotnet build",
            "dotnet run --project McpBenchmarkServer",
        ],
        "ide_support": "Excellent (Visual Studio, Rider, VS Code + C# Dev Kit)",
        "async_model": "Task/async-await + thread pool (true parallelism)",
        "container_base": "mcr.microsoft.com/dotnet/aspnet:9.0 (~110 MB)",
    },
}


def _count_loc(path: Path) -> int:
    """Count non-blank, non-comment lines in a source file."""
    if not path.exists():
        return -1
    count = 0
    comment_chars = {"#", "//", "<!--", "*", "///"}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not any(stripped.startswith(c) for c in comment_chars):
            count += 1
    return count


def _fill_loc(benchmark_dir: Path) -> None:
    """Populate LOC fields in ONBOARDING_DATA from actual source files."""
    mappings = {
        "python": {
            "server_loc": benchmark_dir / "python" / "server.py",
            "tools_loc": benchmark_dir / "python" / "tools.py",
        },
        "typescript": {
            "server_loc": benchmark_dir / "typescript" / "src" / "server.ts",
            "tools_loc": benchmark_dir / "typescript" / "src" / "tools.ts",
        },
        "dotnet": {
            "server_loc": benchmark_dir / "dotnet" / "McpBenchmarkServer" / "Program.cs",
            "tools_loc": benchmark_dir / "dotnet" / "McpBenchmarkServer" / "Tools.cs",
        },
    }
    for lang, files in mappings.items():
        for field, path in files.items():
            ONBOARDING_DATA[lang][field] = _count_loc(path)


def _score(value: float, lower_is_better: bool, peers: list[float]) -> int:
    """Return a score from 1 (worst) to 3 (best) relative to peer values."""
    ranked = sorted(peers, reverse=not lower_is_better)
    rank = ranked.index(value) if value in ranked else 0
    return 3 - rank  # 1st place = 3, 3rd place = 1


def generate(
    results: dict[str, Any],
    benchmark_dir: Path,
    out_dir: Path,
) -> tuple[Path, Path]:
    """
    Write raw JSON and Markdown report. Returns (json_path, md_path).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    _fill_loc(benchmark_dir)

    # ---- Write raw JSON ------------------------------------------------
    json_path = out_dir / f"raw_{ts}.json"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # ---- Build markdown ------------------------------------------------
    md_path = out_dir / f"report_{ts}.md"
    md_path.write_text(_build_markdown(results, ts), encoding="utf-8")

    return json_path, md_path


def _build_markdown(results: dict[str, Any], ts: str) -> str:
    langs = ["python", "typescript", "dotnet"]
    labels = {"python": "Python", "typescript": "TypeScript", "dotnet": ".NET"}

    lines: list[str] = []
    a = lines.append

    a(f"# MCP Language Benchmark Report")
    a(f"")
    a(f"**Generated:** {ts.replace('_', ' ')} UTC  ")
    a(f"**Languages:** Python 3.12 · TypeScript (Node 22) · .NET 9  ")
    a(f"**Transport:** Streamable HTTP (MCP 2024-11-05)  ")
    a(f"")

    # ---- Executive Summary Table ---------------------------------------
    a("## Executive Summary")
    a("")
    a("Scores are **1–3** (3 = best). Higher is always better.")
    a("")
    a("| Dimension | Python | TypeScript | .NET |")
    a("|-----------|--------|------------|------|")

    def row(label: str, scores: dict[str, int]) -> str:
        return f"| {label} | {'⭐' * scores['python']} | {'⭐' * scores['typescript']} | {'⭐' * scores['dotnet']} |"

    # Latency score (lower p99 = better)
    p99s = {
        lang: results.get(lang, {}).get("latency", {}).get("p99_ms", 9999)
        for lang in langs
    }
    lat_scores = {lang: _score(p99s[lang], True, list(p99s.values())) for lang in langs}
    a(row("Performance (p99 latency)", lat_scores))

    # Throughput at concurrency=100
    def get_rps(lang: str, c: int) -> float:
        levels = results.get(lang, {}).get("throughput", {}).get("levels", [])
        for lv in levels:
            if lv.get("concurrency") == c:
                return lv.get("rps", 0)
        return 0.0

    rps100 = {lang: get_rps(lang, 100) for lang in langs}
    tp_scores = {lang: _score(rps100[lang], False, list(rps100.values())) for lang in langs}
    a(row("Scalability (RPS @ concurrency=100)", tp_scores))

    # Async I/O (wall time for 100 concurrent calls)
    async_wall = {
        lang: results.get(lang, {}).get("async_io", {}).get("wall_ms", 99999)
        for lang in langs
    }
    async_scores = {lang: _score(async_wall[lang], True, list(async_wall.values())) for lang in langs}
    a(row("Async I/O (100 concurrent fetches)", async_scores))

    # Developer onboarding (total LOC — lower = simpler)
    total_loc = {
        lang: (ONBOARDING_DATA[lang].get("server_loc") or 0)
              + (ONBOARDING_DATA[lang].get("tools_loc") or 0)
        for lang in langs
    }
    dev_scores = {lang: _score(total_loc[lang], True, list(total_loc.values())) for lang in langs}
    a(row("Developer Onboarding (LOC)", dev_scores))

    # Security (tests handled correctly — higher = better)
    sec_handled = {
        lang: results.get(lang, {}).get("security", {}).get("tests_handled_correctly", 0)
        for lang in langs
    }
    sec_scores = {lang: _score(sec_handled[lang], False, list(sec_handled.values())) for lang in langs}
    a(row("Security (input validation)", sec_scores))

    # Total
    totals = {lang: lat_scores[lang] + tp_scores[lang] + async_scores[lang]
                     + dev_scores[lang] + sec_scores[lang] for lang in langs}
    a(f"| **Total** | **{totals['python']}/15** | **{totals['typescript']}/15** | **{totals['dotnet']}/15** |")
    a("")

    # ---- Dimension Details --------------------------------------------
    a("---")
    a("")
    a("## 1. Performance — Latency Baseline (Sequential Echo)")
    a("")
    a("| Metric | Python | TypeScript | .NET |")
    a("|--------|--------|------------|------|")
    for metric in ["p50_ms", "p95_ms", "p99_ms", "mean_ms", "min_ms", "max_ms"]:
        vals = [
            results.get(lang, {}).get("latency", {}).get(metric, "—")
            for lang in langs
        ]
        a(f"| {metric} | {vals[0]} | {vals[1]} | {vals[2]} |")
    a("")

    a("## 2. Scalability — Throughput (Requests / Second)")
    a("")
    a("| Concurrency | Python RPS | TypeScript RPS | .NET RPS |")
    a("|-------------|-----------|----------------|---------|")
    for c in [1, 10, 50, 100]:
        vals = [get_rps(lang, c) for lang in langs]
        a(f"| {c} | {vals[0]} | {vals[1]} | {vals[2]} |")
    a("")

    a("## 3. CPU Performance — fibonacci(30) × 100")
    a("")
    a("| Metric | Python | TypeScript | .NET |")
    a("|--------|--------|------------|------|")
    for metric in ["mean_ms", "p50_ms", "p95_ms", "total_ms"]:
        vals = [
            results.get(lang, {}).get("cpu", {}).get(metric, "—")
            for lang in langs
        ]
        a(f"| {metric} | {vals[0]} | {vals[1]} | {vals[2]} |")
    a("")

    a("## 4. Async I/O — 100 Concurrent fetch_mock(50 ms)")
    a("")
    a("| Metric | Python | TypeScript | .NET |")
    a("|--------|--------|------------|------|")
    for metric in ["wall_ms", "mean_call_ms", "p95_call_ms", "throughput_rps", "concurrency_ratio"]:
        vals = [
            results.get(lang, {}).get("async_io", {}).get(metric, "—")
            for lang in langs
        ]
        a(f"| {metric} | {vals[0]} | {vals[1]} | {vals[2]} |")
    a("")

    a("## 5. Memory Under Load (1 000 Requests)")
    a("")
    a("| Metric | Python | TypeScript | .NET |")
    a("|--------|--------|------------|------|")
    for metric in ["baseline_rss_mb", "peak_rss_mb", "growth_rss_mb"]:
        vals = [
            results.get(lang, {}).get("memory", {}).get(metric, "—")
            for lang in langs
        ]
        a(f"| {metric} | {vals[0]} | {vals[1]} | {vals[2]} |")
    a("")

    a("## 6. Developer Onboarding")
    a("")
    a("| Attribute | Python | TypeScript | .NET |")
    a("|-----------|--------|------------|------|")
    attrs = [
        ("Runtime", "runtime"),
        ("SDK", "sdk"),
        ("SDK Maturity", "sdk_maturity"),
        ("Type Safety", "type_safety"),
        ("Server LOC", "server_loc"),
        ("Tools LOC", "tools_loc"),
        ("Production Dependencies", "prod_deps"),
        ("Dev Dependencies", "dev_deps"),
        ("Async Model", "async_model"),
        ("IDE Support", "ide_support"),
        ("Container Base", "container_base"),
    ]
    for label, key in attrs:
        vals = [ONBOARDING_DATA[lang].get(key, "—") for lang in langs]
        a(f"| {label} | {vals[0]} | {vals[1]} | {vals[2]} |")
    a("")
    a("**Setup steps (clone → running server):**")
    a("")
    for lang in langs:
        a(f"**{labels[lang]}**")
        for i, step in enumerate(ONBOARDING_DATA[lang].get("setup_steps", []), 1):
            a(f"{i}. `{step}`")
        a("")

    a("## 7. Security — Input Validation")
    a("")
    a("| Test | Python | TypeScript | .NET |")
    a("|------|--------|------------|------|")
    # Collect all test names
    all_tests: list[str] = []
    for lang in langs:
        for t in results.get(lang, {}).get("security", {}).get("tests", []):
            if t["test"] not in all_tests:
                all_tests.append(t["test"])

    for test_name in all_tests:
        outcomes = []
        for lang in langs:
            sec = results.get(lang, {}).get("security", {})
            match = next((t for t in sec.get("tests", []) if t["test"] == test_name), None)
            if match:
                icon = "✅" if match["outcome"] == "rejected" or match.get("error") or match.get("valid") is False else "⚠️"
                outcomes.append(f"{icon} {match['outcome']}")
            else:
                outcomes.append("—")
        a(f"| `{test_name}` | {outcomes[0]} | {outcomes[1]} | {outcomes[2]} |")

    for lang in langs:
        sec = results.get(lang, {}).get("security", {})
        alive = "✅" if sec.get("server_alive_after") else "❌"
        a("")
        a(f"**{labels[lang]}** — {sec.get('tests_handled_correctly', '—')}/{sec.get('total_tests', '—')} tests handled correctly · Server alive after probes: {alive}")

    # ---- Recommendation -----------------------------------------------
    a("")
    a("---")
    a("")
    a("## Recommendation")
    a("")
    winner = max(totals, key=lambda k: totals[k])
    a(f"**Overall winner: {labels[winner]}** ({totals[winner]}/15 points)")
    a("")
    a("| Use Case | Recommended Language | Rationale |")
    a("|----------|---------------------|-----------|")
    a("| Maximum performance & throughput | .NET | AOT-compiled, true thread parallelism, Kestrel HTTP stack |")
    a("| Fastest developer onboarding | Python | Fewest lines of code, no build step, richest AI/ML ecosystem |")
    a("| Best async I/O & event-driven | TypeScript | Single-threaded event loop is ideal for I/O-bound MCP tools |")
    a("| Enterprise / existing .NET org | .NET | DI, strong typing, ASP.NET Core middleware ecosystem |")
    a("| Polyglot / multi-team org | TypeScript | Shares skills with frontend teams, excellent tooling |")
    a("")
    a("> **Note:** All three languages have official MCP SDKs and are viable production choices.")
    a("> The scores above reflect raw benchmark conditions; real-world choice should also factor")
    a("> in team expertise, existing infrastructure, and operational preferences.")
    a("")

    return "\n".join(lines)
