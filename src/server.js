/**
 * GitHub MCP Server — Express.js entry point
 *
 * Exposes a Streamable HTTP MCP endpoint at POST/GET/DELETE /mcp
 * authenticated via GitHub App credentials.
 *
 * Environment variables:
 *   GITHUB_APP_ID            - Your GitHub App's numeric ID
 *   GITHUB_PRIVATE_KEY       - PEM private key (newlines as \n or literal)
 *   GITHUB_INSTALLATION_ID   - Default installation ID (optional)
 *   GITHUB_CLIENT_ID         - OAuth client ID (optional)
 *   GITHUB_CLIENT_SECRET     - OAuth client secret (optional)
 *   PORT                     - HTTP port (default: 3000)
 *
 * Per-request installation override:
 *   Send header  x-github-installation-id: <id>  on the initial POST to /mcp
 *   to override the default GITHUB_INSTALLATION_ID.
 */

import 'dotenv/config';
import express from 'express';
import { randomUUID } from 'crypto';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { isInitializeRequest } from '@modelcontextprotocol/sdk/types.js';
import { createGitHubMcpServer } from './mcp-server.js';
import { resolveInstallationId } from './github-auth.js';

const app = express();
app.use(express.json());

// ── Session store ─────────────────────────────────────────────────────────────
// Maps session ID → StreamableHTTPServerTransport
const transports = new Map();

// ── Health check ──────────────────────────────────────────────────────────────
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', sessions: transports.size });
});

// ── POST /mcp — handle new sessions and existing session messages ─────────────
app.post('/mcp', async (req, res) => {
  const existingSessionId = req.headers['mcp-session-id'];

  // ── Resume existing session ──────────────────────────────────────────────
  if (existingSessionId) {
    const transport = transports.get(existingSessionId);
    if (!transport) {
      return res.status(404).json({
        jsonrpc: '2.0',
        error: { code: -32000, message: `Session '${existingSessionId}' not found` },
        id: null,
      });
    }
    return transport.handleRequest(req, res, req.body);
  }

  // ── New session — must be an initialize request ──────────────────────────
  if (!isInitializeRequest(req.body)) {
    return res.status(400).json({
      jsonrpc: '2.0',
      error: { code: -32600, message: 'First request must be an MCP initialize request' },
      id: null,
    });
  }

  // Resolve GitHub App installation ID (header overrides env default)
  let installationId;
  try {
    installationId = resolveInstallationId(req.headers['x-github-installation-id']);
  } catch (err) {
    return res.status(400).json({
      jsonrpc: '2.0',
      error: { code: -32600, message: err.message },
      id: null,
    });
  }

  // Create transport + MCP server for this session
  let transport;
  try {
    transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: () => randomUUID(),
      onsessioninitialized: (sessionId) => {
        transports.set(sessionId, transport);
        console.log(`[MCP] Session initialized: ${sessionId} (installation: ${installationId})`);
      },
    });

    // Clean up when the transport closes
    transport.onclose = () => {
      const sessionId = transport.sessionId;
      if (sessionId) {
        transports.delete(sessionId);
        console.log(`[MCP] Session closed: ${sessionId}`);
      }
    };

    const server = createGitHubMcpServer(installationId);
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  } catch (err) {
    console.error('[MCP] Error creating session:', err.message);
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: '2.0',
        error: { code: -32603, message: 'Internal error: ' + err.message },
        id: null,
      });
    }
  }
});

// ── GET /mcp — SSE stream for server-to-client notifications ─────────────────
app.get('/mcp', async (req, res) => {
  const sessionId = req.headers['mcp-session-id'];
  if (!sessionId) {
    return res.status(400).json({ error: 'Missing mcp-session-id header' });
  }

  const transport = transports.get(sessionId);
  if (!transport) {
    return res.status(404).json({ error: `Session '${sessionId}' not found` });
  }

  console.log(`[MCP] SSE stream opened: ${sessionId}`);
  return transport.handleRequest(req, res);
});

// ── DELETE /mcp — explicit session termination ────────────────────────────────
app.delete('/mcp', async (req, res) => {
  const sessionId = req.headers['mcp-session-id'];
  if (!sessionId) {
    return res.status(400).json({ error: 'Missing mcp-session-id header' });
  }

  const transport = transports.get(sessionId);
  if (!transport) {
    return res.status(404).json({ error: `Session '${sessionId}' not found` });
  }

  await transport.handleRequest(req, res);
  transports.delete(sessionId);
  console.log(`[MCP] Session deleted: ${sessionId}`);
});

// ── Start server ──────────────────────────────────────────────────────────────
const PORT = process.env.PORT ?? 3000;
app.listen(PORT, () => {
  console.log(`GitHub MCP Server listening on http://localhost:${PORT}`);
  console.log(`  MCP endpoint : http://localhost:${PORT}/mcp`);
  console.log(`  Health check : http://localhost:${PORT}/health`);
  console.log();
  console.log('Required env vars:');
  console.log('  GITHUB_APP_ID          :', process.env.GITHUB_APP_ID ? '✓ set' : '✗ MISSING');
  console.log('  GITHUB_PRIVATE_KEY     :', process.env.GITHUB_PRIVATE_KEY ? '✓ set' : '✗ MISSING');
  console.log('  GITHUB_INSTALLATION_ID :', process.env.GITHUB_INSTALLATION_ID ? '✓ set' : '(optional — use header)');
});
