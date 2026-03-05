# deepagents-opensandbox

OpenSandbox backend for the [DeepAgents](https://github.com/shkarupa-alex/deepagents) framework. This package enables DeepAgents to launch and control isolated sandbox environments using [OpenSandbox](https://github.com/nicholasgriffintn/OpenSandbox).

## Key Features

- **Sandbox Provider**: Manages the lifecycle of OpenSandbox instances (create, connect, delete) via the `SandboxProvider` interface from `deepagents-cli`.
- **Sandbox Backend**: Provides a standard interface for command execution and file operations within a sandbox using the synchronous OpenSandbox SDK (`SandboxSync`).
- **DeepAgents Integration**: Fully compatible with `BaseSandbox` and `SandboxProvider` interfaces.

## Installation

```bash
pip install deepagents-opensandbox
```

## Usage

```python
from deepagents_opensandbox import OpensandboxProvider

# Initialize the provider (uses OPEN_SANDBOX_API_KEY and OPEN_SANDBOX_DOMAIN env vars)
provider = OpensandboxProvider()

# Create a new sandbox
sandbox = provider.get_or_create(image="python:3.11")

# Execute a command
result = sandbox.execute("echo 'Hello World'")
print(result.output)

# Clean up
provider.delete(sandbox_id=sandbox.id)
```

### Using the backend directly

```python
from opensandbox.sync.sandbox import SandboxSync
from deepagents_opensandbox import OpensandboxBackend

sandbox = SandboxSync.create("python:3.11")
backend = OpensandboxBackend(sandbox=sandbox)

result = backend.execute("python --version")
print(result.output)

sandbox.kill()
sandbox.close()
```

## Configuration

| Environment Variable      | Description                          | Default          |
|---------------------------|--------------------------------------|------------------|
| `OPEN_SANDBOX_API_KEY`    | API key for authentication           | *(none)*         |
| `OPEN_SANDBOX_DOMAIN`     | OpenSandbox server domain            | `localhost:8080` |

### Server proxy mode

By default, the SDK connects directly to sandbox container IPs. This works when the client and sandbox containers share the same network (e.g. both on the host, or in the same Docker/Kubernetes network).

When the OpenSandbox **server runs inside Docker** and the client runs on the **host machine**, container IPs (like `host.docker.internal`) are not reachable from the host. In this case, enable server proxy mode so that all execd requests are routed through the server:

```python
provider = OpensandboxProvider(use_server_proxy=True)
```

| Deployment                              | `use_server_proxy` |
|-----------------------------------------|--------------------|
| Server native on host, client on host   | `False` (default)  |
| Server in Docker, client on host        | `True`             |
| Server in Docker, client in same network| `False`            |
| Kubernetes with proper networking       | `False`            |

> **Note:** OpenSandbox server `v0.1.4` and earlier have a [bug](https://github.com/alibaba/OpenSandbox) where the proxy handler drops query parameters on GET requests, causing file downloads to fail with `400 MISSING_QUERY`. The fix is merged into `main` but not yet released. If you hit this issue, build the server image from source (`server/` directory).

## Development

This project uses `uv` for dependency management.

### Prerequisites

- [uv](https://github.com/astral-sh/uv) installed.
- Python 3.11 or higher.

### Setup

Install dependencies:

```bash
uv sync
```

### Testing

Tests are split into unit tests (mocked) and integration tests (requiring a real server).

**Run Unit Tests (Mocked)**

These tests mock the OpenSandbox SDK calls and do not require a running server.

```bash
uv run python -m pytest deepagents_opensandbox/ -v
```

**Run Integration Tests**

These tests verify behavior against a real OpenSandbox server. They use `use_server_proxy=True` since the test runner is on the host while the server is in Docker.

```bash
OPEN_SANDBOX_DOMAIN=localhost:8090 uv run python -m pytest deepagents_opensandbox/ -v -k integration
```

### Linting

```bash
uv run ruff check deepagents_opensandbox/
uv run ruff format --check deepagents_opensandbox/
```
