/**
 * GitHub App Authentication
 *
 * Creates an authenticated Octokit instance using GitHub App credentials.
 * Supports both app-level (JWT) and installation-level (access token) auth.
 */

import { createAppAuth } from '@octokit/auth-app';
import { Octokit } from '@octokit/rest';

/**
 * Creates an Octokit instance authenticated as a GitHub App installation.
 *
 * @param {string|number} installationId - GitHub App installation ID
 * @returns {Octokit} Authenticated Octokit instance
 */
export function createInstallationOctokit(installationId) {
  const { GITHUB_APP_ID, GITHUB_PRIVATE_KEY, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET } = process.env;

  if (!GITHUB_APP_ID) throw new Error('GITHUB_APP_ID environment variable is required');
  if (!GITHUB_PRIVATE_KEY) throw new Error('GITHUB_PRIVATE_KEY environment variable is required');

  // Private key may have escaped newlines when stored in env vars
  const privateKey = GITHUB_PRIVATE_KEY.replace(/\\n/g, '\n');

  const authOptions = {
    appId: GITHUB_APP_ID,
    privateKey,
    installationId: Number(installationId),
  };

  if (GITHUB_CLIENT_ID) authOptions.clientId = GITHUB_CLIENT_ID;
  if (GITHUB_CLIENT_SECRET) authOptions.clientSecret = GITHUB_CLIENT_SECRET;

  return new Octokit({
    authStrategy: createAppAuth,
    auth: authOptions,
  });
}

/**
 * Creates an Octokit instance authenticated as the GitHub App itself (JWT).
 * Used for listing installations, etc.
 *
 * @returns {Octokit} App-level authenticated Octokit instance
 */
export function createAppOctokit() {
  const { GITHUB_APP_ID, GITHUB_PRIVATE_KEY } = process.env;

  if (!GITHUB_APP_ID) throw new Error('GITHUB_APP_ID environment variable is required');
  if (!GITHUB_PRIVATE_KEY) throw new Error('GITHUB_PRIVATE_KEY environment variable is required');

  const privateKey = GITHUB_PRIVATE_KEY.replace(/\\n/g, '\n');

  return new Octokit({
    authStrategy: createAppAuth,
    auth: {
      appId: GITHUB_APP_ID,
      privateKey,
    },
  });
}

/**
 * Resolves the installation ID to use for a request.
 * Priority: explicit param > env var GITHUB_INSTALLATION_ID
 *
 * @param {string|number|undefined} installationId
 * @returns {number} Resolved installation ID
 */
export function resolveInstallationId(installationId) {
  const id = installationId || process.env.GITHUB_INSTALLATION_ID;
  if (!id) {
    throw new Error(
      'Installation ID is required. Provide it via x-github-installation-id header or GITHUB_INSTALLATION_ID env var.'
    );
  }
  return Number(id);
}
