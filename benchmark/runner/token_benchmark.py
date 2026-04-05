"""
Token-consumption benchmark: JSON vs TOON in MCP tool responses.

Run standalone (no live MCP servers required):

    cd benchmark/runner
    pip install -r requirements.txt
    python token_benchmark.py

Results are written to benchmark/results/:
    token_raw_<timestamp>.json   ← machine-readable data
    token_report_<timestamp>.md  ← human-readable report

The benchmark measures token count for each serialization format across 11
representative MCP tool-result payloads, using the cl100k_base tokenizer
as a Claude/GPT-4 approximation.
"""

from __future__ import annotations

import json
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from token_scenarios import run_all

console = Console()

BENCHMARK_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR   = BENCHMARK_DIR / "results"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _pct_str(value: float) -> str:
    sign = "-" if value > 0 else "+"
    return f"{sign}{abs(value):.1f}%"


def _build_markdown(results: list[dict[str, Any]], ts: str) -> str:
    lines: list[str] = []
    a = lines.append

    a("# MCP Token-Consumption Benchmark: JSON vs TOON")
    a("")
    a(f"**Generated:** {ts.replace('_', ' ')} UTC  ")
    a(f"**Tokenizer:** tiktoken `cl100k_base` (Claude / GPT-4 BPE approximation)  ")
    a(f"**Scenarios:** {len(results)}  ")
    a("")
    a("## What is TOON?")
    a("")
    a("**TOON (Token-Optimized Output Notation)** is a compact, LLM-friendly")
    a("serialization format for MCP tool results. It replaces JSON's structural")
    a("overhead (braces, colons, redundant quotes) with a flat `key=value|…`")
    a("notation, using dot-notation for nesting and a minimal MCP envelope.")
    a("")
    a("### Format comparison (echo tool, small payload)")
    a("")
    a("```")
    # find echo_small scenario for the example
    ex = next((r for r in results if r["name"] == "echo_small"), results[0])
    a(f"# Full MCP JSON-RPC envelope ({len(ex['mcp_json'])} chars, {ex['tokens']['mcp_json']} tokens):")
    a(ex["mcp_json"])
    a("")
    a(f"# MCP TOON envelope ({len(ex['mcp_toon'])} chars, {ex['tokens']['mcp_toon']} tokens):")
    a(ex["mcp_toon"])
    a("")
    a(f"# Bare JSON ({len(ex['bare_json'])} chars, {ex['tokens']['bare_json']} tokens):")
    a(ex["bare_json"])
    a("")
    a(f"# Bare TOON ({len(ex['bare_toon'])} chars, {ex['tokens']['bare_toon']} tokens):")
    a(ex["bare_toon"])
    a("```")
    a("")

    # ---- Summary table -------------------------------------------------------
    a("## Results: Token Counts by Scenario")
    a("")
    a("| Scenario | Bare JSON | Bare TOON | MCP JSON | MCP TOON | "
      "TOON Saving | MCP TOON Saving |")
    a("|----------|----------:|----------:|---------:|---------:|"
      "------------:|----------------:|")

    for r in results:
        t = r["tokens"]
        s = r["savings"]
        a(
            f"| {r['name']} "
            f"| {t['bare_json']} "
            f"| {t['bare_toon']} "
            f"| {t['mcp_json']} "
            f"| {t['mcp_toon']} "
            f"| {_pct_str(s['toon_vs_json'])} "
            f"| {_pct_str(s['mcp_toon_vs_mcp_json'])} |"
        )

    a("")

    # ---- Character counts ----------------------------------------------------
    a("## Results: Character Counts by Scenario")
    a("")
    a("| Scenario | Bare JSON | Bare TOON | MCP JSON | MCP TOON | "
      "TOON Saving | MCP TOON Saving |")
    a("|----------|----------:|----------:|---------:|---------:|"
      "------------:|----------------:|")

    for r in results:
        c = r["chars"]
        s = r["savings"]
        a(
            f"| {r['name']} "
            f"| {c['bare_json']} "
            f"| {c['bare_toon']} "
            f"| {c['mcp_json']} "
            f"| {c['mcp_toon']} "
            f"| {_pct_str(s['chars_toon_vs_json'])} "
            f"| {_pct_str(s['chars_mcp_toon_vs_json'])} |"
        )

    a("")

    # ---- Aggregate statistics -----------------------------------------------
    toon_savings     = [r["savings"]["toon_vs_json"]           for r in results]
    mcp_toon_savings = [r["savings"]["mcp_toon_vs_mcp_json"]   for r in results]

    a("## Aggregate Statistics")
    a("")
    a("| Metric | Mean | Min | Max | Median |")
    a("|--------|-----:|----:|----:|-------:|")
    for label, data in [
        ("TOON token saving vs bare JSON (%)",    toon_savings),
        ("MCP TOON token saving vs MCP JSON (%)", mcp_toon_savings),
    ]:
        mean   = round(statistics.mean(data), 1)
        lo     = round(min(data), 1)
        hi     = round(max(data), 1)
        median = round(statistics.median(data), 1)
        a(f"| {label} | {mean} | {lo} | {hi} | {median} |")

    a("")

    # ---- Payload detail section ----------------------------------------------
    a("## Payload Detail")
    a("")
    for r in results:
        a(f"### `{r['name']}`")
        a(f"_{r['description']}_")
        a("")
        a(f"| Format | String | Tokens | Chars |")
        a(f"|--------|--------|-------:|------:|")
        for fmt, label in [
            ("bare_json", "Bare JSON"),
            ("bare_toon", "Bare TOON"),
            ("mcp_json",  "MCP JSON envelope"),
            ("mcp_toon",  "MCP TOON envelope"),
        ]:
            s = r[fmt]
            display = s if len(s) <= 80 else s[:77] + "..."
            a(f"| {label} | `{display}` | {r['tokens'][fmt]} | {r['chars'][fmt]} |")
        a("")

    # ---- Interpretation ------------------------------------------------------
    a("## Interpretation")
    a("")
    avg_mcp = round(statistics.mean(mcp_toon_savings), 1)
    a(f"Across {len(results)} benchmark scenarios, MCP TOON envelopes consume on")
    a(f"average **{avg_mcp}% fewer tokens** than canonical MCP JSON-RPC envelopes.")
    a("")
    a("The savings are most pronounced for:")
    a("- **Payloads with many small fields** — JSON key overhead dominates.")
    a("- **Nested structures** — dot-notation eliminates multiple layers of braces.")
    a("- **Repeated key patterns** (e.g., agent observation logs) — key names are")
    a("  repeated per entry in JSON but amortised in TOON.")
    a("")
    a("The savings are smallest for:")
    a("- **Large string values** — the string content itself dominates token count")
    a("  in both formats, so structural savings are diluted.")
    a("")
    a("### When does this matter?")
    a("")
    a("| Context | Impact |")
    a("|---------|--------|")
    a("| Multi-step agent loops (many tool calls per turn) | High — saves accumulate each step |")
    a("| Long context windows with many tool results | High — pushes less content into the window |")
    a("| Cost-sensitive deployments (token-priced APIs) | Direct cost reduction |")
    a("| Single tool call per turn | Low — absolute saving is small |")
    a("")

    return "\n".join(lines)


