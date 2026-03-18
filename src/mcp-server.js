/**
 * GitHub MCP Server Factory
 *
 * Creates and configures an MCP Server instance with GitHub tools.
 * Each call returns a fresh server bound to a specific GitHub App installation.
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { createInstallationOctokit } from './github-auth.js';
import { TOOL_DEFINITIONS, handleToolCall } from './github-tools.js';

/**
 * Creates a new MCP Server instance configured for a specific GitHub App installation.
 *
 * @param {string|number} installationId - GitHub App installation ID
 * @returns {Server} Configured MCP Server instance
 */
export function createGitHubMcpServer(installationId) {
  const octokit = createInstallationOctokit(installationId);

  const server = new Server(
    {
      name: 'github-mcp-server',
      version: '1.0.0',
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  // ── List tools ──────────────────────────────────────────────────────────────
  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: TOOL_DEFINITIONS,
  }));

  // ── Call tool ───────────────────────────────────────────────────────────────
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    try {
      const result = await handleToolCall(name, args ?? {}, octokit);
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2),
          },
        ],
      };
    } catch (error) {
      // Surface GitHub API errors clearly
      const message = error.response?.data?.message ?? error.message;
      const status = error.status ?? error.response?.status;
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({ error: message, status }, null, 2),
          },
        ],
        isError: true,
      };
    }
  });

  return server;
}
