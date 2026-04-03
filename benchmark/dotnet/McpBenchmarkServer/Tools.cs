using System.ComponentModel;
using System.Diagnostics;
using System.Text.Json;
using ModelContextProtocol.Server;
using NJsonSchema;

namespace McpBenchmarkServer;

/// <summary>
/// All five MCP benchmark tools, decorated with [McpServerTool] so they are
/// automatically discovered by WithToolsFromAssembly() in Program.cs.
/// </summary>
[McpServerToolType]
public static class BenchmarkTools
{
    // -----------------------------------------------------------------------
    // echo — baseline latency
    // -----------------------------------------------------------------------
    [McpServerTool(Name = "echo")]
    [Description("Returns input text as-is. Used for baseline latency measurement.")]
    public static object Echo(
        [Description("Text to echo back")] string text)
    {
        return new { echo = text, length = text.Length };
    }

    // -----------------------------------------------------------------------
    // fibonacci — CPU-bound performance
    // -----------------------------------------------------------------------
    [McpServerTool(Name = "fibonacci")]
    [Description("CPU-bound naive recursive Fibonacci. n must be between 0 and 35.")]
    public static object Fibonacci(
        [Description("Input value n (0–35)")] int n)
    {
        if (n < 0 || n > 35)
            throw new ArgumentOutOfRangeException(nameof(n), "n must be between 0 and 35");

        var sw = Stopwatch.StartNew();
        var result = Fib(n);
        sw.Stop();

        return new
        {
            n,
            result,
            elapsed_ms = Math.Round(sw.Elapsed.TotalMilliseconds, 3)
        };
    }

    private static long Fib(int n) => n <= 1 ? n : Fib(n - 1) + Fib(n - 2);

    // -----------------------------------------------------------------------
    // fetch_mock — async I/O simulation
    // -----------------------------------------------------------------------
    [McpServerTool(Name = "fetch_mock")]
    [Description("Simulated async HTTP fetch with configurable delay. delay_ms must be 0–5000.")]
    public static async Task<object> FetchMock(
        [Description("Simulated network delay in milliseconds (0–5000)")] int delay_ms = 50,
        [Description("Mock URL to return")] string url = "https://example.com")
    {
        if (delay_ms < 0 || delay_ms > 5000)
            throw new ArgumentOutOfRangeException(nameof(delay_ms), "delay_ms must be 0–5000");

        await Task.Delay(delay_ms);

        return new { url, delay_ms, status = 200, body_length = 1024 };
    }

    // -----------------------------------------------------------------------
    // batch_process — scalability / bounded concurrency
    // -----------------------------------------------------------------------
    [McpServerTool(Name = "batch_process")]
    [Description("Process N items concurrently with a semaphore. Maximum 1000 items.")]
    public static async Task<object> BatchProcess(
        [Description("Array of items to process (max 1000)")] JsonElement[] items,
        [Description("Maximum concurrent workers (1–100, default 10)")] int concurrency = 10)
    {
        if (items.Length > 1000)
            throw new ArgumentException("Maximum 1000 items per batch");
        if (concurrency < 1 || concurrency > 100)
            throw new ArgumentOutOfRangeException(nameof(concurrency), "concurrency must be 1–100");

        var sw = Stopwatch.StartNew();
        var sem = new SemaphoreSlim(concurrency);

        await Task.WhenAll(items.Select(async _ =>
        {
            await sem.WaitAsync();
            try
            {
                await Task.Delay(1); // simulate minimal per-item work
            }
            finally
            {
                sem.Release();
            }
        }));

        sw.Stop();

        return new
        {
            count = items.Length,
            elapsed_ms = Math.Round(sw.Elapsed.TotalMilliseconds, 3),
            concurrency
        };
    }

    // -----------------------------------------------------------------------
    // validate_schema — security / input validation
    // -----------------------------------------------------------------------
    [McpServerTool(Name = "validate_schema")]
    [Description("Validate arbitrary data against a JSON Schema object. Returns {valid, errors}.")]
    public static async Task<object> ValidateSchema(
        [Description("Data to validate")] JsonElement data,
        [Description("JSON Schema object to validate against")] JsonElement schema)
    {
        JsonSchema jsonSchema;
        try
        {
            jsonSchema = await JsonSchema.FromJsonAsync(schema.GetRawText());
        }
        catch (Exception ex)
        {
            return new { valid = false, errors = new[] { $"Invalid schema: {ex.Message}" } };
        }

        var errors = jsonSchema.Validate(data.GetRawText());
        return new
        {
            valid = errors.Count == 0,
            errors = errors.Select(e => e.ToString()).ToArray()
        };
    }
}
