/**
 * TypeScript MCP benchmark server — Express 4 + StreamableHTTPServerTransport.
 * Mirrors the session-management pattern from the organization's reference
 * implementation (claude/github-mcp-express-server-tH9Zr branch).
 *
 * Port: 8002
 * Endpoints:
 *   POST   /mcp   — initialize (no session header) or call (with mcp-session-id)
 *   GET    /mcp   — SSE stream for server-sent events (with mcp-session-id)
 *   DELETE /mcp   — close session (with mcp-session-id)
 *   GET    /health — liveness probe
 */

import express from "express";
import { randomUUID } from "crypto";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { isInitializeRequest } from "@modelcontextprotocol/sdk/types.js";
import { createMcpServer } from "./mcpServer.js";

const app = express();
app.use(express.json({ limit: "1mb" }));

// Session store: sessionId → transport
const transports = new Map<string, StreamableHTTPServerTransport>();

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------
app.get("/health", (_req, res) => {
  res.json({ status: "ok", sessions: transports.size, lang: "typescript" });
});

// ---------------------------------------------------------------------------
// POST /mcp — initialize (no session) or handle request (with session)
// ---------------------------------------------------------------------------
app.post("/mcp", async (req, res) => {
  const existingId = req.headers["mcp-session-id"] as string | undefined;

  if (existingId) {
    const transport = transports.get(existingId);
    if (!transport) {
      res.status(404).json({
        jsonrpc: "2.0",
        error: { code: -32000, message: "Session not found" },
        id: null,
      });
      return;
    }
    await transport.handleRequest(req, res, req.body);
    return;
  }

  // No session header — must be an initialize request
  if (!isInitializeRequest(req.body)) {
    res.status(400).json({
      jsonrpc: "2.0",
      error: { code: -32600, message: "First request must be initialize" },
      id: null,
    });
    return;
  }

  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: () => randomUUID(),
    onsessioninitialized: (sessionId) => {
      transports.set(sessionId, transport);
      console.log(`[MCP] Session created: ${sessionId}`);
    },
  });

  transport.onclose = () => {
    if (transport.sessionId) {
      transports.delete(transport.sessionId);
      console.log(`[MCP] Session closed: ${transport.sessionId}`);
    }
  };

  const server = createMcpServer();
  await server.connect(transport);
  await transport.handleRequest(req, res, req.body);
});

// ---------------------------------------------------------------------------
// GET /mcp — SSE stream
// ---------------------------------------------------------------------------
app.get("/mcp", async (req, res) => {
  const sessionId = req.headers["mcp-session-id"] as string | undefined;
  if (!sessionId) {
    res.status(400).json({ error: "mcp-session-id header required" });
    return;
  }
  const transport = transports.get(sessionId);
  if (!transport) {
    res.status(404).json({ error: "Session not found" });
    return;
  }
  await transport.handleRequest(req, res);
});

// ---------------------------------------------------------------------------
// DELETE /mcp — close session
// ---------------------------------------------------------------------------
app.delete("/mcp", async (req, res) => {
  const sessionId = req.headers["mcp-session-id"] as string | undefined;
  if (!sessionId) {
    res.status(400).json({ error: "mcp-session-id header required" });
    return;
  }
  const transport = transports.get(sessionId);
  if (!transport) {
    res.status(404).json({ error: "Session not found" });
    return;
  }
  await transport.handleRequest(req, res);
  transports.delete(sessionId);
  console.log(`[MCP] Session deleted: ${sessionId}`);
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
const PORT = parseInt(process.env["PORT"] ?? "8002", 10);
app.listen(PORT, "0.0.0.0", () => {
  console.log(`[MCP] TypeScript benchmark server listening on :${PORT}`);
});
