# MCP Language Benchmark

Quantitative benchmark comparing **Python**, **TypeScript**, and **.NET** as implementation languages for [Model Context Protocol](https://modelcontextprotocol.io) servers. Results inform the organization's language selection across five dimensions:

| Dimension | What we measure |
|-----------|----------------|
| **Performance** | End-to-end latency (p50 / p95 / p99) for sequential requests |
| **Scalability** | Requests/second at concurrency 1 / 10 / 50 / 100 |
| **Async Performance** | Wall time for 100 concurrent I/O-bound tool calls |
| **Developer Onboarding** | Lines of code, dependencies, setup steps, type safety |
| **Security** | Input validation behaviour under adversarial inputs |

---

## Quick Start

### Run the full benchmark (Docker Compose)

```bash
cd benchmark
docker-compose up --build
```

All three servers start, the runner waits for health checks, executes all scenarios, then writes results to `benchmark/results/`:

```
results/
├── raw_20260402_120000.json    ← machine-readable raw data
└── report_20260402_120000.md   ← human-readable decision report
```

### Run a single server locally

**Python**
```bash
cd benchmark/python
pip install -r requirements.txt
python server.py
# → http://localhost:8001/health
```

**TypeScript**
```bash
cd benchmark/typescript
npm install && npm run build
npm start
# → http://localhost:8002/health
```

**.NET**
```bash
cd benchmark/dotnet
dotnet run --project McpBenchmarkServer
# → http://localhost:8003/health
```

### Run the benchmark runner standalone (servers already running)

```bash
cd benchmark/runner
pip install -r requirements.txt
PYTHON_URL=http://localhost:8001 \
TS_URL=http://localhost:8002 \
DOTNET_URL=http://localhost:8003 \
python benchmark.py
```

---

## Architecture

```
benchmark/
├── python/              # FastMCP server (mcp[cli])           port 8001
│   ├── server.py        # FastMCP app + @mcp.tool() decorators
│   ├── tools.py         # Pure-async tool implementations
│   ├── requirements.txt
│   └── Dockerfile
│
├── typescript/          # Express 4 + @modelcontextprotocol/sdk   port 8002
│   ├── src/
│   │   ├── server.ts    # Session management (StreamableHTTP)
│   │   ├── mcpServer.ts # Tool registration (ListTools + CallTool)
│   │   └── tools.ts     # Tool implementations + Semaphore helper
│   ├── package.json
│   ├── tsconfig.json
│   └── Dockerfile
│
├── dotnet/              # ASP.NET Core + ModelContextProtocol    port 8003
│   └── McpBenchmarkServer/
│       ├── Program.cs   # AddMcpServer().WithHttpTransport() + MapMcp()
│       ├── Tools.cs     # [McpServerTool] attributed static methods
│       ├── McpBenchmarkServer.csproj
│       └── appsettings.json
│
├── runner/              # Benchmark harness (Python + httpx)
│   ├── benchmark.py     # Orchestrator — waits, runs, reports
│   ├── mcp_client.py    # Async Streamable-HTTP MCP client
│   ├── scenarios.py     # 7 scenario functions
│   ├── report.py        # JSON + Markdown report generator
│   ├── requirements.txt
│   └── Dockerfile
│
├── docker-compose.yml
├── results/             # Output directory (gitignored except .gitkeep)
└── README.md
```

---

## The Five MCP Tools (identical across all three servers)

| Tool | Input | Purpose |
|------|-------|---------|
| `echo` | `text: string` | Baseline latency — returns input unchanged |
| `fibonacci` | `n: int (0–35)` | CPU-bound — naive recursive fib |
| `fetch_mock` | `delay_ms: int, url: string` | Async I/O — simulated network call |
| `batch_process` | `items: array (≤1000), concurrency: int` | Scalability — bounded concurrent processing |
| `validate_schema` | `data: any, schema: object` | Security — JSON Schema validation |

Each tool includes input guards (range checks, size limits) to test the security scenario.

---

## Benchmark Scenarios

| # | Scenario | Tool | Metric |
|---|----------|------|--------|
| 1 | Latency baseline | `echo` × 200 sequential | p50 / p95 / p99 / mean (ms) |
| 2 | Throughput | `echo` concurrent for 10 s | RPS at concurrency 1 / 10 / 50 / 100 |
| 3 | CPU performance | `fibonacci(30)` × 100 | mean / p95 / total (ms) |
| 4 | Async I/O | 100 concurrent `fetch_mock(50ms)` | wall time, concurrency ratio |
| 5 | Memory under load | `echo` × 1 000 | baseline / peak / growth RSS (MB) |
| 6 | Cold start | Docker container start → `/health` 200 | seconds (requires Docker in runner) |
| 7 | Security | 5 adversarial inputs | tests handled correctly / server alive |

---

## SDK Versions

| Language | SDK | Version | Transport |
|----------|-----|---------|-----------|
| Python | `mcp[cli]` (FastMCP) | 1.9.2 | Streamable HTTP |
| TypeScript | `@modelcontextprotocol/sdk` | ^1.12.0 | Streamable HTTP |
| .NET | `ModelContextProtocol` + `ModelContextProtocol.AspNetCore` | 0.2.0-preview.3 | Streamable HTTP |

> **Note on .NET SDK:** The Microsoft-official MCP SDK is currently pre-release.
> Monitor [NuGet — ModelContextProtocol](https://www.nuget.org/packages/ModelContextProtocol)
> for stable releases before production deployment.

---

## Report Output

The Markdown report (`results/report_<timestamp>.md`) contains:

1. **Executive Summary** — scored comparison table (1–3 stars per dimension)
2. **Performance** — latency percentile table
3. **Scalability** — RPS at each concurrency level
4. **CPU Performance** — fibonacci timing
5. **Async I/O** — concurrent fetch wall times and concurrency ratio
6. **Memory** — RSS baseline, peak, and growth
7. **Developer Onboarding** — LOC, deps, setup steps, type safety, IDE support
8. **Security** — per-test outcome table
9. **Recommendation** — decision matrix with use-case guidance
