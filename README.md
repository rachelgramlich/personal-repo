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

## Feature enhancement backlog (local)

Ideas and fixes you want to tackle later live in `.local/grocery_wizard/enhancements.jsonl` (gitignored). From the repo root:

```shell
uv run python -m src.grocery_wizard dev add-enhancement
uv run python -m src.grocery_wizard dev list-enhancements
uv run python -m src.grocery_wizard dev show-enhancement enh_001
```

See [src/grocery_wizard/README.md](src/grocery_wizard/README.md#feature-enhancement-backlog) for flags and workflow.

## Cursor (optional)

The `.cursor/` folder is **local only** (gitignored). This repo does not ship slash-command templates; if you want Agent chat shortcuts, create your own markdown files under `.cursor/commands/` on your machine.

# Execution
