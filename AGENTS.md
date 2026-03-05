# AGENTS.md

## Project Overview
`deepagents-opensandbox` is a Python package that implements a sandbox backend for the [DeepAgents](https://github.com/shkarupa-alex/deepagents) framework using [OpenSandbox](https://github.com/alibaba/OpenSandbox). It allows DeepAgents to execute code and commands in isolated OpenSandbox environments.

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
├── docker-compose.yaml         # Local dev server (OpenSandbox in Docker)
└── AGENTS.md                   # Documentation for AI coding agents
```

## Architecture

### 1. `OpensandboxBackend` (`backend.py`)
- Inherits from `BaseSandbox` from `deepagents.backends.sandbox`.
- Wraps `SandboxSync` for execute/upload/download.
- Command execution via `sandbox.commands.run()` + `sandbox.commands.get_command_status()`.
- File upload via `sandbox.files.write_file()`, download via `sandbox.files.read_bytes()`.

### 2. `OpensandboxProvider` (`provider.py`)
- Inherits from `SandboxProvider` from `deepagents_cli.integrations.sandbox_provider`.
- Lifecycle management: create, connect, delete (sync + async).
- Async path (`aget_or_create`) uses native async SDK (`Sandbox`) for non-blocking creation, then wraps in sync `SandboxSync` backend.
- Configuration via env vars: `OPEN_SANDBOX_API_KEY`, `OPEN_SANDBOX_DOMAIN`.

## Commands

- **Unit tests**: `uv run python -m pytest deepagents_opensandbox/ -v -k "not integration"`
- **Integration tests**: `OPEN_SANDBOX_DOMAIN=localhost:8090 uv run python -m pytest deepagents_opensandbox/ -v -k integration`
- **All tests**: `OPEN_SANDBOX_DOMAIN=localhost:8090 uv run python -m pytest deepagents_opensandbox/ -v`
- **Lint**: `uv run ruff check deepagents_opensandbox/`
- **Format check**: `uv run ruff format --check deepagents_opensandbox/`

## Server proxy mode

The SDK can talk to sandbox containers in two ways:

1. **Direct** (`use_server_proxy=False`, default): SDK connects to container IP/port directly. Works when client and containers are on the same network.
2. **Server proxy** (`use_server_proxy=True`): All execd requests go through the OpenSandbox server at `OPEN_SANDBOX_DOMAIN`. Required when the client cannot reach container IPs (e.g. server in Docker, client on host — `host.docker.internal` is not resolvable from macOS host).

`use_server_proxy` defaults to `False` in `OpensandboxProvider`. Integration tests pass `True` explicitly because they run from the host against a Docker-based server. Our docker-compose setup runs the server in Docker with `host_ip = "host.docker.internal"`.

## Known issues

- **Server ≤ v0.1.4**: proxy handler in `lifecycle.py` drops query parameters on GET requests (builds `target_url` without `request.url.query`). File downloads via proxy return `400 MISSING_QUERY`. Fixed in `main` (not yet released). Workaround: build server image from source. Our docker-compose uses a locally-built image with this fix.

## Development Standards

### Code Style
- **Formatter/Linter**: `ruff` (configuration in `pyproject.toml`).
- **Type Hints**: Strict typing enforced.
- **Docstrings**: Google-style for public APIs.

### Testing
- Tests are in `*_test.py` files alongside source code.
- Integration tests are gated by `OPEN_SANDBOX_DOMAIN` env var and a TCP connectivity check (`integration_server_available()` in `conftest.py`).
