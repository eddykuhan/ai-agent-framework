/**
 * GitHub MCP Tool Definitions and Handlers
 *
 * Defines all GitHub API tools exposed via MCP, with their input schemas
 * and handler implementations.
 */

// ─── Tool definitions (JSON Schema for MCP) ─────────────────────────────────

export const TOOL_DEFINITIONS = [
  {
    name: 'list_repositories',
    description: 'List repositories accessible to this GitHub App installation.',
    inputSchema: {
      type: 'object',
      properties: {
        per_page: { type: 'number', description: 'Results per page (max 100)', default: 30 },
        page: { type: 'number', description: 'Page number', default: 1 },
      },
    },
  },
  {
    name: 'get_repository',
    description: 'Get detailed information about a repository.',
    inputSchema: {
      type: 'object',
      required: ['owner', 'repo'],
      properties: {
        owner: { type: 'string', description: 'Repository owner (user or org)' },
        repo: { type: 'string', description: 'Repository name' },
      },
    },
  },
  {
    name: 'list_issues',
    description: 'List issues in a repository.',
    inputSchema: {
      type: 'object',
      required: ['owner', 'repo'],
      properties: {
        owner: { type: 'string', description: 'Repository owner' },
        repo: { type: 'string', description: 'Repository name' },
        state: { type: 'string', enum: ['open', 'closed', 'all'], default: 'open' },
        labels: { type: 'string', description: 'Comma-separated list of label names' },
        per_page: { type: 'number', default: 30 },
        page: { type: 'number', default: 1 },
      },
    },
  },
  {
    name: 'get_issue',
    description: 'Get details about a specific issue.',
    inputSchema: {
      type: 'object',
      required: ['owner', 'repo', 'issue_number'],
      properties: {
        owner: { type: 'string' },
        repo: { type: 'string' },
        issue_number: { type: 'number', description: 'Issue number' },
      },
    },
  },
  {
    name: 'create_issue',
    description: 'Create a new issue in a repository.',
    inputSchema: {
      type: 'object',
      required: ['owner', 'repo', 'title'],
      properties: {
        owner: { type: 'string' },
        repo: { type: 'string' },
        title: { type: 'string', description: 'Issue title' },
        body: { type: 'string', description: 'Issue body (markdown)' },
        labels: { type: 'array', items: { type: 'string' }, description: 'Label names' },
        assignees: { type: 'array', items: { type: 'string' }, description: 'Assignee usernames' },
      },
    },
  },
  {
    name: 'add_issue_comment',
    description: 'Add a comment to an issue or pull request.',
    inputSchema: {
      type: 'object',
      required: ['owner', 'repo', 'issue_number', 'body'],
      properties: {
        owner: { type: 'string' },
        repo: { type: 'string' },
        issue_number: { type: 'number' },
        body: { type: 'string', description: 'Comment body (markdown)' },
      },
    },
  },
  {
    name: 'list_pull_requests',
    description: 'List pull requests in a repository.',
    inputSchema: {
      type: 'object',
      required: ['owner', 'repo'],
      properties: {
        owner: { type: 'string' },
        repo: { type: 'string' },
        state: { type: 'string', enum: ['open', 'closed', 'all'], default: 'open' },
        base: { type: 'string', description: 'Filter by base branch' },
        per_page: { type: 'number', default: 30 },
        page: { type: 'number', default: 1 },
      },
    },
  },
  {
    name: 'get_pull_request',
    description: 'Get details about a specific pull request.',
    inputSchema: {
      type: 'object',
      required: ['owner', 'repo', 'pull_number'],
      properties: {
        owner: { type: 'string' },
        repo: { type: 'string' },
        pull_number: { type: 'number', description: 'Pull request number' },
      },
    },
  },
  {
    name: 'get_file_contents',
    description: 'Get the contents of a file or directory from a repository.',
    inputSchema: {
      type: 'object',
      required: ['owner', 'repo', 'path'],
      properties: {
        owner: { type: 'string' },
        repo: { type: 'string' },
        path: { type: 'string', description: 'File or directory path' },
        ref: { type: 'string', description: 'Branch, tag, or commit SHA (defaults to default branch)' },
      },
    },
  },
  {
    name: 'create_or_update_file',
    description: 'Create or update a file in a repository.',
    inputSchema: {
      type: 'object',
      required: ['owner', 'repo', 'path', 'message', 'content'],
      properties: {
        owner: { type: 'string' },
        repo: { type: 'string' },
        path: { type: 'string', description: 'File path in the repository' },
        message: { type: 'string', description: 'Commit message' },
        content: { type: 'string', description: 'File content (will be base64 encoded)' },
        branch: { type: 'string', description: 'Branch name (defaults to default branch)' },
        sha: { type: 'string', description: 'SHA of the file being replaced (required for updates)' },
      },
    },
  },
  {
    name: 'list_commits',
    description: 'List commits in a repository.',
    inputSchema: {
      type: 'object',
      required: ['owner', 'repo'],
      properties: {
        owner: { type: 'string' },
        repo: { type: 'string' },
        sha: { type: 'string', description: 'Branch, tag, or commit SHA to start from' },
        path: { type: 'string', description: 'Only commits affecting this path' },
        per_page: { type: 'number', default: 30 },
        page: { type: 'number', default: 1 },
      },
    },
  },
  {
    name: 'search_repositories',
    description: 'Search GitHub repositories.',
    inputSchema: {
      type: 'object',
      required: ['query'],
      properties: {
        query: { type: 'string', description: 'Search query (GitHub search syntax)' },
        sort: { type: 'string', enum: ['stars', 'forks', 'help-wanted-issues', 'updated'] },
        order: { type: 'string', enum: ['asc', 'desc'], default: 'desc' },
        per_page: { type: 'number', default: 30 },
        page: { type: 'number', default: 1 },
      },
    },
  },
  {
    name: 'search_code',
    description: 'Search code across GitHub repositories.',
    inputSchema: {
      type: 'object',
      required: ['query'],
      properties: {
        query: { type: 'string', description: 'Search query (GitHub code search syntax)' },
        per_page: { type: 'number', default: 30 },
        page: { type: 'number', default: 1 },
      },
    },
  },
  {
    name: 'search_issues',
    description: 'Search issues and pull requests across GitHub.',
    inputSchema: {
      type: 'object',
      required: ['query'],
      properties: {
        query: { type: 'string', description: 'Search query (GitHub issue search syntax)' },
        sort: { type: 'string', enum: ['comments', 'reactions', 'created', 'updated'] },
        order: { type: 'string', enum: ['asc', 'desc'], default: 'desc' },
        per_page: { type: 'number', default: 30 },
        page: { type: 'number', default: 1 },
      },
    },
  },
  {
    name: 'create_branch',
    description: 'Create a new branch in a repository.',
    inputSchema: {
      type: 'object',
      required: ['owner', 'repo', 'branch', 'from_branch'],
      properties: {
        owner: { type: 'string' },
        repo: { type: 'string' },
        branch: { type: 'string', description: 'New branch name' },
        from_branch: { type: 'string', description: 'Source branch or commit SHA' },
      },
    },
  },
  {
    name: 'list_branches',
    description: 'List branches in a repository.',
    inputSchema: {
      type: 'object',
      required: ['owner', 'repo'],
      properties: {
        owner: { type: 'string' },
        repo: { type: 'string' },
        per_page: { type: 'number', default: 30 },
        page: { type: 'number', default: 1 },
      },
    },
  },
];

