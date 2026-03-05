"""Opensandbox provider for DeepAgents.

This module provides OpensandboxProvider, a sandbox provider that manages
the lifecycle of OpenSandbox containers using both synchronous and
asynchronous OpenSandbox SDKs.
"""

import logging
import os
from datetime import timedelta
from typing import Any

from deepagents.backends.protocol import SandboxBackendProtocol
from deepagents_cli.integrations.sandbox_provider import SandboxProvider
from opensandbox.config.connection import ConnectionConfig
from opensandbox.config.connection_sync import ConnectionConfigSync
from opensandbox.sandbox import Sandbox
from opensandbox.sync.sandbox import SandboxSync

from deepagents_opensandbox.backend import OpensandboxBackend

logger = logging.getLogger(__name__)


class OpensandboxProvider(SandboxProvider):
    """Opensandbox provider for managing sandbox lifecycle.

    This provider creates, connects to, and deletes OpenSandbox containers.
    It integrates with the DeepAgents CLI via the ``SandboxProvider`` interface.

    Both synchronous (``get_or_create`` / ``delete``) and native asynchronous
    (``aget_or_create`` / ``adelete``) methods are supported.

    Example:
        ```python
        from deepagents_opensandbox import OpensandboxProvider

        provider = OpensandboxProvider()
        sandbox = provider.get_or_create(image="python:3.11")
        result = sandbox.execute("python --version")
        provider.delete(sandbox_id=sandbox.id)
        ```
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        domain: str | None = None,
        protocol: str = "http",
        use_server_proxy: bool = False,
    ) -> None:
        """Initialize the Opensandbox provider.

        Args:
            api_key: API key for authentication. Defaults to
                ``OPEN_SANDBOX_API_KEY`` environment variable.
            domain: OpenSandbox server domain. Defaults to
                ``OPEN_SANDBOX_DOMAIN`` environment variable or
                ``localhost:8080``.
            protocol: Protocol to use (``http`` or ``https``). Default: ``http``.
            use_server_proxy: Route execd requests through the sandbox server
                instead of connecting to containers directly. Default: ``False``.
                Set to ``True`` when the SDK cannot reach container IPs
                directly (e.g. server runs in Docker, client on host).
        """
        self._api_key = api_key or os.environ.get("OPEN_SANDBOX_API_KEY")
        self._domain = domain or os.environ.get("OPEN_SANDBOX_DOMAIN")
        self._protocol = protocol
        self._use_server_proxy = use_server_proxy

        self._connection_config = ConnectionConfigSync(
            api_key=self._api_key,
            domain=self._domain,
            protocol=self._protocol,
            use_server_proxy=self._use_server_proxy,
        )

        # Cache of active sandbox backends keyed by sandbox ID
        self._active: dict[str, OpensandboxBackend] = {}

        # Async Sandbox instances kept alive for native async delete.
        # Populated only when sandboxes are created via aget_or_create().
        self._async_sandboxes: dict[str, Sandbox] = {}

    # ------------------------------------------------------------------
    # Synchronous interface
    # ------------------------------------------------------------------

    def get_or_create(
        self,
        *,
        sandbox_id: str | None = None,
        image: str = "python:3.11",
        timeout: int = 600,
        ready_timeout: int = 120,
        resource: dict[str, str] | None = None,
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> SandboxBackendProtocol:
        """Get an existing sandbox or create a new one.

        Args:
            sandbox_id: ID of an existing sandbox to connect to.
                If ``None``, creates a new sandbox.
            image: Container image to use. Default: ``python:3.11``.
            timeout: Sandbox lifetime in seconds. Default: 600.
            ready_timeout: Max seconds to wait for sandbox to become ready.
                Default: 120.
            resource: Resource limits (e.g. ``{"cpu": "1", "memory": "2Gi"}``).
            **kwargs: Additional arguments (ignored).

        Returns:
            OpensandboxBackend instance connected to the sandbox.
        """
        if sandbox_id is not None and sandbox_id in self._active:
            return self._active[sandbox_id]

        if sandbox_id is not None:
            sandbox = SandboxSync.connect(
                sandbox_id,
                connection_config=self._connection_config,
                connect_timeout=timedelta(seconds=ready_timeout),
            )
        else:
            sandbox = SandboxSync.create(
                image,
                timeout=timedelta(seconds=timeout),
                ready_timeout=timedelta(seconds=ready_timeout),
                resource=resource,
                connection_config=self._connection_config,
            )

        backend = OpensandboxBackend(sandbox=sandbox)
        self._active[backend.id] = backend
        return backend

    def delete(
        self,
        *,
        sandbox_id: str,
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> None:
        """Delete a sandbox by ID.

        This method is idempotent — calling delete on a non-existent or
        already-deleted sandbox will succeed without raising an error.

        Args:
            sandbox_id: ID of the sandbox to delete.
            **kwargs: Additional arguments (ignored).
        """
        backend = self._active.pop(sandbox_id, None)
        self._async_sandboxes.pop(sandbox_id, None)

        if backend is None:
            return

        sandbox = backend._sandbox  # noqa: SLF001
        try:
            sandbox.kill()
        except Exception:  # noqa: BLE001
            logger.debug("Error killing sandbox %s", sandbox_id, exc_info=True)
        try:
            sandbox.close()
        except Exception:  # noqa: BLE001
            logger.debug("Error closing sandbox %s", sandbox_id, exc_info=True)

    # ------------------------------------------------------------------
    # Asynchronous interface (native async, no thread pool)
    # ------------------------------------------------------------------

    async def aget_or_create(
        self,
        *,
        sandbox_id: str | None = None,
        image: str = "python:3.11",
        timeout: int = 600,
        ready_timeout: int = 120,
        resource: dict[str, str] | None = None,
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> SandboxBackendProtocol:
        """Async version of :meth:`get_or_create`.

        Uses the native async OpenSandbox SDK (``Sandbox``) for
        non-blocking sandbox creation and health-check polling, then
        wraps the result in a sync ``SandboxSync`` backend.

        Args:
            sandbox_id: ID of an existing sandbox to connect to.
                If ``None``, creates a new sandbox.
            image: Container image to use. Default: ``python:3.11``.
            timeout: Sandbox lifetime in seconds. Default: 600.
            ready_timeout: Max seconds to wait for sandbox to become ready.
                Default: 120.
            resource: Resource limits (e.g. ``{"cpu": "1", "memory": "2Gi"}``).
            **kwargs: Additional arguments (ignored).

        Returns:
            OpensandboxBackend instance connected to the sandbox.
        """
        if sandbox_id is not None and sandbox_id in self._active:
            return self._active[sandbox_id]

        async_config = ConnectionConfig(
            api_key=self._api_key,
            domain=self._domain,
            protocol=self._protocol,
            use_server_proxy=self._use_server_proxy,
        )

        if sandbox_id is not None:
            async_sandbox = await Sandbox.connect(
                sandbox_id,
                connection_config=async_config,
                connect_timeout=timedelta(seconds=ready_timeout),
            )
        else:
            async_sandbox = await Sandbox.create(
                image,
                timeout=timedelta(seconds=timeout),
                ready_timeout=timedelta(seconds=ready_timeout),
                resource=resource,
                connection_config=async_config,
            )

        # Create a sync wrapper — health check already passed above.
        sync_sandbox = SandboxSync.connect(
            async_sandbox.id,
            connection_config=self._connection_config,
            skip_health_check=True,
        )

        # Keep async sandbox alive for native async kill in adelete().
        self._async_sandboxes[async_sandbox.id] = async_sandbox

        backend = OpensandboxBackend(sandbox=sync_sandbox)
        self._active[backend.id] = backend
        return backend

    async def adelete(
        self,
        *,
        sandbox_id: str,
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> None:
        """Async version of :meth:`delete`.

        Uses the native async SDK when the sandbox was created via
        :meth:`aget_or_create`; otherwise falls back to sync kill/close.

        This method is idempotent.

        Args:
            sandbox_id: ID of the sandbox to delete.
            **kwargs: Additional arguments (ignored).
        """
        backend = self._active.pop(sandbox_id, None)
        async_sandbox = self._async_sandboxes.pop(sandbox_id, None)

        if backend is None and async_sandbox is None:
            return

        # Prefer native async kill if available.
        if async_sandbox is not None:
            try:
                await async_sandbox.kill()
            except Exception:  # noqa: BLE001
                logger.debug("Error async-killing sandbox %s", sandbox_id, exc_info=True)
            try:
                await async_sandbox.close()
            except Exception:  # noqa: BLE001
                logger.debug("Error async-closing sandbox %s", sandbox_id, exc_info=True)
        elif backend is not None:
            # Created via sync path — fall back to sync kill.
            sandbox = backend._sandbox  # noqa: SLF001
            try:
                sandbox.kill()
            except Exception:  # noqa: BLE001
                logger.debug("Error killing sandbox %s", sandbox_id, exc_info=True)

        # Always close local sync resources.
        if backend is not None:
            try:
                backend._sandbox.close()  # noqa: SLF001
            except Exception:  # noqa: BLE001
                logger.debug("Error closing sandbox %s", sandbox_id, exc_info=True)
