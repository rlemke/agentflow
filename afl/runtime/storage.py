"""Storage abstraction layer for local and HDFS file systems.

Provides a unified interface for file operations across local and HDFS storage,
enabling handlers to work with both local paths and hdfs:// URIs transparently.
"""

from __future__ import annotations

import builtins
import logging
import os
import shutil
import time
from typing import IO, Iterator, Protocol, runtime_checkable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

try:
    import requests as _requests
    from requests.exceptions import ConnectionError as _ReqConnectionError
    from requests.exceptions import HTTPError as _ReqHTTPError

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    _ReqConnectionError = None  # type: ignore[assignment,misc]
    _ReqHTTPError = None  # type: ignore[assignment,misc]


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
    def remove(self, path: str) -> None: ...
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

    def remove(self, path: str) -> None:
        os.remove(path)

    def join(self, *parts: str) -> str:
        return os.path.join(*parts)

    def dirname(self, path: str) -> str:
        return os.path.dirname(path)

    def basename(self, path: str) -> str:
        return os.path.basename(path)


# Retry configuration for transient HDFS/WebHDFS errors
_HDFS_MAX_RETRIES = int(os.environ.get("AFL_HDFS_MAX_RETRIES", "3"))
_HDFS_RETRY_BASE_DELAY = float(os.environ.get("AFL_HDFS_RETRY_DELAY", "1.0"))


def _hdfs_retry(func, *, max_retries: int = _HDFS_MAX_RETRIES, base_delay: float = _HDFS_RETRY_BASE_DELAY):
    """Execute *func* with retries on transient HTTP errors (404, 502, 503, 504, ConnectionError)."""
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as exc:
            retryable = False
            if HAS_REQUESTS:
                if isinstance(exc, _ReqConnectionError):
                    retryable = True
                elif isinstance(exc, _ReqHTTPError):
                    status = getattr(exc.response, "status_code", None)
                    if status in (404, 502, 503, 504):
                        retryable = True
            if not retryable or attempt >= max_retries:
                raise
            last_exc = exc
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "HDFS request failed (attempt %d/%d): %s — retrying in %.1fs",
                attempt + 1, max_retries + 1, exc, delay,
            )
            time.sleep(delay)
    raise last_exc  # pragma: no cover


class HDFSStorageBackend:
    """Storage backend for HDFS via WebHDFS REST API.

    Uses the WebHDFS HTTP interface (default port 9870) instead of the native
    libhdfs JNI library, making it work on any platform without Hadoop native
    libraries installed.
    """

    def __init__(self, host: str = "default", port: int = 0, user: str | None = None):
        if not HAS_REQUESTS:
            raise RuntimeError(
                "requests is required for HDFS support. "
                "Install it with: pip install requests"
            )
        # WebHDFS runs on port 9870 (HTTP) by default; the RPC port (8020)
        # is what callers typically pass, so we convert.
        webhdfs_port = int(os.environ.get("AFL_WEBHDFS_PORT", "9870"))
        self._base_url = f"http://{host}:{webhdfs_port}/webhdfs/v1"
        self._user = user or os.environ.get("HADOOP_USER_NAME", "root")
        self._host = host
        self._port = port

    def _strip_uri(self, path: str) -> str:
        """Strip hdfs://host:port prefix to get the bare HDFS path."""
        if path.startswith("hdfs://"):
            parsed = urlparse(path)
            return parsed.path
        return path

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _params(self, **kwargs) -> dict:
        return {"user.name": self._user, **kwargs}

    @staticmethod
    def _follow_redirect(response) -> _requests.Response:
        """Follow WebHDFS two-step redirect, rewriting container hostnames."""
        if response.status_code in (301, 307):
            location = response.headers["Location"]
            parsed = urlparse(location)
            if parsed.hostname != "localhost":
                location = parsed._replace(
                    netloc=f"{parsed.hostname}:{parsed.port}"
                ).geturl()
            return _requests.request(
                response.request.method, location,
                data=response.request.body,
                headers={"Content-Type": "application/octet-stream"} if response.request.body else {},
            )
        return response

    def exists(self, path: str) -> bool:
        hdfs_path = self._strip_uri(path)
        r = _requests.get(
            self._url(hdfs_path), params=self._params(op="GETFILESTATUS")
        )
        return r.status_code != 404

    def open(self, path: str, mode: str = "r") -> IO:
        hdfs_path = self._strip_uri(path)
        if "w" in mode:
            return _WebHDFSWriteStream(self, hdfs_path)

        # Read: OPEN with redirect follow and retry
        def _do_open():
            r = _requests.get(
                self._url(hdfs_path),
                params=self._params(op="OPEN"),
                allow_redirects=True,
            )
            r.raise_for_status()
            return r

        r = _hdfs_retry(_do_open)
        import io
        if "b" in mode:
            return io.BytesIO(r.content)
        return io.StringIO(r.text)

    def makedirs(self, path: str, exist_ok: bool = True) -> None:
        hdfs_path = self._strip_uri(path)
        r = _requests.put(
            self._url(hdfs_path),
            params=self._params(op="MKDIRS"),
            allow_redirects=True,
        )
        r.raise_for_status()

    def getsize(self, path: str) -> int:
        hdfs_path = self._strip_uri(path)
        r = _requests.get(
            self._url(hdfs_path), params=self._params(op="GETFILESTATUS")
        )
        r.raise_for_status()
        return r.json()["FileStatus"]["length"]

    def getmtime(self, path: str) -> float:
        hdfs_path = self._strip_uri(path)
        r = _requests.get(
            self._url(hdfs_path), params=self._params(op="GETFILESTATUS")
        )
        r.raise_for_status()
        return r.json()["FileStatus"]["modificationTime"] / 1000.0

    def isfile(self, path: str) -> bool:
        hdfs_path = self._strip_uri(path)
        r = _requests.get(
            self._url(hdfs_path), params=self._params(op="GETFILESTATUS")
        )
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return r.json()["FileStatus"]["type"] == "FILE"

    def isdir(self, path: str) -> bool:
        hdfs_path = self._strip_uri(path)
        r = _requests.get(
            self._url(hdfs_path), params=self._params(op="GETFILESTATUS")
        )
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return r.json()["FileStatus"]["type"] == "DIRECTORY"

    def listdir(self, path: str) -> list[str]:
        hdfs_path = self._strip_uri(path)
        r = _requests.get(
            self._url(hdfs_path), params=self._params(op="LISTSTATUS")
        )
        r.raise_for_status()
        entries = r.json()["FileStatuses"]["FileStatus"]
        return [e["pathSuffix"] for e in entries]

    def walk(self, path: str) -> Iterator[tuple[str, list[str], list[str]]]:
        hdfs_path = self._strip_uri(path)
        r = _requests.get(
            self._url(hdfs_path), params=self._params(op="LISTSTATUS")
        )
        r.raise_for_status()
        entries = r.json()["FileStatuses"]["FileStatus"]

        dirs = []
        files = []
        for entry in entries:
            name = entry["pathSuffix"]
            if entry["type"] == "DIRECTORY":
                dirs.append(name)
            else:
                files.append(name)

        yield hdfs_path, dirs, files

        for d in dirs:
            child_path = f"{hdfs_path.rstrip('/')}/{d}"
            yield from self.walk(child_path)

    def rmtree(self, path: str) -> None:
        hdfs_path = self._strip_uri(path)
        r = _requests.delete(
            self._url(hdfs_path),
            params=self._params(op="DELETE", recursive="true"),
        )
        r.raise_for_status()

    def remove(self, path: str) -> None:
        hdfs_path = self._strip_uri(path)
        r = _requests.delete(
            self._url(hdfs_path),
            params=self._params(op="DELETE", recursive="false"),
        )
        r.raise_for_status()

    def join(self, *parts: str) -> str:
        return "/".join(p.rstrip("/") for p in parts if p)

    def dirname(self, path: str) -> str:
        stripped = self._strip_uri(path)
        parent = stripped.rsplit("/", 1)[0] if "/" in stripped else ""
        return parent or "/"

    def basename(self, path: str) -> str:
        stripped = self._strip_uri(path)
        return stripped.rsplit("/", 1)[-1] if "/" in stripped else stripped


