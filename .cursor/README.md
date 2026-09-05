# Cursor MCP configuration

## GitHub MCP (issue/PR tools)

The cloud agent `gh` token (`ghs_…`) can push code but often **cannot edit issues** (403). For issue updates, comments, and PR tools in chat, configure **GitHub MCP** with your personal access token.

1. Create a fine-grained PAT at https://github.com/settings/personal-access-tokens/new with **Issues** and **Pull requests** read/write on your repos.
2. Export locally: `export GITHUB_PERSONAL_ACCESS_TOKEN=github_pat_…`
3. **Desktop:** Cursor Settings → Plugins → GitHub → paste PAT, or rely on this `mcp.json` + env var.
4. **Cloud Agents:** [cursor.com/agents](https://cursor.com/agents) → MCP dropdown → enable GitHub → paste PAT.

Do **not** commit tokens. The `${env:GITHUB_PERSONAL_ACCESS_TOKEN}` placeholder in `mcp.json` is intentional.

See also: [Cursor MCP docs](https://cursor.com/docs/mcp.md), [GitHub MCP install for Cursor](https://github.com/github/github-mcp-server/blob/main/docs/installation-guides/install-cursor.md).
