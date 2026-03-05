"""Shared test fixtures and markers for opensandbox tests."""

import os
import socket
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

# Environment variable for real server testing
INTEGRATION_ENV = "OPEN_SANDBOX_DOMAIN"


def _parse_host_port(domain: str) -> tuple[str, int]:
    """Parse 'host:port' string, defaulting port to 8080."""
    if ":" in domain:
        host, port_str = domain.rsplit(":", 1)
        return host, int(port_str)
    return domain, 8080


def integration_server_available() -> bool:
    """Check if an OpenSandbox server is actually reachable."""
    domain = os.environ.get(INTEGRATION_ENV)
    if domain is None:
        return False
    host, port = _parse_host_port(domain)
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


@pytest.fixture
def mock_execution() -> MagicMock:
    """Create a mock Execution result from commands.run()."""
    from opensandbox.models.execd import Execution, ExecutionLogs, OutputMessage

    execution = MagicMock(spec=Execution)
    execution.id = "exec-123"
    execution.logs = MagicMock(spec=ExecutionLogs)
    execution.logs.stdout = [MagicMock(spec=OutputMessage, text="mocked output\n")]
    execution.logs.stderr = []
    return execution


@pytest.fixture
def mock_command_status() -> MagicMock:
    """Create a mock CommandStatus."""
    from opensandbox.models.execd import CommandStatus

    status = MagicMock(spec=CommandStatus)
    status.exit_code = 0
    return status


@pytest.fixture
def mock_sandbox(mock_execution: MagicMock, mock_command_status: MagicMock) -> MagicMock:
    """Create a mock SandboxSync instance."""
    sandbox = MagicMock()
    sandbox.id = "sandbox-abc123"

    # Mock commands service
    sandbox.commands = MagicMock()
    sandbox.commands.run = MagicMock(return_value=mock_execution)
    sandbox.commands.get_command_status = MagicMock(return_value=mock_command_status)

    # Mock files service
    sandbox.files = MagicMock()
    sandbox.files.write_file = MagicMock()
    sandbox.files.read_bytes = MagicMock(return_value=b"file content")

    # Mock lifecycle
    sandbox.kill = MagicMock()
    sandbox.close = MagicMock()

    return sandbox


@pytest.fixture
def mock_backend(mock_sandbox: MagicMock) -> Generator:
    """Create an OpensandboxBackend with a mocked sandbox."""
    from deepagents_opensandbox import OpensandboxBackend

    return OpensandboxBackend(sandbox=mock_sandbox)
