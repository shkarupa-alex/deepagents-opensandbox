"""Tests for OpensandboxBackend."""

import uuid
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from deepagents.backends.sandbox import BaseSandbox

from deepagents_opensandbox import OpensandboxBackend
from deepagents_opensandbox import OpensandboxBackend as Backend
from deepagents_opensandbox.conftest import integration_server_available


@pytest.fixture
def sandbox_name() -> str:
    """Generate a unique sandbox name for each test."""
    return f"test-backend-{uuid.uuid4().hex[:8]}"


def test_backend_imports() -> None:
    assert Backend is not None


def test_backend_inherits_base_sandbox() -> None:
    assert issubclass(Backend, BaseSandbox)


def test_backend_has_required_methods() -> None:
    """Test that OpensandboxBackend has all required methods."""
    assert hasattr(Backend, "execute")
    assert hasattr(Backend, "upload_files")
    assert hasattr(Backend, "download_files")
    assert hasattr(Backend, "id")

    # Check inherited methods from BaseSandbox
    assert hasattr(Backend, "read")
    assert hasattr(Backend, "write")
    assert hasattr(Backend, "edit")
    assert hasattr(Backend, "grep_raw")
    assert hasattr(Backend, "glob_info")


def test_execute_with_mock(mock_backend: OpensandboxBackend) -> None:
    """Test execute() with mocked sandbox."""
    result = mock_backend.execute("echo 'test'")

    assert result.exit_code == 0
    assert "mocked output" in result.output


def test_execute_with_exit_code(mock_sandbox: MagicMock) -> None:
    """Test that exit codes are captured correctly."""
    from opensandbox.models.execd import CommandStatus, Execution, ExecutionLogs

    execution = MagicMock(spec=Execution)
    execution.id = "exec-42"
    execution.logs = MagicMock(spec=ExecutionLogs)
    execution.logs.stdout = []
    execution.logs.stderr = []

    status = MagicMock(spec=CommandStatus)
    status.exit_code = 42

    mock_sandbox.commands.run = MagicMock(return_value=execution)
    mock_sandbox.commands.get_command_status = MagicMock(return_value=status)

    backend = OpensandboxBackend(sandbox=mock_sandbox)
    result = backend.execute("exit 42")
    assert result.exit_code == 42


def test_execute_with_stderr(mock_sandbox: MagicMock) -> None:
    """Test that stderr is captured in output."""
    from opensandbox.models.execd import CommandStatus, Execution, ExecutionLogs, OutputMessage

    execution = MagicMock(spec=Execution)
    execution.id = "exec-err"
    execution.logs = MagicMock(spec=ExecutionLogs)
    execution.logs.stdout = [MagicMock(spec=OutputMessage, text="out")]
    execution.logs.stderr = [MagicMock(spec=OutputMessage, text="error message\n")]

    status = MagicMock(spec=CommandStatus)
    status.exit_code = 0

    mock_sandbox.commands.run = MagicMock(return_value=execution)
    mock_sandbox.commands.get_command_status = MagicMock(return_value=status)

    backend = OpensandboxBackend(sandbox=mock_sandbox)
    result = backend.execute("echo error >&2")
    assert "error message" in result.output
    assert "out" in result.output


def test_id_property_with_mock(mock_backend: OpensandboxBackend, mock_sandbox: MagicMock) -> None:
    """Test that id property returns correct value."""
    assert mock_backend.id == mock_sandbox.id


def test_upload_files_with_mock(mock_backend: OpensandboxBackend, mock_sandbox: MagicMock) -> None:
    """Test upload_files() calls write_file on sandbox.files."""
    responses = mock_backend.upload_files([("/tmp/test.txt", b"content")])

    assert len(responses) == 1
    assert responses[0].path == "/tmp/test.txt"
    assert responses[0].error is None
    mock_sandbox.files.write_file.assert_called_once_with("/tmp/test.txt", b"content")


def test_upload_files_error(mock_sandbox: MagicMock) -> None:
    """Test upload_files() handles write errors gracefully."""
    mock_sandbox.files.write_file.side_effect = RuntimeError("write failed")
    backend = OpensandboxBackend(sandbox=mock_sandbox)

    responses = backend.upload_files([("/tmp/test.txt", b"content")])

    assert len(responses) == 1
    assert responses[0].error == "permission_denied"


def test_download_files_with_mock(mock_backend: OpensandboxBackend, mock_sandbox: MagicMock) -> None:
    """Test download_files() calls read_bytes on sandbox.files."""
    mock_sandbox.files.read_bytes.return_value = b"test content"

    responses = mock_backend.download_files(["/tmp/test.txt"])

    assert len(responses) == 1
    assert responses[0].path == "/tmp/test.txt"
    assert responses[0].content == b"test content"
    assert responses[0].error is None


def test_download_files_not_found(mock_sandbox: MagicMock) -> None:
    """Test download_files() when file not found."""
    mock_sandbox.files.read_bytes.side_effect = RuntimeError("file not found")
    backend = OpensandboxBackend(sandbox=mock_sandbox)

    responses = backend.download_files(["/nonexistent.txt"])

    assert len(responses) == 1
    assert responses[0].error == "file_not_found"
    assert responses[0].content is None


def test_download_files_is_directory(mock_sandbox: MagicMock) -> None:
    """Test download_files() when path is a directory."""
    mock_sandbox.files.read_bytes.side_effect = RuntimeError("is a directory")
    backend = OpensandboxBackend(sandbox=mock_sandbox)

    responses = backend.download_files(["/tmp"])

    assert len(responses) == 1
    assert responses[0].error == "is_directory"


def test_download_files_permission_denied(mock_sandbox: MagicMock) -> None:
    """Test download_files() on permission error."""
    mock_sandbox.files.read_bytes.side_effect = RuntimeError("access denied")
    backend = OpensandboxBackend(sandbox=mock_sandbox)

    responses = backend.download_files(["/root/secret.txt"])

    assert len(responses) == 1
    assert responses[0].error == "permission_denied"


# --- Integration tests (require OPEN_SANDBOX_DOMAIN) ---


@pytest.fixture(scope="module")
def integration_backend() -> Generator[OpensandboxBackend]:
    """Create a shared integration sandbox for backend tests."""
    from datetime import timedelta

    from opensandbox.config.connection_sync import ConnectionConfigSync
    from opensandbox.sync.sandbox import SandboxSync

    config = ConnectionConfigSync(use_server_proxy=True)
    sandbox = SandboxSync.create("python:3.11", ready_timeout=timedelta(seconds=120), connection_config=config)
    backend = OpensandboxBackend(sandbox=sandbox)
    yield backend
    sandbox.kill()
    sandbox.close()


@pytest.mark.skipif(not integration_server_available(), reason="No OpenSandbox server available")
def test_integration_execute(integration_backend: OpensandboxBackend) -> None:
    """Integration test: basic command execution."""
    result = integration_backend.execute("echo 'Hello, World!'")
    assert result.exit_code == 0
    assert "Hello, World!" in result.output


@pytest.mark.skipif(not integration_server_available(), reason="No OpenSandbox server available")
def test_integration_upload_download(integration_backend: OpensandboxBackend) -> None:
    """Integration test: file upload and download."""
    test_content = b"Hello, this is test content!\nWith multiple lines."
    test_path = "/tmp/test_upload.txt"

    upload_responses = integration_backend.upload_files([(test_path, test_content)])
    assert upload_responses[0].error is None

    download_responses = integration_backend.download_files([test_path])
    assert download_responses[0].error is None
    assert download_responses[0].content == test_content
