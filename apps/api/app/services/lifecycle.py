"""Process identity and shutdown state shared by the worker, the API and the scan code."""

from __future__ import annotations

import os
import socket
import threading
import uuid

_role = "cli"
_instance = uuid.uuid4().hex[:8]
shutdown_event = threading.Event()


def set_role(role: str) -> None:
    """Call once at process start (\"worker\", \"api\"); CLI invocations keep the default."""
    global _role
    _role = role


def owner_id() -> str:
    """Identifies this process: role@hostname#pid-instance. Unique per process start."""
    return f"{_role}@{socket.gethostname()}#{os.getpid()}-{_instance}"


def same_host_worker_prefix() -> str:
    """Owner prefix of any worker process on this host (the container hostname for Docker)."""
    return f"worker@{socket.gethostname()}#"


def shutting_down() -> bool:
    return shutdown_event.is_set()
