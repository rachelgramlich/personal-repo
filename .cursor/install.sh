#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for personal-repo (Grocery Wizard).
# Installs the uv (Python deps) and just (task runner) toolchains, then
# syncs project dependencies. Safe to run repeatedly.
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

# Install uv if it is not already available.
if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Install just if it is not already available.
if ! command -v just >/dev/null 2>&1; then
  echo "Installing just..."
  mkdir -p "$HOME/.local/bin"
  curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to "$HOME/.local/bin"
fi

# Ensure ~/.local/bin is on PATH for interactive shells the agent opens later.
if ! grep -qs '.local/bin' "$HOME/.bashrc" 2>/dev/null; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
fi

# Sync Python dependencies (creates .venv from uv.lock, including dev extras).
just setup

echo "Environment setup complete."
