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

## Cursor (optional)

The `.cursor/` folder is **local only** (gitignored). To use enhancement backlog slash commands in Agent chat, copy templates from [docs/cursor-commands/](docs/cursor-commands/README.md) into `.cursor/commands/`. The CLI (`uv run python -m src.grocery_wizard dev …`) works without Cursor.

# Execution
