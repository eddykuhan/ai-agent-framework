/**
 * MCP Server factory for the TypeScript benchmark server.
 * Registers all five benchmark tools using the low-level SDK handlers.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import {
  batchProcess,
  echo,
  fetchMock,
  fibonacci,
  validateSchema,
} from "./tools.js";

const TOOLS = [
  {
    name: "echo",
    description: "Returns input text as-is. Baseline latency measurement.",
    inputSchema: {
      type: "object",
      required: ["text"],
      properties: { text: { type: "string" } },
    },
  },
  {
    name: "fibonacci",
    description: "CPU-bound naive recursive Fibonacci. n must be 0–35.",
    inputSchema: {
      type: "object",
      required: ["n"],
      properties: { n: { type: "number", minimum: 0, maximum: 35 } },
    },
  },
  {
    name: "fetch_mock",
    description: "Simulated async HTTP fetch with configurable delay (ms).",
    inputSchema: {
      type: "object",
      properties: {
        delay_ms: { type: "number", minimum: 0, maximum: 5000, default: 50 },
        url: { type: "string", default: "https://example.com" },
      },
    },
  },
  {
    name: "batch_process",
    description: "Process N items concurrently (max 1000) with bounded concurrency.",
    inputSchema: {
      type: "object",
      required: ["items"],
      properties: {
        items: { type: "array", maxItems: 1000 },
        concurrency: { type: "number", minimum: 1, maximum: 100, default: 10 },
      },
    },
  },
  {
    name: "validate_schema",
    description: "Validate data against a JSON Schema object.",
    inputSchema: {
      type: "object",
      required: ["data", "schema"],
      properties: {
        data: {},
        schema: { type: "object" },
      },
    },
  },
];

export function createMcpServer(): Server {
  const server = new Server(
    { name: "mcp-benchmark-typescript", version: "1.0.0" },
    { capabilities: { tools: {} } }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const { name, arguments: args = {} } = req.params;
    const a = args as Record<string, unknown>;

    try {
      let result: unknown;

      if (name === "echo") {
        if (typeof a["text"] !== "string") throw new Error("text must be a string");
        result = await echo(a["text"] as string);
      } else if (name === "fibonacci") {
        const n = Number(a["n"]);
        if (n < 0 || n > 35) throw new Error("n must be between 0 and 35");
        result = await fibonacci(n);
      } else if (name === "fetch_mock") {
        const delay_ms = a["delay_ms"] !== undefined ? Number(a["delay_ms"]) : 50;
        const url = typeof a["url"] === "string" ? a["url"] : "https://example.com";
        if (delay_ms < 0 || delay_ms > 5000) throw new Error("delay_ms must be 0–5000");
        result = await fetchMock(delay_ms, url);
      } else if (name === "batch_process") {
        const items = a["items"];
        if (!Array.isArray(items)) throw new Error("items must be an array");
        if (items.length > 1000) throw new Error("Maximum 1000 items per batch");
        const concurrency = a["concurrency"] !== undefined ? Number(a["concurrency"]) : 10;
        result = await batchProcess(items, concurrency);
      } else if (name === "validate_schema") {
        if (typeof a["schema"] !== "object" || a["schema"] === null)
          throw new Error("schema must be a JSON object");
        result = await validateSchema(a["data"], a["schema"] as object);
      } else {
        throw new Error(`Unknown tool: ${name}`);
      }

      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text", text: JSON.stringify({ error: msg }) }],
        isError: true,
      };
    }
  });

  return server;
}
