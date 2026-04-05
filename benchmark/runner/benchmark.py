"""
Main benchmark orchestrator.

Usage (inside Docker via docker-compose):
    python benchmark.py

Usage (standalone, servers already running):
    PYTHON_URL=http://localhost:8001 \
    TS_URL=http://localhost:8002 \
    DOTNET_URL=http://localhost:8003 \
    python benchmark.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from mcp_client import wait_for_health
from report import generate
from scenarios import (
    scenario_async_io,
    scenario_cpu,
    scenario_latency,
    scenario_memory,
    scenario_security,
    scenario_throughput,
)
from token_scenarios import run_all as run_token_scenarios

console = Console()

SERVERS: dict[str, str] = {
    "python":     os.getenv("PYTHON_URL", "http://localhost:8001"),
    "typescript": os.getenv("TS_URL",     "http://localhost:8002"),
    "dotnet":     os.getenv("DOTNET_URL", "http://localhost:8003"),
}

BENCHMARK_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR   = BENCHMARK_DIR / "results"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hdr(title: str) -> None:
    console.rule(f"[bold cyan]{title}[/bold cyan]")


async def _run_scenario(
    label: str,
    coro: Any,
    progress: Progress,
) -> Any:
    task = progress.add_task(f"  {label}", total=None)
    t0 = time.perf_counter()
    try:
        result = await coro
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        progress.update(task, description=f"  ✅ {label} ({elapsed} ms)", completed=True)
        return result
    except Exception as exc:
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        progress.update(task, description=f"  ❌ {label} — {exc} ({elapsed} ms)", completed=True)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Per-language benchmark suite
# ---------------------------------------------------------------------------

async def benchmark_server(lang: str, url: str) -> dict[str, Any]:
    console.print(f"\n[bold yellow]▶  {lang.upper()} ({url})[/bold yellow]")

    results: dict[str, Any] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:

        results["latency"] = await _run_scenario(
            "Latency baseline (200 sequential echo)",
            scenario_latency(url, n_requests=200),
            progress,
        )

        results["throughput"] = await _run_scenario(
            "Throughput (concurrency 1/10/50/100 × 10 s)",
            scenario_throughput(url, concurrency_levels=[1, 10, 50, 100], duration_s=10.0),
            progress,
        )

        results["cpu"] = await _run_scenario(
            "CPU performance (fibonacci(30) × 100)",
            scenario_cpu(url, n_value=30, repeats=100),
            progress,
        )

        results["async_io"] = await _run_scenario(
            "Async I/O (100 concurrent fetch_mock @ 50 ms)",
            scenario_async_io(url, concurrency=100, delay_ms=50),
            progress,
        )

        results["memory"] = await _run_scenario(
            "Memory under load (1 000 echo requests)",
            scenario_memory(url, n_requests=1000, sample_every=50),
            progress,
        )

        results["security"] = await _run_scenario(
            "Security / error handling (5 adversarial probes)",
            scenario_security(url),
            progress,
        )

    return results


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def main() -> None:
    console.print()
    console.print("[bold green]MCP Language Benchmark[/bold green]")
    console.print("Python · TypeScript · .NET\n")

    # ---- Wait for all servers ------------------------------------------
    _hdr("Waiting for servers to be ready")
    ready_tasks = {
        lang: asyncio.create_task(wait_for_health(url, timeout_s=90.0))
        for lang, url in SERVERS.items()
    }
    all_ready = True
    for lang, task in ready_tasks.items():
        ok = await task
        icon = "✅" if ok else "❌"
        console.print(f"  {icon}  {lang:12s}  {SERVERS[lang]}")
        if not ok:
            all_ready = False

    if not all_ready:
        console.print("\n[bold red]One or more servers failed to start. Aborting.[/bold red]")
        sys.exit(1)

    # ---- Run scenarios per language ------------------------------------
    _hdr("Running benchmark scenarios")
    all_results: dict[str, Any] = {}

    for lang, url in SERVERS.items():
        try:
            all_results[lang] = await benchmark_server(lang, url)
        except Exception as exc:
            console.print(f"[red]Fatal error benchmarking {lang}: {exc}[/red]")
            all_results[lang] = {"fatal_error": str(exc)}

    # ---- Token consumption: JSON vs TOON ----------------------------------
    _hdr("Token consumption: JSON vs TOON")
    console.print("  Running token-consumption scenarios (no live servers needed)…")
    try:
        token_results = run_token_scenarios()
        all_results["token_consumption"] = {
            "scenarios": len(token_results),
            "results": [
                {k: v for k, v in r.items()
                 if k not in {"bare_json", "bare_toon", "mcp_json", "mcp_toon", "tool_result"}}
                for r in token_results
            ],
        }
        import statistics as _stats
        mcp_savings = [r["savings"]["mcp_toon_vs_mcp_json"] for r in token_results]
        avg_saving = round(_stats.mean(mcp_savings), 1)
        console.print(
            f"  ✅ {len(token_results)} scenarios complete — "
            f"MCP TOON saves [green]~{avg_saving}%[/green] tokens vs MCP JSON on average"
        )
    except Exception as exc:
        console.print(f"  [yellow]⚠️  Token benchmark skipped: {exc}[/yellow]")
        all_results["token_consumption"] = {"error": str(exc)}

    # ---- Generate report -----------------------------------------------
    _hdr("Generating report")
    json_path, md_path = generate(all_results, BENCHMARK_DIR, RESULTS_DIR)
    console.print(f"  Raw JSON : [cyan]{json_path}[/cyan]")
    console.print(f"  Report   : [cyan]{md_path}[/cyan]")

    # ---- Print quick summary table ------------------------------------
    _hdr("Quick Summary")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="bold")
    for lang in SERVERS:
        table.add_column(lang.capitalize(), justify="right")

    def _v(lang: str, *keys: str) -> str:
        d = all_results.get(lang, {})
        for k in keys:
            if isinstance(d, dict):
                d = d.get(k, "—")
            else:
                return "—"
        return str(d) if d != "—" else "—"

    rows = [
        ("Latency p99 (ms)",          "latency",    "p99_ms"),
        ("Latency mean (ms)",          "latency",    "mean_ms"),
        ("RPS @ concurrency=1",        None,         None),
        ("RPS @ concurrency=100",      None,         None),
        ("CPU fib(30) mean (ms)",      "cpu",        "mean_ms"),
        ("Async I/O wall (ms)",        "async_io",   "wall_ms"),
        ("Memory peak (MB)",           "memory",     "peak_rss_mb"),
        ("Security handled",           "security",   "tests_handled_correctly"),
    ]

    for label, s1, s2 in rows:
        if label.startswith("RPS @"):
            c = int(label.split("=")[1])
            vals = []
            for lang in SERVERS:
                levels = all_results.get(lang, {}).get("throughput", {}).get("levels", [])
                rps = next((lv["rps"] for lv in levels if lv.get("concurrency") == c), "—")
                vals.append(str(rps))
            table.add_row(label, *vals)
        else:
            vals = [_v(lang, s1, s2) for lang in SERVERS]  # type: ignore[arg-type]
            table.add_row(label, *vals)

    console.print(table)
    console.print(f"\n[bold green]Done.[/bold green] Full report: {md_path}\n")


if __name__ == "__main__":
    asyncio.run(main())
