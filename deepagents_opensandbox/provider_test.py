"""Tests for OpensandboxProvider."""

from unittest.mock import MagicMock, patch

import pytest

from deepagents_opensandbox.conftest import integration_server_available

try:
    from deepagents_opensandbox.provider import OpensandboxProvider as Provider

    _HAS_CLI = True
except ImportError:
    _HAS_CLI = False

pytestmark = pytest.mark.skipif(not _HAS_CLI, reason="deepagents-cli not installed")


def _make_mock_sandbox(sandbox_id: str = "sandbox-abc123") -> MagicMock:
    """Create a mock SandboxSync for provider tests."""
    sandbox = MagicMock()
    sandbox.id = sandbox_id
    sandbox.kill = MagicMock()
    sandbox.close = MagicMock()

    # Mock commands service
    sandbox.commands = MagicMock()
    sandbox.files = MagicMock()
    return sandbox


def test_provider_imports() -> None:
    """Test that OpensandboxProvider can be imported."""
    assert Provider is not None


def test_provider_inherits_sandbox_provider() -> None:
    """Test that OpensandboxProvider inherits from SandboxProvider."""
    from deepagents_cli.integrations.sandbox_provider import SandboxProvider

    assert issubclass(Provider, SandboxProvider)


def test_provider_interface() -> None:
    """Test that OpensandboxProvider has all required methods."""
    assert hasattr(Provider, "get_or_create")
    assert hasattr(Provider, "delete")


@patch("deepagents_opensandbox.provider.ConnectionConfigSync")
def test_provider_default_values(mock_config_cls: MagicMock) -> None:
    """Test that provider uses sensible defaults."""
    mock_config_cls.return_value = MagicMock()
    provider = Provider()
    assert provider._active == {}  # noqa: SLF001


@patch("deepagents_opensandbox.provider.ConnectionConfigSync")
@patch("opensandbox.sync.sandbox.SandboxSync.create")
def test_get_or_create_new(mock_create: MagicMock, mock_config_cls: MagicMock) -> None:
    """Test creating a new sandbox."""
    mock_config_cls.return_value = MagicMock()
    mock_sandbox = _make_mock_sandbox()
    mock_create.return_value = mock_sandbox

    provider = Provider()
    backend = provider.get_or_create(image="python:3.11")

    assert backend is not None
    assert backend.id == "sandbox-abc123"
    mock_create.assert_called_once()


@patch("deepagents_opensandbox.provider.ConnectionConfigSync")
@patch("opensandbox.sync.sandbox.SandboxSync.connect")
def test_get_or_create_existing(mock_connect: MagicMock, mock_config_cls: MagicMock) -> None:
    """Test connecting to an existing sandbox."""
    mock_config_cls.return_value = MagicMock()
    mock_sandbox = _make_mock_sandbox("existing-123")
    mock_connect.return_value = mock_sandbox

    provider = Provider()
    backend = provider.get_or_create(sandbox_id="existing-123")

    assert backend is not None
    assert backend.id == "existing-123"
    mock_connect.assert_called_once()


@patch("deepagents_opensandbox.provider.ConnectionConfigSync")
@patch("opensandbox.sync.sandbox.SandboxSync.create")
def test_get_or_create_cached(mock_create: MagicMock, mock_config_cls: MagicMock) -> None:
    """Test that get_or_create returns cached backend on second call."""
    mock_config_cls.return_value = MagicMock()
    mock_sandbox = _make_mock_sandbox("cached-123")
    mock_create.return_value = mock_sandbox

    provider = Provider()
    backend1 = provider.get_or_create()
    backend2 = provider.get_or_create(sandbox_id="cached-123")

    assert backend1 is backend2
    mock_create.assert_called_once()  # Only created once


@patch("deepagents_opensandbox.provider.ConnectionConfigSync")
@patch("opensandbox.sync.sandbox.SandboxSync.create")
def test_delete(mock_create: MagicMock, mock_config_cls: MagicMock) -> None:
    """Test deleting a sandbox."""
    mock_config_cls.return_value = MagicMock()
    mock_sandbox = _make_mock_sandbox()
    mock_create.return_value = mock_sandbox

    provider = Provider()
    backend = provider.get_or_create()
    provider.delete(sandbox_id=backend.id)

    mock_sandbox.kill.assert_called_once()
    mock_sandbox.close.assert_called_once()


@patch("deepagents_opensandbox.provider.ConnectionConfigSync")
def test_delete_nonexistent_idempotent(mock_config_cls: MagicMock) -> None:
    """Test that deleting a nonexistent sandbox doesn't raise."""
    mock_config_cls.return_value = MagicMock()
    provider = Provider()
    provider.delete(sandbox_id="nonexistent-sandbox")  # Should not raise


@patch("deepagents_opensandbox.provider.ConnectionConfigSync")
@patch("opensandbox.sync.sandbox.SandboxSync.create")
def test_delete_idempotent(mock_create: MagicMock, mock_config_cls: MagicMock) -> None:
    """Test that delete is idempotent."""
    mock_config_cls.return_value = MagicMock()
    mock_sandbox = _make_mock_sandbox()
    mock_create.return_value = mock_sandbox

    provider = Provider()
    backend = provider.get_or_create()
    sandbox_id = backend.id

    provider.delete(sandbox_id=sandbox_id)
    provider.delete(sandbox_id=sandbox_id)  # Should not raise


# --- Integration tests (require OPEN_SANDBOX_DOMAIN) ---


@pytest.mark.skipif(not integration_server_available(), reason="No OpenSandbox server available")
def test_integration_lifecycle() -> None:
    """Integration test: create, execute, delete."""
    provider = Provider()
    backend = provider.get_or_create(image="python:3.11", timeout=300, ready_timeout=120)

    try:
        result = backend.execute("echo 'integration test'")
        assert result.exit_code == 0
        assert "integration test" in result.output
    finally:
        provider.delete(sandbox_id=backend.id)
