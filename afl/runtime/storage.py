"""Storage abstraction layer for local and HDFS file systems.

Provides a unified interface for file operations across local and HDFS storage,
enabling handlers to work with both local paths and hdfs:// URIs transparently.
"""

from __future__ import annotations

import builtins
import os
import shutil
from contextlib import contextmanager
from typing import IO, Iterator, Protocol, runtime_checkable
from urllib.parse import urlparse

try:
    from pyarrow.fs import FileSelector, FileType, HadoopFileSystem

    HAS_PYARROW = True
except ImportError:
    HAS_PYARROW = False


@runtime_checkable
class StorageBackend(Protocol):
    """Protocol for storage backends (local filesystem, HDFS, etc.)."""

    def exists(self, path: str) -> bool: ...
    def open(self, path: str, mode: str = "r") -> IO: ...
    def makedirs(self, path: str, exist_ok: bool = True) -> None: ...
    def getsize(self, path: str) -> int: ...
    def getmtime(self, path: str) -> float: ...
    def isfile(self, path: str) -> bool: ...
    def isdir(self, path: str) -> bool: ...
    def listdir(self, path: str) -> list[str]: ...
    def walk(self, path: str) -> Iterator[tuple[str, list[str], list[str]]]: ...
    def rmtree(self, path: str) -> None: ...
    def join(self, *parts: str) -> str: ...
    def dirname(self, path: str) -> str: ...
    def basename(self, path: str) -> str: ...


class LocalStorageBackend:
    """Storage backend for the local filesystem."""

    def exists(self, path: str) -> bool:
        return os.path.exists(path)

    def open(self, path: str, mode: str = "r") -> IO:
        return builtins.open(path, mode)

    def makedirs(self, path: str, exist_ok: bool = True) -> None:
        os.makedirs(path, exist_ok=exist_ok)

    def getsize(self, path: str) -> int:
        return os.path.getsize(path)

    def getmtime(self, path: str) -> float:
        return os.path.getmtime(path)

    def isfile(self, path: str) -> bool:
        return os.path.isfile(path)

    def isdir(self, path: str) -> bool:
        return os.path.isdir(path)

    def listdir(self, path: str) -> list[str]:
        return os.listdir(path)

    def walk(self, path: str) -> Iterator[tuple[str, list[str], list[str]]]:
        yield from os.walk(path)

    def rmtree(self, path: str) -> None:
        shutil.rmtree(path)

    def join(self, *parts: str) -> str:
        return os.path.join(*parts)

    def dirname(self, path: str) -> str:
        return os.path.dirname(path)

    def basename(self, path: str) -> str:
        return os.path.basename(path)


class HDFSStorageBackend:
    """Storage backend for HDFS via PyArrow's HadoopFileSystem."""

    def __init__(self, host: str = "default", port: int = 0, user: str | None = None):
        if not HAS_PYARROW:
            raise RuntimeError(
                "pyarrow is required for HDFS support. "
                "Install it with: pip install agentflow[hdfs]"
            )
        self._fs = HadoopFileSystem(host=host, port=port, user=user)
        self._host = host
        self._port = port

    def _strip_uri(self, path: str) -> str:
        """Strip hdfs://host:port prefix to get the bare HDFS path."""
        if path.startswith("hdfs://"):
            parsed = urlparse(path)
            return parsed.path
        return path

    def exists(self, path: str) -> bool:
        hdfs_path = self._strip_uri(path)
        try:
            self._fs.get_file_info(hdfs_path)
            return True
        except Exception:
            return False

    def open(self, path: str, mode: str = "r") -> IO:
        hdfs_path = self._strip_uri(path)
        if "w" in mode:
            return self._fs.open_output_stream(hdfs_path)
        return self._fs.open_input_stream(hdfs_path)

    def makedirs(self, path: str, exist_ok: bool = True) -> None:
        hdfs_path = self._strip_uri(path)
        self._fs.create_dir(hdfs_path, recursive=True)

    def getsize(self, path: str) -> int:
        hdfs_path = self._strip_uri(path)
        info = self._fs.get_file_info(hdfs_path)
        return info.size

    def getmtime(self, path: str) -> float:
        hdfs_path = self._strip_uri(path)
        info = self._fs.get_file_info(hdfs_path)
        if info.mtime is not None:
            return info.mtime.timestamp()
        return 0.0

    def isfile(self, path: str) -> bool:
        hdfs_path = self._strip_uri(path)
        try:
            info = self._fs.get_file_info(hdfs_path)
            return info.type == FileType.File
        except Exception:
            return False

    def isdir(self, path: str) -> bool:
        hdfs_path = self._strip_uri(path)
        try:
            info = self._fs.get_file_info(hdfs_path)
            return info.type == FileType.Directory
        except Exception:
            return False

    def listdir(self, path: str) -> list[str]:
        hdfs_path = self._strip_uri(path)
        selector = FileSelector(hdfs_path, recursive=False)
        entries = self._fs.get_file_info(selector)
        return [os.path.basename(e.path) for e in entries]

    def walk(self, path: str) -> Iterator[tuple[str, list[str], list[str]]]:
        hdfs_path = self._strip_uri(path)
        selector = FileSelector(hdfs_path, recursive=False)
        entries = self._fs.get_file_info(selector)

        dirs = []
        files = []
        for entry in entries:
            name = os.path.basename(entry.path)
            if entry.type == FileType.Directory:
                dirs.append(name)
            else:
                files.append(name)

        yield hdfs_path, dirs, files

        for d in dirs:
            child_path = f"{hdfs_path.rstrip('/')}/{d}"
            yield from self.walk(child_path)

    def rmtree(self, path: str) -> None:
        hdfs_path = self._strip_uri(path)
        self._fs.delete_dir(hdfs_path)

    def join(self, *parts: str) -> str:
        return "/".join(p.rstrip("/") for p in parts if p)

    def dirname(self, path: str) -> str:
        stripped = self._strip_uri(path)
        parent = stripped.rsplit("/", 1)[0] if "/" in stripped else ""
        return parent or "/"

    def basename(self, path: str) -> str:
        stripped = self._strip_uri(path)
        return stripped.rsplit("/", 1)[-1] if "/" in stripped else stripped


# Singleton and cache for backend instances
_local_backend: LocalStorageBackend | None = None
_hdfs_backends: dict[str, HDFSStorageBackend] = {}


def get_storage_backend(path: str | None = None) -> StorageBackend:
    """Return the appropriate storage backend for the given path.

    Args:
        path: A file path or URI. If it starts with ``hdfs://``, an
            HDFSStorageBackend is returned (cached per host:port).
            Otherwise a LocalStorageBackend singleton is returned.

    Returns:
        A StorageBackend instance.
    """
    global _local_backend

    if path and path.startswith("hdfs://"):
        parsed = urlparse(path)
        host = parsed.hostname or "default"
        port = parsed.port or 0
        cache_key = f"{host}:{port}"
        if cache_key not in _hdfs_backends:
            _hdfs_backends[cache_key] = HDFSStorageBackend(host=host, port=port)
        return _hdfs_backends[cache_key]

    if _local_backend is None:
        _local_backend = LocalStorageBackend()
    return _local_backend