// ─── Tool handlers ────────────────────────────────────────────────────────────

/**
 * Executes a tool call against the GitHub API.
 *
 * @param {string} toolName - Name of the tool to call
 * @param {object} args - Tool arguments from the MCP request
 * @param {import('@octokit/rest').Octokit} octokit - Authenticated Octokit instance
 * @returns {Promise<object>} Tool result
 */
export async function handleToolCall(toolName, args, octokit) {
  switch (toolName) {
    case 'list_repositories':
      return listRepositories(args, octokit);
    case 'get_repository':
      return getRepository(args, octokit);
    case 'list_issues':
      return listIssues(args, octokit);
    case 'get_issue':
      return getIssue(args, octokit);
    case 'create_issue':
      return createIssue(args, octokit);
    case 'add_issue_comment':
      return addIssueComment(args, octokit);
    case 'list_pull_requests':
      return listPullRequests(args, octokit);
    case 'get_pull_request':
      return getPullRequest(args, octokit);
    case 'get_file_contents':
      return getFileContents(args, octokit);
    case 'create_or_update_file':
      return createOrUpdateFile(args, octokit);
    case 'list_commits':
      return listCommits(args, octokit);
    case 'search_repositories':
      return searchRepositories(args, octokit);
    case 'search_code':
      return searchCode(args, octokit);
    case 'search_issues':
      return searchIssues(args, octokit);
    case 'create_branch':
      return createBranch(args, octokit);
    case 'list_branches':
      return listBranches(args, octokit);
    default:
      throw new Error(`Unknown tool: ${toolName}`);
  }
}

