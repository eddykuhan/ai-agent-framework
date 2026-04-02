using McpBenchmarkServer;

var builder = WebApplication.CreateBuilder(args);

// -------------------------------------------------------------------------
// MCP services — Streamable HTTP transport, tools discovered via reflection
// -------------------------------------------------------------------------
builder.Services
    .AddMcpServer()
    .WithHttpTransport()
    .WithToolsFromAssembly(typeof(BenchmarkTools).Assembly);

// Health checks
builder.Services.AddHealthChecks();

// -------------------------------------------------------------------------
// Configure Kestrel port from environment (default 8003)
// -------------------------------------------------------------------------
var port = Environment.GetEnvironmentVariable("PORT") ?? "8003";
builder.WebHost.UseUrls($"http://0.0.0.0:{port}");

var app = builder.Build();

// -------------------------------------------------------------------------
// Endpoints
// -------------------------------------------------------------------------

// Liveness probe — returns {status, lang}
app.MapGet("/health", () => Results.Ok(new { status = "ok", lang = "dotnet" }));

// MCP Streamable HTTP — POST/GET/DELETE handled by the SDK middleware
app.MapMcp("/mcp");

app.Run();
