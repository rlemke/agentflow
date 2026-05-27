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
from collections.abc import Iterator
from typing import IO, Any, Protocol, runtime_checkable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

try:
    import requests as _requests
    from requests.exceptions import ConnectionError as _ReqConnectionError
    from requests.exceptions import HTTPError as _ReqHTTPError

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    _ReqConnectionError: Any = None  # type: ignore[no-redef]
    _ReqHTTPError: Any = None  # type: ignore[no-redef]

# boto3 is an optional dependency, soft-imported only when an s3:// path is used
# (S3 / MinIO backend). The platform's only hard runtime dep stays minimal.
try:
    import boto3 as _boto3
    from botocore.config import Config as _BotoConfig
    from botocore.exceptions import ClientError as _BotoClientError

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    _BotoClientError = Exception  # type: ignore[assignment,misc]


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


# Retry configuration for transient HDFS/WebHDFS errors — resolved lazily
# from the centralized config so that env vars and config files are respected.


def _hdfs_max_retries() -> int:
    from facetwork.config import get_config

    return get_config().storage.hdfs_max_retries


def _hdfs_retry_base_delay() -> float:
    from facetwork.config import get_config

    return get_config().storage.hdfs_retry_delay


def _hdfs_retry(func, *, max_retries: int | None = None, base_delay: float | None = None):
    """Execute *func* with retries on transient HTTP errors (404, 502, 503, 504, ConnectionError)."""
    if max_retries is None:
        max_retries = _hdfs_max_retries()
    if base_delay is None:
        base_delay = _hdfs_retry_base_delay()
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
            delay = base_delay * (2**attempt)
            logger.warning(
                "HDFS request failed (attempt %d/%d): %s — retrying in %.1fs",
                attempt + 1,
                max_retries + 1,
                exc,
                delay,
            )
            time.sleep(delay)
    assert last_exc is not None  # pragma: no cover
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
                "requests is required for HDFS support. Install it with: pip install requests"
            )
        # WebHDFS runs on port 9870 (HTTP) by default; the RPC port (8020)
        # is what callers typically pass, so we convert.
        from facetwork.config import get_config

        storage_cfg = get_config().storage
        webhdfs_port = storage_cfg.hdfs_webhdfs_port
        self._base_url = f"http://{host}:{webhdfs_port}/webhdfs/v1"
        self._user = user or storage_cfg.hdfs_user
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
                location = parsed._replace(netloc=f"{parsed.hostname}:{parsed.port}").geturl()
            return _requests.request(
                response.request.method,
                location,
                data=response.request.body,
                headers={"Content-Type": "application/octet-stream"}
                if response.request.body
                else {},
            )
        return response

    def exists(self, path: str) -> bool:
        hdfs_path = self._strip_uri(path)
        r = _requests.get(self._url(hdfs_path), params=self._params(op="GETFILESTATUS"))
        return r.status_code != 404

    def open(self, path: str, mode: str = "r") -> IO:
        hdfs_path = self._strip_uri(path)
        if "w" in mode:
            return _WebHDFSWriteStream(self, hdfs_path)  # type: ignore[return-value]

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
        r = _requests.get(self._url(hdfs_path), params=self._params(op="GETFILESTATUS"))
        r.raise_for_status()
        return r.json()["FileStatus"]["length"]

    def getmtime(self, path: str) -> float:
        hdfs_path = self._strip_uri(path)
        r = _requests.get(self._url(hdfs_path), params=self._params(op="GETFILESTATUS"))
        r.raise_for_status()
        return r.json()["FileStatus"]["modificationTime"] / 1000.0

    def isfile(self, path: str) -> bool:
        hdfs_path = self._strip_uri(path)
        r = _requests.get(self._url(hdfs_path), params=self._params(op="GETFILESTATUS"))
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return r.json()["FileStatus"]["type"] == "FILE"

    def isdir(self, path: str) -> bool:
        hdfs_path = self._strip_uri(path)
        r = _requests.get(self._url(hdfs_path), params=self._params(op="GETFILESTATUS"))
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return r.json()["FileStatus"]["type"] == "DIRECTORY"

    def listdir(self, path: str) -> list[str]:
        hdfs_path = self._strip_uri(path)
        r = _requests.get(self._url(hdfs_path), params=self._params(op="LISTSTATUS"))
        r.raise_for_status()
        entries = r.json()["FileStatuses"]["FileStatus"]
        return [e["pathSuffix"] for e in entries]

    def walk(self, path: str) -> Iterator[tuple[str, list[str], list[str]]]:
        hdfs_path = self._strip_uri(path)
        r = _requests.get(self._url(hdfs_path), params=self._params(op="LISTSTATUS"))
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


