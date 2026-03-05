# AGENTS.md

## Project Overview
`deepagents-opensandbox` is a Python package that implements a sandbox backend for the [DeepAgents](https://github.com/shkarupa-alex/deepagents) framework using [OpenSandbox](https://github.com/nicholasgriffintn/OpenSandbox). It allows DeepAgents to execute code and commands in isolated OpenSandbox environments.

- **Language**: Python 3.11+
- **Dependency Manager**: `uv`

## Project Structure

```
deepagents-opensandbox/
├── deepagents_opensandbox/
│   ├── __init__.py             # Package exports
│   ├── backend.py              # OpensandboxBackend implementation
│   ├── provider.py             # OpensandboxProvider implementation
│   ├── conftest.py             # Shared test fixtures
│   ├── backend_test.py         # Backend unit and integration tests
│   └── provider_test.py        # Provider unit and integration tests
├── pyproject.toml              # Project configuration and dependencies
├── uv.lock                     # Dependency lock file
└── AGENTS.md                   # Documentation for AI coding agents
```

## Architecture

This package provides two main components in the `deepagents_opensandbox` package:

### 1. `OpensandboxProvider` (`provider.py`)
- Inherits from `SandboxProvider` from `deepagents_cli.integrations.sandbox_provider`.
- Responsible for the lifecycle of sandboxes (create, connect, delete).
- Uses `SandboxSync.create()` / `SandboxSync.connect()` from the OpenSandbox SDK.
- Configuration via env vars: `OPEN_SANDBOX_API_KEY`, `OPEN_SANDBOX_DOMAIN`.

### 2. `OpensandboxBackend` (`backend.py`)
- Inherits from `BaseSandbox` from `deepagents.backends.sandbox`.
- Represents a single active sandbox instance wrapping `SandboxSync`.
- Command execution via `sandbox.commands.run()` + `sandbox.commands.get_command_status()`.
- File upload via `sandbox.files.write_file()`.
- File download via `sandbox.files.read_bytes()`.

## Development Standards

### Dependency Management
This project uses `uv` for all dependency management and running commands.
- **Install dependencies**: `uv sync`
- **Add dependency**: `uv add <package>`
- **Add dev dependency**: `uv add --dev <package>`

### Code Style
- **Formatter/Linter**: `ruff` is used for linting and formatting. Configuration is in `pyproject.toml`.
- **Type Hints**: Strict typing is enforced.
- **Docstrings**: Google-style docstrings are required for public APIs.

### Testing
Tests are located in `*_test.py` files alongside the source code.

#### Unit Tests (Mocked)
Tests that do not require a running OpenSandbox server. These mock SDK calls.
```bash
uv run pytest deepagents_opensandbox/ -v
```

#### Integration Tests (Real Server)
Tests that run against a live OpenSandbox server.
```bash
OPEN_SANDBOX_DOMAIN=localhost:8080 uv run pytest deepagents_opensandbox/ -v -k integration
```

### Verification
```bash
uv run ruff check deepagents_opensandbox/
uv run ruff format --check deepagents_opensandbox/
uv run pytest deepagents_opensandbox/ -v
```

## Key Files
- `pyproject.toml`: Project configuration, dependencies, and tool settings.
- `deepagents_opensandbox/backend.py`: Backend implementation.
- `deepagents_opensandbox/provider.py`: Provider implementation.
- `deepagents_opensandbox/backend_test.py`: Tests for the backend.
- `deepagents_opensandbox/provider_test.py`: Tests for the provider.