def _print_summary_table(results: list[dict[str, Any]]) -> None:
    table = Table(
        title="JSON vs TOON — Token Consumption",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Scenario", style="bold")
    table.add_column("JSON tokens", justify="right")
    table.add_column("TOON tokens", justify="right")
    table.add_column("TOON saving", justify="right")
    table.add_column("MCP JSON", justify="right")
    table.add_column("MCP TOON", justify="right")
    table.add_column("MCP saving", justify="right")

    for r in results:
        t = r["tokens"]
        s = r["savings"]
        table.add_row(
            r["name"],
            str(t["bare_json"]),
            str(t["bare_toon"]),
            f"[green]{_pct_str(s['toon_vs_json'])}[/green]",
            str(t["mcp_json"]),
            str(t["mcp_toon"]),
            f"[green]{_pct_str(s['mcp_toon_vs_mcp_json'])}[/green]",
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    console.rule("[bold cyan]MCP Token Consumption Benchmark: JSON vs TOON[/bold cyan]")
    console.print()
    console.print("Tokenizer: [cyan]tiktoken cl100k_base[/cyan] (Claude/GPT-4 BPE approx)")
    console.print()

    console.print("Running scenarios…")
    results = run_all()
    console.print(f"  Completed [green]{len(results)}[/green] scenarios.\n")

    _print_summary_table(results)

    # ---- Write outputs -------------------------------------------------------
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    json_path = RESULTS_DIR / f"token_raw_{ts}.json"
    json_path.write_text(
        json.dumps(
            # Omit raw strings from JSON output to keep it machine-parseable.
            [{k: v for k, v in r.items() if k not in {"bare_json", "bare_toon", "mcp_json", "mcp_toon"}}
             for r in results],
            indent=2,
        ),
        encoding="utf-8",
    )

    md_path = RESULTS_DIR / f"token_report_{ts}.md"
    md_path.write_text(_build_markdown(results, ts), encoding="utf-8")

    console.print()
    console.print(f"  Raw JSON : [cyan]{json_path}[/cyan]")
    console.print(f"  Report   : [cyan]{md_path}[/cyan]")

    # Print headline figure
    mcp_savings = [r["savings"]["mcp_toon_vs_mcp_json"] for r in results]
    avg = round(statistics.mean(mcp_savings), 1)
    console.print()
    console.rule(
        f"[bold green]MCP TOON saves ~{avg}% tokens on average vs MCP JSON[/bold green]"
    )
    console.print()


if __name__ == "__main__":
    main()
