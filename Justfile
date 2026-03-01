# Justfile for personal-repo

set dotenv-load

# Default recipe to show help
default:
    @just --list

# Setup: Install Python dependencies
setup:
    uv sync --all-extras

# Upgrade and sync dependencies
setup-upgrade:
    uv sync --upgrade

# Run linting checks
lint:
    uv run ruff check --fix
    uv run mypy . --ignore-missing-imports

# Format code
format:
    uv run ruff format

# Run tests
test:
    uv run pytest

# Run tests with coverage
test-cov:
    uv run pytest --cov=. --cov-report=html

# Clean up Python cache files
clean:
    find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
    find . -type d -name .pytest_cache -exec rm -r {} + 2>/dev/null || true
    find . -type d -name .mypy_cache -exec rm -r {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete
    rm -rf .coverage htmlcov/
    rm -rf dist/ build/ *.egg-info

# Run all checks (lint, format check, tests)
check: lint test

# Run pre-commit checks
pre-commit:
    uv run pre-commit run --all-files

# Full development setup
dev-setup: setup format lint test
    @echo "Development setup complete!"

# Show Python version and environment info
info:
    @echo "Python version:"
    @uv run python --version
    @echo "\nPython location:"
    @uv run which python
    @echo "\nInstalled packages:"
    @uv pip list
