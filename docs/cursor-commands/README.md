# Cursor slash commands (enhancement backlog)

Templates for project slash commands. **Do not commit `.cursor/`** — it is gitignored. Copy these files into your local Cursor project folder so Agent chat can use them.

## Install commands locally

From the repo root:

```bash
mkdir -p .cursor/commands
cp docs/cursor-commands/add-enhancement.md \
   docs/cursor-commands/list-enhancements.md \
   docs/cursor-commands/work-on-enhancement.md \
   .cursor/commands/
```

In Cursor Agent chat, the filename (without `.md`) becomes the slash command, e.g. `/add-enhancement`.

| Command | Purpose |
|---------|---------|
| `/add-enhancement` | Append a feature idea to `.local/grocery_wizard/enhancements.jsonl` |
| `/list-enhancements` | Show open backlog items |
| `/work-on-enhancement` | Implement one item (optional ID after the command) |

These wrap `uv run python -m src.grocery_wizard dev …` and are the preferred UX over running CLI subcommands manually. Ingredient edit logs still use `dev suggest-fixes` for parser-oriented suggestions.

## GitHub MCP (issue/PR tools)

The cloud agent `gh` token can push code but often **cannot edit issues** (403). For issue updates, comments, and PR tools in chat, configure **GitHub MCP** with your personal access token.

### 1. Create a PAT

Create a fine-grained PAT at https://github.com/settings/personal-access-tokens/new with **Issues** and **Pull requests** read/write on your repos.

### 2. Enable GitHub MCP in Cursor (recommended)

Do **not** commit MCP config or tokens to the repo. Configure GitHub MCP through the Cursor UI:

- **Desktop:** Cursor Settings → Plugins → GitHub → paste your PAT.
- **Cloud Agents:** [cursor.com/agents](https://cursor.com/agents) → MCP dropdown → enable GitHub → paste your PAT.

### 3. Optional: local file config (not committed)

If you prefer file-based MCP config on Desktop, create `.cursor/mcp.json` locally (the whole `.cursor/` directory is gitignored).

Use an environment variable for the token (never paste a real token into the file):

```json
{
  "mcpServers": {
    "github": {
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": "Bearer ${env:GITHUB_PERSONAL_ACCESS_TOKEN}"
      }
    }
  }
}
```

Then export the token in your shell before starting Cursor:

```bash
export GITHUB_PERSONAL_ACCESS_TOKEN=github_pat_…
```

See also: [Cursor MCP docs](https://cursor.com/docs/mcp.md), [GitHub MCP install for Cursor](https://github.com/github/github-mcp-server/blob/main/docs/installation-guides/install-cursor.md).
