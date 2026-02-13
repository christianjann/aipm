# AIPM — Agent Instructions

## Project Overview

- **Language:** Python 3.14+
- **Package manager:** uv (for deps, builds, runs, and tool installs)
- **Build backend:** hatchling
- **Source layout:** `src/aipm/`
- **CLI framework:** click + rich
- **Task runner:** just (`.justfile`)

## Development Workflow

- Use `uv` for all Python project management, builds, and running
- Never use `pip` or `pip install` directly — always `uv sync`, `uv run`, or `uv tool install`
- Run commands via `just <target>` or `uv run <command>`

## Code Quality

- **Linter:** ruff (`uv run ruff check src/ tests/`)
- **Formatter:** ruff (`uv run ruff format src/ tests/`)
- **Type checker:** ty (`uv run ty check src/`)
- Fix all lint and format issues before committing
- Follow the ruff rule set configured in `pyproject.toml` (E, W, F, I, N, UP, B, SIM, RUF)
- Line length: 120 characters max

## Testing

- **Framework:** pytest
- **Test directory:** `tests/`
- Always run the tests after making changes: `uv run pytest tests/ -v`
- Add tests for every new feature or command
- Tests use a `work_dir` fixture (from `conftest.py`) that creates directories under `tests/.tmp/<test_name>/` for easy debugging
- Use `CliRunner` from click for testing CLI commands
- Run all checks with: `just check`
- For each error log that the user pastes in the chat, that was not covered by tests before, add a regression test case

## Documentation

- Update `README.md` for new options, commands, and features
- Keep the command reference table in the README in sync with the CLI
- Update the project structure section when adding new directories or file types

## Code Style

- Use `from __future__ import annotations` in every module
- Type-annotate all function signatures
- Use lazy imports inside click command functions (import the command handler inside the function body)
- Use `rich.console.Console` for user-facing output
- Use `click.prompt` / `click.confirm` for interactive input
- Prefer `pathlib.Path` over `os.path`
- Use dataclasses for configuration and data structures

## Project Structure

```
src/aipm/
├── __init__.py          # Package version
├── cli.py               # Click CLI entry point and command registration
├── config.py            # aipm.toml config loading/saving
├── horizons.py          # Time horizon constants, inference, validation
├── utils.py             # Git helpers, sanitization, markdown formatting
├── commands/            # One module per command
│   ├── init.py
│   ├── add.py
│   ├── sync.py
│   ├── diff.py
│   ├── plan.py
│   ├── summary.py
│   ├── commit.py
│   ├── check.py
│   ├── report.py
│   └── ticket.py
└── sources/             # Issue source backends
    ├── base.py          # Abstract base class + Ticket dataclass
    ├── jira_source.py
    └── github_source.py
```