class _WebHDFSWriteStream:
    """Write stream that buffers data and uploads via WebHDFS CREATE on close."""

    def __init__(self, backend: HDFSStorageBackend, hdfs_path: str):
        import io
        self._backend = backend
        self._hdfs_path = hdfs_path
        self._buffer = io.BytesIO()

    def write(self, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        return self._buffer.write(data)

    def close(self):
        data = self._buffer.getvalue()
        size_mb = len(data) / 1_048_576
        logger.info("HDFS upload: %s (%.1f MB) — starting", self._hdfs_path, size_mb)

        def _do_create():
            r = _requests.put(
                self._backend._url(self._hdfs_path),
                params=self._backend._params(op="CREATE", overwrite="true"),
                allow_redirects=False,
            )
            r.raise_for_status()
            if r.status_code in (301, 307):
                location = r.headers["Location"]
                r2 = _requests.put(location, data=data)
                r2.raise_for_status()

        _hdfs_retry(_do_create)
        logger.info("HDFS upload: %s (%.1f MB) — complete", self._hdfs_path, size_mb)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# Singleton and cache for backend instances
_local_backend: LocalStorageBackend | None = None
_hdfs_backends: dict[str, HDFSStorageBackend] = {}

_DEFAULT_LOCAL_CACHE = "/tmp/osm-local"


def localize(path: str, target_dir: str = _DEFAULT_LOCAL_CACHE) -> str:
    """Ensure a file is available on the local filesystem.

    For local paths, returns *path* unchanged.  For ``hdfs://`` URIs,
    downloads the file to *target_dir* (preserving the HDFS directory
    structure) and returns the local path.  Skips download when a local
    copy with the same byte-size already exists.

    Args:
        path: Local path or ``hdfs://`` URI.
        target_dir: Root directory for cached downloads.

    Returns:
        A local filesystem path suitable for tools that require local files
        (e.g. pyosmium ``apply_file``).
    """
    if not path.startswith("hdfs://"):
        return path

    parsed = urlparse(path)
    hdfs_subpath = parsed.path.lstrip("/")
    local_path = os.path.join(target_dir, hdfs_subpath)

    backend = get_storage_backend(path)

    # Check if already cached locally with matching size
    if os.path.isfile(local_path):
        try:
            local_size = os.path.getsize(local_path)
            hdfs_size = backend.getsize(path)
            if local_size == hdfs_size:
                logger.debug("localize: cache hit %s -> %s", path, local_path)
                return local_path
        except Exception:
            pass  # re-download on any error

    # Stream download from HDFS via WebHDFS OPEN
    logger.info("localize: downloading %s -> %s", path, local_path)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    hdfs_path = parsed.path

    def _do_download() -> None:
        r = _requests.get(
            backend._url(hdfs_path),
            params=backend._params(op="OPEN"),
            allow_redirects=True,
            stream=True,
        )
        r.raise_for_status()
        with builtins.open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)

    _hdfs_retry(_do_download)
    dl_size = os.path.getsize(local_path)
    logger.info("localize: downloaded %s (%d bytes)", local_path, dl_size)
    return local_path


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