// ─── Individual handlers ──────────────────────────────────────────────────────

async function listRepositories({ per_page = 30, page = 1 }, octokit) {
  const { data } = await octokit.rest.apps.listReposAccessibleToInstallation({
    per_page,
    page,
  });
  return {
    total_count: data.total_count,
    repositories: data.repositories.map(formatRepo),
  };
}

async function getRepository({ owner, repo }, octokit) {
  const { data } = await octokit.rest.repos.get({ owner, repo });
  return formatRepo(data);
}

async function listIssues({ owner, repo, state = 'open', labels, per_page = 30, page = 1 }, octokit) {
  const params = { owner, repo, state, per_page, page };
  if (labels) params.labels = labels;
  const { data } = await octokit.rest.issues.listForRepo(params);
  return data
    .filter((i) => !i.pull_request) // exclude PRs
    .map(formatIssue);
}

async function getIssue({ owner, repo, issue_number }, octokit) {
  const { data } = await octokit.rest.issues.get({ owner, repo, issue_number });
  return formatIssue(data);
}

async function createIssue({ owner, repo, title, body, labels, assignees }, octokit) {
  const params = { owner, repo, title };
  if (body) params.body = body;
  if (labels) params.labels = labels;
  if (assignees) params.assignees = assignees;
  const { data } = await octokit.rest.issues.create(params);
  return formatIssue(data);
}

async function addIssueComment({ owner, repo, issue_number, body }, octokit) {
  const { data } = await octokit.rest.issues.createComment({ owner, repo, issue_number, body });
  return {
    id: data.id,
    body: data.body,
    user: data.user?.login,
    created_at: data.created_at,
    html_url: data.html_url,
  };
}

async function listPullRequests({ owner, repo, state = 'open', base, per_page = 30, page = 1 }, octokit) {
  const params = { owner, repo, state, per_page, page };
  if (base) params.base = base;
  const { data } = await octokit.rest.pulls.list(params);
  return data.map(formatPR);
}

async function getPullRequest({ owner, repo, pull_number }, octokit) {
  const { data } = await octokit.rest.pulls.get({ owner, repo, pull_number });
  return formatPR(data);
}

async function getFileContents({ owner, repo, path, ref }, octokit) {
  const params = { owner, repo, path };
  if (ref) params.ref = ref;
  const { data } = await octokit.rest.repos.getContent(params);

  // Directory listing
  if (Array.isArray(data)) {
    return {
      type: 'directory',
      path,
      entries: data.map((e) => ({ name: e.name, path: e.path, type: e.type, size: e.size, sha: e.sha })),
    };
  }

  // File content
  const content = data.encoding === 'base64'
    ? Buffer.from(data.content, 'base64').toString('utf-8')
    : data.content;

  return {
    type: 'file',
    name: data.name,
    path: data.path,
    sha: data.sha,
    size: data.size,
    encoding: 'utf-8',
    content,
    html_url: data.html_url,
  };
}

async function createOrUpdateFile({ owner, repo, path, message, content, branch, sha }, octokit) {
  const params = {
    owner,
    repo,
    path,
    message,
    content: Buffer.from(content).toString('base64'),
  };
  if (branch) params.branch = branch;
  if (sha) params.sha = sha;

  const { data } = await octokit.rest.repos.createOrUpdateFileContents(params);
  return {
    commit: {
      sha: data.commit.sha,
      message: data.commit.message,
      html_url: data.commit.html_url,
    },
    content: {
      path: data.content.path,
      sha: data.content.sha,
      html_url: data.content.html_url,
    },
  };
}

