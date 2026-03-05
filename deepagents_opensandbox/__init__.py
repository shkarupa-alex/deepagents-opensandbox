"""Opensandbox integration for DeepAgents.

This package provides:
- OpensandboxBackend: Sandbox backend for executing commands in OpenSandbox containers
- OpensandboxProvider: Provider for managing OpenSandbox lifecycle (requires ``deepagents-cli``)

Example usage:
    ```python
    from deepagents_opensandbox import OpensandboxProvider

    provider = OpensandboxProvider()
    sandbox = provider.get_or_create(image="python:3.11")
    result = sandbox.execute("echo 'Hello'")
    provider.delete(sandbox_id=sandbox.id)
    ```
"""

from deepagents_opensandbox.backend import OpensandboxBackend

__all__ = ["OpensandboxBackend"]

try:
    from deepagents_opensandbox.provider import OpensandboxProvider

    __all__ += ["OpensandboxProvider"]  # type: ignore[assignment]
except ImportError:
    pass
