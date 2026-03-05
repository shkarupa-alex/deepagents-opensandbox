"""Opensandbox provider for DeepAgents.

This module provides OpensandboxProvider, a sandbox provider that manages
the lifecycle of OpenSandbox containers using the synchronous SDK.
"""

import logging
import os
from datetime import timedelta
from typing import Any

from deepagents.backends.protocol import SandboxBackendProtocol
from deepagents_cli.integrations.sandbox_provider import SandboxProvider
from opensandbox.config.connection_sync import ConnectionConfigSync
from opensandbox.sync.sandbox import SandboxSync

from deepagents_opensandbox.backend import OpensandboxBackend

logger = logging.getLogger(__name__)


class OpensandboxProvider(SandboxProvider):
    """Opensandbox provider for managing sandbox lifecycle.

    This provider creates, connects to, and deletes OpenSandbox containers.
    It integrates with the DeepAgents CLI via the ``SandboxProvider`` interface.

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
    ) -> None:
        """Initialize the Opensandbox provider.

        Args:
            api_key: API key for authentication. Defaults to
                ``OPEN_SANDBOX_API_KEY`` environment variable.
            domain: OpenSandbox server domain. Defaults to
                ``OPEN_SANDBOX_DOMAIN`` environment variable or
                ``localhost:8080``.
            protocol: Protocol to use (``http`` or ``https``). Default: ``http``.
        """
        self._api_key = api_key or os.environ.get("OPEN_SANDBOX_API_KEY")
        self._domain = domain or os.environ.get("OPEN_SANDBOX_DOMAIN")
        self._protocol = protocol
        self._connection_config = ConnectionConfigSync(
            api_key=self._api_key,
            domain=self._domain,
            protocol=self._protocol,
        )

        # Cache of active sandbox backends keyed by sandbox ID
        self._active: dict[str, OpensandboxBackend] = {}

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
        # Return cached backend if available
        if sandbox_id is not None and sandbox_id in self._active:
            return self._active[sandbox_id]

        if sandbox_id is not None:
            # Connect to existing sandbox
            sandbox = SandboxSync.connect(
                sandbox_id,
                connection_config=self._connection_config,
                connect_timeout=timedelta(seconds=ready_timeout),
            )
        else:
            # Create new sandbox
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