def _s3_split(path: str) -> tuple[str, str]:
    """Split an ``s3://bucket/key/...`` URI into ``(bucket, key)``."""
    parsed = urlparse(path)
    return parsed.netloc, parsed.path.lstrip("/")


class _S3WriteStream:
    """Buffers writes and uploads via a single put_object on close (like WebHDFS).

    S3 has no append/partial-object semantics, so a whole-object PUT on close is
    the natural unit. Adequate for the cache's modest artifacts (graph.json,
    GeoJSON layers); not for streaming a multi-GB object, which should be staged
    locally and uploaded with the managed transfer instead.
    """

    def __init__(self, backend: S3StorageBackend, bucket: str, key: str):
        import io

        self._backend = backend
        self._bucket = bucket
        self._key = key
        self._buffer = io.BytesIO()

    def write(self, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        return self._buffer.write(data)

    def close(self):
        body = self._buffer.getvalue()
        logger.info("S3 upload: s3://%s/%s (%.1f MB)", self._bucket, self._key, len(body) / 1_048_576)
        self._backend._client.put_object(Bucket=self._bucket, Key=self._key, Body=body)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class S3StorageBackend:
    """Storage backend for S3-compatible object stores (AWS S3 or a self-hosted
    MinIO surfacing the shared cache).

    Configured from the environment so MinIO "just works" locally:

    - ``AFL_S3_ENDPOINT``  — endpoint URL (e.g. ``http://localhost:9000`` for
      MinIO). Unset → real AWS S3.
    - ``AFL_S3_REGION``    — region (default ``us-east-1``).
    - credentials via the standard boto3 chain (``AWS_ACCESS_KEY_ID`` /
      ``AWS_SECRET_ACCESS_KEY`` / profile / instance role), or the convenience
      ``AFL_S3_ACCESS_KEY`` / ``AFL_S3_SECRET_KEY``.

    Objects are addressed by ``s3://bucket/key`` URIs. There are no real
    directories: ``makedirs`` is a no-op and ``isdir`` is emulated by a prefix
    listing — adequate for the cache's stage-locally-then-finalize pattern.
    """

    def __init__(self) -> None:
        if not HAS_BOTO3:
            raise RuntimeError(
                "boto3 is required for S3/MinIO support. Install it with: "
                "pip install boto3 (or the package's 's3' extra)."
            )
        endpoint = os.environ.get("AFL_S3_ENDPOINT") or None
        region = os.environ.get("AFL_S3_REGION", "us-east-1")
        access = os.environ.get("AFL_S3_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID")
        secret = os.environ.get("AFL_S3_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY")
        self._client = _boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=access,
            aws_secret_access_key=secret,
            # MinIO speaks S3v4 + path-style addressing.
            config=_BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def _split(self, path: str) -> tuple[str, str]:
        return _s3_split(path)

    def exists(self, path: str) -> bool:
        bucket, key = self._split(path)
        try:
            self._client.head_object(Bucket=bucket, Key=key)
            return True
        except _BotoClientError:
            return self.isdir(path)

    def open(self, path: str, mode: str = "r") -> IO:
        bucket, key = self._split(path)
        if "w" in mode:
            return _S3WriteStream(self, bucket, key)  # type: ignore[return-value]
        data = self._client.get_object(Bucket=bucket, Key=key)["Body"].read()
        import io

        return io.BytesIO(data) if "b" in mode else io.StringIO(data.decode("utf-8"))

    def makedirs(self, path: str, exist_ok: bool = True) -> None:
        return None  # object stores have no directories

    def getsize(self, path: str) -> int:
        bucket, key = self._split(path)
        return self._client.head_object(Bucket=bucket, Key=key)["ContentLength"]

    def getmtime(self, path: str) -> float:
        bucket, key = self._split(path)
        return self._client.head_object(Bucket=bucket, Key=key)["LastModified"].timestamp()

    def isfile(self, path: str) -> bool:
        bucket, key = self._split(path)
        try:
            self._client.head_object(Bucket=bucket, Key=key)
            return True
        except _BotoClientError:
            return False

    def isdir(self, path: str) -> bool:
        bucket, key = self._split(path)
        prefix = (key.rstrip("/") + "/") if key else ""
        resp = self._client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
        return resp.get("KeyCount", 0) > 0

    def listdir(self, path: str) -> list[str]:
        bucket, key = self._split(path)
        prefix = (key.rstrip("/") + "/") if key else ""
        names: set[str] = set()
        for page in self._client.get_paginator("list_objects_v2").paginate(
            Bucket=bucket, Prefix=prefix, Delimiter="/"
        ):
            for cp in page.get("CommonPrefixes", []):
                names.add(cp["Prefix"][len(prefix):].rstrip("/"))
            for obj in page.get("Contents", []):
                name = obj["Key"][len(prefix):]
                if name:
                    names.add(name)
        return sorted(names)

    def walk(self, path: str) -> Iterator[tuple[str, list[str], list[str]]]:
        bucket, root = self._split(path)
        root = root.rstrip("/")
        prefix = root + "/" if root else ""
        from collections import defaultdict

        dirs: dict[str, set[str]] = defaultdict(set)
        files: dict[str, list[str]] = defaultdict(list)
        for page in self._client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                rel = obj["Key"][len(prefix):]
                parts = rel.split("/")
                cur = root
                for i, part in enumerate(parts):
                    if i == len(parts) - 1:
                        files[cur].append(part)
                    else:
                        dirs[cur].add(part)
                        cur = f"{cur}/{part}" if cur else part

        def _emit(d: str):
            sub = sorted(dirs.get(d, []))
            base = f"s3://{bucket}/{d}" if d else f"s3://{bucket}"
            yield base, sub, files.get(d, [])
            for s in sub:
                yield from _emit(f"{d}/{s}" if d else s)

        yield from _emit(root)

    def rmtree(self, path: str) -> None:
        bucket, key = self._split(path)
        prefix = key.rstrip("/") + "/"
        batch: list[dict] = []
        for page in self._client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                batch.append({"Key": obj["Key"]})
                if len(batch) == 1000:
                    self._client.delete_objects(Bucket=bucket, Delete={"Objects": batch})
                    batch = []
        if batch:
            self._client.delete_objects(Bucket=bucket, Delete={"Objects": batch})

    def remove(self, path: str) -> None:
        bucket, key = self._split(path)
        self._client.delete_object(Bucket=bucket, Key=key)

    def join(self, *parts: str) -> str:
        if not parts:
            return ""
        out = [parts[0].rstrip("/")] + [p.strip("/") for p in parts[1:] if p]
        return "/".join(p for p in out if p)

    def dirname(self, path: str) -> str:
        bucket, key = self._split(path)
        parent = key.rsplit("/", 1)[0] if "/" in key else ""
        return f"s3://{bucket}/{parent}" if parent else f"s3://{bucket}"

    def basename(self, path: str) -> str:
        _bucket, key = self._split(path)
        return key.rsplit("/", 1)[-1] if "/" in key else key


# Singleton and cache for backend instances
_local_backend: LocalStorageBackend | None = None
_hdfs_backends: dict[str, HDFSStorageBackend] = {}
_s3_backend: S3StorageBackend | None = None


def _default_local_cache() -> str:
    from facetwork.config import get_output_base

    return os.path.join(get_output_base(), "cache", "osm-local")


_DEFAULT_LOCAL_CACHE = None  # resolved lazily


def _should_localize_mount(path: str) -> bool:
    """Check if a local path is on a mount that should be copied locally.

    Reads ``AFL_LOCALIZE_MOUNTS`` (comma-separated list of path prefixes).
    When a path starts with any listed prefix, ``localize()`` will copy it
    to the local cache instead of reading directly from the mount.  This
    avoids VirtioFS hangs on large files in Docker containers.
    """
    prefixes = os.environ.get("AFL_LOCALIZE_MOUNTS", "")
    if not prefixes:
        return False
    return any(path.startswith(p.strip()) for p in prefixes.split(",") if p.strip())


def localize(path: str, target_dir: str | None = None) -> str:
    """Ensure a file is available on the local filesystem.

    For local paths, returns *path* unchanged unless the path matches a
    prefix in ``AFL_LOCALIZE_MOUNTS``, in which case the file is copied to
    *target_dir*.  For ``hdfs://`` URIs, downloads the file to *target_dir*
    (preserving the HDFS directory structure) and returns the local path.
    Skips copy/download when a local copy with the same byte-size already
    exists.

    Args:
        path: Local path or ``hdfs://`` URI.
        target_dir: Root directory for cached downloads.

    Returns:
        A local filesystem path suitable for tools that require local files
        (e.g. pyosmium ``apply_file``).
    """
    if target_dir is None:
        target_dir = _default_local_cache()

    if path.startswith("s3://"):
        parsed = urlparse(path)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        local_path = os.path.join(target_dir, bucket, key)
        backend = get_storage_backend(path)
        if os.path.isfile(local_path):
            try:
                if os.path.getsize(local_path) == backend.getsize(path):
                    logger.debug("localize: s3 cache hit %s -> %s", path, local_path)
                    return local_path
            except Exception:
                pass  # re-download on any error
        logger.info("localize: downloading %s -> %s", path, local_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        assert isinstance(backend, S3StorageBackend)
        backend._client.download_file(bucket, key, local_path)
        return local_path

    if not path.startswith("hdfs://"):
        if not _should_localize_mount(path):
            return path
        # Copy mount-backed file to local cache.
        # Use subprocess cp instead of shutil.copy2 because Python's open()
        # can hang indefinitely on VirtioFS mounts for large files.
        local_path = os.path.join(target_dir, path.lstrip("/"))
        if os.path.isfile(local_path):
            local_size = os.path.getsize(local_path)
            if local_size > 0:
                logger.debug(
                    "localize: mount cache hit %s -> %s (%d bytes)", path, local_path, local_size
                )
                return local_path
            # 0-byte file = stale from a previous failed copy; re-copy
            logger.warning("localize: removing stale 0-byte cache file %s", local_path)
            os.unlink(local_path)
        logger.info("localize: copying mount file %s -> %s (via cp)", path, local_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        import subprocess

        subprocess.run(["cp", path, local_path], check=True)
        copied_size = os.path.getsize(local_path)
        logger.info("localize: copied %s (%d bytes)", local_path, copied_size)
        return local_path

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
    assert isinstance(backend, HDFSStorageBackend)

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
    global _local_backend, _s3_backend

    if path and path.startswith("hdfs://"):
        parsed = urlparse(path)
        host = parsed.hostname or "default"
        port = parsed.port or 0
        cache_key = f"{host}:{port}"
        if cache_key not in _hdfs_backends:
            _hdfs_backends[cache_key] = HDFSStorageBackend(host=host, port=port)
        return _hdfs_backends[cache_key]

    if path and path.startswith("s3://"):
        if _s3_backend is None:
            _s3_backend = S3StorageBackend()
        return _s3_backend

    if _local_backend is None:
        _local_backend = LocalStorageBackend()
    return _local_backend