async function listCommits({ owner, repo, sha, path, per_page = 30, page = 1 }, octokit) {
  const params = { owner, repo, per_page, page };
  if (sha) params.sha = sha;
  if (path) params.path = path;
  const { data } = await octokit.rest.repos.listCommits(params);
  return data.map((c) => ({
    sha: c.sha,
    message: c.commit.message,
    author: c.commit.author?.name,
    date: c.commit.author?.date,
    html_url: c.html_url,
  }));
}

async function searchRepositories({ query, sort, order = 'desc', per_page = 30, page = 1 }, octokit) {
  const params = { q: query, order, per_page, page };
  if (sort) params.sort = sort;
  const { data } = await octokit.rest.search.repos(params);
  return {
    total_count: data.total_count,
    items: data.items.map(formatRepo),
  };
}

async function searchCode({ query, per_page = 30, page = 1 }, octokit) {
  const { data } = await octokit.rest.search.code({ q: query, per_page, page });
  return {
    total_count: data.total_count,
    items: data.items.map((i) => ({
      name: i.name,
      path: i.path,
      sha: i.sha,
      repository: `${i.repository.owner.login}/${i.repository.name}`,
      html_url: i.html_url,
    })),
  };
}

async function searchIssues({ query, sort, order = 'desc', per_page = 30, page = 1 }, octokit) {
  const params = { q: query, order, per_page, page };
  if (sort) params.sort = sort;
  const { data } = await octokit.rest.search.issuesAndPullRequests(params);
  return {
    total_count: data.total_count,
    items: data.items.map(formatIssue),
  };
}

async function createBranch({ owner, repo, branch, from_branch }, octokit) {
  // Get the SHA of the source branch
  const { data: ref } = await octokit.rest.git.getRef({
    owner,
    repo,
    ref: `heads/${from_branch}`,
  });

  const { data } = await octokit.rest.git.createRef({
    owner,
    repo,
    ref: `refs/heads/${branch}`,
    sha: ref.object.sha,
  });

  return {
    ref: data.ref,
    sha: data.object.sha,
    url: data.url,
  };
}

async function listBranches({ owner, repo, per_page = 30, page = 1 }, octokit) {
  const { data } = await octokit.rest.repos.listBranches({ owner, repo, per_page, page });
  return data.map((b) => ({
    name: b.name,
    sha: b.commit.sha,
    protected: b.protected,
  }));
}

// ─── Formatters ───────────────────────────────────────────────────────────────

function formatRepo(r) {
  return {
    id: r.id,
    name: r.name,
    full_name: r.full_name,
    description: r.description,
    private: r.private,
    fork: r.fork,
    language: r.language,
    default_branch: r.default_branch,
    stars: r.stargazers_count,
    forks: r.forks_count,
    open_issues: r.open_issues_count,
    html_url: r.html_url,
    created_at: r.created_at,
    updated_at: r.updated_at,
  };
}

function formatIssue(i) {
  return {
    number: i.number,
    title: i.title,
    body: i.body,
    state: i.state,
    user: i.user?.login,
    labels: i.labels?.map((l) => l.name) ?? [],
    assignees: i.assignees?.map((a) => a.login) ?? [],
    comments: i.comments,
    html_url: i.html_url,
    created_at: i.created_at,
    updated_at: i.updated_at,
    closed_at: i.closed_at,
  };
}

function formatPR(pr) {
  return {
    number: pr.number,
    title: pr.title,
    body: pr.body,
    state: pr.state,
    user: pr.user?.login,
    draft: pr.draft,
    head: pr.head?.ref,
    base: pr.base?.ref,
    merged: pr.merged ?? false,
    mergeable: pr.mergeable,
    html_url: pr.html_url,
    created_at: pr.created_at,
    updated_at: pr.updated_at,
    merged_at: pr.merged_at,
  };
}
