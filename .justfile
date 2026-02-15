# AIPM development commands
set dotenv-load

default:
    @just --list

# Sync dependencies for local development
sync:
    uv sync

# Install aipm globally (available in any shell)
install:
    uv tool install -e .

# Uninstall aipm from global tools
uninstall:
    uv tool uninstall aipm

# Install the GitHub Copilot CLI (Linux/macOS)
install-copilot:
    curl -fsSL https://gh.io/copilot-install | bash

# Build the package
build:
    uv build

# Run the CLI
run *args:
    uv run aipm {{args}}

# Run all tests
test *args:
    uv run pytest tests/ -v {{args}}

# Run a specific test file
test-file file *args:
    uv run pytest {{file}} -v {{args}}

# Lint with ruff
lint:
    uv run ruff check src/ tests/

# Lint and auto-fix
lint-fix:
    uv run ruff check --fix src/ tests/

# Format with ruff
fmt:
    uv run ruff format src/ tests/

# Check formatting without changing files
fmt-check:
    uv run ruff format --check src/ tests/

# Type check with ty
typecheck:
    uv run ty check src/

# Audit dependencies for vulnerabilities
audit:
    uv run pip-audit

# Run all checks (lint + format check + typecheck + audit + tests)
check: lint fmt-check typecheck audit test

# Clean build artifacts and caches
clean:
    rm -rf dist/ build/ .pytest_cache/ .ruff_cache/ tests/.tmp/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Run all pre-commit checks
pre-commit: fmt-check lint test
