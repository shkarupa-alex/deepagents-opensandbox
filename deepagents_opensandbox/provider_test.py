"""Tests for OpensandboxProvider."""

from unittest.mock import AsyncMock, MagicMock, patch

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
    sandbox.commands = MagicMock()
    sandbox.files = MagicMock()
    return sandbox


def _make_mock_async_sandbox(sandbox_id: str = "sandbox-abc123") -> MagicMock:
    """Create a mock async Sandbox for provider tests."""
    sandbox = MagicMock()
    sandbox.id = sandbox_id
    sandbox.kill = AsyncMock()
    sandbox.close = AsyncMock()
    return sandbox


# --- Sync interface tests ---


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
    assert hasattr(Provider, "aget_or_create")
    assert hasattr(Provider, "adelete")


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
    mock_create.assert_called_once()


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
    provider.delete(sandbox_id="nonexistent-sandbox")


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
    provider.delete(sandbox_id=sandbox_id)


# --- Async interface tests ---


@pytest.mark.asyncio
@patch("deepagents_opensandbox.provider.ConnectionConfigSync")
@patch("deepagents_opensandbox.provider.ConnectionConfig")
@patch("deepagents_opensandbox.provider.Sandbox.create", new_callable=AsyncMock)
@patch("deepagents_opensandbox.provider.SandboxSync.connect")
async def test_aget_or_create_new(
    mock_sync_connect: MagicMock,
    mock_async_create: AsyncMock,
    mock_async_config_cls: MagicMock,
    mock_sync_config_cls: MagicMock,
) -> None:
    """Test async creation of a new sandbox."""
    mock_sync_config_cls.return_value = MagicMock()
    mock_async_config_cls.return_value = MagicMock()

    mock_async_sandbox = _make_mock_async_sandbox("async-new-123")
    mock_async_create.return_value = mock_async_sandbox

    mock_sync_sandbox = _make_mock_sandbox("async-new-123")
    mock_sync_connect.return_value = mock_sync_sandbox

    provider = Provider()
    backend = await provider.aget_or_create(image="python:3.11")

    assert backend is not None
    assert backend.id == "async-new-123"
    mock_async_create.assert_called_once()
    mock_sync_connect.assert_called_once()


@pytest.mark.asyncio
@patch("deepagents_opensandbox.provider.ConnectionConfigSync")
@patch("deepagents_opensandbox.provider.ConnectionConfig")
@patch("deepagents_opensandbox.provider.Sandbox.connect", new_callable=AsyncMock)
@patch("deepagents_opensandbox.provider.SandboxSync.connect")
async def test_aget_or_create_existing(
    mock_sync_connect: MagicMock,
    mock_async_connect: AsyncMock,
    mock_async_config_cls: MagicMock,
    mock_sync_config_cls: MagicMock,
) -> None:
    """Test async connect to an existing sandbox."""
    mock_sync_config_cls.return_value = MagicMock()
    mock_async_config_cls.return_value = MagicMock()

    mock_async_sandbox = _make_mock_async_sandbox("existing-456")
    mock_async_connect.return_value = mock_async_sandbox

    mock_sync_sandbox = _make_mock_sandbox("existing-456")
    mock_sync_connect.return_value = mock_sync_sandbox

    provider = Provider()
    backend = await provider.aget_or_create(sandbox_id="existing-456")

    assert backend.id == "existing-456"
    mock_async_connect.assert_called_once()


@pytest.mark.asyncio
@patch("deepagents_opensandbox.provider.ConnectionConfigSync")
@patch("deepagents_opensandbox.provider.ConnectionConfig")
@patch("deepagents_opensandbox.provider.Sandbox.create", new_callable=AsyncMock)
@patch("deepagents_opensandbox.provider.SandboxSync.connect")
async def test_aget_or_create_cached(
    mock_sync_connect: MagicMock,
    mock_async_create: AsyncMock,
    mock_async_config_cls: MagicMock,
    mock_sync_config_cls: MagicMock,
) -> None:
    """Test that aget_or_create returns cached backend on second call."""
    mock_sync_config_cls.return_value = MagicMock()
    mock_async_config_cls.return_value = MagicMock()

    mock_async_sandbox = _make_mock_async_sandbox("cached-789")
    mock_async_create.return_value = mock_async_sandbox

    mock_sync_sandbox = _make_mock_sandbox("cached-789")
    mock_sync_connect.return_value = mock_sync_sandbox

    provider = Provider()
    backend1 = await provider.aget_or_create()
    backend2 = await provider.aget_or_create(sandbox_id="cached-789")

    assert backend1 is backend2
    mock_async_create.assert_called_once()


