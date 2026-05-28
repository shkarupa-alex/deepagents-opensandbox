"""OpenSandbox Provider for DeepAgents.

Manages the lifecycle of OpenSandbox containers using both synchronous and
asynchronous OpenSandbox SDKs.
"""

import asyncio
import logging
import os
from datetime import timedelta
from typing import Any

from deepagents.backends.protocol import SandboxBackendProtocol
from opensandbox.config.connection_sync import ConnectionConfigSync
from opensandbox.sync.sandbox import SandboxSync

from deepagents_opensandbox.backend import OpensandboxBackend

logger = logging.getLogger(__name__)


class OpensandboxProvider:
    """OpenSandbox provider for managing sandbox lifecycle.

    Creates, connects to, and deletes OpenSandbox containers.
    Integrates with DeepAgents CLI via the ``SandboxProvider`` interface.

    Supports both synchronous (``get_or_create`` / ``delete``) and
    native asynchronous (``aget_or_create`` / ``adelete``) interfaces.

    Example:
        ```python
        from deepagents_opensandbox import OpensandboxProvider

        provider = OpensandboxProvider()
        backend = provider.get_or_create(image="opensandbox/code-interpreter:v1.0.2")
        result = backend.execute("python --version")
        provider.delete(sandbox_id=backend.id)
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
        api_key = api_key or os.environ.get("OPEN_SANDBOX_API_KEY")
        domain = domain or os.environ.get("OPEN_SANDBOX_DOMAIN")

        self._connection_config = ConnectionConfigSync(
            api_key=api_key,
            domain=domain,
            protocol=protocol,
            use_server_proxy=use_server_proxy,
        )

        # Cache of active sandbox backends keyed by sandbox ID
        self._active: dict[str, OpensandboxBackend] = {}

    # ------------------------------------------------------------------
    # Synchronous interface
    # ------------------------------------------------------------------

    def get_or_create(
        self,
        *,
        sandbox_id: str | None = None,
        image: str = "opensandbox/code-interpreter:v1.0.2",
        timeout: int = 600,
        ready_timeout: int = 120,
        resource: dict[str, str] | None = None,
        metadata: dict[str, str] | None = None,
        entrypoint: list[str] | None = None,
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> SandboxBackendProtocol:
        """Get an existing sandbox or create a new one.

        First checks local cache and remote connection by sandbox_id;
        if not found, searches by metadata session_id;
        otherwise creates a new sandbox with the given metadata.

        Args:
            sandbox_id: ID of an existing sandbox to connect to.
                If ``None``, creates a new sandbox.
            image: Container image to use. Default: ``python:3.11``.
            timeout: Sandbox lifetime in seconds. Default: 600.
            ready_timeout: Max seconds to wait for sandbox to become ready.
                Default: 120.
            resource: Resource limits (e.g. ``{"cpu": "1", "memory": "2Gi"}``).
            metadata: Custom metadata (e.g. ``{"session_id": "xxx"}``).
            entrypoint: Container entrypoint command. Default: ``None``
                (use image default).
            **kwargs: Additional arguments (ignored).

        Returns:
            OpensandboxBackend instance connected to the sandbox.
        """
        if sandbox_id is not None and sandbox_id in self._active:
            logger.info(f"[OpensandboxProvider] sandbox {sandbox_id} found in local cache")
            return self._active[sandbox_id]

        sandbox = None

        # Try to connect to remote sandbox by sandbox_id first
        if sandbox_id is not None:
            try:
                sandbox = SandboxSync.connect(
                    sandbox_id,
                    connection_config=self._connection_config,
                )
                logger.info(f"[OpensandboxProvider] sandbox {sandbox_id} connected remotely")
            except Exception as e:
                logger.info(f"[OpensandboxProvider] connect {sandbox_id} failed: {e}")

        # If remote connect failed, try searching by metadata
        if sandbox is None and metadata:
            sandbox = self._find_by_metadata(metadata)
            if sandbox:
                logger.info(f"[OpensandboxProvider] sandbox found by metadata {metadata}")

        if sandbox is None:
            sandbox = SandboxSync.create(
                image,
                timeout=timedelta(seconds=timeout),
                entrypoint=entrypoint,
                ready_timeout=timedelta(seconds=ready_timeout),
                resource=resource,
                metadata=metadata,
                connection_config=self._connection_config,
            )
            logger.info(f"[OpensandboxProvider] sandbox created, id={getattr(sandbox, 'id', sandbox)}, metadata={metadata}")

        backend = OpensandboxBackend(sandbox=sandbox)
        self._active[backend.id] = backend
        return backend

    def _find_by_metadata(self, metadata: dict[str, str]) -> "SandboxSync | None":
        """Find existing sandbox by metadata.

        Checks local cache first, then queries the server via
        SandboxManager.list_sandbox_infos.
        """
        # Check local cache first
        for backend_id, backend in self._active.items():
            sandbox_meta = getattr(backend._sandbox, "metadata", {}) or {}
            if all(sandbox_meta.get(k) == v for k, v in metadata.items()):
                logger.info(f"[OpensandboxProvider] found sandbox in local cache: {backend_id}")
                return backend._sandbox

        # Query server via SandboxManagerSync
        try:
            from opensandbox import SandboxManagerSync
            from opensandbox.models.sandboxes import SandboxFilter

            sync_mgr = SandboxManagerSync.create(connection_config=self._connection_config)
            filter_obj = SandboxFilter(metadata=metadata)
            result = sync_mgr.list_sandbox_infos(filter_obj)

            if result.sandbox_infos:
                info = result.sandbox_infos[0]
                logger.info(f"[OpensandboxProvider] found sandbox on server by metadata: {info.id}")
                return SandboxSync.connect(
                    info.id,
                    connection_config=self._connection_config,
                )
        except Exception as e:
            logger.info(f"[OpensandboxProvider] find by metadata failed: {e}")

        return None

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

        try:
            backend.kill()
        except Exception:  # noqa: BLE001
            logger.debug("Error killing sandbox %s", sandbox_id, exc_info=True)
        try:
            backend.close()
        except Exception:  # noqa: BLE001
            logger.debug("Error closing sandbox %s", sandbox_id, exc_info=True)

    # ------------------------------------------------------------------
    # Asynchronous interface (native async, no thread pool)
    # ------------------------------------------------------------------

    async def aget_or_create(
        self,
        *,
        sandbox_id: str | None = None,
        image: str = "opensandbox/code-interpreter:v1.0.2",
        timeout: int = 600,
        ready_timeout: int = 120,
        resource: dict[str, str] | None = None,
        metadata: dict[str, str] | None = None,
        entrypoint: list[str] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> SandboxBackendProtocol:
        """Async version of :meth:`get_or_create`.

        Reuses the sync implementation via ``asyncio.to_thread``.

        Args:
            sandbox_id: ID of an existing sandbox to connect to.
                If ``None``, creates a new sandbox.
            image: Container image to use. Default: ``python:3.11``.
            timeout: Sandbox lifetime in seconds. Default: 600.
            ready_timeout: Max seconds to wait for sandbox to become ready.
                Default: 120.
            resource: Resource limits (e.g. ``{"cpu": "1", "memory": "2Gi"}``).
            metadata: Custom metadata (e.g. ``{"session_id": "xxx"}``).
            entrypoint: Container entrypoint command. Default: ``None``
                (use image default).
            **kwargs: Additional arguments (ignored).

        Returns:
            OpensandboxBackend instance connected to the sandbox.
        """
        return await asyncio.to_thread(
            self.get_or_create,
            sandbox_id=sandbox_id,
            image=image,
            timeout=timeout,
            ready_timeout=ready_timeout,
            resource=resource,
            metadata=metadata,
            entrypoint=entrypoint,
            **kwargs,
        )

    async def adelete(
        self,
        *,
        sandbox_id: str,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Async version of :meth:`delete`.

        Reuses the sync implementation via ``asyncio.to_thread``.

        This method is idempotent.

        Args:
            sandbox_id: ID of the sandbox to delete.
            **kwargs: Additional arguments (ignored).
        """
        await asyncio.to_thread(self.delete, sandbox_id=sandbox_id, **kwargs)
