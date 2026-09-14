# One-Time Setup

1. Install [brew](https://brew.sh/): a package manager.
   - Install it directly as a package from its GitHub repo.
   - Follow installation steps, including command to setup your shell, by exporting path -> .zshrc.

2. Install other tools
   ```shell
   brew install \
     just
     uv
   ```

# Local setup

1. Update local environment by running:
   ```shell
   just setup
   ```

## Enhancement backlog

Feature ideas and fixes live in `.local/grocery_wizard/enhancements.jsonl` (gitignored). Slash commands are **not** in the repo — templates are under `docs/cursor-commands/` (see [docs/cursor-commands/README.md](docs/cursor-commands/README.md)).

Install them locally once (from repo root):

```shell
mkdir -p .cursor/commands && cp docs/cursor-commands/*.md .cursor/commands/
```

Then in **Cursor Agent chat**:

- `/add-enhancement` — capture a new idea (title, optional description, area)
- `/list-enhancements` — show open backlog items
- `/work-on-enhancement` — implement one item (optional ID, e.g. `/work-on-enhancement enh_001`)

**CLI fallback** (no Cursor, or scripts):

```shell
uv run python -m src.grocery_wizard dev add-enhancement --title "..." --area ui
uv run python -m src.grocery_wizard dev list-enhancements
uv run python -m src.grocery_wizard dev show-enhancement <id>
```

# Execution