@pytest.mark.asyncio
@patch("deepagents_opensandbox.provider.ConnectionConfigSync")
@patch("deepagents_opensandbox.provider.ConnectionConfig")
@patch("deepagents_opensandbox.provider.Sandbox.create", new_callable=AsyncMock)
@patch("deepagents_opensandbox.provider.SandboxSync.connect")
async def test_adelete(
    mock_sync_connect: MagicMock,
    mock_async_create: AsyncMock,
    mock_async_config_cls: MagicMock,
    mock_sync_config_cls: MagicMock,
) -> None:
    """Test async delete uses native async kill/close."""
    mock_sync_config_cls.return_value = MagicMock()
    mock_async_config_cls.return_value = MagicMock()

    mock_async_sandbox = _make_mock_async_sandbox("del-123")
    mock_async_create.return_value = mock_async_sandbox

    mock_sync_sandbox = _make_mock_sandbox("del-123")
    mock_sync_connect.return_value = mock_sync_sandbox

    provider = Provider()
    backend = await provider.aget_or_create()
    await provider.adelete(sandbox_id=backend.id)

    mock_async_sandbox.kill.assert_called_once()
    mock_async_sandbox.close.assert_called_once()
    mock_sync_sandbox.close.assert_called_once()


@pytest.mark.asyncio
@patch("deepagents_opensandbox.provider.ConnectionConfigSync")
async def test_adelete_nonexistent_idempotent(mock_config_cls: MagicMock) -> None:
    """Test that async deleting a nonexistent sandbox doesn't raise."""
    mock_config_cls.return_value = MagicMock()
    provider = Provider()
    await provider.adelete(sandbox_id="nonexistent-sandbox")


@pytest.mark.asyncio
@patch("deepagents_opensandbox.provider.ConnectionConfigSync")
@patch("opensandbox.sync.sandbox.SandboxSync.create")
async def test_adelete_sync_created(mock_create: MagicMock, mock_config_cls: MagicMock) -> None:
    """Test adelete on a sandbox created via sync get_or_create."""
    mock_config_cls.return_value = MagicMock()
    mock_sandbox = _make_mock_sandbox()
    mock_create.return_value = mock_sandbox

    provider = Provider()
    backend = provider.get_or_create()
    await provider.adelete(sandbox_id=backend.id)

    # Falls back to sync kill + close
    mock_sandbox.kill.assert_called_once()
    mock_sandbox.close.assert_called_once()


# --- Integration tests (require OPEN_SANDBOX_DOMAIN) ---


@pytest.mark.skipif(not integration_server_available(), reason="No OpenSandbox server available")
def test_integration_lifecycle() -> None:
    """Integration test: create, execute, delete."""
    provider = Provider(use_server_proxy=True)
    backend = provider.get_or_create(image="python:3.11", timeout=300, ready_timeout=120)

    try:
        result = backend.execute("echo 'integration test'")
        assert result.exit_code == 0
        assert "integration test" in result.output
    finally:
        provider.delete(sandbox_id=backend.id)


@pytest.mark.skipif(not integration_server_available(), reason="No OpenSandbox server available")
@pytest.mark.asyncio
async def test_integration_async_lifecycle() -> None:
    """Integration test: async create, execute, async delete."""
    provider = Provider(use_server_proxy=True)
    backend = await provider.aget_or_create(image="python:3.11", timeout=300, ready_timeout=120)

    try:
        result = backend.execute("echo 'async integration test'")
        assert result.exit_code == 0
        assert "async integration test" in result.output
    finally:
        await provider.adelete(sandbox_id=backend.id)
