"""Opensandbox backend for DeepAgents.

This module provides OpensandboxBackend, a sandbox backend implementation
that executes commands in OpenSandbox containers via the synchronous SDK.
"""

import logging
from datetime import timedelta

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox
from opensandbox.models.execd import RunCommandOpts
from opensandbox.sync.sandbox import SandboxSync

logger = logging.getLogger(__name__)


class OpensandboxBackend(BaseSandbox):
    """Opensandbox backend for DeepAgents.

    This backend executes commands in OpenSandbox containers via the
    synchronous OpenSandbox SDK (``SandboxSync``). It inherits from
    ``BaseSandbox``, which provides implementations for read, write, edit,
    grep, and glob operations using shell commands executed via ``execute()``.

    Example:
        ```python
        from opensandbox.sync.sandbox import SandboxSync

        from deepagents_opensandbox import OpensandboxBackend

        sandbox = SandboxSync.create("python:3.11")
        backend = OpensandboxBackend(sandbox=sandbox)
        result = backend.execute("echo 'Hello, World!'")
        print(result.output)

        sandbox.kill()
        sandbox.close()
        ```
    """

    def __init__(self, *, sandbox: SandboxSync) -> None:
        """Initialize the Opensandbox backend.

        Args:
            sandbox: An active ``SandboxSync`` instance (already created or
                connected via ``SandboxSync.create()`` / ``SandboxSync.connect()``).
        """
        self._sandbox = sandbox

    @property
    def id(self) -> str:
        """Return the unique identifier for this sandbox."""
        return self._sandbox.id

    def kill(self) -> None:
        """Kill the sandbox container."""
        self._sandbox.kill()

    def close(self) -> None:
        """Close the sandbox connection."""
        self._sandbox.close()

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        """Execute a shell command inside the sandbox.

        Args:
            command: Shell command string to execute.
            timeout: Maximum time in seconds to wait for the command to
                complete. If ``None``, no explicit timeout is set.

        Returns:
            ExecuteResponse with combined stdout/stderr output and exit code.
        """
        opts = RunCommandOpts()
        if timeout is not None:
            opts = RunCommandOpts(timeout=timedelta(seconds=timeout))

        execution = self._sandbox.commands.run(command, opts=opts)

        # Collect stdout and stderr from execution logs
        stdout = "".join(msg.text for msg in execution.logs.stdout)
        stderr = "".join(msg.text for msg in execution.logs.stderr)

        # Combine stdout and stderr
        output = stdout
        if stderr:
            if output and not output.endswith("\n"):
                output += "\n"
            output += stderr

        # Get exit code from command status
        exit_code: int | None = None
        if execution.id:
            status = self._sandbox.commands.get_command_status(execution.id)
            exit_code = status.exit_code

        return ExecuteResponse(
            output=output,
            exit_code=exit_code,
            truncated=False,
        )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Upload files to the sandbox using native file operations.

        Args:
            files: List of (path, content) tuples to upload.

        Returns:
            List of FileUploadResponse objects, one per input file.
        """
        responses: list[FileUploadResponse] = []
        for path, content in files:
            try:
                self._sandbox.files.write_file(path, content)
                responses.append(FileUploadResponse(path=path, error=None))
            except Exception:  # noqa: BLE001
                logger.debug("Failed to upload %s", path, exc_info=True)
                responses.append(FileUploadResponse(path=path, error="permission_denied"))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Download files from the sandbox using native file operations.

        Args:
            paths: List of file paths to download.

        Returns:
            List of FileDownloadResponse objects, one per input path.
        """
        responses: list[FileDownloadResponse] = []
        for path in paths:
            try:
                content = self._sandbox.files.read_bytes(path)
                responses.append(FileDownloadResponse(path=path, content=content, error=None))
            except Exception as exc:  # noqa: BLE001
                error = _map_file_error(exc)
                responses.append(FileDownloadResponse(path=path, content=None, error=error))
        return responses


def _map_file_error(exc: Exception) -> str:
    """Map an OpenSandbox exception to a FileOperationError string."""
    msg = str(exc).lower()
    if "not found" in msg or "no such file" in msg:
        return "file_not_found"
    if "is a directory" in msg or "directory" in msg:
        return "is_directory"
    return "permission_denied"
